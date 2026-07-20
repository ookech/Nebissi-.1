from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from .models import Payment, Service


class PageAndAdminTests(TestCase):
    def test_homepage_renders_without_static_manifest_error(self):
        response = self.client.get(reverse('overview'))
        self.assertEqual(response.status_code, 200)

    def test_payment_model_is_not_registered_in_admin(self):
        self.assertNotIn(Payment, admin.site._registry)

    def test_admin_pages_render_for_key_models(self):
        admin_user = User.objects.create_user(username='admin-test', password='secret123')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        self.client.force_login(admin_user)
        for path in [
            '/admin/',
            '/admin/ledger/service/',
            '/admin/stationery/product/',
            '/admin/stationery/sale/',
            '/admin/customer/order/',
            '/admin/accounts/profile/',
        ]:
            response = self.client.get(path, HTTP_HOST='127.0.0.1')
            self.assertEqual(response.status_code, 200, msg=path)

    def test_worker_dashboard_shows_service_availability_status(self):
        employee = User.objects.create_user(username='employee-only', password='secret123')
        employee.profile.role = 'employee'
        employee.profile.save()
        Service.objects.create(name='Inactive Service', default_price=5, is_active=False)

        self.client.force_login(employee)
        response = self.client.get(reverse('worker_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Available services')
        self.assertContains(response, 'Inactive Service')
        self.assertContains(response, 'disabled by admin')


class RoleAndPaymentAccessTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='secret123')
        self.admin.profile.role = 'admin'
        self.admin.profile.save()

        self.employee = User.objects.create_user(username='worker', password='secret123')
        self.employee.profile.role = 'employee'
        self.employee.profile.save()

        self.service = Service.objects.create(name='Printing', default_price=10, is_active=True)

    def test_employee_can_use_staff_views_but_cannot_edit_or_delete_payments(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse('worker_dashboard'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('stationery:inventory'))
        self.assertEqual(response.status_code, 200)

        payment = Payment.objects.create(
            service=self.service,
            quantity=1,
            unit_price=Decimal('10.00'),
            amount=Decimal('10.00'),
            customer_name='Jane',
            phone_number='0712345678',
            method='mpesa',
            date='2026-01-01',
            recorded_by=self.admin,
        )

        response = self.client.get(reverse('edit_payment', args=[payment.pk]))
        self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse('delete_payment', args=[payment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())

    @patch('ledger.views.stk_push')
    def test_admin_payment_creation_uses_mpesa_prompt_for_customer_phone(self, mock_stk_push):
        mock_stk_push.return_value = {'CheckoutRequestID': 'test-request'}
        self.client.force_login(self.admin)

        response = self.client.post(reverse('new_payment'), {
            'service': self.service.pk,
            'quantity': 1,
            'unit_price': '10.00',
            'amount': '10.00',
            'customer_name': 'Jane',
            'phone_number': '0712345678',
            'date': '2026-01-01',
            'notes': 'Printing job',
        })

        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(customer_name='Jane')
        self.assertEqual(payment.method, 'mpesa')
        self.assertEqual(payment.phone_number, '0712345678')
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.checkout_request_id, 'test-request')
        mock_stk_push.assert_called_once()

    def test_payment_status_is_updated_to_successful_after_mpesa_callback(self):
        payment = Payment.objects.create(
            service=self.service,
            quantity=1,
            unit_price=Decimal('10.00'),
            amount=Decimal('10.00'),
            customer_name='Jane',
            phone_number='0712345678',
            method='mpesa',
            status='pending',
            checkout_request_id='req-123',
            date='2026-01-01',
            recorded_by=self.admin,
        )

        response = self.client.post(
            reverse('customer:mpesa_callback'),
            data='{"Body":{"stkCallback":{"CheckoutRequestID":"req-123","ResultCode":0,"CallbackMetadata":{"Item":[{"Name":"MpesaReceiptNumber","Value":"ABC123"}]}}}}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'successful')
        self.assertEqual(payment.mpesa_receipt, 'ABC123')

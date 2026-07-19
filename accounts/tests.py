from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import WorkerRequest


class WorkerApprovalFlowTests(TestCase):
    def test_worker_signup_creates_pending_request(self):
        response = self.client.post(reverse('accounts:signup'), {
            'username': 'newworker',
            'email': 'worker@example.com',
            'password': 'secret123',
            'phone_number': '0712345678',
        })

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newworker')
        self.assertEqual(user.profile.role, 'customer')
        self.assertTrue(WorkerRequest.objects.filter(username='newworker', status='pending').exists())

    def test_admin_approval_grants_employee_access(self):
        user = User.objects.create_user(username='pendingworker', password='secret123')
        request = WorkerRequest.objects.create(
            username=user.username,
            email='pending@example.com',
            password_hash=user.password,
            phone_number='0712345678',
            status='pending',
        )

        self.client.force_login(User.objects.create_superuser(username='admin', email='admin@example.com', password='secret123'))

        response = self.client.post(reverse('accounts:approve_request', args=[request.pk]))

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.profile.role, 'employee')
        request.refresh_from_db()
        self.assertEqual(request.status, 'approved')

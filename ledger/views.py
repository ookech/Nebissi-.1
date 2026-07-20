from datetime import timedelta, date
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
import csv

from .models import Payment, Service
from .forms import PaymentForm, ServiceForm, PaymentFilterForm
from accounts.models import WorkerRequest
from customer.mpesa import stk_push


def is_admin(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'admin'


def is_employee(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'employee'


def admin_required(view_func):
    """Only allow users whose profile.role is 'admin'. Everyone else is sent home."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            messages.error(request, "You don't have permission to view that.")
            return redirect('accounts:post_login')
        return view_func(request, *args, **kwargs)
    return wrapper


class RoleHintLoginView(LoginView):
    template_name = 'ledger/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        # Remember which button the person clicked, so post_login_redirect
        # can confirm their actual role matches what they intended to log in as.
        self.request.session['role_hint'] = self.request.GET.get('role', '')
        return response


def overview(request):
    if not request.user.is_authenticated:
        return render(request, 'ledger/landing.html')

    if not is_admin(request.user) and not is_employee(request.user):
        messages.info(request, 'Only staff members can access the management dashboard.')
        return render(request, 'ledger/landing.html')

    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)

    successful_payments = Payment.objects.filter(status='successful')
    today_total = successful_payments.filter(date=today).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    week_total = successful_payments.filter(date__gte=week_start).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    month_total = successful_payments.filter(date__gte=month_start).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    all_total = successful_payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    count = successful_payments.count()

    by_service = (
        successful_payments.values('service__name')
        .annotate(total=Sum('amount'), n=Count('id'))
        .order_by('-total')
    )
    max_total = by_service[0]['total'] if by_service else Decimal('1')

    pending_requests = WorkerRequest.objects.filter(status='pending')
    recent_payments = Payment.objects.select_related('service', 'recorded_by').order_by('-date', '-created_at')[:10]
    employee_activity = (
        Payment.objects.exclude(recorded_by__isnull=True)
        .values('recorded_by__username')
        .annotate(count=Count('id'))
        .order_by('-count', 'recorded_by__username')[:8]
    )

    context = {
        'today_total': today_total,
        'week_total': week_total,
        'month_total': month_total,
        'all_total': all_total,
        'count': count,
        'by_service': by_service,
        'max_total': max_total or Decimal('1'),
        'pending_requests': pending_requests,
        'recent_payments': recent_payments,
        'employee_activity': employee_activity,
    }
    return render(request, 'ledger/overview.html', context)


@login_required
@admin_required
def new_payment(request, pk=None):
    instance = get_object_or_404(Payment, pk=pk) if pk else None
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=instance)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.method = 'mpesa'
            payment.status = 'pending'
            if not payment.recorded_by_id:
                payment.recorded_by = request.user
            payment.save()
            try:
                response = stk_push(
                    phone_number=payment.phone_number or getattr(payment.recorded_by.profile, 'phone_number', ''),
                    amount=payment.amount,
                    account_reference=f'Payment{payment.pk}',
                    transaction_desc=f'Nebissi payment for {payment.customer_name or payment.service.name}',
                )
                payment.checkout_request_id = response.get('CheckoutRequestID', '')
                payment.save(update_fields=['checkout_request_id'])
                messages.success(request, 'Payment request sent. The payment is pending until the M-Pesa transaction completes.')
            except Exception as exc:
                payment.status = 'failed'
                payment.save(update_fields=['status'])
                messages.warning(request, f'Payment could not be sent to M-Pesa: {exc}')
            return redirect('ledger')
    else:
        initial = {'date': date.today(), 'quantity': 1}
        form = PaymentForm(instance=instance, initial=initial)

    services = Service.objects.filter(is_active=True)
    return render(request, 'ledger/new_payment.html', {
        'form': form,
        'services': services,
        'editing': instance is not None,
    })


@login_required
@admin_required
def delete_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        payment.delete()
        messages.success(request, 'Payment deleted.')
    return redirect('ledger')


@login_required
@admin_required
def ledger(request):
    form = PaymentFilterForm(request.GET or None)
    qs = Payment.objects.select_related('service').all()

    if form.is_valid():
        service = form.cleaned_data.get('service')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        q = form.cleaned_data.get('q')
        if service:
            qs = qs.filter(service=service)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(customer_name__icontains=q) | Q(notes__icontains=q))

    total = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return render(request, 'ledger/ledger.html', {
        'form': form,
        'payments': qs,
        'total': total,
    })


@login_required
@admin_required
def export_csv(request):
    form = PaymentFilterForm(request.GET or None)
    qs = Payment.objects.select_related('service').all()
    if form.is_valid():
        service = form.cleaned_data.get('service')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        q = form.cleaned_data.get('q')
        if service:
            qs = qs.filter(service=service)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(customer_name__icontains=q) | Q(notes__icontains=q))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="nebissi-payments.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Service', 'Quantity', 'Unit price', 'Amount', 'Customer', 'Method', 'Notes'])
    for p in qs:
        writer.writerow([p.date, p.service.name, p.quantity, p.unit_price, p.amount, p.customer_name, p.get_method_display(), p.notes])
    return response


@login_required
@admin_required
def services(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service added.')
            return redirect('services')
    else:
        form = ServiceForm()

    return render(request, 'ledger/services.html', {
        'form': form,
        'services': Service.objects.all(),
    })


@login_required
@admin_required
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated.')
    return redirect('services')


@login_required
@admin_required
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        if service.payments.exists():
            messages.error(request, "Can't remove a service that has payments recorded against it. Mark it inactive instead.")
        else:
            service.delete()
            messages.success(request, 'Service removed.')
    return redirect('services')


@login_required
def worker_dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != 'employee':
        return redirect('accounts:post_login')

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.method = 'mpesa'
            payment.status = 'pending'
            payment.recorded_by = request.user
            payment.save()
            try:
                response = stk_push(
                    phone_number=payment.phone_number or getattr(request.user.profile, 'phone_number', ''),
                    amount=payment.amount,
                    account_reference=f'Payment{payment.pk}',
                    transaction_desc=f'Nebissi payment for {payment.customer_name or payment.service.name}',
                )
                payment.checkout_request_id = response.get('CheckoutRequestID', '')
                payment.save(update_fields=['checkout_request_id'])
                messages.success(request, 'Payment request sent. The payment is pending until the M-Pesa transaction completes.')
            except Exception as exc:
                payment.status = 'failed'
                payment.save(update_fields=['status'])
                messages.warning(request, f'Payment could not be sent to M-Pesa: {exc}')
            return redirect('worker_dashboard')
    else:
        form = PaymentForm(initial={'date': date.today(), 'quantity': 1})

    my_payments = (
        Payment.objects.filter(recorded_by=request.user)
        .select_related('service')
        .order_by('-date', '-id')[:50]
    )
    services = Service.objects.order_by('name')
    available_services = services.filter(is_active=True)
    unavailable_services = services.filter(is_active=False)

    return render(request, 'ledger/worker_dashboard.html', {
        'form': form,
        'services': available_services,
        'available_services': available_services,
        'unavailable_services': unavailable_services,
        'my_payments': my_payments,
    })
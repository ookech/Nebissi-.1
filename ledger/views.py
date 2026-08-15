import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Sum, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import csv

from .models import Payment, Service
from .forms import PaymentForm, ServiceForm, PaymentFilterForm
from accounts.models import WorkerRequest


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
def edit_payment(request, pk):
    """
    Admins can no longer create new payments from the site -- every Payment
    is now created automatically, either by the customer checkout flow or
    by the till (C2B) confirmation callback. This view only lets an admin
    edit an existing payment, e.g. to reassign an auto-recorded till
    payment from the placeholder service to the real one the customer paid for.
    """
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment updated.')
            return redirect('ledger')
    else:
        form = PaymentForm(instance=payment)

    services = Service.objects.filter(is_active=True)
    return render(request, 'ledger/new_payment.html', {
        'form': form,
        'services': services,
        'editing': True,
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
    """
    Workers can no longer create or save payments here. Customers pay
    directly via the till number on their own phone; successful payments
    are recorded automatically by mpesa_c2b_confirmation. This view is now
    read-only, so a worker can confirm a payment has actually come through.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role != 'employee':
        return redirect('accounts:post_login')

    recent_payments = (
        Payment.objects.select_related('service')
        .order_by('-date', '-id')[:50]
    )
    services = Service.objects.order_by('name')
    available_services = services.filter(is_active=True)
    unavailable_services = services.filter(is_active=False)

    return render(request, 'ledger/worker_dashboard.html', {
        'services': available_services,
        'available_services': available_services,
        'unavailable_services': unavailable_services,
        'recent_payments': recent_payments,
    })


def _get_or_create_till_placeholder_service():
    """
    Placeholder Service used for till payments recorded automatically before
    an admin has assigned them to the real service the customer paid for.
    """
    service, _ = Service.objects.get_or_create(
        name='Unassigned Till Payment',
        defaults={'default_price': 0, 'is_active': False},
    )
    return service


@csrf_exempt
def mpesa_c2b_validation(request):
    """
    Safaricom calls this before completing a till (Buy Goods) payment.
    We accept everything here; the actual recording happens on confirmation.
    """
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
def mpesa_c2b_confirmation(request):
    """
    Safaricom calls this automatically after a customer successfully pays
    the till number directly from their own phone. No prompt was sent from
    the site -- this is the only place a till payment turns into a Payment
    row. It's logged against a placeholder service; an admin assigns it to
    the correct service afterward.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid payload'}, status=400)

    trans_id = data.get('TransID', '')
    if not trans_id:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Missing TransID'}, status=400)

    # Safaricom may retry confirmation calls; don't double-record the same transaction.
    if Payment.objects.filter(mpesa_receipt=trans_id).exists():
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    try:
        amount = Decimal(str(data.get('TransAmount', '0')))
    except InvalidOperation:
        amount = Decimal('0')

    phone_number = data.get('MSISDN', '')
    name_parts = [data.get('FirstName', ''), data.get('MiddleName', ''), data.get('LastName', '')]
    customer_name = ' '.join(part for part in name_parts if part).strip() or 'Walk-in'

    trans_time_raw = data.get('TransTime', '')
    try:
        payment_date = datetime.strptime(trans_time_raw, '%Y%m%d%H%M%S').date()
    except ValueError:
        payment_date = date.today()

    Payment.objects.create(
        service=_get_or_create_till_placeholder_service(),
        quantity=1,
        unit_price=amount,
        amount=amount,
        customer_name=customer_name,
        phone_number=phone_number,
        method='mpesa',
        status='successful',
        mpesa_receipt=trans_id,
        date=payment_date,
        notes=f'Till payment, bill ref: {data.get("BillRefNumber", "")}',
    )

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
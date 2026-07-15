from datetime import timedelta, date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
import csv

from .models import Payment, Service
from .forms import PaymentForm, ServiceForm, PaymentFilterForm


@login_required
def overview(request):
    today = date.today()
    week_start = today - timedelta(days=6)

    today_total = Payment.objects.filter(date=today).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    week_total = Payment.objects.filter(date__gte=week_start).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    all_total = Payment.objects.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    count = Payment.objects.count()

    by_service = (
        Payment.objects.values('service__name')
        .annotate(total=Sum('amount'), n=Count('id'))
        .order_by('-total')
    )
    max_total = by_service[0]['total'] if by_service else Decimal('1')

    context = {
        'today_total': today_total,
        'week_total': week_total,
        'all_total': all_total,
        'count': count,
        'by_service': by_service,
        'max_total': max_total or Decimal('1'),
    }
    return render(request, 'ledger/overview.html', context)


@login_required
def new_payment(request, pk=None):
    instance = get_object_or_404(Payment, pk=pk) if pk else None
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=instance)
        if form.is_valid():
            payment = form.save(commit=False)
            if not payment.recorded_by_id:
                payment.recorded_by = request.user
            payment.save()
            messages.success(request, 'Payment updated.' if instance else 'Payment recorded.')
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
def delete_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        payment.delete()
        messages.success(request, 'Payment deleted.')
    return redirect('ledger')


@login_required
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
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated.')
    return redirect('services')


@login_required
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        if service.payments.exists():
            messages.error(request, "Can't remove a service that has payments recorded against it. Mark it inactive instead.")
        else:
            service.delete()
            messages.success(request, 'Service removed.')
    return redirect('services')

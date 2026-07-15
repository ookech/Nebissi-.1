from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F
from .models import product, Sale
from .forms import ProductForm, SaleForm

LOW_STOCK_THRESHOLD = 5


@login_required
def inventory_list(request):
    items = product.objects.all().order_by('category', 'name')
    return render(request, 'stationery/inventory.html', {
        'items': items,
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
    })


@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item added to inventory.')
            return redirect('stationery:inventory')
    else:
        form = ProductForm()
    return render(request, 'stationery/add_item.html', {'form': form})


@login_required
def new_sale(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.unit_price = sale.product.sale_price
                sale.sold_by = request.user
                sale.save()
                product.objects.filter(pk=sale.product.pk).update(
                    stock_qty=F('stock_qty') - sale.quantity
                )
            messages.success(request, 'Sale recorded.')
            return redirect('stationery:overview')
    else:
        form = SaleForm()
    return render(request, 'stationery/new_sale.html', {'form': form})


@login_required
def overview(request):
    sales = Sale.objects.select_related('product').order_by('-created_at')
    total_revenue = sales.aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
    low_stock_items = product.objects.filter(stock_qty__lte=LOW_STOCK_THRESHOLD)
    return render(request, 'stationery/overview.html', {
        'sales': sales[:20],
        'total_revenue': total_revenue,
        'low_stock_items': low_stock_items,
    })
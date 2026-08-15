import json
from datetime import date
from django.http import JsonResponse
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from ledger.models import Payment, Service
from stationery.models import product as Product
from .cart import Cart
from .models import Order, OrderItem


def _get_session_key(request):
    """Anonymous orders are tracked by browser session, not by user account."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def catalog(request):
    return redirect('overview')


def add_to_cart(request, source, source_id):
    cart = Cart(request)
    quantity = int(request.POST.get('quantity', 1))

    if source == 'service':
        item = get_object_or_404(Service, pk=source_id, is_active=True)
        price = item.default_price
    elif source == 'product':
        item = get_object_or_404(Product, pk=source_id)
        price = item.sale_price
    else:
        messages.error(request, 'Invalid item type.')
        return redirect('customer:catalog')

    cart.add(source=source, source_id=source_id, name=item.name, unit_price=price, quantity=quantity)
    messages.success(request, f'{item.name} added to your order.')
    return redirect('customer:catalog')


def view_cart(request):
    cart = Cart(request)
    items = []
    for key, item in cart:
        subtotal = Decimal(item['unit_price']) * item['quantity']
        items.append({**item, 'key': key, 'subtotal': subtotal})
    return render(request, 'customer/cart.html', {'cart': cart, 'items': items})


def remove_from_cart(request, key):
    cart = Cart(request)
    cart.remove(key)
    return redirect('customer:cart')


def _get_or_create_order_payment_service():
    """
    Placeholder Service used to summarize an entire Order (which may include
    non-Service items like stationery products) into a single ledger Payment row.
    """
    service, _ = Service.objects.get_or_create(
        name='Customer Order',
        defaults={'default_price': 0, 'is_active': False},
    )
    return service


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.error(request, 'Your cart is empty.')
        return redirect('customer:catalog')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        if not phone_number:
            messages.error(request, 'Phone number is required.')
            return render(request, 'customer/checkout.html', {'cart': cart})

        order = Order.objects.create(
            session_key=_get_session_key(request),
            phone_number=phone_number,
            status='pending',
        )
        for key, item in cart:
            OrderItem.objects.create(
                order=order,
                source=item['source'],
                source_id=item['source_id'],
                name=item['name'],
                unit_price=Decimal(item['unit_price']),
                quantity=item['quantity'],
            )
        order.recalculate_total()

        try:
            placeholder_service = _get_or_create_order_payment_service()
            Payment.objects.create(
                service=placeholder_service,
                quantity=1,
                unit_price=order.total_amount,
                amount=order.total_amount,
                customer_name='Walk-in',
                phone_number=order.phone_number,
                method='mpesa',
                status='successful',
                date=date.today(),
                notes=f'Order #{order.pk}',
            )
            order.status = 'paid'
            order.save(update_fields=['status'])
            cart.clear()
            messages.success(request, 'Payment recorded successfully.')
        except Exception as e:
            order.status = 'failed'
            order.save(update_fields=['status'])
            messages.error(request, f'Could not record payment: {e}')

        return redirect('customer:order_status', pk=order.pk)

    return render(request, 'customer/checkout.html', {'cart': cart})


def order_status(request, pk):
    order = get_object_or_404(Order, pk=pk, session_key=_get_session_key(request))
    return render(request, 'customer/order_status.html', {'order': order})


def order_history(request):
    session_key = request.session.session_key
    orders = Order.objects.filter(session_key=session_key) if session_key else Order.objects.none()
    return render(request, 'customer/order_history.html', {'orders': orders})
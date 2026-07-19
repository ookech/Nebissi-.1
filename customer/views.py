import json
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from ledger.models import Payment, Service
from stationery.models import product as Product
from .cart import Cart
from .models import Order, OrderItem
from .mpesa import stk_push
import requests as requests_lib  # for exception handling only, avoid name clash


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


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.error(request, 'Your cart is empty.')
        return redirect('customer:catalog')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        if not phone_number:
            messages.error(request, 'Phone number is required for M-Pesa payment.')
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
            response = stk_push(
                phone_number=phone_number,
                amount=order.total_amount,
                account_reference=f"Order{order.pk}",
                transaction_desc=f"Nebissi order #{order.pk}",
            )
            order.checkout_request_id = response.get('CheckoutRequestID', '')
            order.save(update_fields=['checkout_request_id'])
            cart.clear()
            messages.success(request, 'Check your phone to complete the M-Pesa payment.')
        except requests_lib.HTTPError as e:
            order.status = 'failed'
            order.save(update_fields=['status'])
            messages.error(request, f'Could not initiate M-Pesa payment: {e}')
        except Exception as e:
            order.status = 'failed'
            order.save(update_fields=['status'])
            messages.error(request, f'Unexpected error initiating payment: {e}')

        return redirect('customer:order_status', pk=order.pk)

    return render(request, 'customer/checkout.html', {'cart': cart})


def order_status(request, pk):
    order = get_object_or_404(Order, pk=pk, session_key=_get_session_key(request))
    return render(request, 'customer/order_status.html', {'order': order})


def order_history(request):
    session_key = request.session.session_key
    orders = Order.objects.filter(session_key=session_key) if session_key else Order.objects.none()
    return render(request, 'customer/order_history.html', {'orders': orders})


@csrf_exempt
def mpesa_callback(request):
    try:
        data = json.loads(request.body)
        callback = data['Body']['stkCallback']
        checkout_request_id = callback['CheckoutRequestID']
        result_code = callback['ResultCode']

        try:
            order = Order.objects.get(checkout_request_id=checkout_request_id)
        except Order.DoesNotExist:
            pass
        else:
            if result_code == 0:
                metadata_items = callback.get('CallbackMetadata', {}).get('Item', [])
                items = {item.get('Name'): item.get('Value') for item in metadata_items if isinstance(item, dict)}
                order.mpesa_receipt = items.get('MpesaReceiptNumber', '')
                order.status = 'paid'
            else:
                order.status = 'failed'
            order.save(update_fields=['status', 'mpesa_receipt'])

        payment_qs = Payment.objects.filter(checkout_request_id=checkout_request_id)
        if payment_qs.exists():
            payment = payment_qs.get()
            if result_code == 0:
                metadata_items = callback.get('CallbackMetadata', {}).get('Item', [])
                items = {item.get('Name'): item.get('Value') for item in metadata_items if isinstance(item, dict)}
                payment.mpesa_receipt = items.get('MpesaReceiptNumber', '')
                payment.status = 'successful'
            else:
                payment.status = 'failed'
            payment.save(update_fields=['status', 'mpesa_receipt'])

        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    except (KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': f'Invalid callback payload: {e}'}, status=400)
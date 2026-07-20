from django.contrib import admin
from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'status', 'total_amount', 'phone_number', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('phone_number', 'checkout_request_id', 'mpesa_receipt')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'name', 'quantity', 'unit_price', 'subtotal')
    list_filter = ('source',)
    search_fields = ('name',)

from django.contrib import admin
from .models import Service, Payment


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_price', 'is_active']
    list_editable = ['default_price', 'is_active']
    search_fields = ['name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['date', 'service', 'quantity', 'amount', 'customer_name', 'method', 'recorded_by']
    list_filter = ['service', 'method', 'date']
    search_fields = ['customer_name', 'notes']
    date_hierarchy = 'date'
    autocomplete_fields = ['service']

from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_price', 'is_active']
    list_editable = ['default_price', 'is_active']
    search_fields = ['name']

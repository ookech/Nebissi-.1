from django.contrib import admin
from .models import product, Sale


@admin.register(product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'stock_qty', 'cost_price', 'sale_price')
    list_filter = ('category',)
    search_fields = ('name', 'sku')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'unit_price', 'total', 'sold_by', 'created_at')
    list_filter = ('created_at',)
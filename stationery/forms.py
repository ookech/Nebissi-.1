from django import forms
from .models import product, Sale


class ProductForm(forms.ModelForm):
    class Meta:
        model = product
        fields = ['name', 'category', 'sku', 'cost_price', 'sale_price', 'stock_qty']


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['product', 'quantity']

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        if item and quantity and quantity > item.stock_qty:
            raise forms.ValidationError(
                f"Only {item.stock_qty} units of {item.name} left in stock."
            )
        return cleaned_data
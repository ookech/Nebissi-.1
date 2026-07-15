from django.db import models
from django.contrib.auth.models import User

class product(models.Model):
    CATEGORY_CHOICES = [
        ('book', 'Books'),
        ('pen', 'Pens'),
        ('pencil', 'Pencils'),
        ('sharpener', 'Sharpeners'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    sku = models.CharField(max_length=30, unique=True, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_qty = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.stock_qty} in stock)"

    @property
    def profit_margin(self):
        return self.sale_price - self.cost_price


class Sale(models.Model):
    product = models.ForeignKey(product, on_delete=models.PROTECT, related_name='sales')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price at time of sale
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ {self.created_at:%Y-%m-%d}"
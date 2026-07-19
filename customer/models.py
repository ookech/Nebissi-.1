from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending payment'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    session_key = models.CharField(max_length=40, db_index=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    phone_number = models.CharField(max_length=15, blank=True)  # number STK push was sent to
    checkout_request_id = models.CharField(max_length=100, blank=True)  # moved here from OrderItem, fixes mpesa_callback lookup
    mpesa_receipt = models.CharField(max_length=40, blank=True)  # filled in on successful callback
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} - {self.phone_number or 'no phone'} ({self.status})"

    def recalculate_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])


class OrderItem(models.Model):
    SOURCE_CHOICES = [
        ('service', 'Service'),
        ('product', 'Stationery product'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField()  # pk of the Service or product row
    name = models.CharField(max_length=150)  # snapshot at order time
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot at order time
    quantity = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.name}"
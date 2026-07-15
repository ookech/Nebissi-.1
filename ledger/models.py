from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Service(models.Model):
    name = models.CharField(max_length=100, unique=True)
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Payment(models.Model):
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('other', 'Other'),
    ]

    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='payments')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    customer_name = models.CharField(max_length=150, blank=True, default='Walk-in')
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='cash')
    date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.service.name} - {self.amount} ({self.date})"

    def get_absolute_url(self):
        return reverse('ledger')

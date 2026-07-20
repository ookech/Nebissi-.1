from django import forms
from .models import Payment, Service


class PaymentForm(forms.ModelForm):
    phone_number = forms.CharField(required=True, max_length=15, help_text="Enter the customer's phone number for the M-Pesa prompt")

    class Meta:
        model = Payment
        fields = ['service', 'quantity', 'unit_price', 'amount', 'customer_name', 'phone_number', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': 'e.g. CV printing, 2 copies'}),
            'customer_name': forms.TextInput(attrs={'placeholder': 'Walk-in'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'e.g. 0712345678'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True).order_by('name')


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'default_price', 'is_active']


class PaymentFilterForm(forms.Form):
    service = forms.ModelChoiceField(queryset=Service.objects.all(), required=False, empty_label='All services')
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search customer / notes'}))

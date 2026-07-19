from django import forms
from django.contrib.auth.models import User
from .models import WorkerRequest


class WorkerSignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    phone_number = forms.CharField(max_length=15, required=False, help_text="For M-Pesa payments")

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            user.profile.phone_number = self.cleaned_data.get('phone_number', '')
            user.profile.role = 'customer'
            user.profile.save()
            WorkerRequest.objects.create(
                username=user.username,
                email=user.email,
                password_hash=user.password,
                phone_number=user.profile.phone_number,
                status='pending',
            )
        return user
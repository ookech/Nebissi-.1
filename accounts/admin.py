from django.contrib import admin
from .models import Profile, WorkerRequest


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number')
    list_filter = ('role',)
    search_fields = ('user__username', 'phone_number')


@admin.register(WorkerRequest)
class WorkerRequestAdmin(admin.ModelAdmin):
    list_display = ('username', 'status', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('username', 'email', 'phone_number')

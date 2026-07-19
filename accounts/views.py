from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import WorkerSignUpForm
from .models import WorkerRequest


def signup(request):
    if request.method == 'POST':
        form = WorkerSignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your worker request has been submitted. An admin will approve your access shortly.')
            return redirect('login')
    else:
        form = WorkerSignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def pending_approval(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role == 'employee':
        return redirect('worker_dashboard')

    pending_request = WorkerRequest.objects.filter(username=request.user.username, status='pending').first()
    return render(request, 'accounts/pending_approval.html', {'pending_request': pending_request})


def post_login_redirect(request):
    """Point at this from LOGIN_REDIRECT_URL; sends each role to its home,
    and rejects logins where the chosen button doesn't match the account's real role."""
    profile = getattr(request.user, 'profile', None)
    role_hint = request.session.pop('role_hint', '')

    if not profile:
        return redirect('login')

    if role_hint in ('admin', 'employee') and role_hint != profile.role:
        logout(request)
        messages.error(
            request,
            "Those credentials aren't for that login option. Please use the correct button."
        )
        return redirect('login')

    if profile.role == 'admin':
        return redirect('overview')
    if profile.role == 'employee':
        return redirect('worker_dashboard')

    pending_request = WorkerRequest.objects.filter(username=request.user.username, status='pending').first()
    if pending_request:
        return redirect('accounts:pending_approval')
    return redirect('overview')


@login_required
def approve_request(request, pk):
    if not request.user.is_superuser and not (getattr(request.user, 'profile', None) and request.user.profile.role == 'admin'):
        messages.error(request, 'Only admins can approve worker requests.')
        return redirect('accounts:post_login')

    worker_request = get_object_or_404(WorkerRequest, pk=pk)
    user = get_object_or_404(User, username=worker_request.username)
    user.profile.role = 'employee'
    user.profile.save(update_fields=['role'])
    worker_request.status = 'approved'
    worker_request.reviewed_by = request.user
    worker_request.reviewed_at = timezone.now()
    worker_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    messages.success(request, f'{user.username} is now approved as a worker.')
    return redirect('overview')


@login_required
def reject_request(request, pk):
    if not request.user.is_superuser and not (getattr(request.user, 'profile', None) and request.user.profile.role == 'admin'):
        messages.error(request, 'Only admins can reject worker requests.')
        return redirect('accounts:post_login')

    worker_request = get_object_or_404(WorkerRequest, pk=pk)
    worker_request.status = 'rejected'
    worker_request.reviewed_by = request.user
    worker_request.reviewed_at = timezone.now()
    worker_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    messages.success(request, f'{worker_request.username} request was rejected.')
    return redirect('overview')
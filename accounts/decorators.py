from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """Usage: @role_required('employee', 'admin')"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role not in allowed_roles:
                raise PermissionDenied("You don't have access to this area.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
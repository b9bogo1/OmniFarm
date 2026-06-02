from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user
from app.models.user import UserRole


def role_required(*roles):
    """Restricts a route to users whose role is in *roles.

    Unauthenticated requests are redirected to login.
    Authenticated users with wrong role receive HTTP 403.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# Convenience wrappers used throughout every Blueprint
admin_required = role_required(UserRole.ADMIN)
technician_required = role_required(UserRole.ADMIN, UserRole.TECHNICIAN)

"""
utils/decorators.py — Custom route decorators.

Provides role-based access control on top of Flask-Login's
@login_required. Use @role_required("admin") etc. to restrict
a view to one or more roles.
"""

from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles: str):
    """
    Decorator that restricts a view to users with one of the given roles.

    Usage:
        @role_required("admin")
        @role_required("admin", "teacher")   # multiple allowed roles

    Returns:
        403 Forbidden if the authenticated user's role is not in `roles`.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

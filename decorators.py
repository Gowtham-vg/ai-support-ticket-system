from functools import wraps
from flask import session, redirect, url_for, flash


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to continue.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('auth.dashboard_redirect'))
            return f(*args, **kwargs)
        return decorated
    return decorator

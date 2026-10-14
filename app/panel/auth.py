"""Panel sign-in: session login/logout, a login_required decorator for the panel routes, and a
per-session CSRF token every panel form carries (the panel's POSTs change data)."""
import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for

from ..extensions import db
from ..models import AdminUser


def current_admin():
    admin_id = session.get("admin_id")
    return db.session.get(AdminUser, admin_id) if admin_id else None


def log_in(admin):
    session.clear()
    session["admin_id"] = admin.id
    session.permanent = True


def log_out():
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_admin():
            return redirect(url_for("panel.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapper


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    sent = request.form.get("csrf", "")
    if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
        abort(400, "The form expired. Go back, reload the page and try again.")

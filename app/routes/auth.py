"""
routes/auth.py — Authentication blueprint.

Handles login and logout for all roles. After login the user is
redirected to their role-specific dashboard.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/")
def index():
    """Root redirect — send logged-in users to their dashboard."""
    if current_user.is_authenticated:
        return _redirect_to_dashboard()
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page for all roles."""
    if current_user.is_authenticated:
        return _redirect_to_dashboard()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(username=username).first()

        if user and user.is_active and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.username}!", "success")
            # Honor the next parameter for protected redirects
            next_page = request.args.get("next")
            return redirect(next_page or _dashboard_url(user))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out the current user and redirect to login."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _dashboard_url(user: User) -> str:
    """Return the correct dashboard URL for a given user's role."""
    routes = {
        "admin":   "admin.dashboard",
        "teacher": "teacher.dashboard",
        "student": "student.dashboard",
    }
    return url_for(routes.get(user.role, "auth.login"))


def _redirect_to_dashboard():
    """Redirect the currently authenticated user to their dashboard."""
    return redirect(_dashboard_url(current_user))

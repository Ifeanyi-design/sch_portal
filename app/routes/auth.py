"""Authentication blueprint with portal-aware login handling."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from app.forms.auth_forms import LoginForm
from app.models.student import Student
from app.models.user import Role, User

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

STUDENT_PORTAL = "student"
STAFF_PORTAL = "staff"
PORTAL_OPTIONS = {STUDENT_PORTAL, STAFF_PORTAL}


@auth_bp.route("/")
def index():
    """Send signed-in users to their dashboard, otherwise to login."""
    if current_user.is_authenticated:
        return _redirect_to_dashboard()
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Render the login page and enforce portal-specific authentication."""
    if current_user.is_authenticated:
        return _redirect_to_dashboard()

    form = LoginForm()
    selected_portal = _selected_portal()

    if form.validate_on_submit():
        login_id = form.username.data.strip()
        user = _find_user_for_portal(login_id, selected_portal)

        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, {user.username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or _dashboard_url(user))

        other_portal_user = _find_user_across_portals(login_id)
        if (
            other_portal_user
            and other_portal_user.is_active
            and other_portal_user.check_password(form.password.data)
        ):
            required_portal = (
                STUDENT_PORTAL if other_portal_user.role == Role.STUDENT else STAFF_PORTAL
            )
            flash(
                f"This account must sign in through the {required_portal} portal.",
                "danger",
            )
        else:
            flash("Invalid username or password.", "danger")

    return render_template(
        "auth/login.html",
        form=form,
        selected_portal=selected_portal,
        student_portal=STUDENT_PORTAL,
        staff_portal=STAFF_PORTAL,
    )


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out the current user and redirect to login."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


def _dashboard_url(user: User) -> str:
    """Return the correct dashboard URL for a given user's role."""
    routes = {
        Role.ADMIN: "admin.dashboard",
        Role.TEACHER: "teacher.dashboard",
        Role.STUDENT: "student.dashboard",
    }
    return url_for(routes.get(user.role, "auth.login"))


def _redirect_to_dashboard():
    """Redirect the currently authenticated user to their dashboard."""
    return redirect(_dashboard_url(current_user))


def _selected_portal() -> str:
    """Return the selected login portal, defaulting to student."""
    portal = (request.form.get("portal") or request.args.get("portal") or "").strip().lower()
    return portal if portal in PORTAL_OPTIONS else STUDENT_PORTAL


def _find_user_across_portals(login_id: str) -> User | None:
    """Return any user matching the submitted login identifier."""
    normalized = login_id.strip()
    if not normalized:
        return None

    return (
        User.query.filter(
            or_(
                User.username == normalized,
                User.email == normalized,
                User.student_profile.has(Student.student_code == normalized),
            )
        )
        .order_by(User.id.asc())
        .first()
    )


def _find_user_for_portal(login_id: str, portal: str) -> User | None:
    """Return a user only when they belong to the chosen portal."""
    normalized = login_id.strip()
    if not normalized:
        return None

    if portal == STAFF_PORTAL:
        return (
            User.query.filter(
                User.role.in_((Role.ADMIN, Role.TEACHER)),
                or_(User.username == normalized, User.email == normalized),
            )
            .order_by(User.id.asc())
            .first()
        )

    return (
        User.query.filter(
            User.role == Role.STUDENT,
            or_(
                User.username == normalized,
                User.student_profile.has(Student.student_code == normalized),
            ),
        )
        .order_by(User.id.asc())
        .first()
    )

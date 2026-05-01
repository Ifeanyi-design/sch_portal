"""
routes/admin.py — Admin blueprint.

All routes are protected by @login_required and @role_required("admin").
Prefix: /admin
"""

from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.decorators import role_required

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    """Admin main dashboard."""
    return render_template("admin/dashboard.html")


@admin_bp.route("/teachers")
@login_required
@role_required("admin")
def teachers():
    """Manage teachers — list, create, assign to classes."""
    return render_template("admin/teachers.html")


@admin_bp.route("/students")
@login_required
@role_required("admin")
def students():
    """Manage students — list, create, assign to classes."""
    return render_template("admin/students.html")


@admin_bp.route("/classes")
@login_required
@role_required("admin")
def classes():
    """Manage classes and class-teacher assignments."""
    return render_template("admin/classes.html")


@admin_bp.route("/sessions")
@login_required
@role_required("admin")
def sessions():
    """Manage academic sessions and lock/unlock results."""
    return render_template("admin/sessions.html")


@admin_bp.route("/results")
@login_required
@role_required("admin")
def results():
    """View all results across the system."""
    return render_template("admin/results.html")

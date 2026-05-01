"""
routes/teacher.py — Teacher blueprint.

All routes are protected by @login_required and @role_required("teacher").
Teachers only see classes they are assigned to.
Prefix: /teacher
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.utils.decorators import role_required

teacher_bp = Blueprint("teacher", __name__, template_folder="../templates/teacher")


@teacher_bp.route("/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    """Teacher dashboard — shows assigned classes summary."""
    return render_template("teacher/dashboard.html")


@teacher_bp.route("/classes")
@login_required
@role_required("teacher")
def classes():
    """List classes assigned to the logged-in teacher."""
    return render_template("teacher/classes.html")


@teacher_bp.route("/results/upload")
@login_required
@role_required("teacher")
def upload_results():
    """Result upload form (single entry and CSV bulk upload)."""
    return render_template("teacher/upload_results.html")


@teacher_bp.route("/results/edit")
@login_required
@role_required("teacher")
def edit_results():
    """Edit results before the session is locked."""
    return render_template("teacher/edit_results.html")


@teacher_bp.route("/students")
@login_required
@role_required("teacher")
def students():
    """View student list for assigned classes."""
    return render_template("teacher/students.html")

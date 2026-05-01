"""
routes/student.py — Student blueprint.

All routes are protected by @login_required and @role_required("student").
Students can only view their own results.
Prefix: /student
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.utils.decorators import role_required

student_bp = Blueprint("student", __name__, template_folder="../templates/student")


@student_bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    """Student dashboard — quick summary of latest results."""
    return render_template("student/dashboard.html")


@student_bp.route("/results")
@login_required
@role_required("student")
def results():
    """View personal results, filterable by session and term."""
    return render_template("student/results.html")


@student_bp.route("/report-card")
@login_required
@role_required("student")
def report_card():
    """Full report card view (downloadable / printable)."""
    return render_template("student/report_card.html")

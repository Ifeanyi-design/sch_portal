"""Student result-viewing blueprint."""

from __future__ import annotations

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.class_ import Level
from app.models.result import Result, ResultMode
from app.models.session_ import Session
from app.models.session_term import SessionTerm, Term
from app.models.student import Student
from app.utils.decorators import role_required
from app.utils.helpers import build_position_rows

student_bp = Blueprint("student", __name__, template_folder="../templates/student")


def _current_student() -> Student:
    """Return the logged-in student's profile or forbid access."""
    student = current_user.student_profile
    if student is None:
        abort(403)
    return student


def _available_periods(student: Student) -> list[dict]:
    """Return distinct session-term combinations that have student results."""
    rows = (
        Result.query.join(Session, Result.session_id == Session.id)
        .filter(Result.student_id == student.id)
        .with_entities(Result.session_id, Session.name, Result.term)
        .distinct()
        .order_by(Session.name.desc(), Result.term.asc())
        .all()
    )
    return [
        {
            "session_id": session_id,
            "session_name": session_name,
            "term": term,
            "label": f"{session_name} - {term.title()} Term",
        }
        for session_id, session_name, term in rows
    ]


def _available_sessions(periods: list[dict]) -> list[dict]:
    """Collapse period rows into a unique session list for filter dropdowns."""
    seen = set()
    sessions = []
    for period in periods:
        key = period["session_id"]
        if key in seen:
            continue
        seen.add(key)
        sessions.append(
            {
                "session_id": period["session_id"],
                "session_name": period["session_name"],
            }
        )
    return sessions


def _available_terms(periods: list[dict], session_id: int | None) -> list[dict]:
    """Return the terms available for one selected session."""
    return [period for period in periods if period["session_id"] == session_id]


def _default_period(student: Student, periods: list[dict]) -> tuple[int | None, str | None]:
    """Return the selected period or fall back to the latest available one."""
    session_id = request.args.get("session_id", type=int)
    term = request.args.get("term", type=str)

    if session_id is not None and term is not None:
        for period in periods:
            if period["session_id"] == session_id and period["term"] == term:
                return session_id, term

    active_period = (
        SessionTerm.query.join(SessionTerm.session)
        .filter(
            SessionTerm.session_id == student.class_.session_id,
            Session.is_active.is_(True),
            SessionTerm.is_result_entry_active.is_(True),
        )
        .first()
    )
    if active_period is not None:
        for period in periods:
            if (
                period["session_id"] == active_period.session_id
                and period["term"] == active_period.term
            ):
                return active_period.session_id, active_period.term

    if periods:
        return periods[0]["session_id"], periods[0]["term"]
    return None, None


def _result_rows(student: Student, session_id: int | None, term: str | None) -> list[Result]:
    """Return this student's results for one session-term only."""
    if session_id is None or term is None:
        return []

    return (
        Result.query.join(Result.subject)
        .filter(
            Result.student_id == student.id,
            Result.session_id == session_id,
            Result.term == term,
        )
        .order_by(Result.subject_id.asc())
        .all()
    )


def _report_summary(results: list[Result]) -> dict:
    """Compute totals using only offered score-mode subjects."""
    offered_score_results = [
        item
        for item in results
        if item.mode == ResultMode.SCORE and item.is_offered and item.total_score is not None
    ]
    total_score = round(sum(item.total_score for item in offered_score_results), 2)
    subjects_taken = len(offered_score_results)
    percentage = round((total_score / (subjects_taken * 100) * 100), 2) if subjects_taken else 0.0

    return {
        "total_score": total_score,
        "subjects_taken": subjects_taken,
        "percentage": percentage,
        "has_score_mode": any(item.mode == ResultMode.SCORE for item in results),
        "has_assessment_mode": any(item.mode == ResultMode.ASSESSMENT for item in results),
    }


def _position_context(student: Student, session_id: int | None, term: str | None) -> dict:
    """Return student-facing position details when class visibility allows it."""
    class_ = student.class_
    if session_id is None or term is None:
        return {"show_position": False, "position": None, "scope_label": None}
    if not class_.show_position or class_.level == Level.NURSERY:
        return {"show_position": False, "position": None, "scope_label": None}

    query = Result.query.join(Student).filter(
        Result.class_id == class_.id,
        Result.session_id == session_id,
        Result.term == term,
        Result.mode == ResultMode.SCORE,
        Result.is_offered.is_(True),
    )

    scope_label = f"{class_.name} Class"
    if class_.level == Level.SECONDARY and student.stream_id is not None:
        query = query.filter(Result.stream_id == student.stream_id)
        scope_label = f"{class_.name} - {student.stream.name}"

    student_results_map = {}
    for result in query.all():
        student_results_map.setdefault(result.student, []).append(result)

    rows = build_position_rows(student_results_map)
    current_row = next((row for row in rows if row["student"].id == student.id), None)
    return {
        "show_position": True,
        "position": current_row["position"] if current_row else None,
        "scope_label": scope_label,
    }


def _report_context(student: Student) -> dict:
    """Build the common context used by student result views."""
    periods = _available_periods(student)
    session_id, term = _default_period(student, periods)
    results = _result_rows(student, session_id, term)
    selected_period = next(
        (
            period
            for period in periods
            if period["session_id"] == session_id and period["term"] == term
        ),
        None,
    )
    summary = _report_summary(results)
    position = _position_context(student, session_id, term)

    return {
        "student": student,
        "available_periods": periods,
        "available_sessions": _available_sessions(periods),
        "available_terms": _available_terms(periods, session_id),
        "selected_session_id": session_id,
        "selected_term": term,
        "selected_period": selected_period,
        "results": results,
        "summary": summary,
        "position": position,
    }


@student_bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    """Student dashboard with quick access to their latest available report card."""
    student = _current_student()
    context = _report_context(student)
    return render_template("student/dashboard.html", **context)


@student_bp.route("/results")
@login_required
@role_required("student")
def results():
    """View the logged-in student's results filtered by session and term."""
    student = _current_student()
    context = _report_context(student)
    return render_template("student/results.html", **context)


@student_bp.route("/report-card")
@login_required
@role_required("student")
def report_card():
    """Printable report card view for the logged-in student only."""
    student = _current_student()
    context = _report_context(student)
    return render_template("student/report_card.html", **context)

"""Student result-viewing blueprint."""

from __future__ import annotations

from io import BytesIO
from collections import Counter, defaultdict

from flask import Blueprint, abort, render_template, request, send_file
from flask_login import current_user, login_required

from app.models.class_ import Level
from app.models.result import Result, ResultMode
from app.models.session_ import Session
from app.models.session_term import SessionTerm, Term
from app.models.student import Student
from app.utils.decorators import role_required
from app.utils.helpers import (
    build_position_rows,
    build_subject_position_rows,
    calculate_grade,
    calculate_percentage,
    rank_position_rows,
    summarize_score_results,
)

student_bp = Blueprint("student", __name__, template_folder="../templates/student")

GRADE_ORDER = ("A+", "A", "B", "C", "D", "E", "F")


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
        .order_by(Result.subject_id.asc(), Result.id.asc())
        .all()
    )


def _assessment_schema_items(student: Student) -> list[dict]:
    """Return nursery assessment schema entries for the student's class."""
    class_ = student.class_
    if (
        class_.level not in (Level.KINDERGARTEN, Level.NURSERY)
        or not class_.assessment_schema
    ):
        return []

    return [
        {"key": key, "label": key.replace("_", " ").title(), "type": value}
        for key, value in class_.assessment_schema.items()
    ]


def _report_summary(results: list[Result]) -> dict:
    """Compute totals using only offered score-mode subjects."""
    offered_score_results = [
        item
        for item in results
        if item.mode == ResultMode.SCORE and item.is_offered and item.total_score is not None
    ]
    total_score = round(sum(item.total_score for item in offered_score_results), 2)
    subjects_taken = len(offered_score_results)
    percentage = calculate_percentage(total_score, subjects_taken)
    average_score = round((total_score / subjects_taken), 2) if subjects_taken else 0.0
    grade_counts = {grade: 0 for grade in GRADE_ORDER}
    for result in offered_score_results:
        if result.grade in grade_counts:
            grade_counts[result.grade] += 1

    grade_summary = [
        {"grade": grade, "count": count}
        for grade, count in grade_counts.items()
        if count > 0
    ]
    top_grade = next((grade for grade in GRADE_ORDER if grade_counts[grade] > 0), None)

    return {
        "total_score": total_score,
        "subjects_taken": subjects_taken,
        "percentage": percentage,
        "average_score": average_score,
        "has_score_mode": any(item.mode == ResultMode.SCORE for item in results),
        "has_assessment_mode": any(item.mode == ResultMode.ASSESSMENT for item in results),
        "assessment_subjects": len(
            [item for item in results if item.mode == ResultMode.ASSESSMENT and item.is_offered]
        ),
        "remark_count": len([item for item in results if item.remark]),
        "grade_summary": grade_summary,
        "top_grade": top_grade,
    }


def _term_subject_positions(student: Student, results: list[Result], session_id: int, term: str) -> dict:
    """Return subject positions keyed by subject ID for one term."""
    positions = {}
    for result in results:
        if result.mode != ResultMode.SCORE or not result.is_offered or result.total_score is None:
            continue

        query = Result.query.join(Student).filter(
            Result.class_id == student.class_id,
            Result.session_id == session_id,
            Result.term == term,
            Result.subject_id == result.subject_id,
            Result.mode == ResultMode.SCORE,
            Result.is_offered.is_(True),
        )
        if student.class_.level == Level.SECONDARY and result.stream_id is not None:
            query = query.filter(Result.stream_id == result.stream_id)

        ranked_rows = build_subject_position_rows(query.all())
        current_row = next((row for row in ranked_rows if row["student"].id == student.id), None)
        if current_row:
            positions[result.subject_id] = current_row["position"]
    return positions


def _position_context(student: Student, results: list[Result], session_id: int | None, term: str | None) -> dict:
    """Return student-facing position details when class visibility allows it."""
    class_ = student.class_
    if session_id is None or term is None:
        return {
            "show_position": False,
            "overall_position": None,
            "stream_position": None,
            "overall_scope_label": None,
            "stream_scope_label": None,
            "subject_positions": {},
        }
    if not class_.show_position or class_.level in (Level.KINDERGARTEN, Level.NURSERY):
        return {
            "show_position": False,
            "overall_position": None,
            "stream_position": None,
            "overall_scope_label": None,
            "stream_scope_label": None,
            "subject_positions": {},
        }

    class_query = Result.query.join(Student).filter(
        Result.class_id == class_.id,
        Result.session_id == session_id,
        Result.term == term,
        Result.mode == ResultMode.SCORE,
        Result.is_offered.is_(True),
    )

    student_results_map = {}
    for result in class_query.all():
        student_results_map.setdefault(result.student, []).append(result)

    class_rows = build_position_rows(student_results_map)
    current_class_row = next((row for row in class_rows if row["student"].id == student.id), None)
    stream_position = None
    stream_scope_label = None

    if class_.level == Level.SECONDARY and student.stream_id is not None:
        stream_query = class_query.filter(Result.stream_id == student.stream_id)
        stream_map = {}
        for result in stream_query.all():
            stream_map.setdefault(result.student, []).append(result)
        stream_rows = build_position_rows(stream_map)
        current_stream_row = next((row for row in stream_rows if row["student"].id == student.id), None)
        stream_position = current_stream_row["position"] if current_stream_row else None
        stream_scope_label = f"{class_.name} - {student.stream.name}"

    return {
        "show_position": True,
        "overall_position": current_class_row["position"] if current_class_row else None,
        "stream_position": stream_position,
        "overall_scope_label": f"{class_.name} Class",
        "stream_scope_label": stream_scope_label,
        "subject_positions": _term_subject_positions(student, results, session_id, term),
    }


def _annual_ranking_rows(student: Student, session_id: int, *, stream_scope: bool) -> list[dict]:
    """Build annual ranking rows for the student's class or stream."""
    query = Result.query.join(Student).filter(
        Result.class_id == student.class_id,
        Result.session_id == session_id,
        Result.mode == ResultMode.SCORE,
        Result.is_offered.is_(True),
    )
    if stream_scope:
        query = query.filter(Result.stream_id == student.stream_id)

    grouped = defaultdict(lambda: defaultdict(list))
    for result in query.all():
        grouped[result.student][result.term].append(result)

    ranking_rows = []
    for peer, term_map in grouped.items():
        if any(term not in term_map or not term_map[term] for term in Term.ALL):
            continue

        term_summaries = [summarize_score_results(term_map[term]) for term in Term.ALL]
        annual_total_score = round(sum(item["total_score"] for item in term_summaries), 2)
        annual_percentage = round(
            sum(calculate_percentage(item["total_score"], item["subjects_taken"]) for item in term_summaries)
            / 3,
            2,
        )
        grade_counts = Counter()
        for term_results in term_map.values():
            for item in term_results:
                if item.grade:
                    grade_counts[item.grade] += 1

        ranking_rows.append(
            {
                "student": peer,
                "total_score": annual_total_score,
                "subjects_taken": sum(item["subjects_taken"] for item in term_summaries),
                "average_score": annual_percentage,
                "a_plus_count": grade_counts.get("A+", 0),
                "a_count": grade_counts.get("A", 0),
                "annual_percentage": annual_percentage,
            }
        )

    return rank_position_rows(ranking_rows)


def _annual_subject_positions(student: Student, session_id: int, annual_subject_rows: list[dict]) -> dict:
    """Return annual subject positions keyed by subject ID."""
    positions = {}
    for subject_row in annual_subject_rows:
        query = Result.query.join(Student).filter(
            Result.class_id == student.class_id,
            Result.session_id == session_id,
            Result.subject_id == subject_row["subject"].id,
            Result.mode == ResultMode.SCORE,
            Result.is_offered.is_(True),
        )
        if student.class_.level == Level.SECONDARY and student.stream_id is not None:
            query = query.filter(Result.stream_id == student.stream_id)

        grouped = defaultdict(list)
        for result in query.all():
            grouped[result.student].append(result)

        ranking_rows = []
        for peer, peer_results in grouped.items():
            term_map = {result.term: result for result in peer_results}
            if any(term not in term_map or term_map[term].total_score is None for term in Term.ALL):
                continue

            averages = [term_map[term].total_score for term in Term.ALL]
            grades = [term_map[term].grade for term in Term.ALL if term_map[term].grade]
            ranking_rows.append(
                {
                    "student": peer,
                    "total_score": round(sum(averages) / 3, 2),
                    "subjects_taken": 1,
                    "average_score": round(sum(averages) / 3, 2),
                    "a_plus_count": grades.count("A+"),
                    "a_count": grades.count("A"),
                }
            )

        ranked_rows = rank_position_rows(ranking_rows)
        current_row = next((row for row in ranked_rows if row["student"].id == student.id), None)
        if current_row:
            positions[subject_row["subject"].id] = current_row["position"]
    return positions


def _annual_context(student: Student, session_id: int | None) -> dict:
    """Return annual cumulative metrics for the selected session."""
    empty = {
        "available": False,
        "annual_total_score": None,
        "annual_percentage": None,
        "term_summaries": {},
        "subject_rows": [],
        "overall_position": None,
        "stream_position": None,
        "subject_positions": {},
    }
    if session_id is None or student.class_.level in (Level.KINDERGARTEN, Level.NURSERY):
        return empty

    results = (
        Result.query.join(Result.subject)
        .filter(
            Result.student_id == student.id,
            Result.session_id == session_id,
            Result.mode == ResultMode.SCORE,
        )
        .order_by(Result.subject_id.asc(), Result.term.asc())
        .all()
    )
    if not results:
        return empty

    by_term = defaultdict(list)
    for result in results:
        if result.is_offered and result.total_score is not None:
            by_term[result.term].append(result)

    if any(term not in by_term or not by_term[term] for term in Term.ALL):
        return empty

    term_summaries = {}
    for term in Term.ALL:
        summary = summarize_score_results(by_term[term])
        summary["percentage"] = calculate_percentage(summary["total_score"], summary["subjects_taken"])
        term_summaries[term] = summary

    annual_total_score = round(sum(item["total_score"] for item in term_summaries.values()), 2)
    annual_percentage = round(sum(item["percentage"] for item in term_summaries.values()) / 3, 2)

    subject_map = defaultdict(dict)
    for result in results:
        if result.is_offered and result.total_score is not None:
            subject_map[result.subject_id][result.term] = result

    subject_rows = []
    for term_map in subject_map.values():
        if any(term not in term_map for term in Term.ALL):
            continue
        subject = term_map[Term.FIRST].subject
        average_score = round(
            (
                term_map[Term.FIRST].total_score
                + term_map[Term.SECOND].total_score
                + term_map[Term.THIRD].total_score
            )
            / 3,
            2,
        )
        subject_rows.append(
            {
                "subject": subject,
                "average_score": average_score,
                "grade": calculate_grade(average_score),
            }
        )

    class_rows = _annual_ranking_rows(student, session_id, stream_scope=False)
    current_class_row = next((row for row in class_rows if row["student"].id == student.id), None)
    stream_position = None
    if student.class_.level == Level.SECONDARY and student.stream_id is not None:
        stream_rows = _annual_ranking_rows(student, session_id, stream_scope=True)
        current_stream_row = next((row for row in stream_rows if row["student"].id == student.id), None)
        stream_position = current_stream_row["position"] if current_stream_row else None

    return {
        "available": True,
        "annual_total_score": annual_total_score,
        "annual_percentage": annual_percentage,
        "term_summaries": term_summaries,
        "subject_rows": sorted(subject_rows, key=lambda item: item["subject"].name.lower()),
        "overall_position": current_class_row["position"] if current_class_row else None,
        "stream_position": stream_position,
        "subject_positions": _annual_subject_positions(student, session_id, subject_rows),
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
    position = _position_context(student, results, session_id, term)
    assessment_schema_items = _assessment_schema_items(student)
    annual = _annual_context(student, session_id)

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
        "annual": annual,
        "assessment_schema_items": assessment_schema_items,
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


@student_bp.route("/report-card/pdf")
@login_required
@role_required("student")
def report_card_pdf():
    """Return the current student's report card as a downloadable PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    student = _current_student()
    context = _report_context(student)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("School Academic Management System", styles["Title"]))
    story.append(Paragraph("Student Report Card", styles["Heading2"]))
    selected_period = context["selected_period"]["label"] if context["selected_period"] else "No period selected"
    story.append(Paragraph(f"Period: {selected_period}", styles["Normal"]))
    story.append(Spacer(1, 8))

    student_info = [
        ["Student", student.full_name],
        ["Student Code", student.student_code],
        ["Class", student.class_.name],
        ["Stream", student.stream.name if student.stream else "N/A"],
    ]
    student_table = Table(student_info, colWidths=[45 * mm, 120 * mm])
    student_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef6ff")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(student_table)
    story.append(Spacer(1, 10))

    summary = context["summary"]
    position = context["position"]
    annual = context["annual"]
    if summary["has_assessment_mode"] and not summary["has_score_mode"]:
        summary_rows = [
            ["Assessment Subjects", str(summary["assessment_subjects"])],
            ["Remarks Available", str(summary["remark_count"])],
            ["Report Mode", "Assessment"],
        ]
    else:
        summary_rows = [
            ["Subjects Taken", str(summary["subjects_taken"])],
            ["Total Score", f"{summary['total_score']:.2f}"],
            ["Average Score", f"{summary['average_score']:.2f}"],
            ["Percentage", f"{summary['percentage']:.2f}%"],
        ]
        if position["show_position"]:
            summary_rows.append(["Overall Position", str(position["overall_position"] or "-")])
            if position["stream_position"] is not None:
                summary_rows.append(["Stream Position", str(position["stream_position"])])

    summary_table = Table(summary_rows, colWidths=[55 * mm, 110 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 10))

    if summary["grade_summary"]:
        story.append(Paragraph("Grade Summary", styles["Heading3"]))
        grade_rows = [["Grade", "Count"]]
        grade_rows.extend([[item["grade"], str(item["count"])] for item in summary["grade_summary"]])
        grade_table = Table(grade_rows, colWidths=[40 * mm, 35 * mm])
        grade_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2564c9")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(grade_table)
        story.append(Spacer(1, 10))

    results = context["results"]
    if summary["has_assessment_mode"] and not summary["has_score_mode"]:
        headers = ["Subject", "Offered"] + [item["label"] for item in context["assessment_schema_items"]] + ["Remark"]
        rows = [headers]
        for result in results:
            row = [result.subject.name, "Yes" if result.is_offered else "No"]
            for item in context["assessment_schema_items"]:
                row.append(
                    result.assessment_json.get(item["key"], "-")
                    if result.is_offered and result.assessment_json
                    else "-"
                )
            row.append(result.remark or "-")
            rows.append(row)
    else:
        rows = [["Subject", "CA", "Exam", "Total", "Grade", "Subject Position", "Remark"]]
        for result in results:
            if not result.is_offered:
                continue
            rows.append(
                [
                    result.subject.name,
                    str(result.ca_score if result.ca_score is not None else "-"),
                    str(result.exam_score if result.exam_score is not None else "-"),
                    str(result.total_score if result.total_score is not None else "-"),
                    result.grade or "-",
                    str(position["subject_positions"].get(result.subject_id, "-")),
                    result.remark or "-",
                ]
            )

    result_table = Table(rows, repeatRows=1)
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(result_table)
    if annual["available"]:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Annual Summary", styles["Heading3"]))
        annual_summary_rows = [
            ["Annual Total", f"{annual['annual_total_score']:.2f}"],
            ["Annual Percentage", f"{annual['annual_percentage']:.2f}%"],
            ["Overall Annual Position", str(annual["overall_position"] or "-")],
            ["Stream Annual Position", str(annual["stream_position"] or "-")],
        ]
        annual_table = Table(annual_summary_rows, colWidths=[55 * mm, 110 * mm])
        annual_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(annual_table)
        story.append(Spacer(1, 10))
        annual_subject_rows = [["Subject", "Annual Average", "Grade", "Annual Subject Position"]]
        for row in annual["subject_rows"]:
            annual_subject_rows.append(
                [
                    row["subject"].name,
                    f"{row['average_score']:.2f}",
                    row["grade"],
                    str(annual["subject_positions"].get(row["subject"].id, "-")),
                ]
            )
        annual_subject_table = Table(annual_subject_rows, repeatRows=1)
        annual_subject_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2564c9")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe7")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(annual_subject_table)
    doc.build(story)
    buffer.seek(0)

    filename = f"{student.student_code}-{(context['selected_term'] or 'report')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )

"""Teacher result-management blueprint."""

from __future__ import annotations

import csv
import io

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.teacher_forms import ActionForm, CSVUploadForm
from app.models.class_ import Class, Level
from app.models.class_subject import ClassSubject
from app.models.class_teacher import ClassTeacherMap
from app.models.result import Result, ResultMode, ResultStatus
from app.models.session_term import SessionTerm
from app.models.stream import Stream
from app.models.stream_subject import StreamSubject
from app.models.student import Student
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.utils.decorators import role_required
from app.utils.helpers import calculate_grade

teacher_bp = Blueprint("teacher", __name__, template_folder="../templates/teacher")


def _current_teacher() -> Teacher:
    """Return the logged-in teacher profile or forbid access."""
    teacher = current_user.teacher_profile
    if teacher is None:
        abort(403)
    return teacher


def _active_session_term() -> SessionTerm | None:
    """Return the active session-term used for teacher result entry."""
    return (
        SessionTerm.query.join(SessionTerm.session)
        .filter(
            SessionTerm.is_result_entry_active.is_(True),
            SessionTerm.session.has(is_active=True),
        )
        .first()
    )


def _teacher_classes(teacher: Teacher) -> list[Class]:
    """Return distinct classes the teacher can access."""
    return (
        Class.query.join(ClassTeacherMap)
        .filter(ClassTeacherMap.teacher_id == teacher.id, Class.is_active.is_(True))
        .order_by(Class.name.asc())
        .distinct()
        .all()
    )


def _teacher_assignments_for_class(teacher: Teacher, class_id: int) -> list[ClassTeacherMap]:
    """Return all assignment rows for a teacher within one class."""
    return (
        ClassTeacherMap.query.filter_by(teacher_id=teacher.id, class_id=class_id)
        .order_by(ClassTeacherMap.stream_id.asc())
        .all()
    )


def _get_accessible_class(teacher: Teacher, class_id: int | None) -> Class | None:
    """Return a class only if it is assigned to the current teacher."""
    if not class_id:
        return None

    class_ = Class.query.get_or_404(class_id)
    has_access = (
        ClassTeacherMap.query.filter_by(teacher_id=teacher.id, class_id=class_id).first()
        is not None
    )
    if not has_access:
        abort(403)
    return class_


def _accessible_streams(teacher: Teacher, class_: Class | None) -> list[Stream]:
    """Return the streams the teacher can access within a secondary class."""
    if class_ is None or class_.level != Level.SECONDARY:
        return []

    assignments = _teacher_assignments_for_class(teacher, class_.id)
    if not assignments:
        return []

    if any(assignment.stream_id is None for assignment in assignments):
        return (
            Stream.query.filter_by(class_id=class_.id, is_active=True)
            .order_by(Stream.name.asc())
            .all()
        )

    stream_ids = [assignment.stream_id for assignment in assignments if assignment.stream_id]
    return (
        Stream.query.filter(Stream.id.in_(stream_ids), Stream.is_active.is_(True))
        .order_by(Stream.name.asc())
        .all()
    )


def _get_accessible_stream(
    teacher: Teacher, class_: Class | None, stream_id: int | None
) -> Stream | None:
    """Return a stream only if it falls inside the teacher's secondary scope."""
    if class_ is None or class_.level != Level.SECONDARY:
        if stream_id:
            abort(403)
        return None

    streams = _accessible_streams(teacher, class_)
    if not stream_id:
        return None

    stream = next((item for item in streams if item.id == stream_id), None)
    if stream is None:
        abort(403)
    return stream


def _subjects_for_scope(class_: Class | None, stream: Stream | None) -> list[Subject]:
    """Return valid result-entry subjects for the current class or stream."""
    if class_ is None:
        return []

    if class_.level == Level.SECONDARY:
        if stream is None:
            return []
        return (
            Subject.query.join(StreamSubject)
            .filter(
                StreamSubject.stream_id == stream.id,
                Subject.is_active.is_(True),
            )
            .order_by(Subject.name.asc())
            .all()
        )

    return (
        Subject.query.join(ClassSubject)
        .filter(ClassSubject.class_id == class_.id, Subject.is_active.is_(True))
        .order_by(Subject.name.asc())
        .all()
    )


def _get_accessible_subject(
    class_: Class | None, stream: Stream | None, subject_id: int | None
) -> Subject | None:
    """Return a subject only if it belongs to the current class/stream scope."""
    if not subject_id:
        return None

    subject = next(
        (item for item in _subjects_for_scope(class_, stream) if item.id == subject_id),
        None,
    )
    if subject is None:
        abort(403)
    return subject


def _students_for_scope(class_: Class | None, stream: Stream | None) -> list[Student]:
    """Return active students that fall inside the selected scope."""
    if class_ is None:
        return []

    query = Student.query.filter_by(class_id=class_.id, is_active=True)
    if class_.level == Level.SECONDARY:
        if stream is None:
            return []
        query = query.filter_by(stream_id=stream.id)
    return query.order_by(Student.last_name.asc(), Student.first_name.asc()).all()


def _result_lookup(
    class_: Class | None,
    stream: Stream | None,
    subject: Subject | None,
    session_term: SessionTerm | None,
) -> dict[int, Result]:
    """Return existing results keyed by student ID for the selected scope."""
    if not all([class_, subject, session_term]):
        return {}

    query = Result.query.filter_by(
        class_id=class_.id,
        subject_id=subject.id,
        session_id=session_term.session_id,
        term=session_term.term,
    )
    if class_.level == Level.SECONDARY:
        query = query.filter_by(stream_id=stream.id if stream else None)
    else:
        query = query.filter(Result.stream_id.is_(None))

    return {result.student_id: result for result in query.all()}


def _status_badge(status: str | None) -> str:
    """Return a human-friendly status label."""
    labels = {
        ResultStatus.DRAFT: "Draft",
        ResultStatus.SUBMITTED: "Submitted",
        ResultStatus.LOCKED: "Locked",
    }
    return labels.get(status or "", "Not started")


def _parse_bool(value: str | None) -> bool:
    """Parse common boolean-like strings from CSV rows."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _coerce_score(raw_value: str | None, field_name: str, row_label: str) -> float:
    """Convert a score field to float with a clear validation error."""
    value = (raw_value or "").strip()
    if value == "":
        raise ValueError(f"{row_label}: {field_name} is required when the subject is offered.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{row_label}: {field_name} must be a number.") from exc


def _ensure_editable_session(session_term: SessionTerm | None, class_: Class | None) -> None:
    """Abort the save flow if there is no open session-term for the selected class."""
    if session_term is None:
        raise ValueError("No active session-term is available for result entry.")
    if class_ is None or class_.session_id != session_term.session_id:
        raise ValueError("The selected class does not belong to the active result-entry session.")
    if session_term.is_locked:
        raise ValueError("Results are locked for the active session-term.")


def _upsert_score_result(
    *,
    existing: Result | None,
    student: Student,
    subject: Subject,
    class_: Class,
    stream: Stream | None,
    session_term: SessionTerm,
    teacher: Teacher,
    is_offered: bool,
    ca_score: float | None,
    exam_score: float | None,
    target_status: str,
) -> Result:
    """Create or update one score-mode result within the teacher's allowed scope."""
    if existing is not None and existing.result_status != ResultStatus.DRAFT:
        raise ValueError(
            f"{student.full_name}: this result is already {existing.result_status} and cannot be edited."
        )

    result = existing or Result(
        student_id=student.id,
        subject_id=subject.id,
        class_id=class_.id,
        stream_id=stream.id if stream else None,
        session_id=session_term.session_id,
        term=session_term.term,
        mode=ResultMode.SCORE,
        created_by=teacher.id,
        uploaded_by_user_id=current_user.id,
    )
    if existing is None:
        db.session.add(result)

    result.created_by = teacher.id
    result.uploaded_by_user_id = current_user.id
    result.mode = ResultMode.SCORE
    result.is_offered = is_offered
    result.ca_score = ca_score
    result.exam_score = exam_score
    result.result_status = target_status

    if result.result_status == ResultStatus.SUBMITTED and existing is not None:
        if not existing.can_transition_to(ResultStatus.SUBMITTED, current_user.role):
            raise ValueError(f"{student.full_name}: this result cannot be submitted.")

    return result


def _manual_entry_fields_present(student_id: int) -> bool:
    """Return whether a posted manual-entry row contains editable fields."""
    keys = {
        f"is_offered_{student_id}",
        f"ca_score_{student_id}",
        f"exam_score_{student_id}",
    }
    return any(key in request.form for key in keys)


@teacher_bp.route("/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    """Teacher dashboard with scope summary and current result-entry period."""
    teacher = _current_teacher()
    assigned_classes = _teacher_classes(teacher)
    active_session_term = _active_session_term()
    return render_template(
        "teacher/dashboard.html",
        teacher=teacher,
        assigned_classes=assigned_classes,
        active_session_term=active_session_term,
    )


@teacher_bp.route("/classes")
@login_required
@role_required("teacher")
def classes():
    """List the classes and stream scopes assigned to the logged-in teacher."""
    teacher = _current_teacher()
    assigned_classes = _teacher_classes(teacher)
    class_scopes = []
    for class_ in assigned_classes:
        streams = _accessible_streams(teacher, class_)
        class_scopes.append(
            {
                "class": class_,
                "streams": streams,
                "has_stream_scope": class_.level == Level.SECONDARY,
            }
        )

    return render_template(
        "teacher/classes.html",
        teacher=teacher,
        class_scopes=class_scopes,
    )


@teacher_bp.route("/students")
@login_required
@role_required("teacher")
def students():
    """View active students only within the teacher's assigned scope."""
    teacher = _current_teacher()
    assigned_classes = _teacher_classes(teacher)
    selected_class = _get_accessible_class(teacher, request.args.get("class_id", type=int))
    selected_stream = _get_accessible_stream(
        teacher, selected_class, request.args.get("stream_id", type=int)
    )
    streams = _accessible_streams(teacher, selected_class)
    scoped_students = _students_for_scope(selected_class, selected_stream)

    return render_template(
        "teacher/students.html",
        teacher=teacher,
        assigned_classes=assigned_classes,
        selected_class=selected_class,
        selected_stream=selected_stream,
        streams=streams,
        students=scoped_students,
    )


@teacher_bp.route("/results/upload", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def upload_results():
    """Teacher result management for single-entry and CSV upload."""
    teacher = _current_teacher()
    assigned_classes = _teacher_classes(teacher)
    action_form = ActionForm()
    csv_form = CSVUploadForm()
    active_session_term = _active_session_term()

    if request.method == "POST":
        class_id = request.form.get("class_id", type=int)
        stream_id = request.form.get("stream_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        form_name = request.form.get("form_name", "")
        selected_class = _get_accessible_class(teacher, class_id)
        selected_stream = _get_accessible_stream(teacher, selected_class, stream_id)
        selected_subject = _get_accessible_subject(selected_class, selected_stream, subject_id)

        try:
            _ensure_editable_session(active_session_term, selected_class)
            if form_name == "manual-entry":
                if not action_form.validate_on_submit():
                    raise ValueError("The result form is invalid. Please refresh and try again.")
                _save_manual_results(
                    teacher,
                    selected_class,
                    selected_stream,
                    selected_subject,
                    active_session_term,
                )
            elif form_name == "csv-upload":
                if not csv_form.validate_on_submit():
                    raise ValueError("A CSV file is required for bulk upload.")
                _save_csv_results(
                    teacher,
                    selected_class,
                    selected_stream,
                    selected_subject,
                    active_session_term,
                    csv_form,
                )
            else:
                raise ValueError("Unsupported result action.")
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        else:
            flash("Results saved successfully.", "success")

        return redirect(
            url_for(
                "teacher.upload_results",
                class_id=class_id,
                stream_id=stream_id,
                subject_id=subject_id,
            )
        )

    selected_class = _get_accessible_class(teacher, request.args.get("class_id", type=int))
    selected_stream = _get_accessible_stream(
        teacher, selected_class, request.args.get("stream_id", type=int)
    )
    selected_subject = _get_accessible_subject(
        selected_class, selected_stream, request.args.get("subject_id", type=int)
    )
    streams = _accessible_streams(teacher, selected_class)
    subjects = _subjects_for_scope(selected_class, selected_stream)
    scoped_students = _students_for_scope(selected_class, selected_stream)
    existing_results = _result_lookup(
        selected_class, selected_stream, selected_subject, active_session_term
    )

    return render_template(
        "teacher/upload_results.html",
        teacher=teacher,
        assigned_classes=assigned_classes,
        active_session_term=active_session_term,
        selected_class=selected_class,
        selected_stream=selected_stream,
        selected_subject=selected_subject,
        streams=streams,
        subjects=subjects,
        students=scoped_students,
        existing_results=existing_results,
        action_form=action_form,
        csv_form=csv_form,
        grade_scale=[
            {"minimum": 90, "grade": "A+"},
            {"minimum": 80, "grade": "A"},
            {"minimum": 70, "grade": "B"},
            {"minimum": 60, "grade": "C"},
            {"minimum": 50, "grade": "D"},
            {"minimum": 40, "grade": "E"},
            {"minimum": 0, "grade": "F"},
        ],
        status_badge=_status_badge,
    )


@teacher_bp.route("/results/edit")
@login_required
@role_required("teacher")
def edit_results():
    """Reuse the result management page for editing unlocked draft results."""
    return redirect(
        url_for(
            "teacher.upload_results",
            class_id=request.args.get("class_id", type=int),
            stream_id=request.args.get("stream_id", type=int),
            subject_id=request.args.get("subject_id", type=int),
        )
    )


def _save_manual_results(
    teacher: Teacher,
    selected_class: Class | None,
    selected_stream: Stream | None,
    selected_subject: Subject | None,
    session_term: SessionTerm,
) -> None:
    """Persist one scoped result sheet from the teacher entry table."""
    if not all([selected_class, selected_subject]):
        raise ValueError("Select a class and subject before saving results.")
    if selected_class.level == Level.SECONDARY and selected_stream is None:
        raise ValueError("Select a stream before saving secondary results.")

    target_status = (
        ResultStatus.SUBMITTED
        if request.form.get("action") == "submit_results"
        else ResultStatus.DRAFT
    )
    students = _students_for_scope(selected_class, selected_stream)
    existing_results = _result_lookup(selected_class, selected_stream, selected_subject, session_term)

    if not students:
        raise ValueError("There are no students in the selected scope.")

    changed_rows = 0
    for student in students:
        existing = existing_results.get(student.id)
        if existing is not None and existing.result_status != ResultStatus.DRAFT:
            if _manual_entry_fields_present(student.id):
                raise ValueError(
                    f"{student.full_name}: submitted or locked results cannot be edited by teachers."
                )
            continue

        is_offered = request.form.get(f"is_offered_{student.id}") == "on"
        ca_score = None
        exam_score = None
        if is_offered:
            ca_score = _coerce_score(
                request.form.get(f"ca_score_{student.id}"),
                "CA score",
                student.full_name,
            )
            exam_score = _coerce_score(
                request.form.get(f"exam_score_{student.id}"),
                "Exam score",
                student.full_name,
            )

        _upsert_score_result(
            existing=existing,
            student=student,
            subject=selected_subject,
            class_=selected_class,
            stream=selected_stream,
            session_term=session_term,
            teacher=teacher,
            is_offered=is_offered,
            ca_score=ca_score,
            exam_score=exam_score,
            target_status=target_status,
        )
        changed_rows += 1

    if changed_rows == 0:
        raise ValueError("No editable results were found in the selected scope.")


def _save_csv_results(
    teacher: Teacher,
    selected_class: Class | None,
    selected_stream: Stream | None,
    selected_subject: Subject | None,
    session_term: SessionTerm,
    csv_form: CSVUploadForm,
) -> None:
    """Persist bulk results from a teacher-uploaded CSV file."""
    if not all([selected_class, selected_subject]):
        raise ValueError("Select a class and subject before uploading a CSV.")
    if selected_class.level == Level.SECONDARY and selected_stream is None:
        raise ValueError("Select a stream before uploading secondary results.")

    upload_action = request.form.get("action")
    target_status = (
        ResultStatus.SUBMITTED if upload_action == "submit_csv_results" else ResultStatus.DRAFT
    )
    students = _students_for_scope(selected_class, selected_stream)
    if not students:
        raise ValueError("There are no students in the selected scope.")

    student_by_code = {student.student_code: student for student in students}
    existing_results = _result_lookup(selected_class, selected_stream, selected_subject, session_term)

    try:
        content = csv_form.csv_file.data.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The uploaded file must be a UTF-8 encoded CSV.") from exc

    reader = csv.DictReader(io.StringIO(content))
    required_columns = {"student_code", "ca_score", "exam_score", "is_offered"}
    if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
        raise ValueError(
            "CSV headers must include: student_code, ca_score, exam_score, is_offered."
        )

    rows = list(reader)
    if not rows:
        raise ValueError("The uploaded CSV file is empty.")

    pending_rows = {}
    for row_number, row in enumerate(rows, start=2):
        student_code = (row.get("student_code") or "").strip()
        if not student_code:
            raise ValueError(f"Row {row_number}: student_code is required.")
        student = student_by_code.get(student_code)
        if student is None:
            raise ValueError(
                f"Row {row_number}: {student_code} is not a student in the selected class or stream."
            )

        is_offered = _parse_bool(row.get("is_offered"))
        ca_score = None
        exam_score = None
        if is_offered:
            row_label = f"Row {row_number} ({student_code})"
            ca_score = _coerce_score(row.get("ca_score"), "CA score", row_label)
            exam_score = _coerce_score(row.get("exam_score"), "Exam score", row_label)

        pending_rows[student.id] = {
            "student": student,
            "is_offered": is_offered,
            "ca_score": ca_score,
            "exam_score": exam_score,
        }

    for student_id, payload in pending_rows.items():
        existing = existing_results.get(student_id)
        if existing is not None and existing.result_status != ResultStatus.DRAFT:
            raise ValueError(
                f"{payload['student'].full_name}: submitted or locked results cannot be edited by teachers."
            )

        _upsert_score_result(
            existing=existing,
            student=payload["student"],
            subject=selected_subject,
            class_=selected_class,
            stream=selected_stream,
            session_term=session_term,
            teacher=teacher,
            is_offered=payload["is_offered"],
            ca_score=payload["ca_score"],
            exam_score=payload["exam_score"],
            target_status=target_status,
        )

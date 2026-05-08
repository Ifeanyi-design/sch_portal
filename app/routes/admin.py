"""Admin blueprint for academic setup and result control."""

from __future__ import annotations

from datetime import date
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.teacher_forms import ActionForm, CSVUploadForm
from app.models.class_ import Class, Level
from app.models.class_subject import ClassSubject
from app.models.class_teacher import ClassTeacherMap
from app.models.result import Result, ResultMode, ResultStatus
from app.models.session_ import Session
from app.models.session_term import SessionTerm, Term
from app.models.stream import Stream
from app.models.stream_subject import StreamSubject
from app.models.student import Student
from app.models.subject import Subject
from app.models.system_setting import SystemSetting
from app.models.teacher import Teacher
from app.models.user import Role, User
from app.utils.decorators import role_required
from app.utils.helpers import (
    build_position_rows,
    build_subject_position_rows,
    generate_student_id,
)

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def _checkbox(name: str) -> bool:
    """Return True when a checkbox-style field is enabled."""
    return request.form.get(name) in {"on", "true", "1", "yes"}


def _split_name(first_name: str, last_name: str) -> str:
    """Return a normalized full name string."""
    return f"{first_name.strip()} {last_name.strip()}".strip()


def _parse_date_field(field_name: str) -> date:
    """Return an ISO date field or raise a clear validation error."""
    raw_value = request.form.get(field_name, "").strip()
    if not raw_value:
        raise ValueError(f"{field_name.replace('_', ' ').title()} is required.")
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(f"{field_name.replace('_', ' ').title()} must be a valid date.") from exc


def _parse_assessment_schema(level: str, raw_keys: str) -> dict | None:
    """Return a normalized assessment schema payload for nursery classes."""
    if level not in (Level.KINDERGARTEN, Level.NURSERY):
        return None

    keys = [key.strip() for key in raw_keys.split(",") if key.strip()]
    if not keys:
        keys = ["participation", "skill_level", "observation"]

    schema = {}
    for key in keys:
        if key in {"attendance"}:
            schema[key] = "integer"
        elif key in {"participation", "skill_level", "behavior"}:
            schema[key] = "rating"
        else:
            schema[key] = "text"
    return schema


def _active_session_term() -> SessionTerm | None:
    """Return the currently active session-term for result entry."""
    return (
        SessionTerm.query.join(Session)
        .filter(Session.is_active.is_(True), SessionTerm.is_result_entry_active.is_(True))
        .first()
    )


def _session_options() -> list[Session]:
    """Return sessions for admin dropdowns."""
    return Session.query.order_by(Session.name.desc()).all()


def _class_options() -> list[Class]:
    """Return classes for admin dropdowns."""
    return Class.query.order_by(Class.name.asc()).all()


def _stream_options(class_id: int | None = None) -> list[Stream]:
    """Return streams for one class or all streams."""
    query = Stream.query.order_by(Stream.name.asc())
    if class_id is not None:
        query = query.filter_by(class_id=class_id)
    return query.all()


def _result_scope_subjects(class_: Class | None, stream: Stream | None) -> list[Subject]:
    """Return subjects valid for the selected result-entry scope."""
    if class_ is None:
        return []
    if class_.level == Level.SECONDARY:
        if stream is None:
            return []
        return (
            Subject.query.join(StreamSubject)
            .filter(StreamSubject.stream_id == stream.id, Subject.is_active.is_(True))
            .order_by(Subject.name.asc())
            .all()
        )
    return (
        Subject.query.join(ClassSubject)
        .filter(ClassSubject.class_id == class_.id, Subject.is_active.is_(True))
        .order_by(Subject.name.asc())
        .all()
    )


def _result_scope_students(class_: Class | None, stream: Stream | None) -> list[Student]:
    """Return active students in the selected result scope."""
    if class_ is None:
        return []
    query = Student.query.filter_by(class_id=class_.id, is_active=True)
    if class_.level == Level.SECONDARY:
        if stream is None:
            return []
        query = query.filter_by(stream_id=stream.id)
    return query.order_by(Student.last_name.asc(), Student.first_name.asc()).all()


def _result_sheet_lookup(
    class_: Class | None,
    stream: Stream | None,
    subject: Subject | None,
    session_id: int | None,
    term: str | None,
) -> dict[int, Result]:
    """Return existing results keyed by student for one admin entry sheet."""
    if not all([class_, subject, session_id, term]):
        return {}
    query = Result.query.filter_by(
        class_id=class_.id,
        subject_id=subject.id,
        session_id=session_id,
        term=term,
    )
    if class_.level == Level.SECONDARY:
        query = query.filter_by(stream_id=stream.id if stream else None)
    else:
        query = query.filter(Result.stream_id.is_(None))
    return {result.student_id: result for result in query.all()}


def _selected_subject(class_: Class | None, stream: Stream | None, subject_id: int | None) -> Subject | None:
    """Return the selected subject only when it belongs to the chosen scope."""
    if not subject_id:
        return None
    return next(
        (subject for subject in _result_scope_subjects(class_, stream) if subject.id == subject_id),
        None,
    )


def _selected_session_term(session_id: int | None, term: str | None) -> SessionTerm | None:
    """Return the matching session-term row for uploads and locks."""
    if not session_id or not term:
        return None
    return SessionTerm.query.filter_by(session_id=session_id, term=term).first()


def _parse_bool(value: str | None) -> bool:
    """Parse common boolean-like strings."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_score(raw_value: str | None, field_name: str, row_label: str) -> float:
    """Convert a score field to float with a clear validation error."""
    value = (raw_value or "").strip()
    if value == "":
        raise ValueError(f"{row_label}: {field_name} is required when the subject is offered.")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{row_label}: {field_name} must be a number.") from exc


def _coerce_assessment_value(raw_value: str | None, field_type: str, field_label: str, row_label: str, *, required: bool):
    """Normalize one assessment field based on its schema type."""
    value = (raw_value or "").strip()
    if value == "":
        if required:
            raise ValueError(f"{row_label}: {field_label} is required when the subject is offered.")
        return None
    if field_type == "integer":
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{row_label}: {field_label} must be a whole number.") from exc
    return value


def _ensure_admin_upload_window(session_term: SessionTerm | None, class_: Class | None, session_id: int | None) -> None:
    """Ensure the selected upload scope is writable."""
    if session_term is None or class_ is None or session_id is None:
        raise ValueError("Class, session, and term are required before uploading results.")
    if class_.session_id != session_id:
        raise ValueError("The selected class does not belong to the chosen session.")
    if session_term.is_locked:
        raise ValueError("Results are locked for the selected session-term.")


def _teacher_options() -> list[Teacher]:
    """Return active teacher profiles."""
    return Teacher.query.order_by(Teacher.first_name.asc(), Teacher.last_name.asc()).all()


def _student_options() -> list[Student]:
    """Return active student profiles."""
    return Student.query.order_by(Student.first_name.asc(), Student.last_name.asc()).all()


def _subject_options() -> list[Subject]:
    """Return active subjects."""
    return Subject.query.order_by(Subject.name.asc()).all()


def _class_subjects_map() -> dict[int, list[ClassSubject]]:
    """Return class subject assignments grouped by class."""
    grouped = {}
    for assignment in ClassSubject.query.order_by(ClassSubject.class_id.asc()).all():
        grouped.setdefault(assignment.class_id, []).append(assignment)
    return grouped


def _stream_subjects_map() -> dict[int, list[StreamSubject]]:
    """Return stream subject assignments grouped by stream."""
    grouped = {}
    for assignment in StreamSubject.query.order_by(StreamSubject.stream_id.asc()).all():
        grouped.setdefault(assignment.stream_id, []).append(assignment)
    return grouped


def _assessment_schema_items(class_: Class | None) -> list[dict]:
    """Return nursery assessment schema entries in display order."""
    if (
        class_ is None
        or class_.level not in (Level.KINDERGARTEN, Level.NURSERY)
        or not class_.assessment_schema
    ):
        return []

    return [
        {"key": key, "label": key.replace("_", " ").title(), "type": value}
        for key, value in class_.assessment_schema.items()
    ]


def _teacher_assignments_map() -> dict[int, list[ClassTeacherMap]]:
    """Return teacher assignments grouped by teacher."""
    grouped = {}
    for assignment in ClassTeacherMap.query.order_by(ClassTeacherMap.class_id.asc()).all():
        grouped.setdefault(assignment.teacher_id, []).append(assignment)
    return grouped


def _system_settings() -> SystemSetting:
    """Return the single mutable settings row."""
    return SystemSetting.get_current()


def _student_results_query(class_id: int | None, stream_id: int | None, session_id: int | None, term: str | None):
    """Return a filtered result query for the admin results page."""
    query = (
        Result.query.join(Student)
        .join(Subject)
        .join(Session)
    )
    if class_id:
        query = query.filter(Result.class_id == class_id)
    if stream_id:
        query = query.filter(Result.stream_id == stream_id)
    if session_id:
        query = query.filter(Result.session_id == session_id)
    if term:
        query = query.filter(Result.term == term)
    return query.order_by(Student.last_name.asc(), Subject.name.asc())


def _position_boards(selected_class: Class | None, session_id: int | None, term: str | None) -> list[dict]:
    """Compute ranking boards for the selected class and session-term."""
    if selected_class is None or session_id is None or term is None:
        return []
    if selected_class.level in (Level.KINDERGARTEN, Level.NURSERY):
        return []

    boards = []
    base_results = (
        Result.query.join(Student)
        .filter(
            Result.class_id == selected_class.id,
            Result.session_id == session_id,
            Result.term == term,
            Result.mode == ResultMode.SCORE,
            Result.is_offered.is_(True),
        )
        .all()
    )

    if selected_class.level == Level.PRIMARY:
        student_map = {}
        for result in base_results:
            student_map.setdefault(result.student, []).append(result)
        boards.append(
            {
                "label": f"{selected_class.name} Class Ranking",
                "scope": "class",
                "rows": build_position_rows(student_map),
            }
        )
        return boards

    streams = selected_class.streams
    student_map = {}
    for result in base_results:
        student_map.setdefault(result.student, []).append(result)
    boards.append(
        {
            "label": f"{selected_class.name} Overall Class Ranking",
            "scope": "class",
            "rows": build_position_rows(student_map),
        }
    )
    if not streams:
        return boards

    for stream in streams:
        student_map = {}
        for result in base_results:
            if result.stream_id != stream.id:
                continue
            student_map.setdefault(result.student, []).append(result)
        boards.append(
            {
                "label": f"{selected_class.name} - {stream.name}",
                "scope": "stream",
                "stream": stream,
                "rows": build_position_rows(student_map),
            }
        )
    return boards


def _subject_position_board(
    selected_class: Class | None,
    selected_stream: Stream | None,
    selected_subject: Subject | None,
    session_id: int | None,
    term: str | None,
) -> dict | None:
    """Compute one subject ranking board for the currently selected subject scope."""
    if not all([selected_class, selected_subject, session_id, term]):
        return None
    if selected_class.level in (Level.KINDERGARTEN, Level.NURSERY):
        return None

    query = Result.query.join(Student).filter(
        Result.class_id == selected_class.id,
        Result.subject_id == selected_subject.id,
        Result.session_id == session_id,
        Result.term == term,
        Result.mode == ResultMode.SCORE,
        Result.is_offered.is_(True),
    )
    if selected_class.level == Level.SECONDARY and selected_stream is not None:
        query = query.filter(Result.stream_id == selected_stream.id)

    rows = build_subject_position_rows(query.all())
    if selected_class.level == Level.SECONDARY and selected_stream is not None:
        label = f"{selected_subject.name} - {selected_stream.name} Subject Ranking"
    else:
        label = f"{selected_subject.name} Subject Ranking"
    return {"label": label, "rows": rows}


def _manual_entry_fields_present(student_id: int) -> bool:
    """Return whether a posted manual-entry row contains editable fields."""
    keys = {
        f"is_offered_{student_id}",
        f"ca_score_{student_id}",
        f"exam_score_{student_id}",
        f"remark_{student_id}",
    }
    if any(key in request.form for key in keys):
        return True
    return any(
        key.startswith("assessment__") and key.endswith(f"__{student_id}")
        for key in request.form.keys()
    )


def _upsert_admin_score_result(
    *,
    existing: Result | None,
    student: Student,
    subject: Subject,
    class_: Class,
    stream: Stream | None,
    session_id: int,
    term: str,
    is_offered: bool,
    ca_score: float | None,
    exam_score: float | None,
    target_status: str,
) -> None:
    """Create or update one score-mode result from the admin workspace."""
    if existing is not None and existing.result_status == ResultStatus.LOCKED:
        raise ValueError(f"{student.full_name}: locked results must be unlocked before upload.")

    result = existing or Result(
        student_id=student.id,
        subject_id=subject.id,
        class_id=class_.id,
        stream_id=stream.id if stream else None,
        session_id=session_id,
        term=term,
        mode=ResultMode.SCORE,
        uploaded_by_user_id=current_user.id,
    )
    if existing is None:
        db.session.add(result)

    result.mode = ResultMode.SCORE
    result.is_offered = is_offered
    result.ca_score = ca_score
    result.exam_score = exam_score
    result.result_status = target_status
    result.uploaded_by_user_id = current_user.id


def _upsert_admin_assessment_result(
    *,
    existing: Result | None,
    student: Student,
    subject: Subject,
    class_: Class,
    session_id: int,
    term: str,
    is_offered: bool,
    assessment_json: dict,
    remark: str | None,
    target_status: str,
) -> None:
    """Create or update one assessment-mode result from the admin workspace."""
    if existing is not None and existing.result_status == ResultStatus.LOCKED:
        raise ValueError(f"{student.full_name}: locked assessments must be unlocked before upload.")

    result = existing or Result(
        student_id=student.id,
        subject_id=subject.id,
        class_id=class_.id,
        stream_id=None,
        session_id=session_id,
        term=term,
        mode=ResultMode.ASSESSMENT,
        uploaded_by_user_id=current_user.id,
    )
    if existing is None:
        db.session.add(result)

    result.mode = ResultMode.ASSESSMENT
    result.is_offered = is_offered
    result.assessment_json = assessment_json
    result.remark = remark
    result.result_status = target_status
    result.uploaded_by_user_id = current_user.id


def _save_admin_manual_results(
    selected_class: Class | None,
    selected_stream: Stream | None,
    selected_subject: Subject | None,
    selected_session: Session | None,
    selected_term: str | None,
) -> None:
    """Persist one admin-managed result sheet."""
    if not all([selected_class, selected_subject, selected_session, selected_term]):
        raise ValueError("Select class, session, term, and subject before saving results.")
    if selected_class.level == Level.SECONDARY and selected_stream is None:
        raise ValueError("Select a stream before saving secondary results.")

    session_term = _selected_session_term(selected_session.id, selected_term)
    _ensure_admin_upload_window(session_term, selected_class, selected_session.id)
    target_status = (
        ResultStatus.SUBMITTED
        if request.form.get("action") == "submit_admin_results"
        else ResultStatus.DRAFT
    )
    students = _result_scope_students(selected_class, selected_stream)
    existing_results = _result_sheet_lookup(
        selected_class,
        selected_stream,
        selected_subject,
        selected_session.id,
        selected_term,
    )
    if not students:
        raise ValueError("There are no students in the selected scope.")

    schema_items = _assessment_schema_items(selected_class)
    changed_rows = 0
    for student in students:
        existing = existing_results.get(student.id)
        if existing is not None and existing.result_status == ResultStatus.LOCKED:
            if _manual_entry_fields_present(student.id):
                raise ValueError(f"{student.full_name}: locked rows must be unlocked before upload.")
            continue

        is_offered = request.form.get(f"is_offered_{student.id}") == "on"
        if selected_class.level in (Level.KINDERGARTEN, Level.NURSERY):
            assessment_json = {}
            for item in schema_items:
                field_name = f"assessment__{item['key']}__{student.id}"
                assessment_json[item["key"]] = _coerce_assessment_value(
                    request.form.get(field_name),
                    item["type"],
                    item["label"],
                    student.full_name,
                    required=is_offered,
                )
            remark = request.form.get(f"remark_{student.id}", "").strip() or None
            _upsert_admin_assessment_result(
                existing=existing,
                student=student,
                subject=selected_subject,
                class_=selected_class,
                session_id=selected_session.id,
                term=selected_term,
                is_offered=is_offered,
                assessment_json=assessment_json,
                remark=remark,
                target_status=target_status,
            )
        else:
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
            _upsert_admin_score_result(
                existing=existing,
                student=student,
                subject=selected_subject,
                class_=selected_class,
                stream=selected_stream,
                session_id=selected_session.id,
                term=selected_term,
                is_offered=is_offered,
                ca_score=ca_score,
                exam_score=exam_score,
                target_status=target_status,
            )
        changed_rows += 1

    if changed_rows == 0:
        raise ValueError("No editable results were found in the selected scope.")


def _save_admin_csv_results(
    selected_class: Class | None,
    selected_stream: Stream | None,
    selected_subject: Subject | None,
    selected_session: Session | None,
    selected_term: str | None,
    csv_form: CSVUploadForm,
) -> None:
    """Persist bulk CSV results from the admin workspace."""
    import csv
    import io

    if not all([selected_class, selected_subject, selected_session, selected_term]):
        raise ValueError("Select class, session, term, and subject before uploading a CSV.")
    if selected_class.level in (Level.KINDERGARTEN, Level.NURSERY):
        raise ValueError("CSV upload is not available for assessment-mode classes.")
    if selected_class.level == Level.SECONDARY and selected_stream is None:
        raise ValueError("Select a stream before uploading secondary results.")

    session_term = _selected_session_term(selected_session.id, selected_term)
    _ensure_admin_upload_window(session_term, selected_class, selected_session.id)
    target_status = (
        ResultStatus.SUBMITTED
        if request.form.get("action") == "submit_admin_csv"
        else ResultStatus.DRAFT
    )
    students = _result_scope_students(selected_class, selected_stream)
    if not students:
        raise ValueError("There are no students in the selected scope.")

    student_by_code = {student.student_code: student for student in students}
    existing_results = _result_sheet_lookup(
        selected_class,
        selected_stream,
        selected_subject,
        selected_session.id,
        selected_term,
    )

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

    for row_number, row in enumerate(rows, start=2):
        student_code = (row.get("student_code") or "").strip()
        if not student_code:
            raise ValueError(f"Row {row_number}: student_code is required.")
        student = student_by_code.get(student_code)
        if student is None:
            raise ValueError(
                f"Row {row_number}: {student_code} is not a student in the selected class or stream."
            )

        existing = existing_results.get(student.id)
        if existing is not None and existing.result_status == ResultStatus.LOCKED:
            raise ValueError(f"{student.full_name}: locked rows must be unlocked before upload.")

        is_offered = _parse_bool(row.get("is_offered"))
        ca_score = None
        exam_score = None
        if is_offered:
            row_label = f"Row {row_number} ({student_code})"
            ca_score = _coerce_score(row.get("ca_score"), "CA score", row_label)
            exam_score = _coerce_score(row.get("exam_score"), "Exam score", row_label)

        _upsert_admin_score_result(
            existing=existing,
            student=student,
            subject=selected_subject,
            class_=selected_class,
            stream=selected_stream,
            session_id=selected_session.id,
            term=selected_term,
            is_offered=is_offered,
            ca_score=ca_score,
            exam_score=exam_score,
            target_status=target_status,
        )


def _create_teacher() -> None:
    """Create a teacher user and profile."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    staff_id = request.form.get("staff_id", "").strip() or None
    phone = request.form.get("phone", "").strip() or None

    if not all([first_name, last_name, username, email, password]):
        raise ValueError("Teacher first name, last name, username, email, and password are required.")
    if User.query.filter((User.username == username) | (User.email == email)).first():
        raise ValueError("A user with that username or email already exists.")
    if staff_id and Teacher.query.filter_by(staff_id=staff_id).first():
        raise ValueError("That staff ID is already in use.")

    user = User(
        username=username,
        full_name=_split_name(first_name, last_name),
        email=email,
        role=Role.TEACHER,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    db.session.add(
        Teacher(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            staff_id=staff_id,
            phone=phone,
            is_active=True,
        )
    )


def _update_teacher() -> None:
    """Update one teacher profile and login details."""
    teacher = Teacher.query.get_or_404(request.form.get("teacher_id", type=int))
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    staff_id = request.form.get("staff_id", "").strip() or None
    phone = request.form.get("phone", "").strip() or None

    if not all([first_name, last_name, username, email]):
        raise ValueError("Teacher first name, last name, username, and email are required.")

    duplicate_user = User.query.filter(
        ((User.username == username) | (User.email == email)),
        User.id != teacher.user_id,
    ).first()
    if duplicate_user:
        raise ValueError("Another user already uses that username or email.")

    if staff_id:
        duplicate_staff = Teacher.query.filter(
            Teacher.staff_id == staff_id,
            Teacher.id != teacher.id,
        ).first()
        if duplicate_staff:
            raise ValueError("Another teacher already uses that staff ID.")

    teacher.first_name = first_name
    teacher.last_name = last_name
    teacher.staff_id = staff_id
    teacher.phone = phone
    teacher.user.username = username
    teacher.user.email = email
    teacher.user.full_name = _split_name(first_name, last_name)


def _toggle_teacher_active() -> None:
    """Activate or deactivate one teacher account."""
    teacher = Teacher.query.get_or_404(request.form.get("teacher_id", type=int))
    teacher.is_active = not teacher.is_active
    teacher.user.is_active = teacher.is_active


def _assign_teacher() -> None:
    """Assign a teacher to a class."""
    teacher_id = request.form.get("teacher_id", type=int)
    class_id = request.form.get("class_id", type=int)

    teacher = Teacher.query.get_or_404(teacher_id)
    class_ = Class.query.get_or_404(class_id)

    existing = ClassTeacherMap.query.filter_by(
        teacher_id=teacher.id,
        class_id=class_.id,
    ).first()
    if existing:
        raise ValueError("That teacher assignment already exists.")

    db.session.add(
        ClassTeacherMap(
            teacher_id=teacher.id,
            class_id=class_.id,
            stream_id=None,
        )
    )


def _create_student() -> None:
    """Create a student user and profile."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    gender = request.form.get("gender", "").strip().lower()
    date_of_birth = _parse_date_field("date_of_birth")
    admission_year = request.form.get("admission_year", type=int)
    class_id = request.form.get("class_id", type=int)
    stream_id = request.form.get("stream_id", type=int)
    parent_name = request.form.get("parent_name", "").strip() or None
    parent_phone = request.form.get("parent_phone", "").strip() or None
    address = request.form.get("address", "").strip() or None

    class_ = Class.query.get_or_404(class_id)
    if not all([first_name, last_name, email, password, admission_year, gender]):
        raise ValueError(
            "Student first name, last name, email, password, gender, class, and admission year are required."
        )
    if User.query.filter_by(email=email).first():
        raise ValueError("A user with that email already exists.")
    if gender not in {"male", "female"}:
        raise ValueError("Student gender must be either male or female.")

    if class_.level != Level.SECONDARY:
        stream_id = None
    elif class_.streams and stream_id is None:
        raise ValueError("Secondary students must be assigned to a stream when the class uses streams.")

    stream = Stream.query.get(stream_id) if stream_id else None
    if stream is not None and stream.class_id != class_.id:
        raise ValueError("The selected stream does not belong to the chosen class.")

    student_code = generate_student_id(admission_year)
    user = User(
        username=student_code,
        full_name=_split_name(first_name, last_name),
        email=email,
        role=Role.STUDENT,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    db.session.add(
        Student(
            user_id=user.id,
            student_code=student_code,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            class_id=class_.id,
            stream_id=stream_id,
            admission_year=admission_year,
            parent_name=parent_name,
            parent_phone=parent_phone,
            address=address,
            level=class_.level,
            is_active=True,
        )
    )


def _update_student() -> None:
    """Update one student profile and account details."""
    student = Student.query.get_or_404(request.form.get("student_id", type=int))
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    gender = request.form.get("gender", "").strip().lower()
    date_of_birth = _parse_date_field("date_of_birth")
    admission_year = request.form.get("admission_year", type=int)
    class_id = request.form.get("class_id", type=int)
    stream_id = request.form.get("stream_id", type=int)
    parent_name = request.form.get("parent_name", "").strip() or None
    parent_phone = request.form.get("parent_phone", "").strip() or None
    address = request.form.get("address", "").strip() or None

    if not all([first_name, last_name, email, gender, admission_year, class_id]):
        raise ValueError(
            "Student first name, last name, email, gender, class, and admission year are required."
        )
    if gender not in {"male", "female"}:
        raise ValueError("Student gender must be either male or female.")

    duplicate_email = User.query.filter(User.email == email, User.id != student.user_id).first()
    if duplicate_email:
        raise ValueError("Another user already uses that email address.")

    class_ = Class.query.get_or_404(class_id)
    if class_.level != Level.SECONDARY:
        stream_id = None
    elif class_.streams and stream_id is None:
        raise ValueError("Secondary students must be assigned to a stream when the class uses streams.")

    stream = Stream.query.get(stream_id) if stream_id else None
    if stream is not None and stream.class_id != class_.id:
        raise ValueError("The selected stream does not belong to the chosen class.")

    student.first_name = first_name
    student.last_name = last_name
    student.gender = gender
    student.date_of_birth = date_of_birth
    student.admission_year = admission_year
    student.class_id = class_.id
    student.stream_id = stream_id
    student.parent_name = parent_name
    student.parent_phone = parent_phone
    student.address = address
    student.level = class_.level
    student.user.email = email
    student.user.full_name = _split_name(first_name, last_name)


def _toggle_student_active() -> None:
    """Activate or deactivate one student account."""
    student = Student.query.get_or_404(request.form.get("student_id", type=int))
    student.is_active = not student.is_active
    student.user.is_active = student.is_active


def _assign_student_stream() -> None:
    """Assign or update a student's stream for secondary classes."""
    student_id = request.form.get("student_id", type=int)
    stream_id = request.form.get("stream_id", type=int)

    student = Student.query.get_or_404(student_id)
    if student.class_.level != Level.SECONDARY:
        raise ValueError("Only secondary students can be assigned to a stream.")
    stream = Stream.query.get_or_404(stream_id)
    if stream.class_id != student.class_id:
        raise ValueError("The selected stream does not belong to the student's class.")

    student.stream_id = stream.id


def _create_class() -> None:
    """Create a class for one session."""
    name = request.form.get("name", "").strip()
    level = request.form.get("level", "").strip()
    session_id = request.form.get("session_id", type=int)
    arm = request.form.get("arm", "").strip() or None
    show_position = _checkbox("show_position")
    schema_keys = request.form.get("assessment_schema_keys", "").strip()

    if not all([name, level, session_id]):
        raise ValueError("Class name, level, and session are required.")
    if level not in Level.ALL:
        raise ValueError("Invalid class level.")

    assessment_schema = _parse_assessment_schema(level, schema_keys)

    if Class.query.filter_by(session_id=session_id, name=name, arm=arm).first():
        raise ValueError("That class already exists for the selected session.")

    db.session.add(
        Class(
            name=name,
            level=level,
            session_id=session_id,
            arm=arm,
            show_position=show_position,
            is_active=True,
            assessment_schema=assessment_schema,
        )
    )


def _update_class() -> None:
    """Update one class record."""
    class_ = Class.query.get_or_404(request.form.get("class_id", type=int))
    name = request.form.get("name", "").strip()
    level = request.form.get("level", "").strip()
    session_id = request.form.get("session_id", type=int)
    arm = request.form.get("arm", "").strip() or None
    show_position = _checkbox("show_position")
    schema_keys = request.form.get("assessment_schema_keys", "").strip()

    if not all([name, level, session_id]):
        raise ValueError("Class name, level, and session are required.")
    if level not in Level.ALL:
        raise ValueError("Invalid class level.")

    if level != class_.level:
        has_linked_data = any(
            [
                class_.students.count() > 0,
                class_.results.count() > 0,
                len(class_.streams) > 0,
                class_.teacher_assignments.count() > 0,
            ]
        )
        if has_linked_data:
            raise ValueError("Class level cannot be changed after students, streams, assignments, or results exist.")

    duplicate = Class.query.filter(
        Class.session_id == session_id,
        Class.name == name,
        Class.arm == arm,
        Class.id != class_.id,
    ).first()
    if duplicate:
        raise ValueError("Another class already uses that name, arm, and session combination.")

    class_.name = name
    class_.level = level
    class_.session_id = session_id
    class_.arm = arm
    class_.show_position = show_position
    class_.assessment_schema = _parse_assessment_schema(level, schema_keys)


def _toggle_class_active() -> None:
    """Activate or deactivate one class."""
    class_ = Class.query.get_or_404(request.form.get("class_id", type=int))
    class_.is_active = not class_.is_active


def _toggle_show_position() -> None:
    """Update the show_position flag for one class."""
    class_ = Class.query.get_or_404(request.form.get("class_id", type=int))
    class_.show_position = not class_.show_position


def _create_stream() -> None:
    """Create a stream for a secondary class."""
    class_id = request.form.get("class_id", type=int)
    name = request.form.get("name", "").strip()
    class_ = Class.query.get_or_404(class_id)

    if class_.level != Level.SECONDARY:
        raise ValueError("Streams can only be created for secondary classes.")
    if name not in {"Science", "Commercial", "Arts"}:
        raise ValueError("Stream name must be Science, Commercial, or Arts.")
    if Stream.query.filter_by(class_id=class_.id, name=name).first():
        raise ValueError("That stream already exists for the selected class.")

    db.session.add(Stream(class_id=class_.id, name=name, is_active=True))


def _update_stream() -> None:
    """Update one secondary stream."""
    stream = Stream.query.get_or_404(request.form.get("stream_id", type=int))
    class_id = request.form.get("class_id", type=int)
    name = request.form.get("name", "").strip()
    class_ = Class.query.get_or_404(class_id)

    if class_.level != Level.SECONDARY:
        raise ValueError("Streams can only belong to secondary classes.")
    if name not in {"Science", "Commercial", "Arts"}:
        raise ValueError("Stream name must be Science, Commercial, or Arts.")

    if class_id != stream.class_id and any(
        [
            stream.students.count() > 0,
            stream.results.count() > 0,
            stream.teacher_assignments.count() > 0,
        ]
    ):
        raise ValueError("A stream with linked students, results, or assignments cannot be moved to another class.")

    duplicate = Stream.query.filter(
        Stream.class_id == class_.id,
        Stream.name == name,
        Stream.id != stream.id,
    ).first()
    if duplicate:
        raise ValueError("Another stream with that name already exists for the selected class.")

    stream.class_id = class_.id
    stream.name = name


def _toggle_stream_active() -> None:
    """Activate or deactivate one stream."""
    stream = Stream.query.get_or_404(request.form.get("stream_id", type=int))
    stream.is_active = not stream.is_active


def _create_subject() -> None:
    """Create a global subject."""
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Subject name is required.")
    if Subject.query.filter_by(name=name).first():
        raise ValueError("That subject already exists.")
    db.session.add(Subject(name=name, is_active=True))


def _update_subject() -> None:
    """Rename one subject."""
    subject = Subject.query.get_or_404(request.form.get("subject_id", type=int))
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Subject name is required.")

    duplicate = Subject.query.filter(Subject.name == name, Subject.id != subject.id).first()
    if duplicate:
        raise ValueError("Another subject already uses that name.")
    subject.name = name


def _toggle_subject_active() -> None:
    """Activate or deactivate one subject."""
    subject = Subject.query.get_or_404(request.form.get("subject_id", type=int))
    subject.is_active = not subject.is_active


def _assign_class_subject() -> None:
    """Assign a subject directly to a non-secondary class."""
    class_id = request.form.get("class_id", type=int)
    subject_id = request.form.get("subject_id", type=int)
    is_compulsory = _checkbox("is_compulsory")
    class_ = Class.query.get_or_404(class_id)

    if class_.level == Level.SECONDARY:
        raise ValueError("Secondary subjects should be managed per stream.")
    if ClassSubject.query.filter_by(class_id=class_id, subject_id=subject_id).first():
        raise ValueError("That subject is already assigned to the selected class.")

    db.session.add(
        ClassSubject(class_id=class_id, subject_id=subject_id, is_compulsory=is_compulsory)
    )


def _assign_stream_subject() -> None:
    """Assign a subject to one secondary stream."""
    stream_id = request.form.get("stream_id", type=int)
    subject_id = request.form.get("subject_id", type=int)
    is_compulsory = _checkbox("is_compulsory")
    stream = Stream.query.get_or_404(stream_id)

    if StreamSubject.query.filter_by(stream_id=stream.id, subject_id=subject_id).first():
        raise ValueError("That subject is already assigned to the selected stream.")

    db.session.add(
        StreamSubject(stream_id=stream.id, subject_id=subject_id, is_compulsory=is_compulsory)
    )


def _create_session() -> None:
    """Create a session and its three terms."""
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Session name is required.")
    if Session.query.filter_by(name=name).first():
        raise ValueError("That session already exists.")

    session = Session(name=name, is_active=False)
    db.session.add(session)
    db.session.flush()
    for term in Term.ALL:
        db.session.add(
            SessionTerm(
                session_id=session.id,
                term=term,
                is_result_entry_active=False,
                is_locked=False,
            )
        )


def _update_session() -> None:
    """Rename one academic session."""
    session = Session.query.get_or_404(request.form.get("session_id", type=int))
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Session name is required.")

    duplicate = Session.query.filter(Session.name == name, Session.id != session.id).first()
    if duplicate:
        raise ValueError("Another session already uses that name.")
    session.name = name


def _set_active_session() -> None:
    """Mark exactly one session as active."""
    session_id = request.form.get("session_id", type=int)
    target = Session.query.get_or_404(session_id)
    Session.query.update({Session.is_active: False})
    target.is_active = True


def _set_active_term() -> None:
    """Mark exactly one session-term as active for result entry."""
    session_term_id = request.form.get("session_term_id", type=int)
    target = SessionTerm.query.get_or_404(session_term_id)
    SessionTerm.query.update({SessionTerm.is_result_entry_active: False})
    target.is_result_entry_active = True
    target.session.is_active = True


def _toggle_global_lock() -> None:
    """Toggle the lock state for one session-term."""
    session_term = SessionTerm.query.get_or_404(request.form.get("session_term_id", type=int))
    session_term.is_locked = not session_term.is_locked


def _toggle_session_active() -> None:
    """Activate or deactivate one session record."""
    session = Session.query.get_or_404(request.form.get("session_id", type=int))
    if session.is_active:
        session.is_active = False
        for session_term in session.session_terms:
            session_term.is_result_entry_active = False
        return

    Session.query.update({Session.is_active: False})
    SessionTerm.query.update({SessionTerm.is_result_entry_active: False})
    session.is_active = True


def _toggle_teacher_result_upload() -> None:
    """Flip the global teacher upload permission."""
    settings = _system_settings()
    settings.allow_teacher_result_upload = not settings.allow_teacher_result_upload


def _toggle_class_lock() -> None:
    """Lock or unlock all results for one class and session-term."""
    class_id = request.form.get("class_id", type=int)
    session_id = request.form.get("session_id", type=int)
    term = request.form.get("term", "").strip()
    lock_action = request.form.get("lock_action", "").strip()

    if not all([class_id, session_id, term]):
        raise ValueError("Class, session, and term are required for class result control.")

    results = Result.query.filter_by(
        class_id=class_id,
        session_id=session_id,
        term=term,
    ).all()
    if not results:
        raise ValueError("No results exist for that class and session-term.")

    if lock_action == "lock":
        for result in results:
            result.result_status = ResultStatus.LOCKED
    elif lock_action == "unlock":
        for result in results:
            result.result_status = ResultStatus.DRAFT
    else:
        raise ValueError("Invalid class result control action.")


def _override_result() -> None:
    """Allow admin to edit and override one result row."""
    result = Result.query.get_or_404(request.form.get("result_id", type=int))
    target_status = request.form.get("result_status", "").strip()
    override_reason = request.form.get("override_reason", "").strip()

    if not override_reason:
        raise ValueError("Admin overrides require an override reason.")
    if target_status not in ResultStatus.ALL:
        raise ValueError("Invalid result status selected.")

    result.is_offered = _checkbox("is_offered")
    result.remark = request.form.get("remark", "").strip() or None
    result.override_reason = override_reason
    result.overridden_by_user_id = current_user.id
    result.overridden_at = datetime.now(timezone.utc)

    if result.mode == ResultMode.ASSESSMENT:
        class_ = result.class_
        if (
            class_ is None
            or class_.level not in (Level.KINDERGARTEN, Level.NURSERY)
            or not class_.assessment_schema
        ):
            raise ValueError("Nursery assessment overrides require a valid class schema.")

        assessment_json = {}
        for key in class_.assessment_schema.keys():
            field_name = f"assessment__{key}"
            value = request.form.get(field_name, "").strip()
            if result.is_offered and value == "":
                raise ValueError(f"{key.replace('_', ' ').title()} is required when the subject is offered.")
            if class_.assessment_schema[key] == "integer" and value != "":
                try:
                    assessment_json[key] = int(value)
                except ValueError as exc:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be a whole number.") from exc
            else:
                assessment_json[key] = value or None

        result.assessment_json = assessment_json
        result.ca_score = None
        result.exam_score = None
        result.total_score = None
        result.grade = None
    else:
        if result.is_offered:
            ca_score = request.form.get("ca_score", "").strip()
            exam_score = request.form.get("exam_score", "").strip()
            if ca_score == "" or exam_score == "":
                raise ValueError("CA and exam scores are required when a result is offered.")
            result.ca_score = float(ca_score)
            result.exam_score = float(exam_score)
        else:
            result.ca_score = None
            result.exam_score = None
        result.assessment_json = None

    result.result_status = target_status
    if not result.can_transition_to(target_status, current_user.role):
        raise ValueError("That result status transition is not allowed.")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    """Admin summary dashboard."""
    summary = {
        "teachers": Teacher.query.count(),
        "students": Student.query.count(),
        "classes": Class.query.count(),
        "streams": Stream.query.count(),
        "subjects": Subject.query.count(),
        "results": Result.query.count(),
    }
    return render_template(
        "admin/dashboard.html",
        summary=summary,
        active_session_term=_active_session_term(),
    )


@admin_bp.route("/teachers", methods=["GET", "POST"])
@login_required
@role_required("admin")
def teachers():
    """Manage teachers and teacher assignment scope."""
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "create_teacher":
                _create_teacher()
                message = "Teacher created successfully."
            elif action == "update_teacher":
                _update_teacher()
                message = "Teacher updated successfully."
            elif action == "toggle_teacher_active":
                _toggle_teacher_active()
                message = "Teacher account status updated."
            elif action == "assign_teacher":
                _assign_teacher()
                message = "Teacher assignment saved."
            else:
                raise ValueError("Unsupported teacher action.")
            db.session.commit()
            flash(message, "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.teachers"))

    return render_template(
        "admin/teachers.html",
        action_form=ActionForm(),
        teachers=Teacher.query.order_by(Teacher.first_name.asc(), Teacher.last_name.asc()).all(),
        classes=_class_options(),
        assignments_by_teacher=_teacher_assignments_map(),
    )


@admin_bp.route("/students", methods=["GET", "POST"])
@login_required
@role_required("admin")
def students():
    """Manage students and secondary stream placement."""
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "create_student":
                _create_student()
                message = "Student created successfully."
            elif action == "update_student":
                _update_student()
                message = "Student updated successfully."
            elif action == "toggle_student_active":
                _toggle_student_active()
                message = "Student account status updated."
            elif action == "assign_student_stream":
                _assign_student_stream()
                message = "Student stream assignment updated."
            else:
                raise ValueError("Unsupported student action.")
            db.session.commit()
            flash(message, "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.students"))

    return render_template(
        "admin/students.html",
        action_form=ActionForm(),
        students=Student.query.order_by(Student.first_name.asc(), Student.last_name.asc()).all(),
        classes=_class_options(),
        streams=_stream_options(),
    )


@admin_bp.route("/classes", methods=["GET", "POST"])
@login_required
@role_required("admin")
def classes():
    """Manage classes, streams, subjects, and subject assignments."""
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "create_class":
                _create_class()
                message = "Class created successfully."
            elif action == "update_class":
                _update_class()
                message = "Class updated successfully."
            elif action == "toggle_class_active":
                _toggle_class_active()
                message = "Class status updated."
            elif action == "toggle_show_position":
                _toggle_show_position()
                message = "Class position visibility updated."
            elif action == "create_stream":
                _create_stream()
                message = "Stream created successfully."
            elif action == "update_stream":
                _update_stream()
                message = "Stream updated successfully."
            elif action == "toggle_stream_active":
                _toggle_stream_active()
                message = "Stream status updated."
            elif action == "create_subject":
                _create_subject()
                message = "Subject created successfully."
            elif action == "update_subject":
                _update_subject()
                message = "Subject updated successfully."
            elif action == "toggle_subject_active":
                _toggle_subject_active()
                message = "Subject status updated."
            elif action == "assign_class_subject":
                _assign_class_subject()
                message = "Subject assigned to class."
            elif action == "assign_stream_subject":
                _assign_stream_subject()
                message = "Subject assigned to stream."
            else:
                raise ValueError("Unsupported class action.")
            db.session.commit()
            flash(message, "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.classes"))

    class_list = Class.query.order_by(Class.name.asc()).all()
    return render_template(
        "admin/classes.html",
        action_form=ActionForm(),
        classes=class_list,
        sessions=_session_options(),
        streams=_stream_options(),
        subjects=_subject_options(),
        class_subjects_map=_class_subjects_map(),
        stream_subjects_map=_stream_subjects_map(),
    )


@admin_bp.route("/sessions", methods=["GET", "POST"])
@login_required
@role_required("admin")
def sessions():
    """Manage sessions, active result period, and global locking."""
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "create_session":
                _create_session()
                message = "Session created successfully."
            elif action == "update_session":
                _update_session()
                message = "Session updated successfully."
            elif action == "toggle_session_active":
                _toggle_session_active()
                message = "Session status updated."
            elif action == "set_active_session":
                _set_active_session()
                message = "Active session updated."
            elif action == "set_active_term":
                _set_active_term()
                message = "Active session-term updated."
            elif action == "toggle_global_lock":
                _toggle_global_lock()
                message = "Session-term lock state updated."
            elif action == "toggle_teacher_result_upload":
                _toggle_teacher_result_upload()
                message = "Teacher result upload setting updated."
            else:
                raise ValueError("Unsupported session action.")
            db.session.commit()
            flash(message, "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.sessions"))

    sessions = _session_options()
    return render_template(
        "admin/sessions.html",
        action_form=ActionForm(),
        sessions=sessions,
        settings=_system_settings(),
        session_terms_by_session={
            session.id: session.session_terms.order_by(SessionTerm.term.asc()).all()
            for session in sessions
        },
    )


@admin_bp.route("/results", methods=["GET", "POST"])
@login_required
@role_required("admin")
def results():
    """View, override, lock, and rank results across the system."""
    csv_form = CSVUploadForm()
    if request.method == "POST":
        action = request.form.get("action", "")
        selected_class = Class.query.get(request.form.get("class_id", type=int))
        selected_stream = Stream.query.get(request.form.get("stream_id", type=int)) if request.form.get("stream_id", type=int) else None
        selected_session = Session.query.get(request.form.get("session_id", type=int)) if request.form.get("session_id", type=int) else None
        selected_term = request.form.get("term") or None
        selected_subject = _selected_subject(
            selected_class,
            selected_stream,
            request.form.get("subject_id", type=int),
        )
        try:
            if action == "toggle_class_lock":
                _toggle_class_lock()
                message = "Class result lock state updated."
            elif action == "override_result":
                _override_result()
                message = "Result override saved."
            elif action in {"save_admin_results", "submit_admin_results"}:
                _save_admin_manual_results(
                    selected_class,
                    selected_stream,
                    selected_subject,
                    selected_session,
                    selected_term,
                )
                message = "Admin result sheet saved."
            elif action in {"save_admin_csv", "submit_admin_csv"}:
                if not csv_form.validate_on_submit():
                    raise ValueError("A CSV file is required for bulk upload.")
                _save_admin_csv_results(
                    selected_class,
                    selected_stream,
                    selected_subject,
                    selected_session,
                    selected_term,
                    csv_form,
                )
                message = "Admin CSV upload saved."
            elif action == "recalculate_positions":
                message = "Positions recalculated from the current class result totals."
            else:
                raise ValueError("Unsupported result action.")
            db.session.commit()
            flash(message, "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(
            url_for(
                "admin.results",
                class_id=request.form.get("class_id", type=int),
                stream_id=request.form.get("stream_id", type=int),
                session_id=request.form.get("session_id", type=int),
                term=request.form.get("term"),
                subject_id=request.form.get("subject_id", type=int),
            )
        )

    selected_class_id = request.args.get("class_id", type=int)
    selected_stream_id = request.args.get("stream_id", type=int)
    selected_session_id = request.args.get("session_id", type=int)
    selected_subject_id = request.args.get("subject_id", type=int)
    selected_class = Class.query.get(selected_class_id) if selected_class_id else None
    selected_stream = Stream.query.get(selected_stream_id) if selected_stream_id else None
    selected_session = Session.query.get(selected_session_id) if selected_session_id else None
    selected_term = request.args.get("term", type=str) or None
    available_streams = (
        _stream_options(selected_class.id)
        if selected_class and selected_class.level == Level.SECONDARY
        else []
    )
    available_subjects = _result_scope_subjects(selected_class, selected_stream)
    selected_subject = _selected_subject(selected_class, selected_stream, selected_subject_id)
    scoped_students = _result_scope_students(selected_class, selected_stream)
    existing_results = _result_sheet_lookup(
        selected_class,
        selected_stream,
        selected_subject,
        selected_session.id if selected_session else None,
        selected_term,
    )
    selected_session_term = _selected_session_term(
        selected_session.id if selected_session else None,
        selected_term,
    )

    results_query = _student_results_query(
        selected_class.id if selected_class else None,
        selected_stream.id if selected_stream else None,
        selected_session.id if selected_session else None,
        selected_term,
    )
    result_rows = results_query.all() if selected_class and selected_session and selected_term else []
    assessment_schema_items = _assessment_schema_items(selected_class)
    position_boards = _position_boards(
        selected_class,
        selected_session.id if selected_session else None,
        selected_term,
    )
    subject_position_board = _subject_position_board(
        selected_class,
        selected_stream,
        selected_subject,
        selected_session.id if selected_session else None,
        selected_term,
    )

    return render_template(
        "admin/results.html",
        action_form=ActionForm(),
        csv_form=csv_form,
        classes=_class_options(),
        sessions=_session_options(),
        terms=Term.ALL,
        selected_class=selected_class,
        selected_stream=selected_stream,
        selected_session=selected_session,
        selected_term=selected_term,
        selected_subject=selected_subject,
        selected_session_term=selected_session_term,
        available_streams=available_streams,
        available_subjects=available_subjects,
        students=scoped_students,
        existing_results=existing_results,
        results=result_rows,
        assessment_schema_items=assessment_schema_items,
        position_boards=position_boards,
        subject_position_board=subject_position_board,
    )

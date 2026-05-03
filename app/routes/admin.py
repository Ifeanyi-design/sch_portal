"""Admin blueprint for academic setup and result control."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.teacher_forms import ActionForm
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
from app.models.teacher import Teacher
from app.models.user import Role, User
from app.utils.decorators import role_required
from app.utils.helpers import build_position_rows, generate_student_id

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def _checkbox(name: str) -> bool:
    """Return True when a checkbox-style field is enabled."""
    return request.form.get(name) in {"on", "true", "1", "yes"}


def _split_name(first_name: str, last_name: str) -> str:
    """Return a normalized full name string."""
    return f"{first_name.strip()} {last_name.strip()}".strip()


def _parse_assessment_schema(level: str, raw_keys: str) -> dict | None:
    """Return a normalized assessment schema payload for nursery classes."""
    if level != Level.NURSERY:
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
    if class_ is None or class_.level != Level.NURSERY or not class_.assessment_schema:
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
    if selected_class.level == Level.NURSERY:
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
    if not streams:
        student_map = {}
        for result in base_results:
            student_map.setdefault(result.student, []).append(result)
        boards.append(
            {
                "label": f"{selected_class.name} Ranking",
                "scope": "class",
                "rows": build_position_rows(student_map),
            }
        )
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
    """Assign a teacher to a class or class-stream scope."""
    teacher_id = request.form.get("teacher_id", type=int)
    class_id = request.form.get("class_id", type=int)
    stream_id = request.form.get("stream_id", type=int)

    teacher = Teacher.query.get_or_404(teacher_id)
    class_ = Class.query.get_or_404(class_id)
    stream = Stream.query.get(stream_id) if stream_id else None

    if class_.level != Level.SECONDARY:
        stream = None
        stream_id = None
    elif stream_id and (stream is None or stream.class_id != class_.id):
        raise ValueError("The selected stream does not belong to the chosen class.")

    existing = ClassTeacherMap.query.filter_by(
        teacher_id=teacher.id,
        class_id=class_.id,
        stream_id=stream_id,
    ).first()
    if existing:
        raise ValueError("That teacher assignment already exists.")

    db.session.add(
        ClassTeacherMap(
            teacher_id=teacher.id,
            class_id=class_.id,
            stream_id=stream_id,
        )
    )


def _create_student() -> None:
    """Create a student user and profile."""
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    admission_year = request.form.get("admission_year", type=int)
    class_id = request.form.get("class_id", type=int)
    stream_id = request.form.get("stream_id", type=int)

    class_ = Class.query.get_or_404(class_id)
    if not all([first_name, last_name, email, password, admission_year]):
        raise ValueError("Student first name, last name, email, password, class, and admission year are required.")
    if User.query.filter_by(email=email).first():
        raise ValueError("A user with that email already exists.")

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
            class_id=class_.id,
            stream_id=stream_id,
            admission_year=admission_year,
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
    admission_year = request.form.get("admission_year", type=int)
    class_id = request.form.get("class_id", type=int)
    stream_id = request.form.get("stream_id", type=int)

    if not all([first_name, last_name, email, admission_year, class_id]):
        raise ValueError("Student first name, last name, email, class, and admission year are required.")

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
    student.admission_year = admission_year
    student.class_id = class_.id
    student.stream_id = stream_id
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
        if class_ is None or class_.level != Level.NURSERY or not class_.assessment_schema:
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
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "toggle_class_lock":
                _toggle_class_lock()
                message = "Class result lock state updated."
            elif action == "override_result":
                _override_result()
                message = "Result override saved."
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
            )
        )

    selected_class_id = request.args.get("class_id", type=int)
    selected_stream_id = request.args.get("stream_id", type=int)
    selected_session_id = request.args.get("session_id", type=int)
    selected_class = Class.query.get(selected_class_id) if selected_class_id else None
    selected_stream = Stream.query.get(selected_stream_id) if selected_stream_id else None
    selected_session = Session.query.get(selected_session_id) if selected_session_id else None
    selected_term = request.args.get("term", type=str) or None
    available_streams = _stream_options(selected_class.id) if selected_class else []

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

    return render_template(
        "admin/results.html",
        action_form=ActionForm(),
        classes=_class_options(),
        sessions=_session_options(),
        terms=Term.ALL,
        selected_class=selected_class,
        selected_stream=selected_stream,
        selected_session=selected_session,
        selected_term=selected_term,
        available_streams=available_streams,
        results=result_rows,
        assessment_schema_items=assessment_schema_items,
        position_boards=position_boards,
    )

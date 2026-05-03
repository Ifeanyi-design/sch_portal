"""Seed the SAMS development database with starter data."""

from app import create_app
from app.extensions import db
from app.models.class_ import Class, Level
from app.models.class_subject import ClassSubject
from app.models.class_teacher import ClassTeacherMap
from app.models.session_ import Session
from app.models.session_term import SessionTerm, Term
from app.models.stream import Stream
from app.models.stream_subject import StreamSubject
from app.models.student import Student
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.user import Role, User


def get_or_create(model, defaults=None, **filters):
    """Return an existing row or create a new one with the supplied defaults."""
    instance = model.query.filter_by(**filters).first()
    if instance:
        return instance, False

    params = dict(filters)
    if defaults:
        params.update(defaults)

    instance = model(**params)
    db.session.add(instance)
    return instance, True


def ensure_password(user: User, password: str) -> None:
    """Set the initial password only when the user has no stored hash yet."""
    if not user.password_hash:
        user.set_password(password)


def seed_users():
    """Create initial admin, teacher, and student user accounts."""
    users = {}

    definitions = [
        {
            "username": "admin",
            "full_name": "System Administrator",
            "email": "admin@sams.local",
            "role": Role.ADMIN,
            "password": "Admin@12345",
        },
        {
            "username": "grace.adeyemi",
            "full_name": "Grace Adeyemi",
            "email": "grace.adeyemi@sams.local",
            "role": Role.TEACHER,
            "password": "Teacher@123",
        },
        {
            "username": "samuel.okoro",
            "full_name": "Samuel Okoro",
            "email": "samuel.okoro@sams.local",
            "role": Role.TEACHER,
            "password": "Teacher@123",
        },
        {
            "username": "miriam.odu",
            "full_name": "Miriam Odu",
            "email": "miriam.odu@sams.local",
            "role": Role.TEACHER,
            "password": "Teacher@123",
        },
        {
            "username": "STU-2025-0001",
            "full_name": "Ifeoma Nnaji",
            "email": "ifeoma.nnaji@sams.local",
            "role": Role.STUDENT,
            "password": "Student@123",
        },
        {
            "username": "STU-2025-0002",
            "full_name": "Daniel Adebayo",
            "email": "daniel.adebayo@sams.local",
            "role": Role.STUDENT,
            "password": "Student@123",
        },
        {
            "username": "STU-2025-0003",
            "full_name": "Amaka Okafor",
            "email": "amaka.okafor@sams.local",
            "role": Role.STUDENT,
            "password": "Student@123",
        },
    ]

    for data in definitions:
        password = data.pop("password")
        user, _ = get_or_create(User, **data)
        ensure_password(user, password)
        users[user.username] = user

    db.session.flush()
    return users


def seed_sessions():
    """Create the active academic session and its terms."""
    session, _ = get_or_create(Session, name="2025/2026", defaults={"is_active": True})
    session.is_active = True
    db.session.flush()

    session_terms = {}
    for term in Term.ALL:
        session_term, _ = get_or_create(
            SessionTerm,
            session_id=session.id,
            term=term,
            defaults={
                "is_result_entry_active": term == Term.FIRST,
                "is_locked": False,
            },
        )
        session_term.is_result_entry_active = term == Term.FIRST
        session_term.is_locked = False
        session_terms[term] = session_term

    db.session.flush()
    return session, session_terms


def seed_classes(session: Session):
    """Create one nursery, one primary, and one secondary class."""
    nursery, _ = get_or_create(
        Class,
        session_id=session.id,
        name="Nursery 1",
        arm=None,
        defaults={
            "level": Level.NURSERY,
            "show_position": False,
            "is_active": True,
            "assessment_schema": {
                "behavior": "rating",
                "attendance": "integer",
                "participation": "rating",
                "teacher_comment": "text",
            },
        },
    )
    primary, _ = get_or_create(
        Class,
        session_id=session.id,
        name="Primary 1",
        arm=None,
        defaults={
            "level": Level.PRIMARY,
            "show_position": True,
            "is_active": True,
            "assessment_schema": None,
        },
    )
    secondary, _ = get_or_create(
        Class,
        session_id=session.id,
        name="SS1",
        arm=None,
        defaults={
            "level": Level.SECONDARY,
            "show_position": True,
            "is_active": True,
            "assessment_schema": None,
        },
    )

    db.session.flush()
    return nursery, primary, secondary


def seed_streams(secondary_class: Class):
    """Create the supported secondary streams for the demo class."""
    streams = {}
    for name in ("Science", "Commercial", "Arts"):
        stream, _ = get_or_create(
            Stream,
            class_id=secondary_class.id,
            name=name,
            defaults={"is_active": True},
        )
        streams[name] = stream

    db.session.flush()
    return streams


def seed_subjects():
    """Create reusable subjects used across classes and streams."""
    subject_names = [
        "Numbers",
        "Rhymes",
        "English Language",
        "Mathematics",
        "Basic Science",
        "Civic Education",
        "Physics",
        "Chemistry",
        "Biology",
        "Economics",
        "Commerce",
        "Financial Accounting",
        "Literature in English",
        "Government",
        "CRS",
    ]

    subjects = {}
    for name in subject_names:
        subject, _ = get_or_create(Subject, name=name, defaults={"is_active": True})
        subjects[name] = subject

    db.session.flush()
    return subjects


def seed_subject_assignments(nursery: Class, primary: Class, streams: dict, subjects: dict):
    """Assign subjects to nursery/primary classes and secondary streams."""
    nursery_subjects = ("Numbers", "Rhymes")
    for name in nursery_subjects:
        get_or_create(
            ClassSubject,
            class_id=nursery.id,
            subject_id=subjects[name].id,
            defaults={"is_compulsory": True},
        )

    primary_subjects = (
        "English Language",
        "Mathematics",
        "Basic Science",
        "Civic Education",
    )
    for name in primary_subjects:
        get_or_create(
            ClassSubject,
            class_id=primary.id,
            subject_id=subjects[name].id,
            defaults={"is_compulsory": True},
        )

    stream_subject_map = {
        "Science": (
            ("English Language", True),
            ("Mathematics", True),
            ("Physics", True),
            ("Chemistry", True),
            ("Biology", True),
        ),
        "Commercial": (
            ("English Language", True),
            ("Mathematics", True),
            ("Economics", True),
            ("Commerce", True),
            ("Financial Accounting", True),
        ),
        "Arts": (
            ("English Language", True),
            ("Mathematics", True),
            ("Literature in English", True),
            ("Government", True),
            ("CRS", False),
        ),
    }

    for stream_name, assignments in stream_subject_map.items():
        stream = streams[stream_name]
        for subject_name, is_compulsory in assignments:
            get_or_create(
                StreamSubject,
                stream_id=stream.id,
                subject_id=subjects[subject_name].id,
                defaults={"is_compulsory": is_compulsory},
            )

    db.session.flush()


def seed_staff(users: dict):
    """Create teacher profile records."""
    teachers = {}
    teacher_definitions = [
        ("grace.adeyemi", "Grace", "Adeyemi", "TCH-001", "08030000001"),
        ("samuel.okoro", "Samuel", "Okoro", "TCH-002", "08030000002"),
        ("miriam.odu", "Miriam", "Odu", "TCH-003", "08030000003"),
    ]

    for username, first_name, last_name, staff_id, phone in teacher_definitions:
        teacher, _ = get_or_create(
            Teacher,
            user_id=users[username].id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "staff_id": staff_id,
                "phone": phone,
                "is_active": True,
            },
        )
        teachers[username] = teacher

    db.session.flush()
    return teachers


def seed_teacher_assignments(primary: Class, secondary: Class, streams: dict, teachers: dict):
    """Assign teachers to their allowed class or class-stream scope."""
    get_or_create(
        ClassTeacherMap,
        class_id=primary.id,
        teacher_id=teachers["grace.adeyemi"].id,
        stream_id=None,
    )
    get_or_create(
        ClassTeacherMap,
        class_id=secondary.id,
        teacher_id=teachers["samuel.okoro"].id,
        stream_id=streams["Science"].id,
    )
    get_or_create(
        ClassTeacherMap,
        class_id=secondary.id,
        teacher_id=teachers["miriam.odu"].id,
        stream_id=streams["Arts"].id,
    )

    db.session.flush()


def seed_students(users: dict, nursery: Class, primary: Class, secondary: Class, streams: dict):
    """Create sample students across the supported levels."""
    student_definitions = [
        {
            "username": "STU-2025-0001",
            "student_code": "STU-2025-0001",
            "first_name": "Ifeoma",
            "last_name": "Nnaji",
            "class_id": nursery.id,
            "stream_id": None,
            "admission_year": 2025,
            "level": Level.NURSERY,
        },
        {
            "username": "STU-2025-0002",
            "student_code": "STU-2025-0002",
            "first_name": "Daniel",
            "last_name": "Adebayo",
            "class_id": primary.id,
            "stream_id": None,
            "admission_year": 2025,
            "level": Level.PRIMARY,
        },
        {
            "username": "STU-2025-0003",
            "student_code": "STU-2025-0003",
            "first_name": "Amaka",
            "last_name": "Okafor",
            "class_id": secondary.id,
            "stream_id": streams["Science"].id,
            "admission_year": 2025,
            "level": Level.SECONDARY,
        },
    ]

    for data in student_definitions:
        username = data.pop("username")
        get_or_create(Student, user_id=users[username].id, defaults=data)

    db.session.flush()


def main():
    """Populate the development database with starter records."""
    app = create_app("development")

    with app.app_context():
        users = seed_users()
        session, _ = seed_sessions()
        nursery, primary, secondary = seed_classes(session)
        streams = seed_streams(secondary)
        subjects = seed_subjects()
        seed_subject_assignments(nursery, primary, streams, subjects)
        teachers = seed_staff(users)
        seed_teacher_assignments(primary, secondary, streams, teachers)
        seed_students(users, nursery, primary, secondary, streams)
        db.session.commit()

        print("Seed complete.")
        print("Admin login: admin / Admin@12345")
        print("Teacher login: grace.adeyemi / Teacher@123")
        print("Student login: STU-2025-0002 / Student@123")


if __name__ == "__main__":
    main()

"""Reset and seed the SAMS development database with full demo data."""

from __future__ import annotations

from app import create_app
from app.extensions import db
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

ASSESSMENT_SCHEMA = {
    "participation": "rating",
    "skill_level": "rating",
    "observation": "text",
}

ASSESSMENT_RATINGS = [
    "Outstanding",
    "Very Good",
    "Good",
    "Developing",
    "Needs Support",
]

NURSERY_SUBJECTS = [
    "Number Work",
    "Letter Work",
    "Writing Patterns",
    "Rhymes and Songs",
    "Social Habits",
    "Health Habits",
    "Creative Arts",
    "Bible Knowledge",
    "Computer Studies",
]

PRIMARY_SUBJECTS = [
    "English Language",
    "Mathematics",
    "Basic Science",
    "Social Studies",
    "Civic Education",
    "Verbal Reasoning",
    "Quantitative Reasoning",
    "Agricultural Science",
    "Computer Studies",
    "Creative Arts",
    "CRS",
    "Handwriting",
]

JSS_SUBJECTS = [
    "English Studies",
    "Mathematics",
    "Basic Science",
    "Basic Technology",
    "Social Studies",
    "Civic Education",
    "Cultural and Creative Arts",
    "Computer Studies",
    "Agricultural Science",
    "Business Studies",
    "Physical and Health Education",
    "CRS",
]

SSS_COMMON_SUBJECTS = [
    "English Language",
    "Mathematics",
    "Civic Education",
    "Computer Studies",
]

SSS_STREAM_SUBJECTS = {
    "Science": [
        ("Physics", True),
        ("Chemistry", True),
        ("Biology", True),
        ("Further Mathematics", False),
    ],
    "Commercial": [
        ("Economics", True),
        ("Commerce", True),
        ("Financial Accounting", True),
        ("Marketing", False),
    ],
    "Arts": [
        ("Literature in English", True),
        ("Government", True),
        ("CRS", True),
        ("History", False),
    ],
}

TEACHER_DEFINITIONS = [
    ("grace.adeyemi", "Grace", "Adeyemi", "TCH-001", "08030000001"),
    ("samuel.okoro", "Samuel", "Okoro", "TCH-002", "08030000002"),
    ("miriam.odu", "Miriam", "Odu", "TCH-003", "08030000003"),
    ("yetunde.balogun", "Yetunde", "Balogun", "TCH-004", "08030000004"),
    ("chinedu.obi", "Chinedu", "Obi", "TCH-005", "08030000005"),
    ("halima.bello", "Halima", "Bello", "TCH-006", "08030000006"),
    ("tunde.alabi", "Tunde", "Alabi", "TCH-007", "08030000007"),
    ("esther.uko", "Esther", "Uko", "TCH-008", "08030000008"),
    ("taiwo.shittu", "Taiwo", "Shittu", "TCH-009", "08030000009"),
    ("ibrahim.musa", "Ibrahim", "Musa", "TCH-010", "08030000010"),
    ("funke.adeola", "Funke", "Adeola", "TCH-011", "08030000011"),
    ("chinenye.eze", "Chinenye", "Eze", "TCH-012", "08030000012"),
    ("patrick.james", "Patrick", "James", "TCH-013", "08030000013"),
    ("amina.sule", "Amina", "Sule", "TCH-014", "08030000014"),
    ("bola.adesina", "Bola", "Adesina", "TCH-015", "08030000015"),
    ("lilian.okafor", "Lilian", "Okafor", "TCH-016", "08030000016"),
    ("isaac.edet", "Isaac", "Edet", "TCH-017", "08030000017"),
    ("kemi.folarin", "Kemi", "Folarin", "TCH-018", "08030000018"),
    ("ugochi.madu", "Ugochi", "Madu", "TCH-019", "08030000019"),
]

FIRST_NAMES = [
    "Ifeoma", "Daniel", "Amaka", "Zainab", "Tobi", "Favour", "Emeka", "Bolanle",
    "Chisom", "Aisha", "Michael", "Eniola", "Somto", "Deborah", "David", "Kelechi",
    "Hauwa", "Morenike", "Olamide", "Precious", "Wisdom", "Adaobi", "Ridwan", "Janet",
    "Chukwudi", "Ayomide", "Ngozi", "Farouk", "Blessing", "Temiloluwa", "Sade", "Ogechi",
    "Gbenga", "Ruth", "Nkem", "Ibrahim", "Khadijah", "Oluwaseun", "Chiamaka", "Tochukwu",
    "Abigail", "Joseph", "Peace", "Uche", "Maryam", "Victory", "Ayo", "Anita",
    "Philip", "Damilola", "Ese", "Nnaemeka", "Mubarak", "Nifemi", "Tomisin", "Chioma",
]

LAST_NAMES = [
    "Nnaji", "Adebayo", "Okafor", "Bello", "Ogunleye", "Eze", "Okoro", "Adeyemi",
    "Balogun", "Musa", "Udo", "Alabi", "Shittu", "Afolayan", "Onoh", "Yakubu",
    "Lawal", "Ibrahim", "Nwachukwu", "Ogundele", "Edet", "Okechukwu", "Folarin", "Akinsanya",
]


def create_user(username: str, full_name: str, email: str, role: str, password: str) -> User:
    """Create one auth user with a hashed password."""
    user = User(
        username=username,
        full_name=full_name,
        email=email,
        role=role,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def build_score_components(student_index: int, subject_index: int) -> tuple[float, float]:
    """Return deterministic CA and exam values inside the allowed range."""
    ca_score = 18 + ((student_index * 3 + subject_index * 2) % 20)
    exam_score = 28 + ((student_index * 4 + subject_index * 5) % 31)
    return round(float(ca_score), 2), round(float(exam_score), 2)


def build_assessment_payload(student_index: int, subject_index: int) -> dict:
    """Return deterministic nursery assessment values."""
    rating_a = ASSESSMENT_RATINGS[(student_index + subject_index) % len(ASSESSMENT_RATINGS)]
    rating_b = ASSESSMENT_RATINGS[(student_index + subject_index + 2) % len(ASSESSMENT_RATINGS)]
    observation = [
        "Shows growing confidence during guided activities.",
        "Responds well to classroom routines and support.",
        "Demonstrates steady progress in practical tasks.",
        "Participates actively and enjoys group work.",
        "Needs a little more support to stay focused.",
    ][(student_index + subject_index) % 5]

    return {
        "participation": rating_a,
        "skill_level": rating_b,
        "observation": observation,
    }


def seed_sessions() -> tuple[Session, dict[str, SessionTerm]]:
    """Create the active session and its three terms."""
    session = Session(name="2025/2026", is_active=True)
    db.session.add(session)
    db.session.flush()

    session_terms = {}
    for term in Term.ALL:
        session_term = SessionTerm(
            session_id=session.id,
            term=term,
            is_result_entry_active=(term == Term.FIRST),
            is_locked=False,
        )
        db.session.add(session_term)
        session_terms[term] = session_term

    db.session.flush()
    return session, session_terms


def seed_classes(session: Session) -> dict[str, Class]:
    """Create KG, Nursery, Primary, JSS, and SSS classes."""
    class_specs = [
        ("KG 1", Level.NURSERY),
        ("KG 2", Level.NURSERY),
        ("Nursery 1", Level.NURSERY),
        ("Nursery 2", Level.NURSERY),
        ("Primary 1", Level.PRIMARY),
        ("Primary 2", Level.PRIMARY),
        ("Primary 3", Level.PRIMARY),
        ("Primary 4", Level.PRIMARY),
        ("Primary 5", Level.PRIMARY),
        ("Primary 6", Level.PRIMARY),
        ("JSS 1", Level.SECONDARY),
        ("JSS 2", Level.SECONDARY),
        ("JSS 3", Level.SECONDARY),
        ("SSS 1", Level.SECONDARY),
        ("SSS 2", Level.SECONDARY),
        ("SSS 3", Level.SECONDARY),
    ]

    classes = {}
    for name, level in class_specs:
        class_ = Class(
            name=name,
            level=level,
            session_id=session.id,
            arm=None,
            show_position=(level != Level.NURSERY),
            is_active=True,
            assessment_schema=ASSESSMENT_SCHEMA if level == Level.NURSERY else None,
        )
        db.session.add(class_)
        classes[name] = class_

    db.session.flush()
    return classes


def seed_streams(classes: dict[str, Class]) -> dict[str, Stream]:
    """Create Science, Commercial, and Arts streams for SSS classes."""
    streams = {}
    for class_name in ("SSS 1", "SSS 2", "SSS 3"):
        for stream_name in ("Science", "Commercial", "Arts"):
            stream = Stream(
                class_id=classes[class_name].id,
                name=stream_name,
                is_active=True,
            )
            db.session.add(stream)
            streams[f"{class_name}:{stream_name}"] = stream

    db.session.flush()
    return streams


def seed_subjects() -> dict[str, Subject]:
    """Create all reusable subjects referenced by the demo classes."""
    subject_names = sorted(
        set(
            NURSERY_SUBJECTS
            + PRIMARY_SUBJECTS
            + JSS_SUBJECTS
            + SSS_COMMON_SUBJECTS
            + [name for assignments in SSS_STREAM_SUBJECTS.values() for name, _ in assignments]
        )
    )

    subjects = {}
    for name in subject_names:
        subject = Subject(name=name, is_active=True)
        db.session.add(subject)
        subjects[name] = subject

    db.session.flush()
    return subjects


def seed_subject_assignments(classes: dict[str, Class], streams: dict[str, Stream], subjects: dict[str, Subject]) -> None:
    """Attach subjects to classes and streams."""
    for class_name in ("KG 1", "KG 2", "Nursery 1", "Nursery 2"):
        for subject_name in NURSERY_SUBJECTS:
            db.session.add(
                ClassSubject(
                    class_id=classes[class_name].id,
                    subject_id=subjects[subject_name].id,
                    is_compulsory=True,
                )
            )

    for class_name in ("Primary 1", "Primary 2", "Primary 3", "Primary 4", "Primary 5", "Primary 6"):
        for subject_name in PRIMARY_SUBJECTS:
            db.session.add(
                ClassSubject(
                    class_id=classes[class_name].id,
                    subject_id=subjects[subject_name].id,
                    is_compulsory=True,
                )
            )

    for class_name in ("JSS 1", "JSS 2", "JSS 3"):
        for subject_name in JSS_SUBJECTS:
            db.session.add(
                ClassSubject(
                    class_id=classes[class_name].id,
                    subject_id=subjects[subject_name].id,
                    is_compulsory=True,
                )
            )

    for class_name in ("SSS 1", "SSS 2", "SSS 3"):
        for stream_name, assignments in SSS_STREAM_SUBJECTS.items():
            stream = streams[f"{class_name}:{stream_name}"]
            for subject_name in SSS_COMMON_SUBJECTS:
                db.session.add(
                    StreamSubject(
                        stream_id=stream.id,
                        subject_id=subjects[subject_name].id,
                        is_compulsory=True,
                    )
                )
            for subject_name, is_compulsory in assignments:
                db.session.add(
                    StreamSubject(
                        stream_id=stream.id,
                        subject_id=subjects[subject_name].id,
                        is_compulsory=is_compulsory,
                    )
                )

    db.session.flush()


def seed_teachers(classes: dict[str, Class], streams: dict[str, Stream]) -> dict[str, Teacher]:
    """Create teacher users, profiles, and assignments."""
    teachers = {}
    for username, first_name, last_name, staff_id, phone in TEACHER_DEFINITIONS:
        user = create_user(
            username=username,
            full_name=f"{first_name} {last_name}",
            email=f"{username}@sams.local",
            role=Role.TEACHER,
            password="Teacher@123",
        )
        teacher = Teacher(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            staff_id=staff_id,
            phone=phone,
            is_active=True,
        )
        db.session.add(teacher)
        db.session.flush()
        teachers[username] = teacher

    assignments = [
        ("grace.adeyemi", "Nursery 1", None),
        ("grace.adeyemi", "Primary 1", None),
        ("yetunde.balogun", "KG 1", None),
        ("yetunde.balogun", "KG 2", None),
        ("yetunde.balogun", "Nursery 2", None),
        ("chinedu.obi", "Primary 2", None),
        ("halima.bello", "Primary 3", None),
        ("tunde.alabi", "Primary 4", None),
        ("esther.uko", "Primary 5", None),
        ("taiwo.shittu", "Primary 6", None),
        ("ibrahim.musa", "JSS 1", None),
        ("funke.adeola", "JSS 2", None),
        ("chinenye.eze", "JSS 3", None),
        ("samuel.okoro", "SSS 1", "Science"),
        ("patrick.james", "SSS 1", "Commercial"),
        ("miriam.odu", "SSS 1", "Arts"),
        ("amina.sule", "SSS 2", "Science"),
        ("bola.adesina", "SSS 2", "Commercial"),
        ("lilian.okafor", "SSS 2", "Arts"),
        ("isaac.edet", "SSS 3", "Science"),
        ("kemi.folarin", "SSS 3", "Commercial"),
        ("ugochi.madu", "SSS 3", "Arts"),
    ]

    for username, class_name, stream_name in assignments:
        db.session.add(
            ClassTeacherMap(
                class_id=classes[class_name].id,
                teacher_id=teachers[username].id,
                stream_id=streams[f"{class_name}:{stream_name}"].id if stream_name else None,
            )
        )

    db.session.flush()
    return teachers


def seed_students(classes: dict[str, Class], streams: dict[str, Stream]) -> list[dict]:
    """Create student users and profiles across all demo classes."""
    student_specs = [
        ("KG 1", None, 2),
        ("KG 2", None, 2),
        ("Nursery 1", None, 2),
        ("Nursery 2", None, 2),
        ("Primary 1", None, 3),
        ("Primary 2", None, 3),
        ("Primary 3", None, 3),
        ("Primary 4", None, 3),
        ("Primary 5", None, 3),
        ("Primary 6", None, 3),
        ("JSS 1", None, 3),
        ("JSS 2", None, 3),
        ("JSS 3", None, 3),
        ("SSS 1", "Science", 2),
        ("SSS 1", "Commercial", 2),
        ("SSS 1", "Arts", 2),
        ("SSS 2", "Science", 2),
        ("SSS 2", "Commercial", 2),
        ("SSS 2", "Arts", 2),
        ("SSS 3", "Science", 2),
        ("SSS 3", "Commercial", 2),
        ("SSS 3", "Arts", 2),
    ]

    special_students = {
        1: ("Ifeoma", "Nnaji"),
        2: ("Daniel", "Adebayo"),
        3: ("Amaka", "Okafor"),
    }

    seeded_students = []
    code_counter = 1
    generated_name_index = 0

    for class_name, stream_name, count in student_specs:
        for _ in range(count):
            if code_counter in special_students:
                first_name, last_name = special_students[code_counter]
            else:
                first_name = FIRST_NAMES[generated_name_index % len(FIRST_NAMES)]
                last_name = LAST_NAMES[(generated_name_index * 3) % len(LAST_NAMES)]
                generated_name_index += 1

            student_code = f"STU-2025-{code_counter:04d}"
            user = create_user(
                username=student_code,
                full_name=f"{first_name} {last_name}",
                email=f"{student_code.lower()}@sams.local",
                role=Role.STUDENT,
                password="Student@123",
            )

            class_ = classes[class_name]
            stream = streams.get(f"{class_name}:{stream_name}") if stream_name else None
            student = Student(
                user_id=user.id,
                student_code=student_code,
                first_name=first_name,
                last_name=last_name,
                class_id=class_.id,
                stream_id=stream.id if stream else None,
                admission_year=2025,
                level=class_.level,
                is_active=True,
            )
            db.session.add(student)
            db.session.flush()

            seeded_students.append(
                {
                    "user": user,
                    "student": student,
                    "class_name": class_name,
                    "stream_name": stream_name,
                    "cohort_index": code_counter,
                }
            )
            code_counter += 1

    return seeded_students


def subject_names_for_student(class_name: str, stream_name: str | None) -> list[tuple[str, bool]]:
    """Return subject names and compulsory flags for one academic group."""
    if class_name in {"KG 1", "KG 2", "Nursery 1", "Nursery 2"}:
        return [(name, True) for name in NURSERY_SUBJECTS]
    if class_name.startswith("Primary"):
        return [(name, True) for name in PRIMARY_SUBJECTS]
    if class_name.startswith("JSS"):
        return [(name, True) for name in JSS_SUBJECTS]

    stream_subjects = [(name, True) for name in SSS_COMMON_SUBJECTS]
    stream_subjects.extend(SSS_STREAM_SUBJECTS[stream_name or "Science"])
    return stream_subjects


def assigned_teacher_for_student(class_name: str, stream_name: str | None, teachers: dict[str, Teacher]) -> Teacher:
    """Return the teacher profile responsible for the student's result scope."""
    teacher_key_map = {
        ("Nursery 1", None): "grace.adeyemi",
        ("KG 1", None): "yetunde.balogun",
        ("KG 2", None): "yetunde.balogun",
        ("Nursery 2", None): "yetunde.balogun",
        ("Primary 1", None): "grace.adeyemi",
        ("Primary 2", None): "chinedu.obi",
        ("Primary 3", None): "halima.bello",
        ("Primary 4", None): "tunde.alabi",
        ("Primary 5", None): "esther.uko",
        ("Primary 6", None): "taiwo.shittu",
        ("JSS 1", None): "ibrahim.musa",
        ("JSS 2", None): "funke.adeola",
        ("JSS 3", None): "chinenye.eze",
        ("SSS 1", "Science"): "samuel.okoro",
        ("SSS 1", "Commercial"): "patrick.james",
        ("SSS 1", "Arts"): "miriam.odu",
        ("SSS 2", "Science"): "amina.sule",
        ("SSS 2", "Commercial"): "bola.adesina",
        ("SSS 2", "Arts"): "lilian.okafor",
        ("SSS 3", "Science"): "isaac.edet",
        ("SSS 3", "Commercial"): "kemi.folarin",
        ("SSS 3", "Arts"): "ugochi.madu",
    }
    return teachers[teacher_key_map[(class_name, stream_name)]]


def seed_results(
    session: Session,
    students: list[dict],
    classes: dict[str, Class],
    streams: dict[str, Stream],
    subjects: dict[str, Subject],
    teachers: dict[str, Teacher],
) -> None:
    """Create first-term demo report data for all seeded students."""
    for student_index, entry in enumerate(students, start=1):
        student = entry["student"]
        class_name = entry["class_name"]
        stream_name = entry["stream_name"]
        class_ = classes[class_name]
        stream = streams.get(f"{class_name}:{stream_name}") if stream_name else None
        teacher = assigned_teacher_for_student(class_name, stream_name, teachers)
        subject_entries = subject_names_for_student(class_name, stream_name)

        for subject_index, (subject_name, is_compulsory) in enumerate(subject_entries, start=1):
            subject = subjects[subject_name]
            result = Result(
                student_id=student.id,
                subject_id=subject.id,
                class_id=class_.id,
                stream_id=stream.id if stream else None,
                term=Term.FIRST,
                session_id=session.id,
                created_by=teacher.id,
                uploaded_by_user_id=teacher.user_id,
                result_status=ResultStatus.DRAFT,
                is_offered=True,
            )

            if class_.level == Level.NURSERY:
                result.mode = ResultMode.ASSESSMENT
                result.assessment_json = build_assessment_payload(student_index, subject_index)
                result.remark = [
                    "Keeps improving with gentle guidance.",
                    "Shows strong interest in classroom routines.",
                    "Works well with peers during activities.",
                    "Needs regular encouragement to stay engaged.",
                    "Progress is steady and promising.",
                ][(student_index + subject_index) % 5]
            else:
                result.mode = ResultMode.SCORE
                is_optional_subject = not is_compulsory
                offered = True
                if is_optional_subject:
                    offered = (student_index + subject_index) % 2 == 0
                result.is_offered = offered
                if offered:
                    ca_score, exam_score = build_score_components(student_index, subject_index)
                    result.ca_score = ca_score
                    result.exam_score = exam_score
                else:
                    result.ca_score = None
                    result.exam_score = None

            db.session.add(result)

    db.session.flush()


def seed_admin() -> None:
    """Create the single system admin account."""
    create_user(
        username="admin",
        full_name="System Administrator",
        email="admin@sams.local",
        role=Role.ADMIN,
        password="Admin@12345",
    )


def main() -> None:
    """Reset and repopulate the development database."""
    app = create_app("development")

    with app.app_context():
        db.drop_all()
        db.create_all()

        seed_admin()
        session, _ = seed_sessions()
        classes = seed_classes(session)
        streams = seed_streams(classes)
        subjects = seed_subjects()
        seed_subject_assignments(classes, streams, subjects)
        teachers = seed_teachers(classes, streams)
        students = seed_students(classes, streams)
        seed_results(session, students, classes, streams, subjects, teachers)
        db.session.commit()

        print("Seed complete.")
        print("Admin login: admin / Admin@12345")
        print("Teacher login: grace.adeyemi / Teacher@123")
        print("Student login: STU-2025-0002 / Student@123")


if __name__ == "__main__":
    main()

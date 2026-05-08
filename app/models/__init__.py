"""Import all models so SQLAlchemy can discover every table."""

from app.models.user import User  # noqa: F401
from app.models.session_ import AcademicSession, Session  # noqa: F401
from app.models.session_term import SessionTerm, Term  # noqa: F401
from app.models.class_ import Class, Level  # noqa: F401
from app.models.stream import Stream  # noqa: F401
from app.models.subject import Subject  # noqa: F401
from app.models.class_subject import ClassSubject  # noqa: F401
from app.models.stream_subject import StreamSubject  # noqa: F401
from app.models.system_setting import SystemSetting  # noqa: F401
from app.models.student import Student  # noqa: F401
from app.models.teacher import Teacher  # noqa: F401
from app.models.class_teacher import ClassTeacherMap  # noqa: F401
from app.models.result import Result, ResultMode, ResultStatus  # noqa: F401

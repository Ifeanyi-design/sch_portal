"""
models/__init__.py

Imports all models so that db.create_all() can discover every table,
regardless of which module triggers the first import.
"""

from app.models.user import User          # noqa: F401
from app.models.student import Student    # noqa: F401
from app.models.teacher import Teacher    # noqa: F401
from app.models.class_ import Class       # noqa: F401
from app.models.subject import Subject    # noqa: F401
from app.models.result import Result      # noqa: F401
from app.models.session_ import AcademicSession  # noqa: F401
from app.models.class_teacher import class_teacher_map  # noqa: F401

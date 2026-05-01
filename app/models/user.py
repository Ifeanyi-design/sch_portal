"""
models/user.py — Core User model.

A single users table stores all account types. The `role` column
determines what the user can do. Specific profile details are stored
in the related Student or Teacher models.
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Role:
    """String constants for user roles — avoids magic strings in code."""
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

    ALL_ROLES = [ADMIN, TEACHER, STUDENT]


class User(UserMixin, db.Model):
    """
    Represents an authenticated account in the system.

    Relationships:
        - One User → One Student (if role == 'student')
        - One User → One Teacher (if role == 'teacher')
    """

    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    email      = db.Column(db.String(150), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.String(20),  nullable=False, default=Role.STUDENT)
    is_active  = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Back-references populated by Student / Teacher models
    student_profile = db.relationship("Student", back_populates="user", uselist=False, lazy="select")
    teacher_profile = db.relationship("Teacher", back_populates="user", uselist=False, lazy="select")

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hash and store a plain-text password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plain-text password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT

    # ------------------------------------------------------------------
    # Flask-Login required properties
    # ------------------------------------------------------------------

    def get_id(self) -> str:
        """Flask-Login uses this to store the user ID in the session."""
        return str(self.id)

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"

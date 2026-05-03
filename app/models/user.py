"""Core user model and role constants."""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Role:
    """String constants for the supported user roles."""

    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

    ALL = (ADMIN, TEACHER, STUDENT)


class User(UserMixin, db.Model):
    """Authentication record shared by admins, teachers, and students."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    student_profile = db.relationship(
        "Student", back_populates="user", uselist=False, lazy="select"
    )
    teacher_profile = db.relationship(
        "Teacher", back_populates="user", uselist=False, lazy="select"
    )
    uploaded_results = db.relationship(
        "Result",
        back_populates="uploaded_by_user",
        foreign_keys="Result.uploaded_by_user_id",
        lazy="dynamic",
    )
    overridden_results = db.relationship(
        "Result",
        back_populates="overridden_by_user",
        foreign_keys="Result.overridden_by_user_id",
        lazy="dynamic",
    )

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('admin', 'teacher', 'student')", name="ck_users_role"
        ),
    )

    def set_password(self, password: str) -> None:
        """Hash and store a plain-text password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plain-text password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT

    def get_id(self) -> str:
        """Flask-Login stores the user ID as a string in the session."""
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"

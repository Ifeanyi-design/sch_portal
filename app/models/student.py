"""
models/student.py — Student profile model.

Stores student-specific data separate from the auth User model.
A student is linked to a User account (role='student') and belongs
to a single Class.
"""

from datetime import datetime, timezone
from app.extensions import db


class Student(db.Model):
    """
    Extended profile for a student user.

    student_code is auto-generated (e.g. STU-2025-0001) by the
    utils.helpers.generate_student_id() helper.
    """

    __tablename__ = "students"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    student_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name   = db.Column(db.String(80), nullable=False)
    last_name    = db.Column(db.String(80), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender       = db.Column(db.String(10), nullable=True)   # 'male' | 'female'
    class_id     = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=True)
    enrolled_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user    = db.relationship("User",    back_populates="student_profile")
    class_  = db.relationship("Class",   back_populates="students")
    results = db.relationship("Result",  back_populates="student", lazy="dynamic")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Student {self.student_code} — {self.full_name}>"

"""
models/teacher.py — Teacher profile model.

Stores teacher-specific data. A Teacher is linked to a User account
(role='teacher') and can be assigned to multiple Classes via the
class_teacher_map association table.
"""

from app.extensions import db


class Teacher(db.Model):
    """Extended profile for a teacher user."""

    __tablename__ = "teachers"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name  = db.Column(db.String(80), nullable=False)
    staff_code = db.Column(db.String(20), unique=True, nullable=True, index=True)
    phone      = db.Column(db.String(20), nullable=True)

    # Relationships
    user    = db.relationship("User",  back_populates="teacher_profile")
    classes = db.relationship(
        "Class",
        secondary="class_teacher_map",
        back_populates="teachers",
        lazy="select",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Teacher id={self.id} — {self.full_name}>"

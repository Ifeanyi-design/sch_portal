"""
models/class_.py — Class (classroom) model.

Represents a school class such as "Primary 3" or "JSS 2".
Each class belongs to a level (Nursery, Primary, Secondary).
"""

from app.extensions import db


class Level:
    """School level constants."""
    NURSERY   = "nursery"
    PRIMARY   = "primary"
    SECONDARY = "secondary"

    ALL = [NURSERY, PRIMARY, SECONDARY]


class Class(db.Model):
    """
    A single classroom/form group within the school.

    Examples:
        name='Nursery 1', level='nursery'
        name='Primary 3', level='primary'
        name='JSS 2',     level='secondary'
    """

    __tablename__ = "classes"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(50),  nullable=False, unique=True)
    level    = db.Column(db.String(20),  nullable=False)   # nursery | primary | secondary
    arm      = db.Column(db.String(10),  nullable=True)    # e.g. 'A', 'B' for split classes
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    students = db.relationship("Student", back_populates="class_", lazy="dynamic")
    subjects = db.relationship("Subject", back_populates="class_", lazy="select")
    teachers = db.relationship(
        "Teacher",
        secondary="class_teacher_map",
        back_populates="classes",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Class {self.name!r} ({self.level})>"

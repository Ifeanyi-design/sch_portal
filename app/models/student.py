"""Student model."""

from datetime import date

from sqlalchemy import event
from sqlalchemy.orm import synonym

from app.extensions import db
from app.models.class_ import Class, Level
from app.models.stream import Stream


class Student(db.Model):
    """Student profile linked to a user account."""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    student_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey("streams.id"), nullable=True)
    admission_year = db.Column(db.Integer, nullable=False)
    parent_name = db.Column(db.String(150), nullable=True)
    parent_phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    level = db.Column(db.String(20), nullable=False)
    is_active = db.Column("active_status", db.Boolean, nullable=False, default=True)

    active_status = synonym("is_active")

    user = db.relationship("User", back_populates="student_profile")
    class_ = db.relationship("Class", back_populates="students")
    stream = db.relationship("Stream", back_populates="students")
    results = db.relationship("Result", back_populates="student", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint(
            "level IN ('kindergarten', 'nursery', 'primary', 'secondary')",
            name="ck_students_level",
        ),
        db.CheckConstraint(
            "gender IN ('male', 'female')", name="ck_students_gender"
        ),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Student code={self.student_code!r} name={self.full_name!r}>"


@event.listens_for(Student, "before_insert")
@event.listens_for(Student, "before_update")
def validate_student(mapper, connection, target):
    """Enforce class/stream rules defined in the project specification."""
    class_ = target.class_ or db.session.get(Class, target.class_id)
    if class_ is None:
        raise ValueError("Student must belong to a valid class.")

    if target.level != class_.level:
        raise ValueError("Student level must match the assigned class level.")

    if not isinstance(target.date_of_birth, date):
        raise ValueError("Student date_of_birth must be a valid date.")

    if class_.level in (Level.KINDERGARTEN, Level.NURSERY, Level.PRIMARY):
        if target.stream_id is not None:
            raise ValueError("Only Secondary students can have a stream.")
        return

    if target.stream_id is None and class_.streams:
        raise ValueError("Secondary students must have a stream when the class uses streams.")

    if target.stream_id is not None:
        stream = target.stream or db.session.get(Stream, target.stream_id)
        if stream is None or stream.class_id != target.class_id:
            raise ValueError("Student stream must belong to the same class.")

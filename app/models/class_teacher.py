"""Teacher assignment model with optional stream scope."""

from sqlalchemy import event

from app.extensions import db
from app.models.class_ import Class, Level
from app.models.stream import Stream


class ClassTeacherMap(db.Model):
    """Assigns a teacher to a class, optionally narrowed to a stream."""

    __tablename__ = "class_teacher_map"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey("streams.id"), nullable=True)

    class_ = db.relationship("Class", back_populates="teacher_assignments")
    teacher = db.relationship("Teacher", back_populates="assignment_links")
    stream = db.relationship("Stream", back_populates="teacher_assignments")

    __table_args__ = (
        db.UniqueConstraint(
            "class_id", "teacher_id", "stream_id", name="uq_class_teacher_scope"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ClassTeacherMap class_id={self.class_id} teacher_id={self.teacher_id} "
            f"stream_id={self.stream_id}>"
        )


@event.listens_for(ClassTeacherMap, "before_insert")
@event.listens_for(ClassTeacherMap, "before_update")
def validate_teacher_assignment(mapper, connection, target):
    """Ensure stream-scoped assignments only exist on valid secondary classes."""
    class_ = target.class_ or db.session.get(Class, target.class_id)
    if class_ is None:
        raise ValueError("Teacher assignment must reference a valid class.")

    if class_.level in (Level.NURSERY, Level.PRIMARY) and target.stream_id is not None:
        raise ValueError("Nursery and Primary teacher assignments cannot include a stream.")

    if target.stream_id is not None:
        stream = target.stream or db.session.get(Stream, target.stream_id)
        if stream is None or stream.class_id != target.class_id:
            raise ValueError("Teacher assignment stream must belong to the same class.")

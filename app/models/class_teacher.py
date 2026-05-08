"""Teacher assignment model."""

from sqlalchemy import event

from app.extensions import db
from app.models.class_ import Class


class ClassTeacherMap(db.Model):
    """Assigns a teacher to a class."""

    __tablename__ = "class_teacher_map"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)

    class_ = db.relationship("Class", back_populates="teacher_assignments")
    teacher = db.relationship("Teacher", back_populates="assignment_links")

    __table_args__ = (
        db.UniqueConstraint("class_id", "teacher_id", name="uq_class_teacher_scope"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClassTeacherMap class_id={self.class_id} teacher_id={self.teacher_id}>"
        )


@event.listens_for(ClassTeacherMap, "before_insert")
@event.listens_for(ClassTeacherMap, "before_update")
def validate_teacher_assignment(mapper, connection, target):
    """Ensure teacher assignments remain class-only under the V2.2 spec."""
    class_ = target.class_ or db.session.get(Class, target.class_id)
    if class_ is None:
        raise ValueError("Teacher assignment must reference a valid class.")

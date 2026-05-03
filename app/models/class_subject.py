"""Class-level subject assignment model."""

from app.extensions import db


class ClassSubject(db.Model):
    """Assigns subjects directly to a class."""

    __tablename__ = "class_subjects"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    is_compulsory = db.Column(db.Boolean, nullable=False, default=True)

    class_ = db.relationship("Class", back_populates="class_subjects")
    subject = db.relationship("Subject", back_populates="class_assignments")

    __table_args__ = (
        db.UniqueConstraint("class_id", "subject_id", name="uq_class_subjects_class_subject"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClassSubject class_id={self.class_id} subject_id={self.subject_id} "
            f"compulsory={self.is_compulsory}>"
        )

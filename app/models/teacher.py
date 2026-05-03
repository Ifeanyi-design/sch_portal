"""Teacher model."""

from sqlalchemy.orm import synonym

from app.extensions import db


class Teacher(db.Model):
    """Teacher profile linked to a user account."""

    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    staff_id = db.Column(db.String(30), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    staff_code = synonym("staff_id")

    user = db.relationship("User", back_populates="teacher_profile")
    assignment_links = db.relationship(
        "ClassTeacherMap",
        back_populates="teacher",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    created_results = db.relationship(
        "Result", back_populates="created_by_teacher", foreign_keys="Result.created_by"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def classes(self):
        """Return unique classes assigned to this teacher."""
        by_id = {}
        for assignment in self.assignment_links:
            by_id[assignment.class_id] = assignment.class_
        return list(by_id.values())

    def __repr__(self) -> str:
        return f"<Teacher id={self.id} name={self.full_name!r}>"

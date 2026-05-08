"""Class model and school level constants."""

from app.extensions import db


class Level:
    """Supported school levels."""

    KINDERGARTEN = "kindergarten"
    NURSERY = "nursery"
    PRIMARY = "primary"
    SECONDARY = "secondary"

    ALL = (KINDERGARTEN, NURSERY, PRIMARY, SECONDARY)


class Class(db.Model):
    """Academic class such as Primary 1 or SS 2."""

    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    arm = db.Column(db.String(10), nullable=True)
    show_position = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    assessment_schema = db.Column(db.JSON, nullable=True)

    session = db.relationship("Session", back_populates="classes")
    streams = db.relationship(
        "Stream", back_populates="class_", cascade="all, delete-orphan", lazy="selectin"
    )
    students = db.relationship("Student", back_populates="class_", lazy="dynamic")
    class_subjects = db.relationship(
        "ClassSubject",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    teacher_assignments = db.relationship(
        "ClassTeacherMap",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    results = db.relationship("Result", back_populates="class_", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("session_id", "name", "arm", name="uq_classes_session_name_arm"),
        db.CheckConstraint(
            "level IN ('kindergarten', 'nursery', 'primary', 'secondary')",
            name="ck_classes_level",
        ),
    )

    @property
    def teachers(self):
        """Return unique teachers assigned to this class."""
        by_id = {}
        for assignment in self.teacher_assignments:
            by_id[assignment.teacher_id] = assignment.teacher
        return list(by_id.values())

    def __repr__(self) -> str:
        return f"<Class name={self.name!r} level={self.level!r}>"

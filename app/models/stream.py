"""Secondary stream model."""

from sqlalchemy import event

from app.extensions import db
from app.models.class_ import Class
from app.models.class_ import Level


class Stream(db.Model):
    """Secondary stream such as Science or Arts."""

    __tablename__ = "streams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    class_ = db.relationship("Class", back_populates="streams")
    students = db.relationship("Student", back_populates="stream", lazy="dynamic")
    stream_subjects = db.relationship(
        "StreamSubject",
        back_populates="stream",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    results = db.relationship("Result", back_populates="stream", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("class_id", "name", name="uq_streams_class_name"),
        db.CheckConstraint(
            "name IN ('Science', 'Commercial', 'Arts')", name="ck_streams_name"
        ),
    )

    def __repr__(self) -> str:
        return f"<Stream class_id={self.class_id} name={self.name!r}>"


@event.listens_for(Stream, "before_insert")
@event.listens_for(Stream, "before_update")
def validate_stream(mapper, connection, target):
    """Streams may exist only on secondary classes."""
    class_level = target.class_.level if target.class_ is not None else None
    if class_level is None and target.class_id is not None:
        class_ = db.session.get(Class, target.class_id)
        class_level = class_.level if class_ is not None else None
    if class_level != Level.SECONDARY:
        raise ValueError("Streams can only be assigned to secondary classes.")

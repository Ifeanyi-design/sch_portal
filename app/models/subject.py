"""Reusable subject model."""

from app.extensions import db


class Subject(db.Model):
    """Academic subject such as Mathematics or Chemistry."""

    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    class_assignments = db.relationship(
        "ClassSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    stream_assignments = db.relationship(
        "StreamSubject",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    results = db.relationship("Result", back_populates="subject", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Subject name={self.name!r}>"

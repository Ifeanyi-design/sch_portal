"""
models/subject.py — Subject model.

A subject belongs to a specific class (e.g. "Mathematics" in "Primary 3").
"""

from app.extensions import db


class Subject(db.Model):
    """A subject taught in a particular class."""

    __tablename__ = "subjects"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)

    # Relationships
    class_  = db.relationship("Class",  back_populates="subjects")
    results = db.relationship("Result", back_populates="subject", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Subject {self.name!r} (class_id={self.class_id})>"

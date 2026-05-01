"""
models/result.py — Flexible result model.

A single table handles all grading structures across Nursery, Primary,
and Secondary levels by using a JSON `meta` field for level-specific data.

Core scalar fields (score, grade, remark) are stored directly for easy
querying. Level-specific breakdown (e.g. CA scores, behavior ratings)
is stored in `meta`.
"""

from datetime import datetime, timezone
from app.extensions import db


class Result(db.Model):
    """
    Generic result record for any student, subject, and session.

    meta field examples by level
    ─────────────────────────────
    Nursery:
        {"behavior": "Excellent", "attendance": 18, "comment": "Great effort"}

    Primary:
        {"test1": 10, "test2": 8, "exam": 50, "total": 68}

    Secondary:
        {"ca1": 10, "ca2": 10, "ca3": 10, "exam": 60, "total": 90}
    """

    __tablename__ = "results"

    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),  nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),  nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"),  nullable=False)
    class_id   = db.Column(db.Integer, db.ForeignKey("classes.id"),   nullable=False)

    # Core result fields (optional — Nursery may not have numeric scores)
    score      = db.Column(db.Float,   nullable=True)
    grade      = db.Column(db.String(5), nullable=True)    # e.g. 'A', 'B+', 'Pass'
    remark     = db.Column(db.String(100), nullable=True)  # e.g. 'Excellent'

    # Level-specific extra data
    meta       = db.Column(db.JSON, nullable=True, default=dict)

    # Audit
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    student = db.relationship("Student", back_populates="results")
    subject = db.relationship("Subject", back_populates="results")
    session = db.relationship("AcademicSession", back_populates="results")

    __table_args__ = (
        # One result entry per student per subject per session
        db.UniqueConstraint("student_id", "subject_id", "session_id",
                            name="uq_result_student_subject_session"),
    )

    def __repr__(self) -> str:
        return (
            f"<Result student_id={self.student_id} "
            f"subject_id={self.subject_id} score={self.score}>"
        )

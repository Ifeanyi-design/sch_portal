"""
models/session_.py — Academic session model.

Tracks academic years (e.g. "2025/2026") and terms within them.
Results are grouped by session + term.
"""

from datetime import datetime, timezone
from app.extensions import db


class Term:
    """Term name constants."""
    FIRST  = "first"
    SECOND = "second"
    THIRD  = "third"

    ALL = [FIRST, SECOND, THIRD]


class AcademicSession(db.Model):
    """
    Represents one academic year divided into terms.

    Example:
        name='2025/2026', term='first', is_active=True
    """

    __tablename__ = "sessions"

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(20), nullable=False)          # e.g. '2025/2026'
    term       = db.Column(db.String(10), nullable=False)          # first | second | third
    is_active  = db.Column(db.Boolean, default=False, nullable=False)
    results_locked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    results = db.relationship("Result", back_populates="session", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("name", "term", name="uq_session_term"),
    )

    def __repr__(self) -> str:
        return f"<AcademicSession {self.name} — {self.term} term (locked={self.results_locked})>"

"""Session-term model used for locking and entry workflow."""

from app.extensions import db


class Term:
    """Fixed term values used across the system."""

    FIRST = "first"
    SECOND = "second"
    THIRD = "third"

    ALL = (FIRST, SECOND, THIRD)


class SessionTerm(db.Model):
    """Represents one session-term combination for workflow control."""

    __tablename__ = "session_terms"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    term = db.Column(db.String(10), nullable=False)
    is_result_entry_active = db.Column(db.Boolean, nullable=False, default=False)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)

    session = db.relationship("Session", back_populates="session_terms")

    __table_args__ = (
        db.UniqueConstraint("session_id", "term", name="uq_session_terms_session_term"),
        db.CheckConstraint(
            "term IN ('first', 'second', 'third')",
            name="ck_session_terms_term",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SessionTerm session_id={self.session_id} term={self.term} "
            f"active={self.is_result_entry_active} locked={self.is_locked}>"
        )

"""Academic session model."""

from app.extensions import db


class Session(db.Model):
    """Represents one academic year such as 2025/2026."""

    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    classes = db.relationship("Class", back_populates="session", lazy="dynamic")
    session_terms = db.relationship(
        "SessionTerm",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    results = db.relationship("Result", back_populates="session", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Session name={self.name!r} active={self.is_active}>"


# Backward-compatible alias for existing imports.
AcademicSession = Session

"""Stream-level subject assignment model."""

from app.extensions import db


class StreamSubject(db.Model):
    """Assigns a subject to a secondary stream."""

    __tablename__ = "stream_subjects"

    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey("streams.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    is_compulsory = db.Column(db.Boolean, nullable=False, default=True)

    stream = db.relationship("Stream", back_populates="stream_subjects")
    subject = db.relationship("Subject", back_populates="stream_assignments")

    __table_args__ = (
        db.UniqueConstraint(
            "stream_id", "subject_id", name="uq_stream_subjects_stream_subject"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<StreamSubject stream_id={self.stream_id} subject_id={self.subject_id} "
            f"compulsory={self.is_compulsory}>"
        )

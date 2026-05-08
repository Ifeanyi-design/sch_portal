"""Global application settings model."""

from datetime import datetime, timezone

from app.extensions import db


class SystemSetting(db.Model):
    """Stores global runtime toggles that affect system workflow."""

    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True, default=1)
    allow_teacher_result_upload = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def get_current(cls) -> "SystemSetting":
        """Return the single settings row, creating an in-memory default if needed."""
        setting = cls.query.get(1)
        if setting is None:
            setting = cls(id=1, allow_teacher_result_upload=False)
            db.session.add(setting)
            db.session.flush()
        return setting

    def __repr__(self) -> str:
        return (
            "<SystemSetting allow_teacher_result_upload="
            f"{self.allow_teacher_result_upload}>"
        )

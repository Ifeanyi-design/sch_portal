"""Result model covering score-mode and assessment-mode workflows."""

from datetime import datetime, timezone

from sqlalchemy import event

from app.extensions import db
from app.models.class_ import Class, Level
from app.models.class_subject import ClassSubject
from app.models.stream import Stream
from app.models.stream_subject import StreamSubject
from app.models.student import Student
from app.models.subject import Subject
from app.models.session_term import Term
from app.utils.helpers import calculate_grade, calculate_remark


class ResultMode:
    """Supported result modes."""

    SCORE = "score"
    ASSESSMENT = "assessment"

    ALL = (SCORE, ASSESSMENT)


class ResultStatus:
    """Allowed result workflow statuses."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    LOCKED = "locked"

    ALL = (DRAFT, SUBMITTED, LOCKED)


class Result(db.Model):
    """Stores one student's result for one subject in one session-term."""

    __tablename__ = "results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey("streams.id"), nullable=True)
    term = db.Column(db.String(10), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    ca_score = db.Column(db.Float, nullable=True)
    exam_score = db.Column(db.Float, nullable=True)
    total_score = db.Column(db.Float, nullable=True)
    grade = db.Column(db.String(5), nullable=True)
    remark = db.Column(db.String(255), nullable=True)
    assessment_json = db.Column(db.JSON, nullable=True)
    is_offered = db.Column(db.Boolean, nullable=False, default=True)
    result_status = db.Column(db.String(20), nullable=False, default=ResultStatus.DRAFT)
    created_by = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    overridden_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    override_reason = db.Column(db.String(255), nullable=True)
    overridden_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", back_populates="results")
    subject = db.relationship("Subject", back_populates="results")
    class_ = db.relationship("Class", back_populates="results")
    stream = db.relationship("Stream", back_populates="results")
    session = db.relationship("Session", back_populates="results")
    created_by_teacher = db.relationship(
        "Teacher", back_populates="created_results", foreign_keys=[created_by]
    )
    uploaded_by_user = db.relationship(
        "User", back_populates="uploaded_results", foreign_keys=[uploaded_by_user_id]
    )
    overridden_by_user = db.relationship(
        "User", back_populates="overridden_results", foreign_keys=[overridden_by_user_id]
    )

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "subject_id",
            "session_id",
            "term",
            name="uq_results_student_subject_session_term",
        ),
        db.CheckConstraint(
            "term IN ('first', 'second', 'third')", name="ck_results_term"
        ),
        db.CheckConstraint(
            "mode IN ('score', 'assessment')", name="ck_results_mode"
        ),
        db.CheckConstraint(
            "result_status IN ('draft', 'submitted', 'locked')",
            name="ck_results_status",
        ),
        db.CheckConstraint(
            "(ca_score IS NULL) OR (ca_score >= 0 AND ca_score <= 40)",
            name="ck_results_ca_score_range",
        ),
        db.CheckConstraint(
            "(exam_score IS NULL) OR (exam_score >= 0 AND exam_score <= 60)",
            name="ck_results_exam_score_range",
        ),
        db.CheckConstraint(
            "(total_score IS NULL) OR (total_score >= 0 AND total_score <= 100)",
            name="ck_results_total_score_range",
        ),
    )

    def can_transition_to(self, new_status: str, actor_role: str) -> bool:
        """Return whether a status change is allowed for the acting role."""
        if actor_role == "admin":
            return new_status in ResultStatus.ALL

        transitions = {
            ResultStatus.DRAFT: {ResultStatus.SUBMITTED, ResultStatus.LOCKED},
            ResultStatus.SUBMITTED: {ResultStatus.DRAFT, ResultStatus.LOCKED},
            ResultStatus.LOCKED: set(),
        }
        if new_status == self.result_status:
            return True
        if new_status not in transitions.get(self.result_status, set()):
            return False
        if new_status == ResultStatus.DRAFT and actor_role != "admin":
            return False
        if self.result_status == ResultStatus.LOCKED and actor_role != "admin":
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"<Result student_id={self.student_id} subject_id={self.subject_id} "
            f"term={self.term} mode={self.mode}>"
        )


@event.listens_for(Result, "before_insert")
@event.listens_for(Result, "before_update")
def validate_result(mapper, connection, target):
    """Enforce score-mode and assessment-mode rules from the spec."""
    with db.session.no_autoflush:
        class_ = target.class_ or db.session.get(Class, target.class_id)
        student = target.student or db.session.get(Student, target.student_id)
        subject = target.subject or db.session.get(Subject, target.subject_id)

        if class_ is None or student is None or subject is None:
            raise ValueError("Result must reference a valid class, student, and subject.")

        if student.class_id != target.class_id:
            raise ValueError("Result class must match the student's class.")

        if class_.level == Level.NURSERY:
            if target.mode != ResultMode.ASSESSMENT:
                raise ValueError("Nursery results must use assessment mode.")
            if target.stream_id is not None:
                raise ValueError("Nursery results cannot have a stream.")
            if not target.assessment_json:
                raise ValueError("Assessment-mode results require assessment_json.")
            if not class_.assessment_schema:
                raise ValueError("Nursery classes must define an assessment_schema.")
            missing_keys = set(class_.assessment_schema) - set(target.assessment_json)
            if missing_keys:
                raise ValueError("assessment_json is missing one or more class schema keys.")
            invalid_keys = set(target.assessment_json) - set(class_.assessment_schema)
            if invalid_keys:
                raise ValueError("assessment_json contains keys not present in the class schema.")
            target.ca_score = None
            target.exam_score = None
            target.total_score = None
            target.grade = None
            return

        if target.mode != ResultMode.SCORE:
            raise ValueError("Primary and Secondary results must use score mode.")

        if target.assessment_json is not None:
            raise ValueError("Score-mode results cannot include assessment_json.")

        if not target.is_offered:
            target.ca_score = None
            target.exam_score = None
            target.total_score = None
            target.grade = None
            return

        if target.ca_score is None or target.exam_score is None:
            raise ValueError("Score-mode offered results require CA and exam scores.")

        target.total_score = round(float(target.ca_score) + float(target.exam_score), 2)
        target.grade = calculate_grade(target.total_score)
        if not target.override_reason:
            target.remark = calculate_remark(target.total_score)

        if class_.level in (Level.PRIMARY, Level.NURSERY):
            if target.stream_id is not None:
                raise ValueError("Only secondary results may include a stream.")
            class_subject = ClassSubject.query.filter_by(
                class_id=class_.id,
                subject_id=target.subject_id,
            ).first()
            if class_subject is None:
                raise ValueError("Subject is not assigned to the student's class.")
            return

        if target.stream_id is not None:
            stream = target.stream or db.session.get(Stream, target.stream_id)
            if stream is None or stream.class_id != target.class_id:
                raise ValueError("Result stream must belong to the same class.")
            if student.stream_id is not None and student.stream_id != target.stream_id:
                raise ValueError("Secondary result stream must match the student's stream.")
            stream_subject = StreamSubject.query.filter_by(
                stream_id=stream.id,
                subject_id=target.subject_id,
            ).first()
            if stream_subject is None:
                raise ValueError("Subject is not assigned to the selected stream.")
            return

        if class_.streams:
            raise ValueError("Secondary classes with streams require stream_id on results.")

        class_subject = ClassSubject.query.filter_by(
            class_id=class_.id,
            subject_id=target.subject_id,
        ).first()
        if class_subject is None:
            raise ValueError("Subject is not assigned to the student's class.")

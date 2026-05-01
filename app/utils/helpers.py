"""
utils/helpers.py — Application utility functions.

Contains:
  - generate_student_id(): Auto-generates unique student codes.
  - calculate_grade():     Maps a numeric score to a letter grade.
  - calculate_remark():    Maps a score to a descriptive remark.
"""

from datetime import datetime
from app.extensions import db


# ------------------------------------------------------------------
# Student ID generation
# ------------------------------------------------------------------

def generate_student_id(year: int | None = None) -> str:
    """
    Generate a unique student code in the format STU-YYYY-NNNN.

    Example:
        STU-2025-0001
        STU-2025-0042

    Args:
        year: Academic year (defaults to current year).

    Returns:
        A unique student code string.
    """
    from app.models.student import Student   # local import to avoid circular

    year = year or datetime.now().year
    prefix = f"STU-{year}-"

    # Find the highest existing sequence for this year
    last = (
        Student.query
        .filter(Student.student_code.like(f"{prefix}%"))
        .order_by(Student.student_code.desc())
        .first()
    )

    if last:
        try:
            last_seq = int(last.student_code.split("-")[-1])
        except ValueError:
            last_seq = 0
    else:
        last_seq = 0

    return f"{prefix}{last_seq + 1:04d}"


# ------------------------------------------------------------------
# Grading helpers (Secondary / Primary scale — customise as needed)
# ------------------------------------------------------------------

# Default grading scale — can be overridden per level
_DEFAULT_GRADE_SCALE = [
    (90, "A+", "Outstanding"),
    (80, "A",  "Excellent"),
    (70, "B",  "Very Good"),
    (60, "C",  "Good"),
    (50, "D",  "Pass"),
    (40, "E",  "Below Average"),
    (0,  "F",  "Fail"),
]


def calculate_grade(score: float, scale: list | None = None) -> str:
    """
    Return a letter grade for a numeric score.

    Args:
        score: Raw numeric score (0–100).
        scale: Optional custom scale list of (min_score, grade, remark) tuples.

    Returns:
        Letter grade string (e.g. 'A', 'B+').
    """
    scale = scale or _DEFAULT_GRADE_SCALE
    for min_score, grade, _ in scale:
        if score >= min_score:
            return grade
    return "F"


def calculate_remark(score: float, scale: list | None = None) -> str:
    """
    Return a descriptive remark for a numeric score.

    Args:
        score: Raw numeric score (0–100).
        scale: Optional custom scale list of (min_score, grade, remark) tuples.

    Returns:
        Remark string (e.g. 'Excellent', 'Pass').
    """
    scale = scale or _DEFAULT_GRADE_SCALE
    for min_score, _, remark in scale:
        if score >= min_score:
            return remark
    return "Fail"

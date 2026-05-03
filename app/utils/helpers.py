"""Application utility helpers for IDs, grading, and ranking."""

from collections import Counter
from datetime import datetime

from app.extensions import db


def generate_student_id(year: int | None = None) -> str:
    """Generate a unique student code in the format STU-YYYY-NNNN."""
    from app.models.student import Student

    year = year or datetime.now().year
    prefix = f"STU-{year}-"

    last = (
        Student.query.filter(Student.student_code.like(f"{prefix}%"))
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


_DEFAULT_GRADE_SCALE = [
    (90, "A+", "Outstanding"),
    (80, "A", "Excellent"),
    (70, "B", "Very Good"),
    (60, "C", "Good"),
    (50, "D", "Pass"),
    (40, "E", "Below Average"),
    (0, "F", "Fail"),
]


def calculate_grade(score: float, scale: list | None = None) -> str:
    """Return a letter grade for a numeric score."""
    scale = scale or _DEFAULT_GRADE_SCALE
    for min_score, grade, _ in scale:
        if score >= min_score:
            return grade
    return "F"


def calculate_remark(score: float, scale: list | None = None) -> str:
    """Return a descriptive remark for a numeric score."""
    scale = scale or _DEFAULT_GRADE_SCALE
    for min_score, _, remark in scale:
        if score >= min_score:
            return remark
    return "Fail"


def summarize_score_results(results) -> dict:
    """Summarize offered score-mode results for one student."""
    offered = [
        item
        for item in results
        if getattr(item, "is_offered", False)
        and getattr(item, "total_score", None) is not None
        and getattr(item, "mode", None) == "score"
    ]
    total_score = round(sum(item.total_score for item in offered), 2)
    subjects_taken = len(offered)
    average_score = round(total_score / subjects_taken, 2) if subjects_taken else 0.0
    grade_counts = Counter(item.grade for item in offered if getattr(item, "grade", None))

    return {
        "total_score": total_score,
        "subjects_taken": subjects_taken,
        "average_score": average_score,
        "grade_counts": grade_counts,
    }


def build_position_rows(student_results_map: dict) -> list[dict]:
    """Build ranked rows using spec tie-breaking rules."""
    ranking_rows = []
    for student, results in student_results_map.items():
        summary = summarize_score_results(results)
        ranking_rows.append(
            {
                "student": student,
                "results": results,
                "total_score": summary["total_score"],
                "subjects_taken": summary["subjects_taken"],
                "average_score": summary["average_score"],
                "a_plus_count": summary["grade_counts"].get("A+", 0),
                "a_count": summary["grade_counts"].get("A", 0),
            }
        )

    ranking_rows.sort(
        key=lambda item: (
            -item["total_score"],
            -item["a_plus_count"],
            -item["a_count"],
            -item["average_score"],
            item["student"].last_name.lower(),
            item["student"].first_name.lower(),
        )
    )

    previous_key = None
    previous_position = 0
    for index, row in enumerate(ranking_rows, start=1):
        key = (
            row["total_score"],
            row["a_plus_count"],
            row["a_count"],
            row["average_score"],
        )
        if key == previous_key:
            row["position"] = previous_position
        else:
            row["position"] = index
            previous_position = index
            previous_key = key

    return ranking_rows

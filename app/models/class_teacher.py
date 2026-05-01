"""
models/class_teacher.py — Association table for Class ↔ Teacher (many-to-many).

A teacher can be assigned to multiple classes;
a class can have multiple teachers (e.g. different subject teachers).
"""

from app.extensions import db

# Pure association table — no ORM class needed
class_teacher_map = db.Table(
    "class_teacher_map",
    db.Column("class_id",   db.Integer, db.ForeignKey("classes.id"),  primary_key=True),
    db.Column("teacher_id", db.Integer, db.ForeignKey("teachers.id"), primary_key=True),
)

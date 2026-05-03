"""Forms used by the teacher result management module."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired


class ActionForm(FlaskForm):
    """CSRF-only form used for POST actions built from dynamic table rows."""


class CSVUploadForm(FlaskForm):
    """CSV upload form for teacher bulk result entry."""

    csv_file = FileField("CSV File", validators=[FileRequired(message="A CSV file is required.")])

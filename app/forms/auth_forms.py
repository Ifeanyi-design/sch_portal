"""
forms/auth_forms.py — WTForms form definitions for authentication.

Flask-WTF adds CSRF protection automatically to every form that
inherits from FlaskForm. The hidden CSRF token is rendered in the
template via {{ form.hidden_tag() }}.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """Login form used by all roles (admin, teacher, student)."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=2, max=80, message="Username must be between 2 and 80 characters."),
        ],
        render_kw={"placeholder": "Enter your username", "autocomplete": "username"},
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
        ],
        render_kw={"placeholder": "Enter your password", "autocomplete": "current-password"},
    )

    remember = BooleanField("Keep me signed in")

    submit = SubmitField("Sign In")

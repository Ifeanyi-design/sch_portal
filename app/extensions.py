"""
extensions.py — Shared Flask extension instances.

Instantiated here to avoid circular imports. The app is bound
to these instances inside create_app() via the init_app() pattern.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# SQLAlchemy instance — shared across all models
db = SQLAlchemy()

# Flask-Login instance
login_manager = LoginManager()
login_manager.login_view = "auth.login"          # redirect here if not logged in
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

"""
app/__init__.py — Application factory.

All Flask extensions and blueprints are registered here inside
create_app() so the app can be instantiated multiple times
(e.g., for testing) without global state conflicts.
"""

import os
from flask import Flask
from config import config_map
from app.extensions import db, login_manager


def create_app(config_name: str = "default") -> Flask:
    """
    Create and configure a Flask application instance.

    Args:
        config_name: Key from config_map ('development', 'production', 'testing').

    Returns:
        Configured Flask app instance.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # ------------------------------------------------------------------
    # Load configuration
    # ------------------------------------------------------------------
    app.config.from_object(config_map[config_name])

    # ------------------------------------------------------------------
    # Initialize extensions with this app instance
    # ------------------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.teacher import teacher_bp
    from app.routes.student import student_bp

    app.register_blueprint(auth_bp)                        # /login, /logout
    app.register_blueprint(admin_bp,   url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")

    # ------------------------------------------------------------------
    # Register the user loader for Flask-Login
    # ------------------------------------------------------------------
    from app.models.user import User  # noqa: F401 — needed for user_loader

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ------------------------------------------------------------------
    # Create database tables on first run (dev only)
    # ------------------------------------------------------------------
    with app.app_context():
        db.create_all()

    return app

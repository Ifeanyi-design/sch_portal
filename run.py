"""
run.py — Application entry point.

Usage:
    python run.py

Set FLASK_ENV environment variable to switch configs:
    set FLASK_ENV=development   (default)
    set FLASK_ENV=production
"""

import os
from app import create_app

env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    app.run()

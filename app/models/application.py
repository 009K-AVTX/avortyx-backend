"""A job application from the careers page, and where it is in review."""
from datetime import datetime

from ..extensions import db

STATUSES = ("new", "reviewing", "interview", "rejected", "hired")


class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    role = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(40))
    telegram = db.Column(db.String(64))
    link = db.Column(db.String(300))
    note = db.Column(db.Text)

    cv_path = db.Column(db.String(300), nullable=False)  # relative to UPLOAD_DIR
    cv_name = db.Column(db.String(200), nullable=False)  # the name shown on download

    status = db.Column(db.String(20), default="new", nullable=False)
    # whether each notification went out, so the panel can show and retry failures
    sent_telegram = db.Column(db.Boolean, default=False, nullable=False)
    sent_email = db.Column(db.Boolean, default=False, nullable=False)

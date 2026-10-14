"""A message the team sent an applicant, from the panel or from Telegram. Kept so everyone can see
what the applicant was told, whichever way it was sent."""
from datetime import datetime

from ..extensions import db


class ApplicationReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer, db.ForeignKey("job_application.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_by = db.Column(db.String(200), nullable=False)  # panel email, or the Telegram name
    via = db.Column(db.String(20), nullable=False)  # "panel" or "telegram"
    emailed = db.Column(db.Boolean, default=False, nullable=False)
    error = db.Column(db.String(300))

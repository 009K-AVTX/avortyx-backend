"""A request for access to the platform, from the website's /request-access form."""
from datetime import datetime

from ..extensions import db

ACCESS_STATUSES = ("new", "reviewing", "approved", "declined")

# "REQ-00012": what the requester and the team see in emails, Telegram and the panel
REQ_PREFIX = "REQ-"


class AccessRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    name = db.Column(db.String(200), nullable=False)
    organization = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(40))
    use_case = db.Column(db.Text, nullable=False)
    page = db.Column(db.String(300))  # the page the form was sent from

    status = db.Column(db.String(20), default="new", nullable=False)
    # whether each notification went out, so the panel can show and retry failures
    sent_telegram = db.Column(db.Boolean, default=False, nullable=False)
    sent_email = db.Column(db.Boolean, default=False, nullable=False)
    # the "we received your request" email to the requester
    sent_confirmation = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def reference(self):
        return f"{REQ_PREFIX}{self.id:05d}" if self.id else ""

"""A job application from the careers page, and where it is in review."""
import re
from datetime import datetime

from ..extensions import db

STATUSES = ("new", "reviewing", "interview", "rejected", "hired")

# "AVX-00012": what the team sees in Telegram and email, and types to reply to an applicant
REF_PREFIX = "AVX-"
REF_PATTERN = re.compile(r"\bAVX-?0*(\d{1,9})\b", re.IGNORECASE)


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
    # the "we received your application" email to the applicant
    sent_confirmation = db.Column(db.Boolean, default=False, nullable=False)

    replies = db.relationship(
        "ApplicationReply", order_by="ApplicationReply.created_at", cascade="all, delete-orphan", lazy="select"
    )

    @property
    def reference(self):
        return f"{REF_PREFIX}{self.id:05d}" if self.id else ""


def find_reference(text):
    """The application id in a piece of text ("AVX-00012", "avx12"), or None."""
    m = REF_PATTERN.search(text or "")
    return int(m.group(1)) if m else None

"""A one-time code that ties a Telegram chat to a panel user.

Panel → Settings → Connect Telegram makes one and opens t.me/<bot>?start=<code>. Telegram sends the
bot "/start <code>", and that is the only moment the bot learns the person's chat id. Same flow as
the call platform's portal.
"""
from datetime import datetime

from ..extensions import db


class TelegramLinkCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admin_user.id", ondelete="CASCADE"), nullable=False, index=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    admin = db.relationship("AdminUser")

    @property
    def is_usable(self):
        return self.used_at is None and self.expires_at > datetime.utcnow()

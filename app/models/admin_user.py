"""Someone allowed into the panel, and where they want to hear about new applications."""
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)

    # Telegram: filled in when they press Start on the bot from Panel → Settings
    telegram_chat_id = db.Column(db.String(64))
    telegram_username = db.Column(db.String(64))
    # what they receive; Telegram only arrives once their account is linked
    telegram_alerts = db.Column(db.Boolean, default=True, nullable=False)
    # CAREERS_EMAIL_TO always gets every application; this adds their own inbox
    email_alerts = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def telegram_linked(self):
        return bool(self.telegram_chat_id)

    @property
    def telegram_label(self):
        """How the panel and the bot name this person's Telegram."""
        if self.telegram_username:
            return f"@{self.telegram_username}"
        return f"chat {self.telegram_chat_id}" if self.telegram_chat_id else ""

"""A conversation from the website's help chat, and its messages.

The visitor writes in the chat box on avortyx.com; each message is forwarded to the team's support
group on Telegram. A teammate answers by replying to it there, and the answer shows up in the
visitor's chat box. Only the visitor's browser holds the conversation's token, so only it can read
the answers.
"""
import secrets
from datetime import datetime

from ..extensions import db

# "CHAT-00012": how the team sees the conversation in the support group
CHAT_PREFIX = "CHAT-"


class ChatConversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    token = db.Column(db.String(64), default=lambda: secrets.token_urlsafe(24), nullable=False, unique=True)

    agent = db.Column(db.String(40))   # the teammate the visitor picked on the site (maya, jordan, milena)
    intent = db.Column(db.String(20))  # sales, support or direct
    page = db.Column(db.String(300))   # the page the chat started on
    ip = db.Column(db.String(64))      # for the per-address limit on new conversations

    messages = db.relationship("ChatMessage", backref="conversation", order_by="ChatMessage.id",
                               cascade="all, delete-orphan")

    @property
    def reference(self):
        return f"{CHAT_PREFIX}{self.id:05d}" if self.id else ""


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("chat_conversation.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # "visitor" or "team"
    author = db.Column(db.String(120))  # for team answers: who answered on Telegram
    text = db.Column(db.Text, nullable=False)
    # where the forwarded copy sits in the support group, so a reply to it finds this conversation
    tg_chat_id = db.Column(db.String(40))
    tg_message_id = db.Column(db.Integer, index=True)

    def public(self):
        """What the visitor's chat box gets."""
        return {"id": self.id, "from": "team" if self.sender == "team" else "me", "text": self.text,
                "at": self.created_at.isoformat(timespec="seconds") + "Z"}

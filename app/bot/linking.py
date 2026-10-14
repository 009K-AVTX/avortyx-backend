"""Linking a panel user to Telegram (the panel's half of /start <code>)."""
import secrets
from datetime import datetime, timedelta

from flask import current_app

from ..extensions import db
from ..models import TelegramLinkCode
from ..notify.telegram import bot_username


def create_link(admin):
    """A fresh one-time code for this user; any older unused code stops working.
    Returns the TelegramLinkCode, or None when the bot isn't set up."""
    if not bot_username():
        return None
    now = datetime.utcnow()
    TelegramLinkCode.query.filter(
        TelegramLinkCode.admin_id == admin.id, TelegramLinkCode.used_at.is_(None), TelegramLinkCode.expires_at > now
    ).update({"expires_at": now})
    # token_urlsafe is [A-Za-z0-9_-], what Telegram allows in a start payload (max 64)
    link = TelegramLinkCode(
        admin_id=admin.id,
        code=secrets.token_urlsafe(16),
        expires_at=now + timedelta(minutes=current_app.config["TELEGRAM_LINK_TTL_MINUTES"]),
    )
    db.session.add(link)
    db.session.commit()
    return link


def pending_link(admin):
    """The user's latest code that still works, or None."""
    link = (
        TelegramLinkCode.query.filter_by(admin_id=admin.id, used_at=None)
        .order_by(TelegramLinkCode.created_at.desc())
        .first()
    )
    return link if link and link.is_usable else None


def link_url(link):
    return f"https://t.me/{bot_username()}?start={link.code}"


def unlink(admin):
    admin.telegram_chat_id = None
    now = datetime.utcnow()
    TelegramLinkCode.query.filter(TelegramLinkCode.admin_id == admin.id, TelegramLinkCode.used_at.is_(None)).update(
        {"expires_at": now}
    )
    db.session.commit()

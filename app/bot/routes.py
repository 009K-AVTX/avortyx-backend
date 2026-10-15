"""POST /telegram/webhook: every message anyone sends the bot.

  /start <code>   link this chat to a panel user (the code comes from Panel → Settings)
  /start          the welcome message
  /help           what the bot does
  /stop           unlink this chat: no more alerts here
  /reply AVX-00012 message
  a reply to an application alert, or "AVX-00012 message"
                  email that message to the applicant (linked users and the team group only)

The webhook always answers 200 once the secret matches: anything else makes Telegram send the same
update again and again. A wrong or missing secret gets 403, so nobody else can drive the bot.
"""
import logging
import re
import secrets
from datetime import datetime
from html import escape

from flask import current_app, request

from ..extensions import db
from ..models import AdminUser, JobApplication, TelegramLinkCode
from ..models.application import REF_PATTERN, find_reference
from ..notify.telegram import TelegramError, bot_username, send_text
from ..replies import reply_to_applicant
from . import bp
from .texts import (
    EXPIRED_TEXT,
    HELP_TEXT,
    LINKED_TEXT,
    NOT_LINKED_TEXT,
    PRIVATE_ONLY_TEXT,
    REPLY_USAGE_TEXT,
    STOPPED_TEXT,
    UNKNOWN_TEXT,
    WELCOME_TEXT,
)

log = logging.getLogger(__name__)

# "AVX-00012 the message" at the start of a message
LEADING_REF = re.compile(r"^\s*AVX-?0*(\d{1,9})[\s:,-]+(.+)$", re.IGNORECASE | re.DOTALL)


@bp.post("/webhook")
def webhook():
    secret = current_app.config["TELEGRAM_WEBHOOK_SECRET"]
    sent = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret and not secrets.compare_digest(sent, secret):
        return {"ok": False}, 403
    try:
        handle(request.get_json(silent=True) or {})
    except Exception:  # never let one bad update block the ones behind it
        log.exception("telegram webhook failed")
        db.session.rollback()
    return {"ok": True}


def say(chat_id, html, reply_to=None):
    """Answer in the chat. A failure is logged, never raised."""
    try:
        send_text(chat_id, html, reply_to=reply_to)
    except TelegramError as err:
        log.warning("telegram reply to %s failed: %s", chat_id, err)


def handle(update):
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", "") or "")
    private = chat.get("type") == "private"
    if not text or not chat_id:
        return

    first = text.split()[0]
    if first.startswith("/"):
        command, _, addressed_to = first[1:].partition("@")
        # in a group, "/help@SomeOtherBot" is not for us
        if addressed_to and addressed_to.lower() != (bot_username() or "").lower():
            return
        rest = text[len(first):].strip()
        command = command.lower()
        if command == "help":
            return say(chat_id, HELP_TEXT)
        if command == "start":
            return start(message, chat_id, private, rest)
        if command == "stop":
            return stop(chat_id)
        if command == "reply":
            m = REF_PATTERN.match(rest) or re.match(r"^0*(\d{1,9})\b", rest)
            body = rest[m.end():].strip(" :,-\n") if m else ""
            if not m or not body:
                return say(chat_id, REPLY_USAGE_TEXT)
            return answer(message, chat_id, private, int(m.group(1)), body)
        if private:
            say(chat_id, UNKNOWN_TEXT)
        return

    # a reply (swipe / "Reply") to one of the bot's application messages
    replied = message.get("reply_to_message") or {}
    ref = find_reference(replied.get("text") or replied.get("caption") or "")
    if ref:
        return answer(message, chat_id, private, ref, text)

    m = LEADING_REF.match(text)
    if m:
        return answer(message, chat_id, private, int(m.group(1)), m.group(2).strip())

    if private:
        say(chat_id, UNKNOWN_TEXT if linked_admin(chat_id) else WELCOME_TEXT)


# ── linking ─────────────────────────────────────────────────────────────────

def start(message, chat_id, private, code):
    if not code:
        return say(chat_id, WELCOME_TEXT)
    if not private:
        return say(chat_id, PRIVATE_ONLY_TEXT)

    link = TelegramLinkCode.query.filter_by(code=code).first()
    if link is None:
        log.warning("telegram /start with unknown code from chat %s", chat_id)
        return say(chat_id, WELCOME_TEXT)
    if not link.is_usable:
        return say(chat_id, EXPIRED_TEXT)

    admin = link.admin
    admin.telegram_chat_id = chat_id
    handle_name = (message.get("from") or {}).get("username") or ""
    admin.telegram_username = handle_name[:64] or None
    link.used_at = datetime.utcnow()
    db.session.commit()
    log.info("telegram linked chat %s to %s", chat_id, admin.email)
    say(chat_id, LINKED_TEXT.format(who=admin.email))


def stop(chat_id):
    admins = AdminUser.query.filter_by(telegram_chat_id=chat_id).all()
    if not admins:
        return say(chat_id, NOT_LINKED_TEXT)
    for admin in admins:
        admin.telegram_chat_id = None
    db.session.commit()
    say(chat_id, STOPPED_TEXT)


def linked_admin(chat_id):
    return AdminUser.query.filter_by(telegram_chat_id=chat_id).first()


# ── replying to an applicant ────────────────────────────────────────────────

def sender_name(message, chat_id):
    """Who is replying, if they may: a linked panel user, or anyone in the team group."""
    admin = linked_admin(chat_id)
    if admin:
        return admin.email
    group = current_app.config["TELEGRAM_CHAT_ID"]
    if group and chat_id == str(group):
        person = message.get("from") or {}
        name = person.get("username") and f"@{person['username']}" or person.get("first_name") or "someone"
        return f"{name} (team group)"
    return None


def answer(message, chat_id, private, app_id, body):
    who = sender_name(message, chat_id)
    if not who:
        if private:
            say(chat_id, NOT_LINKED_TEXT)
        return
    application = db.session.get(JobApplication, app_id)
    if application is None:
        return say(chat_id, f"No application <code>AVX-{app_id:05d}</code> found.", reply_to=message.get("message_id"))

    reply = reply_to_applicant(application, body, sent_by=who, via="telegram")
    if reply.emailed:
        say(chat_id, f"✅ Sent to {escape(application.name)} ({escape(application.email)}) by email.",
            reply_to=message.get("message_id"))
    else:
        say(chat_id, f"⚠️ Couldn't email {escape(application.name)}: {escape(reply.error or 'unknown error')}. "
                     "The message is saved in the panel.", reply_to=message.get("message_id"))

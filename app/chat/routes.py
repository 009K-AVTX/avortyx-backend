"""The website's help chat, bridged to the team's support group on Telegram.

  POST /chat/messages   JSON {text*, conversation, token, agent, intent, page, website}
      The visitor's message. Without a conversation it starts one. Saved, then forwarded to the
      support group (TELEGRAM_SUPPORT_CHAT_ID). Replies 200 {"ok": true, "conversation": 12,
      "token": "...", "message": {...}}, 400/429 {"error": "..."} with a message the chat shows as
      it is, or 404 for an unknown conversation or wrong token.
  GET  /chat/<id>/messages?token=...&after=<message id>
      The conversation's messages after that one, oldest first: {"messages": [...]}. The chat box
      asks every few seconds while it is open, which is how the team's answers reach it.

A teammate answers by replying to a forwarded message in the support group (or by sending
"CHAT-00012 the answer" there); app/bot hands those to `answer_from_telegram` below. A message that
could not be forwarded is still saved and goes along with the visitor's next one.
"""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from html import escape

from flask import current_app, request

from ..extensions import db
from ..models import ChatConversation, ChatMessage
from ..notify.telegram import TelegramError, api, destination, is_chat, send_text
from . import bp

log = logging.getLogger(__name__)

# the teammates the chat box offers, as the site shows them
AGENTS = {"maya": "Maya Decker · Sales lead", "jordan": "Jordan Kim · Solutions engineer",
          "milena": "Milena Govich · Customer success"}
INTENTS = ("sales", "support", "direct")

# "CHAT-00012 the answer" at the start of a message in the support group
LEADING_CHAT = re.compile(r"^\s*CHAT-?0*(\d{1,9})[\s:,-]+(.+)$", re.IGNORECASE | re.DOTALL)


def _ip_key():
    """The visitor's address, hashed: enough to count new chats per address, nothing more."""
    salt = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{salt}:{request.remote_addr or ''}".encode()).hexdigest()[:32]


def _conversation(cid, token):
    conv = db.session.get(ChatConversation, cid) if cid else None
    if conv is None or not token or not _same(conv.token, token):
        return None
    return conv


def _same(a, b):
    return secrets.compare_digest(str(a), str(b))


@bp.post("/messages")
def post_message():
    body = request.get_json(silent=True) or {}
    # the honeypot: report success so bots move on, keep nothing
    if body.get("website"):
        return {"ok": True}

    cfg = current_app.config
    text = str(body.get("text") or "").strip()
    if not text:
        return {"error": "Please write a message."}, 400
    if len(text) > cfg["CHAT_MAX_CHARS"]:
        return {"error": f"Please keep it under {cfg['CHAT_MAX_CHARS']} characters."}, 400

    now = datetime.utcnow()
    cid = body.get("conversation")
    if cid:
        try:
            conv = _conversation(int(cid), body.get("token"))
        except (TypeError, ValueError):
            conv = None
        if conv is None:
            return {"error": "This chat has ended. Please start a new one."}, 404
        recent = ChatMessage.query.filter(ChatMessage.conversation_id == conv.id, ChatMessage.sender == "visitor",
                                          ChatMessage.created_at > now - timedelta(minutes=10)).count()
        if recent >= cfg["CHAT_MESSAGES_PER_10_MIN"]:
            return {"error": "That’s a lot of messages at once. Please wait a moment for the team to answer."}, 429
    else:
        ip = _ip_key()
        started = ChatConversation.query.filter(ChatConversation.ip == ip,
                                                ChatConversation.created_at > now - timedelta(hours=1)).count()
        if started >= cfg["CHAT_NEW_PER_HOUR"]:
            return {"error": "Too many new chats from your network. Please try again a little later."}, 429
        agent = str(body.get("agent") or "").lower()
        intent = str(body.get("intent") or "").lower()
        conv = ChatConversation(agent=agent if agent in AGENTS else None, intent=intent if intent in INTENTS else None,
                                page=str(body.get("page") or "")[:300] or None, ip=ip)
        db.session.add(conv)

    msg = ChatMessage(conversation=conv, sender="visitor", text=text)
    conv.last_at = now
    db.session.add(msg)
    db.session.commit()

    forward(conv)
    return {"ok": True, "conversation": conv.id, "token": conv.token, "message": msg.public()}


@bp.get("/<int:cid>/messages")
def list_messages(cid):
    conv = _conversation(cid, request.args.get("token"))
    if conv is None:
        return {"error": "This chat has ended. Please start a new one."}, 404
    after = request.args.get("after", type=int) or 0
    rows = ChatMessage.query.filter(ChatMessage.conversation_id == conv.id, ChatMessage.id > after) \
        .order_by(ChatMessage.id).limit(100).all()
    return {"messages": [m.public() for m in rows]}


# ── to and from the support group ───────────────────────────────────────────

def visitor_name(conv):
    """A short, steady name for the visitor ("Visitor UGWYMY"), so the team can tell chats apart."""
    digest = hashlib.sha256(conv.token.encode()).digest()
    return "Visitor " + "".join(chr(65 + b % 26) for b in digest[:6])


def forward_text(conv, msg, first):
    """A visitor's message as Telegram HTML, in the style of the call platform's support bot: the
    whole picture the first time, the message and how to answer after that."""
    how = ["─────────────────", "📨 To reply, send:", f"<code>{conv.reference} your reply here</code>",
           "or reply to this message."]
    if not first:
        return "\n".join([f"💬 <b>{visitor_name(conv)}</b> · {conv.reference}",
                          f"<b>Message:</b> {escape(msg.text)}"] + how)
    lines = [f"💬 <b>New Support Chat</b> · {conv.reference}", f"👤 {visitor_name(conv)}"]
    if conv.agent:
        lines.append(f"🧑‍💼 Asked for: {escape(AGENTS[conv.agent])}" + (f" ({conv.intent})" if conv.intent else ""))
    if conv.page:
        lines.append(f"🌐 Page: {escape(conv.page)}")
    lines.append(f"<b>Message:</b> {escape(msg.text)}")
    return "\n".join(lines + how)


def forward(conv):
    """Sends the conversation's unsent visitor messages to the support group. Never raises: a
    message that didn't go is saved and tried again with the next one."""
    group, topic = destination(current_app.config["TELEGRAM_SUPPORT_CHAT_ID"])
    if not group or not current_app.config["TELEGRAM_BOT_TOKEN"]:
        log.warning("chat: %s not forwarded, TELEGRAM_SUPPORT_CHAT_ID or the bot token is not set", conv.reference)
        return
    any_sent = ChatMessage.query.filter(ChatMessage.conversation_id == conv.id,
                                        ChatMessage.tg_message_id.isnot(None)).count() > 0
    pending = ChatMessage.query.filter_by(conversation_id=conv.id, sender="visitor", tg_message_id=None) \
        .order_by(ChatMessage.id).all()
    for msg in pending:
        try:
            sent = send_text(group, forward_text(conv, msg, first=not any_sent), topic=topic) or {}
        except TelegramError as err:
            log.warning("chat: forwarding %s to the support group failed: %s", conv.reference, err)
            break
        msg.tg_chat_id = str((sent.get("chat") or {}).get("id") or group)
        msg.tg_message_id = sent.get("message_id")
        any_sent = True
    db.session.commit()


def is_team_chat(chat):
    """Whether a Telegram chat is the support group, or the notification group (often the same
    group, another topic): the team may answer visitors from either."""
    cfg = current_app.config
    return is_chat(cfg["TELEGRAM_SUPPORT_CHAT_ID"], chat) or is_chat(cfg["TELEGRAM_CHAT_ID"], chat)


def answer_from_telegram(message, chat, text):
    """A message in the support group that answers a website chat goes to that visitor's chat box:
    a reply to a forwarded message, "CHAT-00012 answer", or "/reply CHAT-00012 answer".
    Returns True if it was one."""
    if not text or not is_team_chat(chat):
        return False
    command = re.match(r"^/reply(?:@\w+)?\s+(?=CHAT-?\d)", text, re.IGNORECASE)
    if command:
        text = text[command.end():]
    chat_id = str(chat.get("id"))
    conv = None
    replied = message.get("reply_to_message") or {}
    if replied.get("message_id"):
        hit = ChatMessage.query.filter_by(tg_chat_id=chat_id, tg_message_id=replied["message_id"]).first()
        conv = hit.conversation if hit else None
    if conv is None:
        m = LEADING_CHAT.match(text)
        if not m:
            return False
        conv = db.session.get(ChatConversation, int(m.group(1)))
        text = m.group(2).strip()
        if conv is None:
            _say(chat_id, f"No website chat <code>CHAT-{int(m.group(1)):05d}</code> found.", message.get("message_id"))
            return True

    person = message.get("from") or {}
    who = person.get("username") and f"@{person['username']}" or person.get("first_name") or "team"
    db.session.add(ChatMessage(conversation=conv, sender="team", author=who[:120],
                               text=text[:current_app.config["CHAT_MAX_CHARS"] * 4]))
    conv.last_at = datetime.utcnow()
    db.session.commit()
    # a 👍 on the teammate's message: it reached the visitor's chat box
    try:
        api("setMessageReaction", timeout=8, chat_id=chat_id, message_id=message.get("message_id"),
            reaction=[{"type": "emoji", "emoji": "\U0001F44D"}])
    except TelegramError as err:
        log.info("chat: no reaction on the answer to %s: %s", conv.reference, err)
    return True


def _say(chat_id, html, reply_to):
    try:
        send_text(chat_id, html, reply_to=reply_to)
    except TelegramError as err:
        log.warning("chat: answer in %s failed: %s", chat_id, err)

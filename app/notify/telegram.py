"""Telegram: the Bot API calls, and the alerts for a new application and a new access request.

An alert goes to every panel user who linked Telegram (Panel → Settings) and kept Telegram alerts
on, plus the team group in TELEGRAM_CHAT_ID if one is set. Each chat gets the details as one
message, then the CV as a document. Replying to either one - or sending "AVX-00012 your message" -
emails the applicant (see app/bot).
"""
from html import escape

import requests
from flask import current_app

API = "https://api.telegram.org/bot{token}/{method}"
RULE = "━" * 15  # ━━━ separator, as in the call platform's bot


class TelegramError(RuntimeError):
    pass


def api(method, files=None, timeout=30, **params):
    """One Bot API call. Returns its `result`, or raises TelegramError with Telegram's reason."""
    token = current_app.config["TELEGRAM_BOT_TOKEN"]
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN is not set")
    url = API.format(token=token, method=method)
    try:
        if files:
            res = requests.post(url, data=params, files=files, timeout=timeout)
        else:
            res = requests.post(url, json=params, timeout=timeout)
    except requests.RequestException as err:
        raise TelegramError(f"{method}: {err.__class__.__name__}") from err
    try:
        body = res.json()
    except ValueError:
        body = {}
    if not body.get("ok"):
        raise TelegramError(f"{method}: {body.get('description', res.status_code)}")
    return body.get("result")


_usernames = {}


def bot_username():
    """The bot's @username (without @): TELEGRAM_BOT_USERNAME, else asked from Telegram once."""
    cfg = current_app.config
    if cfg["TELEGRAM_BOT_USERNAME"]:
        return cfg["TELEGRAM_BOT_USERNAME"]
    token = cfg["TELEGRAM_BOT_TOKEN"]
    if not token:
        return ""
    if token not in _usernames:
        try:
            _usernames[token] = (api("getMe", timeout=8) or {}).get("username", "")
        except TelegramError:
            return ""
    return _usernames[token]


def panel_url(path=""):
    base = current_app.config["PUBLIC_URL"]
    return f"{base}/panel{path}" if base else ""


def send_text(chat_id, html, buttons=None, reply_to=None):
    """Sends one HTML message. `buttons` is a list of (label, url) shown under it."""
    params = {"chat_id": chat_id, "text": html[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    # Telegram refuses link buttons that don't point at a public https address
    buttons = [(label, url) for label, url in (buttons or []) if url and url.startswith("https://")]
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": label, "url": url} for label, url in buttons]]}
    if reply_to:
        params["reply_to_message_id"] = reply_to
    return api("sendMessage", timeout=15, **params)


# ── the new-application alert ───────────────────────────────────────────────

def details(app):
    """The application as Telegram HTML, with how to answer the applicant."""
    ref = app.reference
    rows = [("Role", app.role), ("Name", app.name), ("Email", app.email)]
    for label, value in (("Phone", app.phone), ("Telegram", app.telegram), ("Link", app.link)):
        if value:
            rows.append((label, value))
    lines = [f"\U0001F4C4 <b>NEW APPLICATION · {ref}</b>", ""]
    lines += [f"<b>{label}:</b> {escape(value)}" for label, value in rows]
    if app.note:
        note = app.note if len(app.note) <= 2000 else app.note[:2000] + "…"
        lines += ["", RULE, "<b>NOTE</b>", escape(note)]
    lines += [
        "",
        RULE,
        "\U0001F4AC <b>REPLY TO THE APPLICANT</b>",
        "Reply to this message, or send:",
        f"<code>{ref} your message</code>",
        "They get it by email.",
    ]
    return "\n".join(lines)


def alert_chats():
    """[(chat_id, who)] to alert: linked panel users with Telegram alerts on, plus the group."""
    from ..models import AdminUser

    chats = {}
    group = current_app.config["TELEGRAM_CHAT_ID"]
    if group:
        chats[str(group)] = "team group"
    linked = AdminUser.query.filter(AdminUser.telegram_chat_id.isnot(None), AdminUser.telegram_chat_id != "")
    for admin in linked.filter_by(telegram_alerts=True):
        chats.setdefault(str(admin.telegram_chat_id), admin.email)
    return list(chats.items())


def send(app, cv_bytes):
    """The notify channel: alert every chat. Succeeds if at least one chat got it."""
    chats = alert_chats()
    if not chats:
        raise TelegramError(
            "no Telegram chat to send to: connect Telegram in Panel → Settings, or set TELEGRAM_CHAT_ID"
        )
    text = details(app)
    caption = f"\U0001F4CE <b>CV</b> · {escape(app.name)} · {app.reference}"
    button = [("Open in panel", panel_url(f"/applications/{app.id}"))]
    failures = []
    for chat_id, who in chats:
        try:
            send_text(chat_id, text, buttons=button)
            api("sendDocument", files={"document": (app.cv_name, cv_bytes)}, chat_id=chat_id,
                parse_mode="HTML", caption=caption)
        except TelegramError as err:
            current_app.logger.warning("telegram: alert for %s to %s failed: %s", app.reference, who, err)
            failures.append(f"{who}: {err}")
    if len(failures) == len(chats):
        raise TelegramError("; ".join(failures))


# ── the access-request alert ────────────────────────────────────────────────

def access_details(req):
    """An access request as Telegram HTML."""
    rows = [("Name", req.name), ("Company", req.organization), ("Email", req.email)]
    if req.phone:
        rows.append(("Phone", req.phone))
    if req.page:
        rows.append(("Sent from", req.page))
    use_case = req.use_case if len(req.use_case) <= 2000 else req.use_case[:2000] + "…"
    lines = [f"\U0001F511 <b>ACCESS REQUEST · {req.reference}</b>", ""]
    lines += [f"<b>{label}:</b> {escape(value)}" for label, value in rows]
    lines += ["", RULE, "<b>WHAT THEY WANT TO ROUTE</b>", escape(use_case), "", RULE,
              "\U0001F4AC Answer them by replying to the email alert."]
    return "\n".join(lines)


def send_access(req, _payload=None):
    """The access channel "telegram": alert every chat. Succeeds if at least one chat got it."""
    chats = alert_chats()
    if not chats:
        raise TelegramError(
            "no Telegram chat to send to: connect Telegram in Panel → Settings, or set TELEGRAM_CHAT_ID"
        )
    text = access_details(req)
    button = [("Open in panel", panel_url(f"/access/{req.id}"))]
    failures = []
    for chat_id, who in chats:
        try:
            send_text(chat_id, text, buttons=button)
        except TelegramError as err:
            current_app.logger.warning("telegram: alert for %s to %s failed: %s", req.reference, who, err)
            failures.append(f"{who}: {err}")
    if len(failures) == len(chats):
        raise TelegramError("; ".join(failures))

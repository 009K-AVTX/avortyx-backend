"""Sends the CV to TELEGRAM_CHAT_ID with sendDocument, details in the caption (HTML, max 1024
characters; longer details go first as a sendMessage)."""
from html import escape

import requests
from flask import current_app

API = "https://api.telegram.org/bot{token}/{method}"


def details(app):
    """The application as Telegram HTML."""
    lines = [f"<b>New application</b>: {escape(app.role)}", "", f"Name: {escape(app.name)}", f"Email: {escape(app.email)}"]
    for label, value in (("Phone", app.phone), ("Telegram", app.telegram), ("Link", app.link)):
        if value:
            lines.append(f"{label}: {escape(value)}")
    if app.note:
        lines += ["", "<b>Note</b>:", escape(app.note)]
    return "\n".join(lines)


def send(app, cv_bytes):
    cfg = current_app.config
    token, chat = cfg["TELEGRAM_BOT_TOKEN"], cfg["TELEGRAM_CHAT_ID"]
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set")

    def call(method, files=None, **data):
        res = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=30)
        body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        if not body.get("ok"):
            raise RuntimeError(f"{method}: {body.get('description', res.status_code)}")

    text = details(app)
    long = len(text) > 1024
    if long:
        call("sendMessage", chat_id=chat, parse_mode="HTML", text=text[:4000])
    caption = f"<b>CV</b>: {escape(app.name)}, {escape(app.role)}" if long else text
    call("sendDocument", files={"document": (app.cv_name, cv_bytes)}, chat_id=chat, parse_mode="HTML", caption=caption)

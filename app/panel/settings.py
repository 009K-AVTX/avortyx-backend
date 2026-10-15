"""Panel → Settings: each person's Telegram link and alerts, the email checks, and the setup status.

  GET  /panel/settings                         the page (settings.html)
  POST /panel/settings/telegram/connect        new one-time link; the page then waits for Start
  GET  /panel/settings/telegram/status         {"linked": true/false, "label": "@name"} for the waiting page
  POST /panel/settings/telegram/disconnect     unlink this person's Telegram
  POST /panel/settings/telegram/test           a test message to their Telegram
  POST /panel/settings/telegram/webhook        point the bot at PUBLIC_URL/telegram/webhook
  POST /panel/settings/alerts                  Telegram alerts / email alerts on or off
  POST /panel/settings/email/test              a test email to their own address

Same flow as the call platform's portal: Connect, tap the link, press Start, done.
"""
from flask import current_app, flash, redirect, render_template, request, url_for

from ..bot.linking import create_link, link_url, pending_link, unlink
from ..extensions import db
from ..notify import email as mail
from ..notify.telegram import TelegramError, api, bot_username, send_text
from . import bp
from .auth import check_csrf, current_admin, login_required


def _setup_status():
    """What is and isn't configured, for the card at the bottom of the page."""
    cfg = current_app.config
    status = {
        "token": bool(cfg["TELEGRAM_BOT_TOKEN"]),
        "bot": bot_username(),
        "group": cfg["TELEGRAM_CHAT_ID"],
        "public_url": cfg["PUBLIC_URL"],
        "secret": bool(cfg["TELEGRAM_WEBHOOK_SECRET"]),
        "webhook": None,
        "webhook_error": "",
        "smtp": mail.configured(),
        "smtp_from": cfg["SMTP_FROM"] or cfg["SMTP_USER"],
        "team_inbox": ", ".join(mail.team_inbox()),
        "confirmation": cfg["SEND_APPLICANT_CONFIRMATION"],
    }
    if status["token"]:
        try:
            info = api("getWebhookInfo", timeout=6) or {}
            status["webhook"] = info.get("url") or ""
            status["webhook_error"] = info.get("last_error_message", "")
        except TelegramError as err:
            status["webhook_error"] = str(err)
    return status


@bp.get("/settings")
@login_required
def settings():
    admin = current_admin()
    link = None if admin.telegram_linked else pending_link(admin)
    return render_template(
        "panel/settings.html",
        admin=admin,
        link=link,
        link_url=link_url(link) if link else "",
        setup=_setup_status(),
    )


@bp.post("/settings/telegram/connect")
@login_required
def telegram_connect():
    check_csrf()
    if not create_link(current_admin()):
        flash("The Telegram bot isn't set up on this server yet: TELEGRAM_BOT_TOKEN is missing or wrong.")
    return redirect(url_for("panel.settings") + "#telegram")


@bp.get("/settings/telegram/status")
@login_required
def telegram_status():
    admin = current_admin()
    db.session.refresh(admin)
    return {"linked": admin.telegram_linked, "label": admin.telegram_label}


@bp.post("/settings/telegram/disconnect")
@login_required
def telegram_disconnect():
    check_csrf()
    unlink(current_admin())
    flash("Telegram disconnected.")
    return redirect(url_for("panel.settings") + "#telegram")


@bp.post("/settings/telegram/test")
@login_required
def telegram_test():
    check_csrf()
    admin = current_admin()
    if not admin.telegram_linked:
        flash("Connect Telegram first.")
    else:
        try:
            send_text(admin.telegram_chat_id, "✅ <b>Test from the Avortyx panel</b>\nNew applications will arrive here.")
            flash("Test message sent to your Telegram.")
        except TelegramError as err:
            flash(f"Telegram refused the test: {err}")
    return redirect(url_for("panel.settings") + "#telegram")


@bp.post("/settings/telegram/webhook")
@login_required
def telegram_webhook():
    check_csrf()
    cfg = current_app.config
    base = cfg["PUBLIC_URL"]
    if not base.startswith("https://"):
        flash("Set PUBLIC_URL to this backend's https address (e.g. https://api.avortyx.com) in .env first.")
        return redirect(url_for("panel.settings") + "#setup")
    params = {"url": f"{base}/telegram/webhook", "allowed_updates": ["message"]}
    if cfg["TELEGRAM_WEBHOOK_SECRET"]:
        params["secret_token"] = cfg["TELEGRAM_WEBHOOK_SECRET"]
    try:
        api("setWebhook", timeout=10, **params)
        api("setMyCommands", timeout=10, commands=[
            {"command": "help", "description": "What this bot does"},
            {"command": "reply", "description": "Reply to an applicant: /reply AVX-00012 message"},
            {"command": "stop", "description": "Stop alerts and unlink this chat"},
        ])
        flash(f"Bot connected: Telegram now sends its messages to {params['url']}.")
    except TelegramError as err:
        flash(f"Telegram refused: {err}")
    return redirect(url_for("panel.settings") + "#setup")


@bp.post("/settings/alerts")
@login_required
def alerts():
    check_csrf()
    admin = current_admin()
    admin.telegram_alerts = request.form.get("telegram_alerts") == "on"
    admin.email_alerts = request.form.get("email_alerts") == "on"
    db.session.commit()
    flash("Alerts saved.")
    return redirect(url_for("panel.settings") + "#alerts")


@bp.post("/settings/email/test")
@login_required
def email_test():
    check_csrf()
    admin = current_admin()
    try:
        mail.send_test(admin.email)
        flash(f"Test email sent to {admin.email}.")
    except mail.EmailError as err:
        flash(f"Email failed: {err}")
    return redirect(url_for("panel.settings") + "#alerts")

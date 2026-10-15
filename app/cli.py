"""Command line (on the server: /srv/avortyx-backend/deploy/flask.sh <command>):

  create-admin you@avortyx.com    add (or reset) a panel login
  telegram-set-webhook            point the bot at PUBLIC_URL/telegram/webhook (run once after deploy)
  telegram-webhook-info           what Telegram knows about the webhook, and its last error
  telegram-delete-webhook         stop the webhook (needed before telegram-chat-id works)
  telegram-chat-id                list the chats the bot has heard from (for TELEGRAM_CHAT_ID)
  send-test-email you@x.com       check the SMTP settings
  chat-resend                     forward website chat messages that didn't reach the support group
"""
import click

from .extensions import db
from .models import AdminUser


def register(app):
    @app.cli.command("create-admin")
    @click.argument("email")
    @click.password_option()
    def create_admin(email, password):
        """Add a panel user, or set a new password for an existing one."""
        email = email.strip().lower()
        admin = AdminUser.query.filter_by(email=email).first() or AdminUser(email=email)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"{email} can now sign in at /panel/login")

    @app.cli.command("telegram-set-webhook")
    def telegram_set_webhook():
        """Tell Telegram to send the bot's messages to this backend."""
        from .notify.telegram import TelegramError, api, bot_username

        base = app.config["PUBLIC_URL"]
        if not base.startswith("https://"):
            raise click.ClickException("Set PUBLIC_URL in .env to this backend's https address first")
        params = {"url": f"{base}/telegram/webhook", "allowed_updates": ["message"]}
        if app.config["TELEGRAM_WEBHOOK_SECRET"]:
            params["secret_token"] = app.config["TELEGRAM_WEBHOOK_SECRET"]
        try:
            api("setWebhook", **params)
            api("setMyCommands", commands=[
                {"command": "help", "description": "What this bot does"},
                {"command": "reply", "description": "Reply to an applicant: /reply AVX-00012 message"},
                {"command": "stop", "description": "Stop alerts and unlink this chat"},
            ])
        except TelegramError as err:
            raise click.ClickException(str(err))
        click.echo(f"Webhook set: {params['url']}  (bot @{bot_username()})")

    @app.cli.command("telegram-webhook-info")
    def telegram_webhook_info():
        from .notify.telegram import TelegramError, api

        try:
            info = api("getWebhookInfo") or {}
        except TelegramError as err:
            raise click.ClickException(str(err))
        click.echo(f"url: {info.get('url') or '(none)'}")
        click.echo(f"pending updates: {info.get('pending_update_count', 0)}")
        if info.get("last_error_message"):
            click.echo(f"last error: {info['last_error_message']}")

    @app.cli.command("telegram-delete-webhook")
    def telegram_delete_webhook():
        from .notify.telegram import TelegramError, api

        try:
            api("deleteWebhook")
        except TelegramError as err:
            raise click.ClickException(str(err))
        click.echo("Webhook removed. Run telegram-set-webhook to turn the bot back on.")

    @app.cli.command("telegram-chat-id")
    def telegram_chat_id():
        """Add the bot to the group, send a message there, then run this (with the webhook removed)."""
        from .notify.telegram import TelegramError, api

        try:
            updates = api("getUpdates") or []
        except TelegramError as err:
            raise click.ClickException(
                f"{err}. If a webhook is set, run telegram-delete-webhook first, then set it again after."
            )
        chats = {}
        for update in updates:
            msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member") or {}
            if msg.get("chat"):
                chats[msg["chat"]["id"]] = msg["chat"]
        if not chats:
            click.echo("No chats yet. Send a message to the bot (or in the group with it), then run this again.")
        for c in chats.values():
            name = c.get("title") or " ".join(filter(None, [c.get("first_name"), c.get("last_name")]))
            click.echo(f"{c['id']}\t{c['type']}\t{name}" + (f" @{c['username']}" if c.get("username") else ""))

    @app.cli.command("chat-resend")
    def chat_resend():
        """Forward every website chat message that didn't reach the support group (for example,
        sent before the bot was added to it)."""
        from .chat.routes import forward
        from .models import ChatConversation, ChatMessage

        ids = {m.conversation_id for m in ChatMessage.query.filter_by(sender="visitor", tg_message_id=None)}
        if not ids:
            return click.echo("Nothing to resend: every chat message reached the support group.")
        done = sum(1 for cid in sorted(ids) if forward(db.session.get(ChatConversation, cid)))
        click.echo(f"Resent {done} of {len(ids)} chat(s)." + ("" if done == len(ids) else
                   " The rest still failed: is the bot in the group, and TELEGRAM_SUPPORT_CHAT_ID right? See the log."))

    @app.cli.command("send-test-email")
    @click.argument("to")
    def send_test_email(to):
        from .notify.email import EmailError, send_test

        try:
            send_test(to)
        except EmailError as err:
            raise click.ClickException(str(err))
        click.echo(f"Sent to {to}")

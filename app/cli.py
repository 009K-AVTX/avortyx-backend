"""Command line:
  flask --app wsgi create-admin you@avortyx.com   add (or reset) a panel login
  flask --app wsgi telegram-chat-id                list the chats the bot has heard from (TELEGRAM_CHAT_ID)
"""
import click
import requests

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

    @app.cli.command("telegram-chat-id")
    def telegram_chat_id():
        """Add the bot to the group (or press Start on it), send a message there, then run this."""
        token = app.config["TELEGRAM_BOT_TOKEN"]
        if not token:
            raise click.ClickException("Set TELEGRAM_BOT_TOKEN in .env first")
        out = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
        if not out.get("ok"):
            raise click.ClickException(f"Telegram said: {out.get('description')}")
        chats = {}
        for update in out["result"]:
            msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member") or {}
            if msg.get("chat"):
                chats[msg["chat"]["id"]] = msg["chat"]
        if not chats:
            click.echo("No chats yet. Send a message to the bot (or in the group with it), then run this again.")
        for c in chats.values():
            name = c.get("title") or " ".join(filter(None, [c.get("first_name"), c.get("last_name")]))
            click.echo(f"{c['id']}\t{c['type']}\t{name}" + (f" @{c['username']}" if c.get("username") else ""))

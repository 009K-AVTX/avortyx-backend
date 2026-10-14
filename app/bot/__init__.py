"""The Telegram bot: POST /telegram/webhook, which Telegram calls for every message to the bot."""
from flask import Blueprint

bp = Blueprint("bot", __name__)

from . import routes  # noqa: E402,F401

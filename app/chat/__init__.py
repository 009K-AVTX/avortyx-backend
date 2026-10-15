"""Public: the website's help chat, bridged to the team's support group on Telegram."""
from flask import Blueprint

bp = Blueprint("chat", __name__)

from . import routes  # noqa: E402,F401

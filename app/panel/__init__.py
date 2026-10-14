"""Admin panel: sign in, list applications, open one, download the CV, change its status, reply to
the applicant, and Settings (Telegram link, alerts, email checks)."""
from flask import Blueprint

bp = Blueprint("panel", __name__, template_folder="templates", static_folder="static")

from . import routes, settings  # noqa: E402,F401

"""Admin panel: sign in, list applications, open one, download the CV, change its status, reply to
the applicant; the same for access requests; and Settings (Telegram link, alerts, email checks)."""
from flask import Blueprint

bp = Blueprint("panel", __name__, template_folder="templates", static_folder="static")

from . import access, routes, settings  # noqa: E402,F401

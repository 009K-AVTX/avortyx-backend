"""Public: the endpoint the website's /request-access form posts to."""
from flask import Blueprint

bp = Blueprint("access", __name__)

from . import routes  # noqa: E402,F401

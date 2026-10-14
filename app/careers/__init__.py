"""Public: the endpoint the website's application form posts to."""
from flask import Blueprint

bp = Blueprint("careers", __name__)

from . import routes  # noqa: E402,F401

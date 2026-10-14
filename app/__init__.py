"""Builds the Flask app: config, extensions and the three parts of the backend.

- careers:  the public endpoint the website's application form posts to
- panel:    the admin panel where the team reviews applications and sets up Telegram / email
- telegram: the bot's webhook (/start linking, /help, replying to applicants from Telegram)
"""
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import cli
from .config import Config
from .extensions import cors, db


def create_app(config=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)
    # production (https cookies) must have its own key: anyone knowing it could forge a panel login
    if app.config["SESSION_COOKIE_SECURE"] and not app.testing and app.config["SECRET_KEY"] in ("dev", "change-me"):
        raise RuntimeError("Set SECRET_KEY in the environment before running in production")
    # behind a proxy (Render, Railway, nginx…) so redirects and secure cookies see https
    if app.config["BEHIND_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    # only the public careers endpoint is open to the website; the panel is same-origin and the
    # webhook is called by Telegram's servers, not a browser
    cors.init_app(app, resources={r"/careers/*": {"origins": app.config["CORS_ORIGINS"]}})

    from .bot import bp as bot_bp
    from .careers import bp as careers_bp
    from .panel import bp as panel_bp
    app.register_blueprint(careers_bp, url_prefix="/careers")
    app.register_blueprint(panel_bp, url_prefix="/panel")
    app.register_blueprint(bot_bp, url_prefix="/telegram")

    @app.get("/health")
    def health():
        return {"ok": True}

    cli.register(app)

    with app.app_context():
        from . import models  # noqa: F401  (registers the tables)
        from .schema import add_missing_columns
        db.create_all()
        add_missing_columns(db)

    return app

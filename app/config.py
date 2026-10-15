"""Settings, read from the environment (.env in development)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _list(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # panel sign-in cookie: https-only unless SESSION_COOKIE_SECURE=0 (plain-http local runs)
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1") != "0"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    BEHIND_PROXY = os.getenv("BEHIND_PROXY", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///avortyx.db")
    CORS_ORIGINS = _list("CORS_ORIGINS")

    # This backend's own public address, e.g. https://api.avortyx.com. Used for the Telegram
    # webhook and for "Open in panel" links in alerts and emails.
    PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
    # The website, linked from the emails applicants receive.
    SITE_URL = os.getenv("SITE_URL", "https://www.avortyx.com").rstrip("/")

    # ── Telegram bot ────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # the bot's @username, for the "Connect Telegram" link; read from Telegram if left empty
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    # the notification group: every application and access request, as well as the linked people
    # (TELEGRAM_CHAT_ID is the older name for it)
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_NOTIFY_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")
    # the team support group: the website's help chat is forwarded here, and replies to it go back
    # to the visitor's chat box (an id like -100..., or the group's @username if it is public)
    TELEGRAM_SUPPORT_CHAT_ID = os.getenv("TELEGRAM_SUPPORT_CHAT_ID", "")
    # Telegram sends this back on every webhook call, so nobody else can post to the webhook
    TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    TELEGRAM_LINK_TTL_MINUTES = int(os.getenv("TELEGRAM_LINK_TTL_MINUTES", "15"))

    # ── Website chat ────────────────────────────────────────────────────────
    CHAT_MAX_CHARS = int(os.getenv("CHAT_MAX_CHARS", "1000"))
    # new conversations one address may start per hour, and messages per conversation per 10 minutes
    CHAT_NEW_PER_HOUR = int(os.getenv("CHAT_NEW_PER_HOUR", "8"))
    CHAT_MESSAGES_PER_10_MIN = int(os.getenv("CHAT_MESSAGES_PER_10_MIN", "20"))

    # ── Email ───────────────────────────────────────────────────────────────
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Avortyx Careers")
    # who receives every application by email (comma-separated)
    CAREERS_EMAIL_TO = os.getenv("CAREERS_EMAIL_TO", "009k@avortyx.com")
    # where an applicant's "reply" goes; defaults to the first CAREERS_EMAIL_TO address
    CAREERS_REPLY_TO = os.getenv("CAREERS_REPLY_TO", "")
    # email the applicant a "we received your application" note
    SEND_APPLICANT_CONFIRMATION = os.getenv("SEND_APPLICANT_CONFIRMATION", "1") != "0"
    # answer the form first and send Telegram / email just after (0 = wait for them, as tests do)
    NOTIFY_IN_BACKGROUND = os.getenv("NOTIFY_IN_BACKGROUND", "1") != "0"

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    MAX_CV_BYTES = int(os.getenv("MAX_CV_BYTES", str(4 * 1024 * 1024)))
    # a little room above the CV for the other form fields
    MAX_CONTENT_LENGTH = MAX_CV_BYTES + 512 * 1024


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SESSION_COOKIE_SECURE = False
    UPLOAD_DIR = ""  # set per test to a temporary folder
    CORS_ORIGINS = ["https://avortyx-prototype.vercel.app"]
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    PUBLIC_URL = "https://api.example.test"
    SITE_URL = "https://avortyx.com"
    TELEGRAM_BOT_TOKEN = TELEGRAM_CHAT_ID = TELEGRAM_BOT_USERNAME = TELEGRAM_WEBHOOK_SECRET = ""
    TELEGRAM_SUPPORT_CHAT_ID = ""
    SMTP_HOST = SMTP_USER = SMTP_PASS = SMTP_FROM = ""
    CAREERS_EMAIL_TO = "hello@avortyx.io"
    CAREERS_REPLY_TO = ""
    SEND_APPLICANT_CONFIRMATION = True
    NOTIFY_IN_BACKGROUND = False  # the tests check what was sent right after each request

"""Settings, read from the environment (.env in development)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # panel sign-in cookie: https-only unless SESSION_COOKIE_SECURE=0 (plain-http local runs)
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1") != "0"
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    BEHIND_PROXY = os.getenv("BEHIND_PROXY", "0") == "1"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///avortyx.db")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    CAREERS_EMAIL_TO = os.getenv("CAREERS_EMAIL_TO", "hello@avortyx.io")

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
    TELEGRAM_BOT_TOKEN = TELEGRAM_CHAT_ID = SMTP_HOST = ""

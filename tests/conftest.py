"""Test fixtures: the app on an in-memory database, plus fakes for Telegram and the mail server so
every flow runs end to end without the network."""
import re

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.extensions import db
from app.models import AdminUser

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_DIR = str(tmp_path / "uploads")

    application = create_app(Cfg)
    with application.app_context():
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sent(monkeypatch):
    """Replaces Telegram and email with recorders; set sent.fail = {'telegram'} to make one fail."""
    from app import notify

    class Sent(list):
        fail = set()
    calls = Sent()

    def fake(name):
        def send(application, cv_bytes):
            if name in calls.fail:
                raise RuntimeError(f"{name} down")
            calls.append((name, application.name, len(cv_bytes)))
        return send
    monkeypatch.setattr(notify, "CHANNELS", {"telegram": fake("telegram"), "email": fake("email")})
    return calls


@pytest.fixture
def admin_client(app, client):
    with app.app_context():
        admin = AdminUser(email="team@avortyx.com")
        admin.set_password("secret-pass")
        db.session.add(admin)
        db.session.commit()
    client.get("/panel/login")
    with client.session_transaction() as s:
        token = s["csrf"]
    client.post("/panel/login", data={"email": "team@avortyx.com", "password": "secret-pass", "csrf": token})
    # signing in starts a fresh session, so the forms carry a new token from here on
    client.get("/panel/")
    with client.session_transaction() as s:
        client.csrf = s["csrf"]
    return client


def fresh(model, id_):
    """The row as the database has it now (requests run in their own sessions)."""
    _db.session.expire_all()
    return _db.session.get(model, id_)


class FakeTelegram:
    """Stands in for api.telegram.org: records every call, answers ok."""

    def __init__(self):
        self.calls = []
        self.fail_chats = set()
        self.webhook = {"url": ""}

    def __call__(self, url, json=None, data=None, files=None, timeout=None):
        method = url.rsplit("/", 1)[-1]
        params = dict(json or data or {})
        self.calls.append((method, params, files))
        if str(params.get("chat_id")) in self.fail_chats:
            return _Res({"ok": False, "description": "Forbidden: bot was blocked by the user"})
        result = True
        if method == "getMe":
            result = {"id": 1, "username": "AvortyxCareersBot"}
        elif method == "getWebhookInfo":
            result = dict(self.webhook, pending_update_count=0)
        elif method == "setWebhook":
            self.webhook = {"url": params["url"]}
        elif method in ("sendMessage", "sendDocument"):
            result = {"message_id": len(self.calls)}
        return _Res({"ok": True, "result": result})

    def sent(self, method=None, chat_id=None):
        return [p for m, p, _ in self.calls
                if (method is None or m == method) and (chat_id is None or str(p.get("chat_id")) == str(chat_id))]


class _Res:
    def __init__(self, body):
        self._body = body
        self.status_code = 200 if body.get("ok") else 400

    def json(self):
        return self._body


@pytest.fixture
def tg(app, monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr("app.notify.telegram.requests.post", fake)
    app.config.update(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_WEBHOOK_SECRET="s3cret")
    from app.notify import telegram

    telegram._usernames.clear()
    return fake


class FakeSMTP:
    sent = []
    fail = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        if FakeSMTP.fail:
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def mail(app, monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.fail = False
    monkeypatch.setattr("app.notify.email.smtplib.SMTP_SSL", FakeSMTP)
    monkeypatch.setattr("app.notify.email.smtplib.SMTP", FakeSMTP)
    app.config.update(SMTP_HOST="smtp.hostinger.com", SMTP_USER="careers@avortyx.com", SMTP_PASS="pw",
                      SMTP_FROM="careers@avortyx.com")
    return FakeSMTP


@pytest.fixture
def admin(app):
    from app.models import AdminUser

    a = AdminUser(email="kevin@avortyx.com")
    a.set_password("pw")
    _db.session.add(a)
    _db.session.commit()
    return a


def sign_in(client, email="kevin@avortyx.com", password="pw"):
    page = client.get("/panel/login").get_data(as_text=True)
    csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    client.post("/panel/login", data={"email": email, "password": password, "csrf": csrf})
    return csrf


def csrf_of(client, path="/panel/settings"):
    page = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def apply_form(**over):
    import io

    data = {"role": "Backend Engineer", "name": "Jane Wanjiru", "email": "jane@example.com",
            "phone": "+254700000000", "telegram": "@jane", "note": "I built <b>bots</b> before."}
    data.update(over)
    data["cv"] = (io.BytesIO(PDF), "cv.pdf")
    return data


def update(text, chat_id=555, chat_type="private", username="kev", reply_to=None):
    msg = {"message_id": 99, "text": text, "chat": {"id": chat_id, "type": chat_type},
           "from": {"id": chat_id, "username": username, "first_name": "Kevin"}}
    if reply_to is not None:
        msg["reply_to_message"] = reply_to
    return {"update_id": 1, "message": msg}


def hook(client, body, secret="s3cret"):
    return client.post("/telegram/webhook", json=body, headers={"X-Telegram-Bot-Api-Secret-Token": secret})

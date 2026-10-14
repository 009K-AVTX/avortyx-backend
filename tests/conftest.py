import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import AdminUser

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        UPLOAD_DIR = str(tmp_path / "uploads")
    return create_app(Config)


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

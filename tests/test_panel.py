import io

from app.extensions import db
from app.models import JobApplication

from .conftest import PDF


def apply(client):
    client.post("/careers/apply", data={"name": "Jo Test", "email": "jo@example.com", "role": "QA Lead", "cv": (io.BytesIO(PDF), "cv.pdf")},
                content_type="multipart/form-data")


def test_wrong_password_is_refused(client):
    client.get("/panel/login")
    with client.session_transaction() as s:
        token = s["csrf"]
    res = client.post("/panel/login", data={"email": "x@y.z", "password": "no", "csrf": token})
    assert b"don&#39;t match" in res.data


def test_list_open_download_and_status(app, admin_client, sent):
    apply(admin_client)
    assert b"Jo Test" in admin_client.get("/panel/").data
    with app.app_context():
        app_id = JobApplication.query.one().id
    assert b"QA Lead" in admin_client.get(f"/panel/applications/{app_id}").data
    cv = admin_client.get(f"/panel/applications/{app_id}/cv")
    assert cv.data == PDF and "CV - Jo Test.pdf" in cv.headers["Content-Disposition"]
    admin_client.post(f"/panel/applications/{app_id}/status", data={"status": "interview", "csrf": admin_client.csrf})
    with app.app_context():
        assert db.session.get(JobApplication, app_id).status == "interview"


def test_post_without_csrf_is_refused(app, admin_client, sent):
    apply(admin_client)
    with app.app_context():
        app_id = JobApplication.query.one().id
    assert admin_client.post(f"/panel/applications/{app_id}/status", data={"status": "hired"}).status_code == 400


def test_resend_failed_notifications(app, admin_client, sent):
    sent.fail = {"telegram"}
    apply(admin_client)
    with app.app_context():
        app_id = JobApplication.query.one().id
    sent.fail = set()
    sent.clear()
    admin_client.post(f"/panel/applications/{app_id}/notify", data={"csrf": admin_client.csrf})
    assert [c[0] for c in sent] == ["telegram"]  # email had already gone out
    with app.app_context():
        assert db.session.get(JobApplication, app_id).sent_telegram

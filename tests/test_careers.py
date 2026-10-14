import io

from app.models import JobApplication

from .conftest import PDF


def form(**over):
    data = {"role": "QA Lead", "name": "Jo Test", "email": "jo@example.com", "telegram": "@jo", "note": "Hello",
            "cv": (io.BytesIO(PDF), "my cv.pdf")}
    data.update(over)
    return data


def post(client, **over):
    return client.post("/careers/apply", data=form(**over), content_type="multipart/form-data",
                       headers={"Origin": "https://avortyx-prototype.vercel.app"})


def test_application_is_saved_and_sent(app, client, sent):
    res = post(client)
    assert res.status_code == 200 and res.get_json() == {"ok": True, "reference": "AVX-00001"}
    assert sorted(c[0] for c in sent) == ["email", "telegram"]
    with app.app_context():
        a = JobApplication.query.one()
        assert (a.role, a.name, a.cv_name, a.status) == ("QA Lead", "Jo Test", "CV - Jo Test.pdf", "new")
        assert a.sent_telegram and a.sent_email


def test_kept_even_when_both_notifications_fail(app, client, sent):
    sent.fail = {"telegram", "email"}
    assert post(client).status_code == 200
    with app.app_context():
        a = JobApplication.query.one()
        assert not a.sent_telegram and not a.sent_email


def test_errors_match_the_website_form(client, sent):
    assert post(client, name="").get_json()["error"] == "Please add your full name."
    assert post(client, email="nope").get_json()["error"] == "Please add a valid email address."
    assert post(client, cv=(io.BytesIO(b""), "")).get_json()["error"] == "Please attach your CV."
    assert post(client, cv=(io.BytesIO(b"not a pdf"), "cv.pdf")).get_json()["error"] == "Please attach your CV as a PDF or Word document."
    big = post(client, cv=(io.BytesIO(b"%PDF" + b"0" * (5 * 1024 * 1024)), "cv.pdf"))
    assert big.status_code == 413 and "over 4 MB" in big.get_json()["error"]
    assert sent == []


def test_honeypot_keeps_nothing(app, client, sent):
    assert post(client, company_site="spam.example").get_json() == {"ok": True}
    with app.app_context():
        assert JobApplication.query.count() == 0


def test_cors_for_the_website_only(client, sent):
    ok = post(client)
    assert ok.headers.get("Access-Control-Allow-Origin") == "https://avortyx-prototype.vercel.app"
    res = client.options("/careers/apply", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert res.headers.get("Access-Control-Allow-Origin") is None

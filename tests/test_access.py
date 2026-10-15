"""The request-access form: saved, the team alerted on Telegram and by email, the requester
confirmed, and the request reviewed in the panel."""
from app.extensions import db
from app.models import AccessRequest

from .conftest import fresh

ORIGIN = "https://avortyx-prototype.vercel.app"


def form(**over):
    data = {"name": "Amina Odhiambo", "organization": "Lakeside Leads", "email": "amina@lakeside.example",
            "phone": "+254711000000", "use_case": "Final expense and <b>Medicare</b> calls, about 3k a month.",
            "page": "https://www.avortyx.com/request-access"}
    data.update(over)
    return data


def test_request_is_saved_alerted_and_confirmed(client, tg, mail, admin, app):
    admin.telegram_chat_id = "555"
    db.session.commit()

    res = client.post("/access/request", data=form(), headers={"Origin": ORIGIN})
    assert res.status_code == 200
    assert res.get_json() == {"ok": True, "reference": "REQ-00001"}
    assert res.headers["Access-Control-Allow-Origin"] == ORIGIN

    r = AccessRequest.query.one()
    assert (r.organization, r.status) == ("Lakeside Leads", "new")
    assert r.sent_telegram and r.sent_email and r.sent_confirmation

    msg = tg.sent("sendMessage", "555")[0]
    assert "ACCESS REQUEST · REQ-00001" in msg["text"] and "Lakeside Leads" in msg["text"]
    assert "&lt;b&gt;Medicare&lt;/b&gt;" in msg["text"]  # the requester's text is escaped
    assert msg["reply_markup"]["inline_keyboard"][0][0]["url"].endswith("/panel/access/1")
    assert not tg.sent("sendDocument")

    team, confirm = sorted(mail.sent, key=lambda m: m["To"] != "hello@avortyx.io")
    assert team["Subject"] == "Access request: Lakeside Leads — Amina Odhiambo (REQ-00001)"
    assert "amina@lakeside.example" in team["Reply-To"] and team["From"].startswith("Avortyx <")
    assert confirm["To"] == "amina@lakeside.example" and "REQ-00001" in confirm["Subject"]
    assert "Hi Amina," in confirm.get_body(("plain",)).get_content()


def test_missing_fields_get_the_forms_own_messages(client):
    cases = [({"name": ""}, "Please add your full name."),
             ({"organization": " "}, "Please add your company."),
             ({"email": "amina@"}, "Please add a valid work email."),
             ({"use_case": ""}, "Please tell us what you are looking to route.")]
    for over, message in cases:
        res = client.post("/access/request", data=form(**over))
        assert res.status_code == 400 and res.get_json() == {"error": message}
    assert AccessRequest.query.count() == 0


def test_honeypot_keeps_nothing(client, sent):
    assert client.post("/access/request", data=form(website="spam.example")).get_json() == {"ok": True}
    assert AccessRequest.query.count() == 0


def test_long_fields_are_cut_not_refused(client, tg, mail):
    client.post("/access/request", data=form(use_case="x" * 5000, organization="y" * 500))
    r = AccessRequest.query.one()
    assert len(r.use_case) == 3000 and len(r.organization) == 200


def test_a_failed_channel_is_kept_for_the_panel(client, tg, mail):
    mail.fail = True
    client.post("/access/request", data=form())
    r = AccessRequest.query.one()
    assert not r.sent_email and not r.sent_confirmation and not r.sent_telegram  # no chat linked either


def test_panel_lists_opens_moves_and_resends(app, admin_client, tg, mail):
    mail.fail = True
    admin_client.post("/access/request", data=form())
    req_id = AccessRequest.query.one().id

    assert b"Lakeside Leads" in admin_client.get("/panel/access").data
    page = admin_client.get(f"/panel/access/{req_id}").get_data(as_text=True)
    assert "REQ-00001" in page and "Medicare" in page and "Send again" in page

    admin_client.post(f"/panel/access/{req_id}/status", data={"status": "approved", "csrf": admin_client.csrf})
    assert fresh(AccessRequest, req_id).status == "approved"
    assert b"approved" in admin_client.get("/panel/access?status=approved").data

    mail.fail = False
    admin_client.post(f"/panel/access/{req_id}/notify", data={"csrf": admin_client.csrf})
    r = fresh(AccessRequest, req_id)
    assert r.sent_email and r.sent_confirmation


def test_panel_pages_need_sign_in(client):
    assert client.get("/panel/access").status_code == 302

"""End to end: an application comes in, the team hears about it on Telegram and by email, links
Telegram from the panel, and replies to the applicant from Telegram and from the panel."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models import AdminUser, ApplicationReply, JobApplication, TelegramLinkCode

from .conftest import apply_form, csrf_of, fresh, hook, sign_in, update


# ── applying ────────────────────────────────────────────────────────────────

def test_apply_alerts_everyone_and_confirms(client, tg, mail, admin, app):
    admin.telegram_chat_id = "555"
    db.session.commit()
    app.config["TELEGRAM_CHAT_ID"] = "-100777"

    res = client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True, "reference": "AVX-00001"}

    a = JobApplication.query.one()
    assert a.sent_telegram and a.sent_email and a.sent_confirmation

    # Telegram: the group and the linked person each get the details, then the CV
    for chat in ("-100777", "555"):
        msgs = tg.sent("sendMessage", chat)
        assert len(msgs) == 1 and "NEW APPLICATION · AVX-00001" in msgs[0]["text"]
        assert "&lt;b&gt;bots&lt;/b&gt;" in msgs[0]["text"]  # applicant text is escaped
        assert msgs[0]["reply_markup"]["inline_keyboard"][0][0]["url"].endswith("/panel/applications/1")
        assert len(tg.sent("sendDocument", chat)) == 1

    # Email: team alert with the CV, and the applicant's confirmation
    team, confirm = sorted(mail.sent, key=lambda m: m["To"] != "hello@avortyx.io")
    assert team["To"] == "hello@avortyx.io" and "AVX-00001" in team["Subject"]
    assert "jane@example.com" in team["Reply-To"]
    assert [p.get_filename() for p in team.iter_attachments()] == ["CV - Jane Wanjiru.pdf"]
    assert confirm["To"] == "jane@example.com" and confirm["Reply-To"] == "hello@avortyx.io"
    html = confirm.get_body(("html",)).get_content()
    assert "AVX-00001" in html and "AVORTYX" in html


def test_apply_answers_first_and_sends_in_background(client, tg, mail, admin, app, monkeypatch):
    import threading

    started = []

    class Recorded(threading.Thread):
        def start(self):
            started.append(self)
            super().start()
    monkeypatch.setattr("app.notify.threading.Thread", Recorded)
    admin.telegram_chat_id = "555"
    db.session.commit()
    app.config["NOTIFY_IN_BACKGROUND"] = True

    res = client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    assert res.get_json() == {"ok": True, "reference": "AVX-00001"}

    jobs = [t for t in started if t.name.startswith("notify-")]  # not the senders' own threads
    assert len(jobs) == 1
    jobs[0].join(timeout=10)
    db.session.expire_all()
    a = JobApplication.query.one()
    assert a.sent_telegram and a.sent_email and a.sent_confirmation
    assert tg.sent("sendDocument", "555") and len(mail.sent) == 2


def test_one_blocked_chat_does_not_fail_telegram(client, tg, mail, admin, app):
    admin.telegram_chat_id = "555"
    db.session.commit()
    app.config["TELEGRAM_CHAT_ID"] = "-100777"
    tg.fail_chats = {"555"}
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    assert JobApplication.query.one().sent_telegram


def test_no_telegram_chat_is_reported(client, tg, mail):
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    a = JobApplication.query.one()
    assert not a.sent_telegram and a.sent_email


def test_email_alerts_opt_in_adds_the_person(client, tg, mail, admin):
    admin.email_alerts = True
    db.session.commit()
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    team = [m for m in mail.sent if "Application:" in m["Subject"]][0]
    assert team["To"] == "hello@avortyx.io, kevin@avortyx.com"


def test_telegram_alerts_off_skips_the_person(client, tg, mail, admin, app):
    admin.telegram_chat_id, admin.telegram_alerts = "555", False
    db.session.commit()
    app.config["TELEGRAM_CHAT_ID"] = "-100777"
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    assert not tg.sent("sendMessage", "555") and tg.sent("sendMessage", "-100777")


# ── linking Telegram from the panel ─────────────────────────────────────────

def test_connect_telegram_from_settings(client, tg, mail, admin):
    sign_in(client)
    csrf = csrf_of(client)
    client.post("/panel/settings/telegram/connect", data={"csrf": csrf})
    page = client.get("/panel/settings").get_data(as_text=True)
    code = TelegramLinkCode.query.one().code
    assert f"https://t.me/AvortyxCareersBot?start={code}" in page
    assert client.get("/panel/settings/telegram/status").get_json()["linked"] is False

    hook(client, update(f"/start {code}"))
    assert client.get("/panel/settings/telegram/status").get_json() == {"linked": True, "label": "@kev"}
    assert "Linked!" in tg.sent("sendMessage", 555)[-1]["text"]
    assert "Connected as <b>@kev</b>" in client.get("/panel/settings").get_data(as_text=True)

    # the same code can't be used twice
    hook(client, update(f"/start {code}", chat_id=999))
    assert "expired" in tg.sent("sendMessage", 999)[-1]["text"]


def test_expired_code_and_group_start(client, tg, admin):
    db.session.add(TelegramLinkCode(admin_id=admin.id, code="old", expires_at=datetime.utcnow() - timedelta(minutes=1)))
    db.session.commit()
    hook(client, update("/start old"))
    assert "expired" in tg.sent("sendMessage", 555)[-1]["text"]
    hook(client, update("/start old", chat_id=-100, chat_type="group"))
    assert "private chat" in tg.sent("sendMessage", -100)[-1]["text"]
    assert fresh(AdminUser, admin.id).telegram_chat_id is None


def test_help_start_stop(client, tg, admin):
    hook(client, update("/help"))
    assert "CAREERS BOT" in tg.sent("sendMessage", 555)[-1]["text"]
    hook(client, update("/start"))
    assert "Welcome" in tg.sent("sendMessage", 555)[-1]["text"]
    admin.telegram_chat_id = "555"
    db.session.commit()
    hook(client, update("/stop"))
    assert "Unlinked" in tg.sent("sendMessage", 555)[-1]["text"]
    assert fresh(AdminUser, admin.id).telegram_chat_id is None


def test_webhook_needs_the_secret(client, tg):
    assert hook(client, update("/help"), secret="wrong").status_code == 403
    assert hook(client, update("/help"), secret="").status_code == 403
    assert not tg.sent("sendMessage")


def test_command_for_another_bot_is_ignored(client, tg):
    hook(client, update("/help@SomeOtherBot", chat_type="group", chat_id=-5))
    assert not tg.sent("sendMessage", -5)
    hook(client, update("/help@AvortyxCareersBot", chat_type="group", chat_id=-5))
    assert tg.sent("sendMessage", -5)


# ── replying to the applicant ───────────────────────────────────────────────

def _one_application(client):
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    return JobApplication.query.one()


def test_reply_from_telegram_three_ways(client, tg, mail, admin, app):
    admin.telegram_chat_id = "555"
    db.session.commit()
    app.config["TELEGRAM_CHAT_ID"] = "-100777"
    a = _one_application(client)
    mail.sent.clear()

    # 1. "AVX-00001 message" in the private chat
    hook(client, update("AVX-00001 Thanks Jane, can you talk Friday?"))
    # 2. a reply to the alert message
    alert = tg.sent("sendMessage", "555")[0]["text"]
    hook(client, update("Great, see you then.", reply_to={"text": alert}))
    # 3. /reply in the notification group (works with the bot's group privacy on)
    hook(client, update("/reply AVX-00001 From the group", chat_id=-100777, chat_type="supergroup", username="mary"))

    replies = ApplicationReply.query.order_by(ApplicationReply.id).all()
    assert [r.body for r in replies] == ["Thanks Jane, can you talk Friday?", "Great, see you then.", "From the group"]
    assert [r.sent_by for r in replies] == ["kevin@avortyx.com", "kevin@avortyx.com", "@mary (notification group)"]
    assert all(r.emailed and r.via == "telegram" for r in replies)
    assert [m["To"] for m in mail.sent] == ["jane@example.com"] * 3
    assert "AVX-00001" in mail.sent[0]["Subject"]
    assert "Sent to Jane Wanjiru" in tg.sent("sendMessage", "555")[-1]["text"]


def test_strangers_cannot_reply(client, tg, mail, admin):
    _one_application(client)
    mail.sent.clear()
    hook(client, update("AVX-00001 I am not on the team", chat_id=4242))
    assert ApplicationReply.query.count() == 0 and not mail.sent
    assert "Only linked team members" in tg.sent("sendMessage", 4242)[-1]["text"]


def test_reply_to_unknown_reference(client, tg, admin):
    admin.telegram_chat_id = "555"
    db.session.commit()
    hook(client, update("AVX-00042 hello"))
    assert "No application" in tg.sent("sendMessage", 555)[-1]["text"]


def test_reply_email_failure_is_saved_and_reported(client, tg, mail, admin):
    admin.telegram_chat_id = "555"
    db.session.commit()
    _one_application(client)
    mail.fail = True
    hook(client, update("AVX-00001 hello"))
    r = ApplicationReply.query.one()
    assert not r.emailed and "SMTPAuthenticationError" in r.error
    assert "Couldn't email" in tg.sent("sendMessage", 555)[-1]["text"]


def test_reply_from_panel_and_history(client, tg, mail, admin):
    _one_application(client)
    mail.sent.clear()
    sign_in(client)
    csrf = csrf_of(client, "/panel/applications/1")
    res = client.post("/panel/applications/1/reply", data={"csrf": csrf, "message": "Hi Jane, welcome aboard"},
                      follow_redirects=True)
    page = res.get_data(as_text=True)
    assert "Emailed to jane@example.com" in page and "Hi Jane, welcome aboard" in page and "via panel" in page
    assert mail.sent[0]["To"] == "jane@example.com"


# ── panel settings ──────────────────────────────────────────────────────────

def test_settings_alerts_and_tests(client, tg, mail, admin):
    sign_in(client)
    csrf = csrf_of(client)
    client.post("/panel/settings/alerts", data={"csrf": csrf, "email_alerts": "on"})
    a = fresh(AdminUser, admin.id)
    assert a.email_alerts and not a.telegram_alerts

    res = client.post("/panel/settings/email/test", data={"csrf": csrf}, follow_redirects=True)
    assert "Test email sent" in res.get_data(as_text=True) and mail.sent[-1]["To"] == "kevin@avortyx.com"

    a.telegram_chat_id = "555"
    db.session.commit()
    client.post("/panel/settings/telegram/test", data={"csrf": csrf})
    assert "Test from the Avortyx panel" in tg.sent("sendMessage", "555")[-1]["text"]

    client.post("/panel/settings/telegram/disconnect", data={"csrf": csrf})
    assert fresh(AdminUser, admin.id).telegram_chat_id is None


def test_settings_connects_the_webhook(client, tg, mail, admin):
    sign_in(client)
    page = client.get("/panel/settings").get_data(as_text=True)
    assert "@AvortyxCareersBot" in page and "press the button below" in page
    client.post("/panel/settings/telegram/webhook", data={"csrf": csrf_of(client)})
    set_call = tg.sent("setWebhook")[-1]
    assert set_call == {"url": "https://api.example.test/telegram/webhook", "allowed_updates": ["message"],
                        "secret_token": "s3cret"}
    assert "yes</span> · https://api.example.test/telegram/webhook" in client.get("/panel/settings").get_data(as_text=True)


def test_settings_without_bot(client, admin):
    sign_in(client)
    page = client.get("/panel/settings").get_data(as_text=True)
    assert "isn't set up on this server yet" in page and "TELEGRAM_BOT_TOKEN not set" in page


# ── command line (used by the setup guide) ──────────────────────────────────

def test_cli_set_webhook_and_test_email(app, tg, mail):
    runner = app.test_cli_runner()
    out = runner.invoke(args=["telegram-set-webhook"])
    assert out.exit_code == 0, out.output
    assert "Webhook set: https://api.example.test/telegram/webhook" in out.output
    assert tg.sent("setWebhook")[-1]["secret_token"] == "s3cret"
    assert [c["command"] for c in tg.sent("setMyCommands")[-1]["commands"]] == ["help", "reply", "stop"]

    out = runner.invoke(args=["send-test-email", "kevin@avortyx.com"])
    assert out.exit_code == 0 and mail.sent[-1]["To"] == "kevin@avortyx.com"


def test_cli_set_webhook_needs_https_public_url(app, tg):
    app.config["PUBLIC_URL"] = "http://localhost:5055"
    out = app.test_cli_runner().invoke(args=["telegram-set-webhook"])
    assert out.exit_code != 0 and "PUBLIC_URL" in out.output

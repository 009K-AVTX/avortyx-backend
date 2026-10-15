"""The website's help chat: the visitor's messages reach the support group on Telegram, and the
team's replies there come back to the visitor's chat box."""
from app.extensions import db
from app.models import ChatConversation, ChatMessage

from .conftest import hook, update

ORIGIN = "https://avortyx-prototype.vercel.app"
SUPPORT = "-100888"


def start(client, text="Hi, how do I port my numbers?", **over):
    body = {"text": text, "agent": "jordan", "intent": "support", "page": "https://www.avortyx.com/pricing"}
    body.update(over)
    return client.post("/chat/messages", json=body, headers={"Origin": ORIGIN})


def test_chat_goes_to_the_support_group_and_answers_come_back(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT, TELEGRAM_CHAT_ID="-100777")

    res = start(client, text="Hi, how do I port my <numbers>?")
    assert res.status_code == 200 and res.headers["Access-Control-Allow-Origin"] == ORIGIN
    data = res.get_json()
    assert data["ok"] and data["conversation"] == 1 and data["message"]["from"] == "me"
    cid, token = data["conversation"], data["token"]

    # forwarded to the support group only, never the notification group
    first = tg.sent("sendMessage", SUPPORT)[0]
    assert "New Support Chat</b> · CHAT-00001" in first["text"] and "Asked for: Jordan Kim · Solutions engineer (support)" in first["text"]
    assert "<b>Message:</b> Hi, how do I port my &lt;numbers&gt;?" in first["text"] and "Page: https://www.avortyx.com/pricing" in first["text"]
    assert "\U0001F464 Visitor " in first["text"] and "<code>CHAT-00001 your reply here</code>" in first["text"]
    assert not tg.sent("sendMessage", "-100777")

    # a second message is short
    client.post("/chat/messages", json={"conversation": cid, "token": token, "text": "We do 2k calls a day"})
    second = tg.sent("sendMessage", SUPPORT)[1]
    visitor = first["text"].split("\U0001F464 ")[1].split("\n")[0]
    assert second["text"].startswith(f"\U0001F4AC <b>{visitor}</b> · CHAT-00001\n<b>Message:</b> We do 2k calls a day\n")

    # a teammate replies to the first forwarded message in the group
    fwd_id = ChatMessage.query.filter_by(sender="visitor").first().tg_message_id
    hook(client, update("Happy to help! Send me your carrier name.", chat_id=int(SUPPORT), chat_type="supergroup",
                        reply_to={"message_id": fwd_id, "text": first["text"]}))
    assert tg.sent("setMessageReaction")[0]["message_id"] == 99

    msgs = client.get(f"/chat/{cid}/messages?token={token}&after=0").get_json()["messages"]
    assert [(m["from"], m["text"]) for m in msgs] == [
        ("me", "Hi, how do I port my <numbers>?"), ("me", "We do 2k calls a day"),
        ("team", "Happy to help! Send me your carrier name.")]
    after = msgs[1]["id"]
    assert [m["text"] for m in client.get(f"/chat/{cid}/messages?token={token}&after={after}").get_json()["messages"]] \
        == ["Happy to help! Send me your carrier name."]
    team = ChatMessage.query.filter_by(sender="team").one()
    assert team.author == "@kev"


def test_answer_by_reference(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT)
    data = start(client).get_json()
    hook(client, update("CHAT-00001 Yes, we support that", chat_id=int(SUPPORT), chat_type="supergroup"))
    msgs = client.get(f"/chat/{data['conversation']}/messages?token={data['token']}").get_json()["messages"]
    assert msgs[-1] == {**msgs[-1], "from": "team", "text": "Yes, we support that"}

    hook(client, update("CHAT-00042 hello", chat_id=int(SUPPORT), chat_type="supergroup"))
    assert "No website chat <code>CHAT-00042</code>" in tg.sent("sendMessage", SUPPORT)[-1]["text"]


def test_public_group_username_is_matched(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID="@Avortyx_Sup")
    data = start(client).get_json()
    assert tg.sent("sendMessage", "@Avortyx_Sup")
    body = update("CHAT-1 On it", chat_id=-100999, chat_type="supergroup")
    body["message"]["chat"]["username"] = "Avortyx_Sup"
    hook(client, body)
    assert ChatMessage.query.filter_by(conversation_id=data["conversation"], sender="team").count() == 1


def test_only_the_team_groups_can_answer(client, tg, app, admin):
    # the support and notification groups may answer visitors; a private chat or another group can't
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT, TELEGRAM_CHAT_ID="-100777")
    data = start(client).get_json()
    for chat_id, kind in ((555, "private"), (-100123, "group")):
        hook(client, update("CHAT-00001 sneaky", chat_id=chat_id, chat_type=kind))
    assert ChatMessage.query.filter_by(conversation_id=data["conversation"], sender="team").count() == 0


def test_token_is_needed_to_read_or_write(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT)
    data = start(client).get_json()
    assert client.get(f"/chat/{data['conversation']}/messages?token=wrong").status_code == 404
    assert client.get(f"/chat/{data['conversation']}/messages").status_code == 404
    res = client.post("/chat/messages", json={"conversation": data["conversation"], "token": "wrong", "text": "hi"})
    assert res.status_code == 404 and "start a new one" in res.get_json()["error"]


def test_unsent_messages_go_with_the_next_one(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT)
    tg.fail_chats.add(SUPPORT)
    data = start(client, text="first").get_json()
    assert data["ok"]  # saved even though Telegram refused it
    tg.fail_chats.clear()
    client.post("/chat/messages", json={"conversation": data["conversation"], "token": data["token"], "text": "second"})
    texts = [m["text"] for m in tg.sent("sendMessage", SUPPORT) if "first" in m["text"] or "second" in m["text"]]
    # the failed attempt, then both, the first one with the whole picture
    assert "New Support Chat" in texts[-2] and "first" in texts[-2] and "Message:</b> second" in texts[-1]
    assert ChatMessage.query.filter(ChatMessage.tg_message_id.is_(None)).count() == 0


def test_checks_limits_and_honeypot(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT, CHAT_NEW_PER_HOUR=2, CHAT_MESSAGES_PER_10_MIN=2)
    assert client.post("/chat/messages", json={"text": "  "}).status_code == 400
    assert client.post("/chat/messages", json={"text": "x" * 1001}).status_code == 400
    assert client.post("/chat/messages", json={"text": "hi", "website": "spam"}).get_json() == {"ok": True}
    assert ChatConversation.query.count() == 0

    data = start(client).get_json()
    client.post("/chat/messages", json={"conversation": data["conversation"], "token": data["token"], "text": "2"})
    res = client.post("/chat/messages", json={"conversation": data["conversation"], "token": data["token"], "text": "3"})
    assert res.status_code == 429
    start(client)
    assert start(client).status_code == 429


def test_without_support_group_messages_are_kept(client, tg, app):
    data = start(client).get_json()
    assert data["ok"] and not tg.sent("sendMessage")
    assert db.session.get(ChatConversation, data["conversation"]).messages[0].tg_message_id is None


def test_chatid_command(client, tg):
    hook(client, update("/chatid", chat_id=-100555, chat_type="supergroup"))
    assert tg.sent("sendMessage", "-100555")[0]["text"] == "This chat's id: <code>-100555</code>"


def test_group_settings_and_topic_links():
    from app.notify.telegram import destination, is_chat

    assert destination("https://t.me/Avortyx_Sup/284") == ("@Avortyx_Sup", 284)
    assert destination("t.me/c/2049812345/285") == ("-1002049812345", 285)
    assert destination("@Avortyx_Sup") == ("@Avortyx_Sup", None)
    assert destination("-100777/12") == ("-100777", 12)
    assert destination("-100777") == ("-100777", None)
    assert destination("") == ("", None)
    assert is_chat("https://t.me/Avortyx_Sup/284", {"id": -1001, "username": "avortyx_sup"})
    assert is_chat("t.me/c/2049812345/285", {"id": -1002049812345})
    assert not is_chat("https://t.me/Avortyx_Sup/284", {"id": -1001, "username": "other"})


def test_support_and_notifications_in_two_topics_of_one_group(client, tg, app, admin):
    from .conftest import apply_form
    # the same group, two topics, as on t.me/Avortyx_Sup
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID="https://t.me/Avortyx_Sup/284",
                      TELEGRAM_CHAT_ID="https://t.me/Avortyx_Sup/285")
    data = start(client).get_json()
    fwd = tg.sent("sendMessage", "@Avortyx_Sup")[0]
    assert fwd["message_thread_id"] == 284 and "New Support Chat" in fwd["text"]

    # an access request lands in the notifications topic
    client.post("/access/request", data={"name": "Amina", "organization": "Lakeside", "email": "a@lakeside.example",
                                         "use_case": "Medicare calls"})
    alert = [m for m in tg.sent("sendMessage", "@Avortyx_Sup") if "ACCESS REQUEST" in m["text"]][0]
    assert alert["message_thread_id"] == 285
    # an application's CV goes to the same topic
    client.post("/careers/apply", data=apply_form(), content_type="multipart/form-data")
    assert tg.sent("sendDocument", "@Avortyx_Sup")[0]["message_thread_id"] == 285

    # the team answers in the support topic: replies to the forwarded message, or /reply CHAT-…
    body = update("/reply CHAT-00001 We can port them in 48h", chat_id=-1001, chat_type="supergroup")
    body["message"].update(chat={"id": -1001, "type": "supergroup", "username": "Avortyx_Sup", "is_forum": True},
                           message_thread_id=284, is_topic_message=True,
                           reply_to_message={"message_id": 284, "text": ""})  # the topic itself
    hook(client, body)
    msgs = client.get(f"/chat/{data['conversation']}/messages?token={data['token']}").get_json()["messages"]
    assert msgs[-1]["from"] == "team" and msgs[-1]["text"] == "We can port them in 48h"


def test_chatid_in_a_topic(client, tg):
    body = update("/chatid", chat_id=-100555, chat_type="supergroup")
    body["message"].update(message_thread_id=284, is_topic_message=True)
    hook(client, body)
    assert tg.sent("sendMessage", "-100555")[0]["text"] == "This chat's id: <code>-100555/284</code> (this topic)"


def test_bot_not_in_group_yet_nothing_breaks_and_messages_catch_up(client, tg, app):
    from datetime import datetime, timedelta

    # deployed before the bot was added to the group: Telegram refuses, the visitor's chat still works
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT)
    tg.fail_chats.add(SUPPORT)
    data = start(client, text="anyone there?").get_json()
    assert data["ok"]
    url = f"/chat/{data['conversation']}/messages?token={data['token']}"
    assert client.get(url).status_code == 200

    # the bot is added; the visitor's open chat box retries once the minute is up
    tg.fail_chats.clear()
    client.get(url)
    assert not [m for m in tg.sent("sendMessage", SUPPORT) if "anyone there?" in m["text"]][1:]  # not yet
    conv = db.session.get(ChatConversation, data["conversation"])
    conv.forward_tried_at = datetime.utcnow() - timedelta(minutes=2)
    db.session.commit()
    client.get(url)
    assert ChatMessage.query.filter(ChatMessage.tg_message_id.is_(None)).count() == 0


def test_chat_resend_command(client, tg, app):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT)
    tg.fail_chats.add(SUPPORT)
    start(client, text="one")
    start(client, text="two")
    runner = app.test_cli_runner()
    assert "Resent 0 of 2 chat(s). The rest still failed" in runner.invoke(args=["chat-resend"]).output
    tg.fail_chats.clear()
    assert "Resent 2 of 2 chat(s)." in runner.invoke(args=["chat-resend"]).output
    assert "Nothing to resend" in runner.invoke(args=["chat-resend"]).output

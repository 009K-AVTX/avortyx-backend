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
    assert "WEBSITE CHAT · CHAT-00001" in first["text"] and "Jordan Kim · Solutions engineer (support)" in first["text"]
    assert "port my &lt;numbers&gt;?" in first["text"] and "/pricing" in first["text"]
    assert not tg.sent("sendMessage", "-100777")

    # a second message is short
    client.post("/chat/messages", json={"conversation": cid, "token": token, "text": "We do 2k calls a day"})
    second = tg.sent("sendMessage", SUPPORT)[1]
    assert second["text"] == "\U0001F4AC <b>CHAT-00001</b>\nWe do 2k calls a day"

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


def test_only_the_support_group_can_answer(client, tg, app, admin):
    app.config.update(TELEGRAM_SUPPORT_CHAT_ID=SUPPORT, TELEGRAM_CHAT_ID="-100777")
    data = start(client).get_json()
    for chat_id, kind in ((-100777, "supergroup"), (555, "private"), (-100123, "group")):
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
    assert "WEBSITE CHAT" in texts[-2] and "first" in texts[-2] and texts[-1].endswith("second")
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

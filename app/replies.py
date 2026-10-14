"""Answering an applicant. One function for both ways in - the panel's reply box and a reply sent to
the bot in Telegram - so the applicant always gets the same email and the panel keeps one history.
"""
from .extensions import db
from .models import ApplicationReply
from .notify.email import EmailError, send_reply

MAX_REPLY = 4000


def reply_to_applicant(application, message, sent_by, via):
    """Emails the applicant and records it. Returns the ApplicationReply (check .emailed / .error)."""
    message = (message or "").strip()[:MAX_REPLY]
    if not message:
        raise ValueError("The message is empty.")
    reply = ApplicationReply(application_id=application.id, body=message, sent_by=sent_by[:200], via=via)
    try:
        send_reply(application, message)
        reply.emailed = True
    except EmailError as err:
        reply.error = str(err)[:300]
    db.session.add(reply)
    db.session.commit()
    return reply

"""Tells the team about something that came in from the website, and the sender that it arrived.
Each channel is tried on its own: one failing never stops the others, and the result is recorded
on the record (sent_<channel>) so the panel can show it and send again.

  telegram      the alert to linked panel users and the team group  (sent_telegram)
  email         the alert to CAREERS_EMAIL_TO and opted-in users    (sent_email)
  confirmation  "we received it" to the person who sent it         (sent_confirmation)

CHANNELS sends a JobApplication (with its CV), ACCESS_CHANNELS an AccessRequest.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from ..extensions import db
from . import email, telegram


CHANNELS = {"telegram": telegram.send, "email": email.send, "confirmation": email.send_confirmation}
ACCESS_CHANNELS = {
    "telegram": telegram.send_access,
    "email": email.send_access,
    "confirmation": email.send_access_confirmation,
}


def channels(senders=None):
    """The senders (CHANNELS by default), without the confirmation when
    SEND_APPLICANT_CONFIRMATION is off."""
    out = dict(CHANNELS if senders is None else senders)
    if not current_app.config["SEND_APPLICANT_CONFIRMATION"]:
        out.pop("confirmation", None)
    return out


def notify(record, payload=None, senders=None):
    """Sends on every channel not yet marked sent, at the same time. Each sender gets
    (record, payload): for an application the payload is the CV. Sets sent_<channel> on the record
    (the caller commits) and returns {channel: error or None}."""
    todo = {name: fn for name, fn in channels(senders).items() if not getattr(record, f"sent_{name}")}
    flask_app = current_app._get_current_object()

    # the senders read current_app.config and the database, so each thread gets the app context
    def run(fn):
        def job():
            with flask_app.app_context():
                fn(record, payload)
        return job

    results = {}
    with ThreadPoolExecutor(max_workers=len(todo) or 1) as pool:
        futures = {name: pool.submit(run(fn)) for name, fn in todo.items()}
        for name, future in futures.items():
            try:
                future.result()
                setattr(record, f"sent_{name}", True)
                results[name] = None
            except Exception as err:  # a channel failing must never lose what came in
                current_app.logger.error("notify: %s failed for %s: %s", name, record.reference, err)
                results[name] = str(err)
    return results


def notify_in_background(model, record_id, payload=None, senders=None):
    """notify() on its own thread, so the visitor's browser gets its answer without waiting on
    Telegram and the mail server. Returns the thread. A channel that fails stays unsent on the
    record, where the panel shows it and can send it again."""
    flask_app = current_app._get_current_object()

    def job():
        with flask_app.app_context():
            try:
                notify(db.session.get(model, record_id), payload, senders)
                db.session.commit()
            except Exception:
                flask_app.logger.exception("notify: %s %s failed", model.__name__, record_id)
                db.session.rollback()

    # not a daemon: a restart waits for the sends in flight instead of cutting them off
    thread = threading.Thread(target=job, name=f"notify-{model.__name__}-{record_id}")
    thread.start()
    return thread

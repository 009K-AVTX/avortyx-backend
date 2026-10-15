"""Tells the hiring team about a new application, and the applicant that it arrived. Each channel is
tried on its own: one failing never stops the others, and the result is recorded on the
JobApplication so the panel can show it and send again.

  telegram      the alert to linked panel users and the team group  (sent_telegram)
  email         the alert to CAREERS_EMAIL_TO and opted-in users    (sent_email)
  confirmation  "we received your application" to the applicant    (sent_confirmation)
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from ..extensions import db
from . import email, telegram


CHANNELS = {"telegram": telegram.send, "email": email.send, "confirmation": email.send_confirmation}


def channels():
    """CHANNELS, without the applicant's confirmation when SEND_APPLICANT_CONFIRMATION is off."""
    out = dict(CHANNELS)
    if not current_app.config["SEND_APPLICANT_CONFIRMATION"]:
        out.pop("confirmation", None)
    return out


def notify(app, cv_bytes):
    """Sends on every channel not yet marked sent, at the same time. Sets sent_<channel> on the
    application (the caller commits) and returns {channel: error or None}."""
    todo = {name: fn for name, fn in channels().items() if not getattr(app, f"sent_{name}")}
    flask_app = current_app._get_current_object()

    # the senders read current_app.config and the database, so each thread gets the app context
    def run(fn):
        def job():
            with flask_app.app_context():
                fn(app, cv_bytes)
        return job

    results = {}
    with ThreadPoolExecutor(max_workers=len(todo) or 1) as pool:
        futures = {name: pool.submit(run(fn)) for name, fn in todo.items()}
        for name, future in futures.items():
            try:
                future.result()
                setattr(app, f"sent_{name}", True)
                results[name] = None
            except Exception as err:  # a channel failing must never lose the application
                current_app.logger.error("careers: %s failed for application %s: %s", name, app.id, err)
                results[name] = str(err)
    return results


def notify_in_background(application_id, cv_bytes):
    """notify() on its own thread, so the applicant's browser gets its answer without waiting on
    Telegram and the mail server. Returns the thread. A channel that fails stays unsent on the
    application, where the panel shows it and can send it again."""
    flask_app = current_app._get_current_object()

    def job():
        from ..models import JobApplication

        with flask_app.app_context():
            try:
                notify(db.session.get(JobApplication, application_id), cv_bytes)
                db.session.commit()
            except Exception:
                flask_app.logger.exception("careers: notifying application %s failed", application_id)
                db.session.rollback()

    # not a daemon: a restart waits for the sends in flight instead of cutting them off
    thread = threading.Thread(target=job, name=f"notify-{application_id}")
    thread.start()
    return thread

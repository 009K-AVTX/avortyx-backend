"""Tells the hiring team about a new application. Each channel is tried on its own: one failing
never stops the other, and the result is recorded on the JobApplication."""
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from . import email, telegram

CHANNELS = {"telegram": telegram.send, "email": email.send}


def notify(app, cv_bytes):
    """Sends to every channel not yet marked sent, at the same time. Sets sent_telegram /
    sent_email on the application (the caller commits) and returns {channel: error or None}."""
    todo = {name: fn for name, fn in CHANNELS.items() if not getattr(app, f"sent_{name}")}
    flask_app = current_app._get_current_object()

    # the senders read current_app.config, so each thread gets the app context
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

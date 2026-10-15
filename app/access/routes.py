"""POST /access/request — the website's request-access form (urlencoded or multipart).

Fields: name*, organization*, email*, use_case*, phone, page (where it was sent from), and website
(hidden from people; bots fill it in). Replies 200 {"ok": true, "reference": "REQ-00012"}, or 400
{"error": "..."} with a message the form shows as it is (the same wording as the form's own checks).

Steps: validate -> save an AccessRequest -> answer the form -> alert the team on Telegram and by
email, and email the requester a confirmation, in the background. A saved request is never lost:
if the notifications fail it still waits in the panel, which can send them again.
"""
from flask import current_app, request

from ..careers.validators import EMAIL
from ..extensions import db
from ..models import AccessRequest
from ..notify import ACCESS_CHANNELS, notify, notify_in_background
from . import bp

# the longest each field may be; anything longer is cut, not refused
LIMITS = {"name": 200, "organization": 200, "email": 200, "phone": 40, "use_case": 3000, "page": 300}


def check(fields):
    if not fields["name"]:
        return "Please add your full name."
    if not fields["organization"]:
        return "Please add your company."
    if not EMAIL.match(fields["email"]):
        return "Please add a valid work email."
    if not fields["use_case"]:
        return "Please tell us what you are looking to route."
    return None


@bp.post("/request")
def request_access():
    # the honeypot: report success so bots move on, keep nothing
    if request.form.get("website"):
        return {"ok": True}

    fields = {k: (request.form.get(k) or "").strip()[:n] for k, n in LIMITS.items()}
    error = check(fields)
    if error:
        return {"error": error}, 400

    req = AccessRequest(**{k: v or None for k, v in fields.items()})
    db.session.add(req)
    db.session.commit()

    if current_app.config["NOTIFY_IN_BACKGROUND"]:
        notify_in_background(AccessRequest, req.id, senders=ACCESS_CHANNELS)
    else:
        notify(req, senders=ACCESS_CHANNELS)
        db.session.commit()
    # the reference the requester sees on the thank-you page and in their confirmation email
    return {"ok": True, "reference": req.reference}

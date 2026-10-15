"""Panel pages for access requests from the website's /request-access form.

  GET  /panel/access                 access requests list  (access_requests.html), filter by status
  GET  /panel/access/<id>            one request           (access_request.html)
  POST /panel/access/<id>/status     new -> reviewing -> approved/declined
  POST /panel/access/<id>/notify     send the Telegram / email notifications that failed, again
"""
from flask import abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import AccessRequest
from ..models.access_request import ACCESS_STATUSES
from ..notify import ACCESS_CHANNELS, notify
from . import bp
from .auth import check_csrf, login_required


def get_request(req_id):
    req = db.session.get(AccessRequest, req_id)
    if not req:
        abort(404)
    return req


@bp.get("/access")
@login_required
def access_requests():
    query = AccessRequest.query.order_by(AccessRequest.created_at.desc())
    status = request.args.get("status", "")
    if status:
        query = query.filter_by(status=status)
    return render_template("panel/access_requests.html", requests=query.limit(500).all(), status=status,
                           ACCESS_STATUSES=ACCESS_STATUSES)


@bp.get("/access/<int:req_id>")
@login_required
def access_request(req_id):
    return render_template("panel/access_request.html", r=get_request(req_id), ACCESS_STATUSES=ACCESS_STATUSES)


@bp.post("/access/<int:req_id>/status")
@login_required
def access_status(req_id):
    check_csrf()
    req = get_request(req_id)
    new = request.form.get("status")
    if new not in ACCESS_STATUSES:
        abort(400)
    req.status = new
    db.session.commit()
    flash(f"Moved to {new}.")
    return redirect(url_for("panel.access_request", req_id=req.id))


@bp.post("/access/<int:req_id>/notify")
@login_required
def access_resend(req_id):
    check_csrf()
    req = get_request(req_id)
    results = notify(req, senders=ACCESS_CHANNELS)
    db.session.commit()
    failed = {k: v for k, v in results.items() if v}
    flash("Sent." if not failed else "Still failing: " + "; ".join(f"{k} ({v})" for k, v in failed.items()))
    return redirect(url_for("panel.access_request", req_id=req.id))

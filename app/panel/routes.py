"""Panel pages.

  GET  /panel/login                     sign-in form          (login.html)
  POST /panel/logout                    sign out
  GET  /panel/                          applications list     (applications.html), filter by role/status
  GET  /panel/applications/<id>         one application       (application.html)
  GET  /panel/applications/<id>/cv      download the CV
  POST /panel/applications/<id>/status  move it along: new -> reviewing -> interview -> hired/rejected
  POST /panel/applications/<id>/notify  send the Telegram / email notifications that failed, again
  POST /panel/applications/<id>/reply   email the applicant a message (also possible from Telegram)

Settings (Telegram, alerts, email) are in settings.py.
"""
from flask import abort, flash, redirect, render_template, request, send_file, url_for

from ..extensions import db
from ..models import AdminUser, JobApplication
from ..models.application import STATUSES
from ..notify import notify
from ..replies import reply_to_applicant
from ..storage import cv_path, read_cv
from . import bp
from .auth import check_csrf, csrf_token, current_admin, log_in, log_out, login_required


@bp.app_context_processor
def panel_globals():
    return {"csrf_token": csrf_token, "current_admin": current_admin, "STATUSES": STATUSES}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        check_csrf()
        admin = AdminUser.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if admin and admin.check_password(request.form.get("password", "")):
            log_in(admin)
            nxt = request.args.get("next", "")
            # only a path on this site, never somewhere else
            return redirect(nxt if nxt.startswith("/panel") else url_for("panel.applications"))
        flash("That email and password don't match.")
    return render_template("panel/login.html")


@bp.post("/logout")
def logout():
    check_csrf()
    log_out()
    return redirect(url_for("panel.login"))


def get_application(app_id):
    application = db.session.get(JobApplication, app_id)
    if not application:
        abort(404)
    return application


@bp.get("/")
@login_required
def applications():
    query = JobApplication.query.order_by(JobApplication.created_at.desc())
    role, status = request.args.get("role", ""), request.args.get("status", "")
    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(status=status)
    roles = [r for (r,) in db.session.query(JobApplication.role).distinct().order_by(JobApplication.role)]
    return render_template("panel/applications.html", applications=query.limit(500).all(), roles=roles, role=role, status=status)


@bp.get("/applications/<int:app_id>")
@login_required
def application(app_id):
    return render_template("panel/application.html", a=get_application(app_id))


@bp.get("/applications/<int:app_id>/cv")
@login_required
def cv(app_id):
    a = get_application(app_id)
    return send_file(cv_path(a.cv_path), as_attachment=True, download_name=a.cv_name)


@bp.post("/applications/<int:app_id>/status")
@login_required
def status(app_id):
    check_csrf()
    a = get_application(app_id)
    new = request.form.get("status")
    if new not in STATUSES:
        abort(400)
    a.status = new
    db.session.commit()
    flash(f"Moved to {new}.")
    return redirect(url_for("panel.application", app_id=a.id))


@bp.post("/applications/<int:app_id>/notify")
@login_required
def resend(app_id):
    check_csrf()
    a = get_application(app_id)
    results = notify(a, read_cv(a.cv_path))
    db.session.commit()
    failed = {k: v for k, v in results.items() if v}
    flash("Sent." if not failed else "Still failing: " + "; ".join(f"{k} ({v})" for k, v in failed.items()))
    return redirect(url_for("panel.application", app_id=a.id))


@bp.post("/applications/<int:app_id>/reply")
@login_required
def reply(app_id):
    check_csrf()
    a = get_application(app_id)
    try:
        r = reply_to_applicant(a, request.form.get("message", ""), sent_by=current_admin().email, via="panel")
    except ValueError as err:
        flash(str(err))
        return redirect(url_for("panel.application", app_id=a.id))
    flash(f"Emailed to {a.email}." if r.emailed else f"Saved, but the email failed: {r.error}")
    return redirect(url_for("panel.application", app_id=a.id) + "#reply")

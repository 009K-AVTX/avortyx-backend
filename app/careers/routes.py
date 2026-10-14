"""POST /careers/apply — multipart form from the website's careers page.

Fields: role, name*, email*, cv* (PDF/DOC/DOCX), phone, telegram, link, note, and company_site
(hidden from people; bots fill it in). Replies 200 {"ok": true}, or 4xx {"error": "..."} with a
message the form shows the applicant as it is.

Steps: validate -> save the CV -> save a JobApplication -> send to Telegram and email. Once the
application is saved it is never lost: if both notifications fail it still waits in the panel,
which can send them again.
"""
from flask import current_app, request
from werkzeug.exceptions import RequestEntityTooLarge

from ..extensions import db
from ..models import JobApplication
from ..notify import notify
from ..storage import save_cv
from . import bp
from .validators import check, clean_fields, download_name


@bp.post("/apply")
def apply():
    # the honeypot: report success so bots move on, keep nothing
    if request.form.get("company_site"):
        return {"ok": True}

    fields = clean_fields(request.form)
    error, data, ext = check(fields, request.files.get("cv"), current_app.config["MAX_CV_BYTES"])
    if error:
        return {"error": error}, 400

    application = JobApplication(**fields, cv_path=save_cv(data, ext), cv_name=download_name(fields["name"], ext))
    db.session.add(application)
    db.session.commit()

    notify(application, data)
    db.session.commit()
    return {"ok": True}


@bp.errorhandler(RequestEntityTooLarge)
def too_large(_):
    mb = current_app.config["MAX_CV_BYTES"] // (1024 * 1024)
    return {"error": f"Your CV is over {mb} MB. Please send a smaller file."}, 413

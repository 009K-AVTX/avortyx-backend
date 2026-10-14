"""Emails the application to CAREERS_EMAIL_TO over SMTP (smtplib), CV attached, Reply-To set
to the applicant. Port 465 uses SSL; any other port (587) upgrades with STARTTLS."""
import mimetypes
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app


def details(app):
    lines = [f"New application: {app.role}", "", f"Name: {app.name}", f"Email: {app.email}"]
    for label, value in (("Phone", app.phone), ("Telegram", app.telegram), ("Link", app.link)):
        if value:
            lines.append(f"{label}: {value}")
    if app.note:
        lines += ["", "Note:", app.note]
    return "\n".join(lines)


def send(app, cv_bytes):
    cfg = current_app.config
    host, port, user, password = cfg["SMTP_HOST"], cfg["SMTP_PORT"], cfg["SMTP_USER"], cfg["SMTP_PASS"]
    if not host or not user or not password:
        raise RuntimeError("SMTP_HOST, SMTP_USER or SMTP_PASS is not set")

    msg = EmailMessage()
    msg["From"] = formataddr(("Avortyx Careers", cfg["SMTP_FROM"] or user))
    msg["To"] = cfg["CAREERS_EMAIL_TO"]
    msg["Reply-To"] = formataddr((app.name, app.email))
    msg["Subject"] = f"Application: {app.role} — {app.name}"
    msg.set_content(details(app))
    kind = (mimetypes.guess_type(app.cv_name)[0] or "application/octet-stream").split("/")
    msg.add_attachment(cv_bytes, maintype=kind[0], subtype=kind[1], filename=app.cv_name)

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)

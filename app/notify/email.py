"""Email over SMTP (smtplib): branded HTML with a plain-text copy, like the call platform's emails.

  send()              the team alert: every application to CAREERS_EMAIL_TO and to panel users who
                      turned email alerts on, CV attached, Reply-To the applicant
  send_confirmation() "we received your application" to the applicant, with their reference
  send_reply()        a message from the team to the applicant (panel or Telegram)
  send_access()       the team alert for an access request, Reply-To the requester
  send_access_confirmation()  "we received your request" to the requester
  send_test()         Panel → Settings → Send test email

Port 465 uses SSL; any other port (587) upgrades with STARTTLS.
"""
import mimetypes
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape

from flask import current_app

BRAND_DARK = "#1e3a8a"
BRAND = "#3b82f6"
TEXT = "#1f2937"
MUTED = "#6b7280"


class EmailError(RuntimeError):
    pass


def _cfg():
    return current_app.config


def configured():
    c = _cfg()
    return bool(c["SMTP_HOST"] and c["SMTP_USER"] and c["SMTP_PASS"])


def team_inbox():
    """CAREERS_EMAIL_TO as a list."""
    return [a.strip() for a in _cfg()["CAREERS_EMAIL_TO"].split(",") if a.strip()]


def reply_to_address():
    return _cfg()["CAREERS_REPLY_TO"] or (team_inbox() or [""])[0]


def deliver(to, subject, text, html, reply_to=None, attachments=(), from_name=None):
    """Sends one email to the addresses in `to`, from MAIL_FROM_NAME unless `from_name` is given.
    Raises EmailError if it can't."""
    c = _cfg()
    if not configured():
        raise EmailError("SMTP_HOST, SMTP_USER or SMTP_PASS is not set")
    to = [a for a in dict.fromkeys(a.strip() for a in to) if a]
    if not to:
        raise EmailError("no recipient")
    sender = c["SMTP_FROM"] or c["SMTP_USER"]

    msg = EmailMessage()
    msg["From"] = formataddr((from_name or c["MAIL_FROM_NAME"], sender))
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] or None)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    for name, data in attachments:
        kind = (mimetypes.guess_type(name)[0] or "application/octet-stream").split("/")
        msg.add_attachment(data, maintype=kind[0], subtype=kind[1], filename=name)

    host, port = c["SMTP_HOST"], c["SMTP_PORT"]
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                smtp.login(c["SMTP_USER"], c["SMTP_PASS"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(c["SMTP_USER"], c["SMTP_PASS"])
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as err:
        raise EmailError(f"{err.__class__.__name__}: {err}") from err


# ── layout ──────────────────────────────────────────────────────────────────

def _button(label, url):
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 4px">'
        f'<tr><td style="border-radius:8px;background:{BRAND}">'
        f'<a href="{escape(url)}" style="display:inline-block;padding:12px 22px;color:#ffffff;'
        f'font-weight:600;font-size:14px;text-decoration:none;border-radius:8px">{escape(label)}</a>'
        f"</td></tr></table>"
    )


def layout(title, body_html, preheader="", button=None):
    """The shared email frame: brand bar, white card, footer. `body_html` is already escaped."""
    site = _cfg()["SITE_URL"]
    host = site.split("//")[-1]
    cta = _button(*button) if button and button[1] else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6">
<span style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;font-family:Segoe UI,Helvetica,Arial,sans-serif">
<tr><td style="background:{BRAND_DARK};border-radius:12px 12px 0 0;padding:20px 28px;border-bottom:3px solid {BRAND}">
<span style="color:#ffffff;font-size:20px;font-weight:800;letter-spacing:.12em">AVORTYX</span></td></tr>
<tr><td style="background:#ffffff;padding:28px;color:{TEXT};font-size:15px;line-height:1.6">
<h1 style="margin:0 0 16px;font-size:20px;color:#111827">{escape(title)}</h1>
{body_html}{cta}
</td></tr>
<tr><td style="background:#ffffff;border-radius:0 0 12px 12px;border-top:1px solid #e5e7eb;padding:16px 28px;color:{MUTED};font-size:12px">
Avortyx · <a href="{escape(site)}" style="color:{MUTED}">{escape(host)}</a></td></tr>
</table></td></tr></table></body></html>"""


def _p(text):
    """A paragraph of plain text, escaped, line breaks kept."""
    return f'<p style="margin:0 0 14px">{escape(text).replace(chr(10), "<br>")}</p>'


def _rows(app):
    rows = [("Reference", app.reference), ("Role", app.role), ("Name", app.name), ("Email", app.email)]
    for label, value in (("Phone", app.phone), ("Telegram", app.telegram), ("Link", app.link)):
        if value:
            rows.append((label, value))
    return rows


def _table(rows):
    cells = "".join(
        f'<tr><td style="padding:6px 16px 6px 0;color:{MUTED};white-space:nowrap;vertical-align:top">{escape(k)}</td>'
        f'<td style="padding:6px 0;color:{TEXT}">{escape(v)}</td></tr>'
        for k, v in rows
    )
    return f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 16px;font-size:14px">{cells}</table>'


def _panel_link(app):
    base = _cfg()["PUBLIC_URL"]
    return f"{base}/panel/applications/{app.id}" if base else ""


# ── the emails ──────────────────────────────────────────────────────────────

def team_recipients():
    """CAREERS_EMAIL_TO, plus every panel user who turned email alerts on."""
    from ..models import AdminUser

    extra = [a.email for a in AdminUser.query.filter_by(email_alerts=True)]
    return list(dict.fromkeys([*team_inbox(), *extra]))


def send(app, cv_bytes):
    """The team alert (notify channel "email")."""
    rows = _rows(app)
    note_html = ""
    note_txt = ""
    if app.note:
        note_html = f'<p style="margin:0 0 6px;font-weight:600">Note</p>{_p(app.note)}'
        note_txt = f"\n\nNote:\n{app.note}"
    how = (
        f"Reply to this email to answer {app.name} directly, or reply to the Telegram alert "
        f"(or send \"{app.reference} your message\" to the bot)."
    )
    body = (
        _p(f"{app.name} applied for {app.role}. The CV is attached.")
        + _table(rows) + note_html
        + f'<p style="margin:16px 0 0;color:{MUTED};font-size:13px">{escape(how)}</p>'
    )
    link = _panel_link(app)
    html = layout(f"New application · {app.reference}", body, preheader=f"{app.name} — {app.role}",
                  button=("Open in panel", link))
    text = (
        f"New application {app.reference}\n\n"
        + "\n".join(f"{k}: {v}" for k, v in rows) + note_txt
        + (f"\n\nOpen in panel: {link}" if link else "") + f"\n\n{how}"
    )
    deliver(
        team_recipients(),
        f"Application: {app.role} — {app.name} ({app.reference})",
        text, html,
        reply_to=formataddr((app.name, app.email)),
        attachments=[(app.cv_name, cv_bytes)],
    )


def send_confirmation(app, _cv_bytes=None):
    """'We received your application' to the applicant (notify channel "confirmation")."""
    first = app.name.split()[0] if app.name.split() else app.name
    lines = [
        f"Hi {first},",
        f"Thank you for applying for {app.role} at Avortyx. Your application and CV reached our hiring team.",
        "We read every application and will get back to you by email. If you need to add anything, "
        "just reply to this email and keep your reference in the subject.",
    ]
    body = "".join(_p(line) for line in lines) + _table([("Reference", app.reference), ("Role", app.role)]) + _p(
        "Avortyx Hiring Team"
    )
    html = layout("We received your application", body, preheader=f"Reference {app.reference}",
                  button=("Visit avortyx.com", _cfg()["SITE_URL"]))
    text = "\n\n".join(lines) + f"\n\nReference: {app.reference}\nRole: {app.role}\n\nAvortyx Hiring Team"
    deliver([app.email], f"We received your application — {app.role} ({app.reference})", text, html,
            reply_to=reply_to_address())


def send_reply(app, message):
    """A message from the team to the applicant."""
    first = app.name.split()[0] if app.name.split() else app.name
    body = _p(f"Hi {first},") + _p(message) + _p("Avortyx Hiring Team") + (
        f'<p style="margin:16px 0 0;color:{MUTED};font-size:13px">'
        f"About your application for {escape(app.role)} · {app.reference}. "
        "Reply to this email to answer us.</p>"
    )
    html = layout(f"About your application · {app.role}", body, preheader=message[:120])
    text = f"Hi {first},\n\n{message}\n\nAvortyx Hiring Team\n\n—\nAbout your application for {app.role} ({app.reference})."
    deliver([app.email], f"Your application for {app.role} at Avortyx ({app.reference})", text, html,
            reply_to=reply_to_address())


ACCESS_FROM = "Avortyx"


def _access_rows(req):
    rows = [("Reference", req.reference), ("Name", req.name), ("Company", req.organization), ("Email", req.email)]
    if req.phone:
        rows.append(("Phone", req.phone))
    if req.page:
        rows.append(("Sent from", req.page))
    return rows


def send_access(req, _payload=None):
    """The team alert for an access request (access channel "email")."""
    rows = _access_rows(req)
    how = f"Reply to this email to answer {req.name} directly."
    body = (
        _p(f"{req.name} from {req.organization} asked for access to Avortyx.")
        + _table(rows)
        + f'<p style="margin:0 0 6px;font-weight:600">What they want to route</p>{_p(req.use_case)}'
        + f'<p style="margin:16px 0 0;color:{MUTED};font-size:13px">{escape(how)}</p>'
    )
    base = _cfg()["PUBLIC_URL"]
    link = f"{base}/panel/access/{req.id}" if base else ""
    html = layout(f"Access request · {req.reference}", body, preheader=f"{req.name} — {req.organization}",
                  button=("Open in panel", link))
    text = (
        f"Access request {req.reference}\n\n"
        + "\n".join(f"{k}: {v}" for k, v in rows)
        + f"\n\nWhat they want to route:\n{req.use_case}"
        + (f"\n\nOpen in panel: {link}" if link else "") + f"\n\n{how}"
    )
    deliver(team_recipients(), f"Access request: {req.organization} — {req.name} ({req.reference})", text, html,
            reply_to=formataddr((req.name, req.email)), from_name=ACCESS_FROM)


def send_access_confirmation(req, _payload=None):
    """'We received your request' to the requester (access channel "confirmation")."""
    first = req.name.split()[0] if req.name.split() else req.name
    lines = [
        f"Hi {first},",
        "Thank you for requesting access to Avortyx. Your request reached our team.",
        "Every request is reviewed by our team, and access is by invitation only. If your request is "
        "approved, we will email you a secure link to set up your account. If you need to add "
        "anything, just reply to this email and keep your reference in the subject.",
    ]
    body = "".join(_p(line) for line in lines) + _table(
        [("Reference", req.reference), ("Company", req.organization)]
    ) + _p("The Avortyx Team")
    html = layout("We received your request", body, preheader=f"Reference {req.reference}",
                  button=("Visit avortyx.com", _cfg()["SITE_URL"]))
    text = "\n\n".join(lines) + f"\n\nReference: {req.reference}\nCompany: {req.organization}\n\nThe Avortyx Team"
    deliver([req.email], f"We received your access request ({req.reference})", text, html,
            reply_to=reply_to_address(), from_name=ACCESS_FROM)


def send_test(to):
    body = _p("This is a test from the Avortyx panel. Email is set up: applications, confirmations "
              "and replies will be sent from this address.")
    deliver([to], "Avortyx panel · test email", "This is a test from the Avortyx panel. Email is set up.",
            layout("Email is working", body))

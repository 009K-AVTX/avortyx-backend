"""Checks an application before anything is saved: required fields, a real PDF/DOC/DOCX by its
first bytes (not just the extension), and the size limit. The messages are shown to the applicant
as they are, so they match the website form's own wording."""
import re

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# extension -> the bytes such a file starts with
CV_TYPES = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",  # a zip
    "doc": b"\xd0\xcf\x11\xe0",  # an OLE compound file
}
# the longest each field may be; anything longer is cut, not refused
LIMITS = {"role": 200, "name": 200, "email": 200, "phone": 40, "telegram": 64, "link": 300, "note": 3000}


def clean_fields(form):
    """The form's text fields, trimmed and cut to length."""
    out = {k: (form.get(k) or "").strip()[:n] for k, n in LIMITS.items()}
    out["role"] = out["role"] or "Open application"
    return out


def check(fields, cv, max_bytes):
    """Returns (error message or None, cv bytes, extension)."""
    if not fields["name"]:
        return "Please add your full name.", None, None
    if not EMAIL.match(fields["email"]):
        return "Please add a valid email address.", None, None
    if cv is None or not cv.filename:
        return "Please attach your CV.", None, None
    data = cv.read(max_bytes + 1)
    if not data:
        return "Please attach your CV.", None, None
    if len(data) > max_bytes:
        return f"Your CV is over {max_bytes // (1024 * 1024)} MB. Please send a smaller file.", None, None
    ext = cv.filename.rsplit(".", 1)[-1].lower() if "." in cv.filename else ""
    if ext not in CV_TYPES or not data.startswith(CV_TYPES[ext]):
        return "Please attach your CV as a PDF or Word document.", None, None
    return None, data, ext


def download_name(name, ext):
    """'CV - Jane Doe.pdf': the applicant's name with anything unusual taken out."""
    safe = re.sub(r"[^\w .'-]", "", name, flags=re.UNICODE).strip()[:60] or "applicant"
    return f"CV - {safe}.{ext}"

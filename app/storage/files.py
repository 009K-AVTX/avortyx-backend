"""Saves a CV under UPLOAD_DIR with a random file name (never the applicant's own name or path)
and finds it again for the panel's download link. Swap for S3 or similar here if needed."""
import os
import uuid
from datetime import datetime

from flask import current_app


def upload_root():
    """UPLOAD_DIR, relative to the project folder unless it is an absolute path."""
    path = current_app.config["UPLOAD_DIR"]
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(current_app.root_path), path)
    return path


def save_cv(data, ext):
    """Writes the CV and returns its path relative to UPLOAD_DIR (e.g. '2026/10/3f2a….pdf')."""
    rel = os.path.join(datetime.utcnow().strftime("%Y/%m"), f"{uuid.uuid4().hex}.{ext}")
    full = os.path.join(upload_root(), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)
    return rel


def cv_path(rel):
    """The CV's full path, refusing anything that would point outside UPLOAD_DIR."""
    root = os.path.realpath(upload_root())
    full = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([root, full]) != root:
        raise ValueError("CV path outside the upload folder")
    return full


def read_cv(rel):
    with open(cv_path(rel), "rb") as f:
        return f.read()

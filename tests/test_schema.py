"""A database made by the first version (no Telegram / reply columns) is brought up to date at
start-up, keeping its rows."""
import sqlite3

from app import create_app
from app.config import TestConfig


def test_old_database_gets_the_new_columns(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE admin_user (id INTEGER PRIMARY KEY, email VARCHAR(200) NOT NULL UNIQUE,
                                 password_hash VARCHAR(300) NOT NULL);
        CREATE TABLE job_application (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL,
            role VARCHAR(200) NOT NULL, name VARCHAR(200) NOT NULL, email VARCHAR(200) NOT NULL,
            phone VARCHAR(40), telegram VARCHAR(64), link VARCHAR(300), note TEXT,
            cv_path VARCHAR(300) NOT NULL, cv_name VARCHAR(200) NOT NULL, status VARCHAR(20) NOT NULL,
            sent_telegram BOOLEAN NOT NULL, sent_email BOOLEAN NOT NULL);
        INSERT INTO admin_user VALUES (1, 'old@avortyx.com', 'x');
        INSERT INTO job_application VALUES (1, '2026-10-01 10:00:00', 'Designer', 'Old Applicant',
            'old@example.com', NULL, NULL, NULL, NULL, '2026/10/a.pdf', 'CV.pdf', 'new', 1, 1);
    """)
    con.commit()
    con.close()

    class Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path}"
        UPLOAD_DIR = str(tmp_path)

    app = create_app(Cfg)
    with app.app_context():
        from app.models import AdminUser, JobApplication

        admin = AdminUser.query.one()
        assert admin.telegram_chat_id is None and admin.telegram_alerts is True and admin.email_alerts is False
        a = JobApplication.query.one()
        assert a.reference == "AVX-00001" and a.sent_confirmation is False and a.replies == []

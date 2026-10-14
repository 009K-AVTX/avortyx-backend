# Avortyx Backend

The Flask backend for the Avortyx website ([avortyx-frontend](https://github.com/kvn-koech/avortyx-frontend), checked out next to this folder as `../Avortyx-Frontend`). For now it handles one job:
**careers applications**. The careers page form posts each application here. It is saved, the CV
goes to the hiring team on **Telegram and by email**, and the team reviews it in an admin **panel**.

```
Avortyx-Backend/
├── wsgi.py                  entry point (flask run / gunicorn)
├── requirements.txt
├── .env.example             every setting, copy to .env
├── app/
│   ├── __init__.py          create_app(): config, CORS, database, blueprints, /health
│   ├── config.py            settings from the environment
│   ├── extensions.py        db (SQLAlchemy), cors
│   ├── cli.py               flask create-admin, flask telegram-chat-id
│   ├── careers/             PUBLIC: POST /careers/apply (the website's form)
│   │   ├── routes.py
│   │   └── validators.py    required fields, real PDF/DOC/DOCX by its bytes, size limit
│   ├── notify/              Telegram + email, sent together; one failing never stops the other
│   │   ├── telegram.py
│   │   └── email.py
│   ├── storage/files.py     CVs on disk under UPLOAD_DIR with random names (swap for S3 here)
│   ├── models/              JobApplication, AdminUser
│   └── panel/               ADMIN: /panel (sign in, list, open, download CV, status, re-send)
├── tests/                   pytest
├── instance/                the SQLite database (dev)
└── uploads/                 the CVs (dev)
```

## Run it locally

```bash
cd Avortyx-Backend
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then fill in the Telegram and SMTP settings
flask --app wsgi create-admin you@avortyx.com
flask --app wsgi run --debug --port 5055
```

- Health check: http://localhost:5055/health
- Panel: http://localhost:5055/panel
- Tests: `python -m pytest -q`

## Connect the website

The careers form posts to whatever `VITE_APPLY_URL` was set to when the site was built. In
`../Avortyx-Frontend/.env.local` (local) or in Vercel's environment variables (live):

```
VITE_APPLY_URL=http://localhost:5055/careers/apply          # local
VITE_APPLY_URL=https://api.avortyx.com/careers/apply        # live (your backend's address)
```

Rebuild or restart the site after changing it. Then add the site's address to this backend's
`CORS_ORIGINS`, or the browser will block the form's request.

## The contract with the form

`POST /careers/apply`, `multipart/form-data`:

| field          | |
|----------------|-|
| `role`         | the job title, or "Open application" |
| `name`, `email`| required |
| `cv`           | required: PDF, DOC or DOCX, up to `MAX_CV_BYTES` (4 MB) |
| `phone`, `telegram`, `link`, `note` | optional |
| `company_site` | hidden spam trap: if filled, the reply is `{"ok": true}` and nothing is kept |

It replies `200 {"ok": true}`, or `400`/`413 {"error": "…"}`. The form shows that message to the
applicant as it is. Once an application is saved it is never lost: if Telegram and email both fail,
it still waits in the panel, where **Send again** retries.

## Telegram and email

- **Telegram:** create a bot with @BotFather and put its token in `TELEGRAM_BOT_TOKEN`. Add the bot
  to the team's group (or press Start on it from @avortyxsupport) and send a message there. Then run
  `flask --app wsgi telegram-chat-id` and put the id in `TELEGRAM_CHAT_ID`. A group's id starts
  with -100.
- **Email:** any SMTP mailbox. For Gmail or Google Workspace that's `smtp.gmail.com`, port 465, and
  an app password. Port 587 uses STARTTLS. Applications go to `CAREERS_EMAIL_TO`, and replying goes
  to the applicant.

## Deploying to the Hostinger VPS

`api.avortyx.com` runs on a Hostinger KVM VPS (Ubuntu): nginx → gunicorn on `127.0.0.1:8000`,
run by systemd as the `avortyx` user. The files are in `deploy/`.

1. In DNS, point an **A record** for `api.avortyx.com` at the VPS's IP.
2. From this folder: `deploy/deploy.sh root@<server-ip>`. The first run installs nginx/Python,
   opens the firewall, writes a production `/srv/avortyx-backend/.env` (with a fresh `SECRET_KEY`)
   and starts the app. Every later run just ships the code and restarts.
3. HTTPS, once DNS resolves: `ssh root@<server-ip> certbot --nginx -d api.avortyx.com`.
4. A panel login: `ssh -t root@<server-ip> /srv/avortyx-backend/deploy/flask.sh create-admin you@avortyx.com`.
5. Telegram/SMTP: edit `/srv/avortyx-backend/.env` on the server, then `systemctl restart avortyx-backend`.

The database and CVs are in `/var/lib/avortyx` and a deploy never touches them. Logs:
`journalctl -u avortyx-backend -f`.

## Deploying elsewhere

```bash
gunicorn wsgi:app --workers 2 --bind 0.0.0.0:$PORT
```

- **Settings:** set a real `SECRET_KEY` (the app won't start in production without one). Keep
  `SESSION_COOKIE_SECURE=1` (https only). Set `BEHIND_PROXY=1` on platforms that terminate https
  in front of the app (Render, Railway, Fly, nginx).
- **Persistent storage:** SQLite and `uploads/` need a disk that survives deploys. Alternatively,
  point `DATABASE_URL` at Postgres (add `psycopg[binary]` to requirements) and keep the CVs on a
  mounted volume, or move them to S3 in `app/storage/files.py`.
- **Database tables:** these are created on start-up. Add Flask-Migrate before changing the
  models on a live database.

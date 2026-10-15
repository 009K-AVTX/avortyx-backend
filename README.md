# Avortyx Backend

The Flask backend for the Avortyx website ([avortyx-frontend](https://github.com/009K-AVTX/avortyx-frontend), checked out next to this folder as `../Avortyx-Frontend`). For now it handles one job:
**careers applications**. The careers page form posts each application here. It is saved, the CV
goes to the hiring team on **Telegram and by email**, the applicant gets a confirmation email, and
the team reviews it in an admin **panel**.

Telegram and email work the same way as on the Avortyx call platform: a real **bot** (each team
member links their own Telegram from Panel → Settings with one tap, `/start`, `/help`, `/stop`)
and branded HTML **emails**. The team can **reply to an applicant** from the panel or straight from
Telegram, and the applicant receives it by email.

```
Avortyx-Backend/
├── wsgi.py                  entry point (flask run / gunicorn)
├── requirements.txt
├── .env.example             every setting, copy to .env
├── app/
│   ├── __init__.py          create_app(): config, CORS, database, blueprints, /health
│   ├── config.py            settings from the environment
│   ├── extensions.py        db (SQLAlchemy), cors
│   ├── cli.py               create-admin, telegram-set-webhook / -webhook-info, send-test-email, …
│   ├── schema.py            adds new columns to an existing database at start-up
│   ├── replies.py           emailing an applicant (shared by the panel and the bot)
│   ├── careers/             PUBLIC: POST /careers/apply (the website's form)
│   │   ├── routes.py
│   │   └── validators.py    required fields, real PDF/DOC/DOCX by its bytes, size limit
│   ├── notify/              Telegram + email, sent together; one failing never stops the other
│   │   ├── telegram.py      Bot API calls; the alert to linked people and the team group
│   │   └── email.py         branded HTML emails: team alert, applicant confirmation, replies
│   ├── chat/                PUBLIC: the website's help chat <-> the team support group on Telegram
│   ├── bot/                 TELEGRAM: POST /telegram/webhook (/start linking, /help, /stop, replies)
│   ├── storage/files.py     CVs on disk under UPLOAD_DIR with random names (swap for S3 here)
│   ├── models/              JobApplication, AccessRequest, ChatConversation/ChatMessage, AdminUser, …
│   └── panel/               ADMIN: /panel (applications, reply, Settings: Telegram + alerts)
├── tests/                   pytest
├── instance/                the SQLite database (dev)
└── uploads/                 the CVs (dev)
```

## What's live

| | |
|-|-|
| Website | https://www.avortyx.com (Vercel project `trackdrive.net-clone`; `avortyx.com` redirects to www) |
| Backend | https://api.avortyx.com on the Hostinger VPS (see [Deploying](#deploying-to-the-hostinger-vps)) |
| Panel | https://api.avortyx.com/panel |
| Bot | [@AvortyxCareersBot](https://t.me/AvortyxCareersBot), webhook `https://api.avortyx.com/telegram/webhook` |
| Email | sent from `009k@avortyx.com` through `smtp.hostinger.com:465`; team alerts to `CAREERS_EMAIL_TO` |
| Form → backend | Vercel Production env `VITE_APPLY_URL=https://api.avortyx.com/careers/apply` |
| DNS | Hostinger: `api` A → the VPS; `@` and `www` → Vercel; MX, SPF and DKIM are Hostinger mail |
| CVs and database | on the VPS in `/var/lib/avortyx` (`uploads/` and `avortyx.db`), not backed up by a deploy |

The secrets (bot token, mailbox password, `SECRET_KEY`, `TELEGRAM_WEBHOOK_SECRET`) live only in
`/srv/avortyx-backend/.env` on the server and in your local `.env`, both outside git. This repo is
public: never put them in `.env.example` or anywhere else that is committed.

## Run it locally

```bash
cd Avortyx-Backend
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then fill in SECRET_KEY, TELEGRAM_BOT_TOKEN and SMTP_PASS
flask --app wsgi create-admin you@avortyx.com
flask --app wsgi run --debug --port 5055
```

- Health check: http://localhost:5055/health
- Panel: http://localhost:5055/panel
- Tests: `python -m pytest -q`

A local copy uses the same bot as the live server, so keep `PUBLIC_URL` empty in your local `.env`
(then it can't take the webhook), and don't run `telegram-delete-webhook` or `telegram-chat-id`
locally: they act on the live bot and stop its alerts until the server runs `telegram-set-webhook`.

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

### The bot

1. Create a bot with **@BotFather** (`/newbot`), put its token in `TELEGRAM_BOT_TOKEN`.
2. Set `PUBLIC_URL` (this backend's https address) and a random `TELEGRAM_WEBHOOK_SECRET`.
3. Connect the bot to this server: **Panel → Settings → Connect the bot to this server**, or
   `flask --app wsgi telegram-set-webhook`. Telegram then sends every message for the bot to
   `POST /telegram/webhook`, which checks the secret.
4. Each team member: **Panel → Settings → Connect Telegram**, tap **Open Telegram**, press
   **Start**. The page notices by itself. That's the call platform's linking flow.

What the bot does:

| | |
|-|-|
| `/start <code>` | links the chat to the panel user who made the code (one-time, 15 minutes) |
| `/start`, `/help` | welcome / everything it does |
| `/stop` | unlinks the chat: no more alerts there |
| new application | details + CV to every linked person with Telegram alerts on, and the team group (`TELEGRAM_CHAT_ID`, optional) |
| reply to an alert, or `AVX-00012 message` | emails that message to the applicant; the bot confirms in the chat |
| `/reply AVX-00012 message` | the same, for groups (bots in groups only see commands and replies to them) |

Only linked panel users and the team group can reply to applicants; anyone else is told to link first.

### The website's chat box → the support group (t.me/Avortyx_Sup)

The careers bot's alerts above are unchanged. Separately, the same bot carries the website's help
chat to the support group: `TELEGRAM_SUPPORT_CHAT_ID=https://t.me/Avortyx_Sup/284` (the Customer
support topic; a link as Telegram copies it, a group without a topic, a `-100…` id or `@username`).

The website's chat box (`site.js` on avortyx.com, built with `VITE_CHAT_URL=https://api.avortyx.com/chat`):
once a visitor picks a teammate, what they type goes to `POST /chat/messages` and on to the
support group as `💬 New Support Chat · CHAT-00012` (a visitor name like `Visitor UGWYMY`, the
teammate they picked, the page, the message). Later messages follow as `💬 Visitor UGWYMY · CHAT-00012`.
To answer, send `CHAT-00012 your reply here`, or **reply** to one of those messages; the bot puts a
👍 on it and the answer appears in the visitor's chat box within a few seconds (it asks `GET /chat/<id>/messages` while open). Only the
visitor's browser has the conversation's token, so nobody else can read it.

Setting up the group: add the bot and **make it an admin** (it then sees every message, so
`CHAT-00012 your reply` works; without admin rights it only sees replies to its own messages and
`/reply CHAT-00012 …`). Make the group **private** so only the team can read visitors' messages,
then copy the topic's link again (it changes to `t.me/c/…`). `/chatid` in a topic answers with the
group's id and the topic.

Deploying before the bot is in the group is safe: the chat keeps working and every message is
saved (the log says `bot is not a member`). Messages are retried while the visitor's chat box is
open, and `deploy/flask.sh chat-resend` sends any that are left once the bot is in.
Every reply is kept on the application in the panel with who sent it and whether the email went.

### Email

Any SMTP mailbox. For a Hostinger mailbox: `smtp.hostinger.com`, port 465, the full address as
`SMTP_USER` and its password. Port 587 uses STARTTLS. Four emails, all branded HTML with a
plain-text copy:

- **team alert** to `CAREERS_EMAIL_TO` (plus anyone who ticked email alerts in Settings), CV attached,
  Reply-To the applicant
- **confirmation** to the applicant with their reference (`SEND_APPLICANT_CONFIRMATION=0` turns it off)
- **replies** to the applicant from the panel or Telegram, Reply-To `CAREERS_REPLY_TO`
- **test** from Panel → Settings, or `flask --app wsgi send-test-email you@x.com`

Panel → Settings → **Setup status** shows what is configured and the last error Telegram reported.

## Deploying to the Hostinger VPS

`api.avortyx.com` runs on the Hostinger KVM VPS `168.231.112.65` (Ubuntu): nginx → gunicorn on
`127.0.0.1:8055`, run by systemd as the `avortyx` user. The files are in `deploy/`.

**The VPS is shared with api.arbityx.com.** The scripts only add to it: their own nginx site, user,
folders, port and service. They never remove other nginx sites, never turn the firewall on or
change its rules, never upgrade packages that are already installed, and if nginx rejects the new
site they take it back out before reloading.

1. In DNS, point an **A record** for `api.avortyx.com` at the VPS's IP.
2. Put the code on the server in `/srv/avortyx-backend` (`git clone`, or `deploy/deploy.sh
   root@<server-ip>` from a Mac/Linux machine) and run `bash /srv/avortyx-backend/deploy/install-on-server.sh`
   on the server. The first run installs what is missing, adds the nginx site, writes a production
   `.env` (fresh `SECRET_KEY` and `TELEGRAM_WEBHOOK_SECRET`), starts the app and, once DNS points
   at the server, gets the Let's Encrypt certificate (`certbot --nginx -d api.avortyx.com`).
   On a network that blocks outgoing port 22, give the server a second SSH port (2222) and use
   `SSH_PORT=2222 deploy/deploy.sh root@<server-ip>`.
3. Fill in Telegram and SMTP in `/srv/avortyx-backend/.env`, then `systemctl restart avortyx-backend`.
4. A panel login: `/srv/avortyx-backend/deploy/flask.sh create-admin you@avortyx.com`.
5. `/srv/avortyx-backend/deploy/flask.sh telegram-set-webhook` (or the button in Settings).

Updating later: new code into `/srv/avortyx-backend`, then `install-on-server.sh` again. The
database and CVs are in `/var/lib/avortyx` and an update never touches them; new columns are added
at start-up. Logs: `journalctl -u avortyx-backend -f`.

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

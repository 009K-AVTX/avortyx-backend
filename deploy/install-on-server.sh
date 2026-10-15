#!/usr/bin/env bash
# Installs or updates the backend ON the Hostinger VPS, run as root from the server itself:
#   bash /srv/avortyx-backend/deploy/install-on-server.sh
# The first run sets the server up (setup-server.sh) and writes a production .env with fresh
# secrets; later runs keep .env, the database and the CVs, reinstall packages and restart.
# deploy.sh (from a Mac/Linux machine) copies the code over and then runs this same script.
set -euo pipefail
APP=/srv/avortyx-backend
DATA=/var/lib/avortyx
chmod +x $APP/deploy/*.sh

[ -f /etc/systemd/system/avortyx-backend.service ] || $APP/deploy/setup-server.sh

if [ ! -f $APP/.env ]; then
  sed -e "s|^SECRET_KEY=.*|SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')|" \
      -e "s|^SESSION_COOKIE_SECURE=.*|SESSION_COOKIE_SECURE=1|" \
      -e "s|^BEHIND_PROXY=.*|BEHIND_PROXY=1|" \
      -e "s|^DATABASE_URL=.*|DATABASE_URL=sqlite:///$DATA/avortyx.db|" \
      -e "s|^UPLOAD_DIR=.*|UPLOAD_DIR=$DATA/uploads|" \
      -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://avortyx.com,https://www.avortyx.com,https://avortyx-prototype.vercel.app|" \
      -e "s|^PUBLIC_URL=.*|PUBLIC_URL=https://api.avortyx.com|" \
      -e "s|^TELEGRAM_WEBHOOK_SECRET=.*|TELEGRAM_WEBHOOK_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')|" \
      $APP/.env.example > $APP/.env
  echo "Wrote $APP/.env: fill in the Telegram and SMTP settings there."
fi
# a server set up by the first version: add the settings it doesn't have yet, keep everything else
grep -q '^PUBLIC_URL=' $APP/.env || echo 'PUBLIC_URL=https://api.avortyx.com' >> $APP/.env
# the website's help chat goes to the Customer support topic, applications and access requests to
# the Notifications topic, both in the team group t.me/Avortyx_Sup (edit .env to change either)
grep -q '^TELEGRAM_SUPPORT_CHAT_ID=' $APP/.env || echo 'TELEGRAM_SUPPORT_CHAT_ID=https://t.me/Avortyx_Sup/284' >> $APP/.env
grep -q '^TELEGRAM_NOTIFY_CHAT_ID=' $APP/.env || echo 'TELEGRAM_NOTIFY_CHAT_ID=https://t.me/Avortyx_Sup/285' >> $APP/.env
grep -q '^TELEGRAM_WEBHOOK_SECRET=' $APP/.env || \
  echo "TELEGRAM_WEBHOOK_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> $APP/.env
chown root:avortyx $APP/.env
chmod 640 $APP/.env

[ -d $APP/venv ] || python3 -m venv $APP/venv
$APP/venv/bin/pip install -q --upgrade pip
$APP/venv/bin/pip install -q -r $APP/requirements.txt

# creates the tables once, before the workers start
$APP/deploy/flask.sh routes >/dev/null
systemctl restart avortyx-backend
sleep 2
curl -fsS http://127.0.0.1:8055/health && echo "  <- backend is up"

# https for api.avortyx.com (Let's Encrypt), once DNS points here. certbot only edits our own
# nginx site and reuses the server's existing certbot account; it renews by itself.
DOMAIN=api.avortyx.com
if [ ! -d /etc/letsencrypt/live/$DOMAIN ]; then
  if [ "$(getent ahostsv4 $DOMAIN | awk 'NR==1{print $1}')" = "$(curl -4 -fsS https://api.ipify.org || true)" ]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --redirect \
      $( [ -d /etc/letsencrypt/accounts ] || echo --register-unsafely-without-email ) \
      || echo "certbot failed: the backend still answers on http://$DOMAIN; see the message above"
  else
    echo "Skipping https: $DOMAIN does not point at this server yet. Re-run this script once it does."
  fi
fi
# keep Telegram pointed at this server (needs the bot token in .env and https working)
if grep -q '^TELEGRAM_BOT_TOKEN=.\+' $APP/.env && [ -d /etc/letsencrypt/live/api.avortyx.com ]; then
  $APP/deploy/flask.sh telegram-set-webhook || echo "Telegram webhook not set: see the message above"
fi

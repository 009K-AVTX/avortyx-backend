#!/usr/bin/env bash
# Deploys this folder to the Hostinger VPS:  deploy/deploy.sh root@<server-ip>
# The first run also sets the server up (setup-server.sh) and writes a production .env.
# The database and CVs live in /var/lib/avortyx and are never touched by a deploy.
set -euo pipefail

HOST=${1:?usage: deploy/deploy.sh root@<server-ip>}
APP=/srv/avortyx-backend
cd "$(dirname "$0")/.."

ssh "$HOST" "mkdir -p $APP && (command -v rsync >/dev/null || (apt-get update -q && apt-get install -y -q rsync))"
rsync -az --delete \
  --exclude venv/ --exclude .env --exclude instance/ --exclude uploads/ \
  --exclude .git/ --exclude __pycache__/ --exclude .pytest_cache/ \
  ./ "$HOST:$APP/"

ssh "$HOST" bash -s <<'REMOTE'
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
      $APP/.env.example > $APP/.env
  echo "Wrote $APP/.env: fill in the Telegram and SMTP settings there."
fi
chown root:avortyx $APP/.env
chmod 640 $APP/.env

[ -d $APP/venv ] || python3 -m venv $APP/venv
$APP/venv/bin/pip install -q --upgrade pip
$APP/venv/bin/pip install -q -r $APP/requirements.txt

# creates the tables once, before the workers start
$APP/deploy/flask.sh routes >/dev/null
systemctl restart avortyx-backend
sleep 2
curl -fsS http://127.0.0.1:8000/health && echo "  <- backend is up"
REMOTE

#!/usr/bin/env bash
# One-time setup of a fresh Hostinger VPS (Ubuntu/Debian), run as root on the server.
# deploy.sh copies this over and runs it on the first deploy; it is safe to run again.
set -euo pipefail

APP=/srv/avortyx-backend
DATA=/var/lib/avortyx
DOMAIN=api.avortyx.com

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx ufw rsync

id avortyx >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin avortyx
mkdir -p "$APP" "$DATA/uploads"
chown -R avortyx:avortyx "$DATA"
chmod 750 "$DATA"

ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

install -m 644 "$APP/deploy/nginx.conf" /etc/nginx/sites-available/avortyx-backend
ln -sf /etc/nginx/sites-available/avortyx-backend /etc/nginx/sites-enabled/avortyx-backend
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

install -m 644 "$APP/deploy/avortyx-backend.service" /etc/systemd/system/avortyx-backend.service
systemctl daemon-reload
systemctl enable avortyx-backend

echo "Server ready. HTTPS: certbot --nginx -d $DOMAIN (once DNS points here)."

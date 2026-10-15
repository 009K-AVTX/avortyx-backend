#!/usr/bin/env bash
# One-time setup of the Hostinger VPS (Ubuntu/Debian), run as root on the server.
# install-on-server.sh runs this on the first deploy; it is safe to run again.
#
# The VPS is shared with other sites (api.arbityx.com), so this only ADDS to the server: its own
# nginx site for api.avortyx.com, its own user, folders and service. It never removes other nginx
# sites, never turns the firewall on or changes its existing rules, and only installs packages
# that are missing (so nginx is never upgraded or restarted under the other sites).
set -euo pipefail

APP=/srv/avortyx-backend
DATA=/var/lib/avortyx
PORT=8055

# gunicorn's port must be free (another app on this server may use a common one)
if ss -ltnH "sport = :$PORT" | grep -q . && ! systemctl is-active -q avortyx-backend; then
  echo "Port $PORT is already in use on this server; pick another in deploy/ (service, nginx.conf, install-on-server.sh)." >&2
  exit 1
fi

missing=()
for pkg in python3 python3-venv python3-pip nginx rsync curl; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
# certbot may already be there (apt or snap) for the other sites: reuse it
if ! command -v certbot >/dev/null; then
  missing+=(certbot python3-certbot-nginx)
elif ! certbot plugins 2>/dev/null | grep -q '^\* nginx'; then
  dpkg -s python3-certbot-nginx >/dev/null 2>&1 || missing+=(python3-certbot-nginx)
fi
if [ ${#missing[@]} -gt 0 ]; then
  apt-get update -q
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q "${missing[@]}"
fi

id avortyx >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin avortyx
mkdir -p "$APP" "$DATA/uploads"
chown -R avortyx:avortyx "$DATA"
chmod 750 "$DATA"

# if the firewall is on, make sure web traffic is allowed; never switch it on here
if command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
  ufw allow 'Nginx Full' || ufw allow 80,443/tcp
fi

# our own site only; if nginx rejects the config, take ours back out so the other sites keep running
# (installed once: certbot then adds the https part to this file, and a re-run must keep it)
[ -f /etc/nginx/sites-available/avortyx-backend ] || \
  install -m 644 "$APP/deploy/nginx.conf" /etc/nginx/sites-available/avortyx-backend
ln -sf /etc/nginx/sites-available/avortyx-backend /etc/nginx/sites-enabled/avortyx-backend
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/avortyx-backend
  echo "nginx rejected the avortyx-backend site; it was disabled again and nginx was not reloaded." >&2
  exit 1
fi
systemctl reload nginx

install -m 644 "$APP/deploy/avortyx-backend.service" /etc/systemd/system/avortyx-backend.service
systemctl daemon-reload
systemctl enable avortyx-backend

echo "Server ready."

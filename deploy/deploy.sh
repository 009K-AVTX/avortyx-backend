#!/usr/bin/env bash
# Deploys this folder to the Hostinger VPS from a Mac/Linux machine:  deploy/deploy.sh root@<server-ip>
# (From Windows, or with the code already on the server: run deploy/install-on-server.sh there.)
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

ssh "$HOST" "bash $APP/deploy/install-on-server.sh"

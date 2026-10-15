#!/usr/bin/env bash
# Deploys this folder to the Hostinger VPS from a Mac/Linux machine:  deploy/deploy.sh root@<server-ip>
# On a network that blocks port 22, use the server's second SSH port:  SSH_PORT=2222 deploy/deploy.sh root@<server-ip>
# (From Windows, or with the code already on the server: run deploy/install-on-server.sh there.)
# The first run also sets the server up (setup-server.sh) and writes a production .env.
# The database and CVs live in /var/lib/avortyx and are never touched by a deploy.
set -euo pipefail

HOST=${1:?usage: deploy/deploy.sh root@<server-ip>}
APP=/srv/avortyx-backend
cd "$(dirname "$0")/.."

SSH="ssh -p ${SSH_PORT:-22}"

$SSH "$HOST" "mkdir -p $APP && (command -v rsync >/dev/null || (apt-get update -q && apt-get install -y -q rsync))"
rsync -az --delete -e "$SSH" \
  --exclude venv/ --exclude .env --exclude instance/ --exclude uploads/ \
  --exclude .git/ --exclude __pycache__/ --exclude .pytest_cache/ \
  ./ "$HOST:$APP/"

$SSH "$HOST" "bash $APP/deploy/install-on-server.sh"

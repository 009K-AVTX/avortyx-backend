#!/usr/bin/env bash
# Runs a flask command on the server as the app's user, with the live settings, e.g.
#   /srv/avortyx-backend/deploy/flask.sh create-admin you@avortyx.com
cd /srv/avortyx-backend
exec sudo -u avortyx venv/bin/flask --app wsgi "$@"

#!/usr/bin/env bash
# Launches CodeHaven as a desktop app (Electron window + local backend).
set -e
cd "$(dirname "$(readlink -f "$0")")/../frontend"
[ -d node_modules ] || npm install
[ -d ../backend/.venv ] || { python -m venv ../backend/.venv && ../backend/.venv/bin/pip install -r ../backend/requirements.txt; }
[ -d node_modules/electron/dist ] || node node_modules/electron/install.js
exec npm run app

#!/usr/bin/env bash
# Development mode: opens CodeHaven as a desktop app (Electron window) with hot
# reload. The backend (FastAPI) is started here with auto-reload; Ollama and any
# missing models are started/downloaded by the backend itself.
# For a plain production-style launch use ./scripts/codehaven.sh instead.
set -e
cd "$(dirname "$(readlink -f "$0")")/.."

if [ ! -d backend/.venv ]; then
  python -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements.txt
fi
[ -d frontend/node_modules ] || (cd frontend && npm install)
[ -d frontend/node_modules/electron/dist ] || node frontend/node_modules/electron/install.js

trap 'kill 0' EXIT
# Reuse a backend that is already running instead of failing with "address in use".
if curl -fs -m 2 http://127.0.0.1:8765/api/health >/dev/null; then
  echo "Backend already running on :8765, reusing it."
else
  (cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload) &
fi
# Vite + Electron: the window opens by itself once the dev server is ready.
# Closing the window stops everything.
(cd frontend && npm run app:dev; kill 0) &
wait

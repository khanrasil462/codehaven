# CodeHaven

**Your code stays on your machine.**

An offline AI coding assistant for Python and Web Development students. Built for the ROSP college project — no internet required at runtime, no rate limits, no data sent to third-party servers.

## Features (roadmap)

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Offline chat + Monaco code editor | ✅ |
| 2 | AI code generation (Python/JS/React/TS) | ✅ |
| 3 | Automated bug fixing & traceback debugging | ✅ |
| 4 | PDF / document notes Q&A (RAG built from scratch) | ✅ |
| 5 | University Reference Exam Paper Generator | ✅ |
| 6 | Persistent local storage & SQLite history (chats, notes, exams) | ✅ |
| 7 | Voice input (Whisper) | Planned |
| 8 | Interview / DSA prep | Planned |

## Requirements

- Windows 10/11
- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com/download)
- 8 GB RAM minimum (16 GB recommended)

## One-time setup

Open PowerShell in the project root and run:

```powershell
.\scripts\setup-windows.ps1
```

This will:

1. Create a Python virtual environment and install backend deps
2. Install frontend npm packages
3. Pull Ollama models (`qwen2.5-coder:7b`, `nomic-embed-text`)

## Run on Linux / macOS

```bash
./scripts/dev.sh   # then open http://127.0.0.1:5173
```

The backend starts Ollama if needed and downloads any missing models automatically; progress shows in the sidebar. CodeHaven runs as a web app; Electron is optional (`npm run dev:electron`).

## Run in development (Windows)

```powershell
.\scripts\dev.ps1
```

Or manually:

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload

# Terminal 2 — frontend + Electron
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173** in a browser, or use the Electron window that opens automatically.

## Verify offline mode

1. Complete setup while online (pull models once).
2. Disconnect from the internet.
3. Start the app — chat should still work.

Health check: **http://127.0.0.1:8765/api/health**

## Project structure

```
codehaven/
├── backend/          FastAPI + Ollama integration
├── frontend/         Electron + React + Monaco
├── scripts/          Setup and dev scripts
├── data/             Local storage (gitignored)
└── docs/             Architecture notes
```

## License

College project — ROSP subject.

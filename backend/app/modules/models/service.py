from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

TURBO_MODEL = "qwen2.5-coder:1.5b"

# Downloaded automatically on first run (small: ~1.1 GB total).
REQUIRED_MODELS: list[dict[str, str]] = [
    {"name": settings.embed_model, "role": "Embeddings (notes search)"},
    {"name": TURBO_MODEL, "role": "Fast chat model"},
]
# Larger model, only downloaded when the user asks for Deep mode.
OPTIONAL_MODELS: list[dict[str, str]] = [
    {"name": "qwen2.5-coder:3b", "role": "Balanced coder (1.9 GB)"},
    {"name": settings.chat_model, "role": "Deep coder (4.7 GB)"},
    {"name": "llama3.2:3b", "role": "General chat (2.0 GB)"},
]
ALL_MODELS = REQUIRED_MODELS + OPTIONAL_MODELS
PULL_ATTEMPTS = 6

# Keep Ollama's memory footprint small.
SERVER_ENV = {
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
}

OLLAMA_CANDIDATES = [
    shutil.which("ollama"),
    str(Path.home() / ".local/ollama/bin/ollama"),
    "/usr/local/bin/ollama",
    "/usr/bin/ollama",
]


class ModelManager:
    """Starts Ollama if needed and pulls any missing models, tracking progress."""

    def __init__(self) -> None:
        self.progress: dict[str, dict[str, Any]] = {
            m["name"]: {"status": "unknown", "completed": 0, "total": 0, "error": None}
            for m in ALL_MODELS
        }
        self._task: asyncio.Task | None = None
        self._server: subprocess.Popen | None = None
        self._last_start = 0.0

    @property
    def base(self) -> str:
        return settings.ollama_base_url.rstrip("/")

    def binary(self) -> str | None:
        return next((c for c in OLLAMA_CANDIDATES if c and Path(c).exists()), None)

    async def reachable(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                return (await c.get(f"{self.base}/api/tags")).status_code == 200
        except Exception:
            return False

    async def ensure_server(self) -> bool:
        if await self.reachable():
            return True
        binary = self.binary()
        if not binary:
            return False
        self._server = subprocess.Popen(
            [binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, **SERVER_ENV},
            start_new_session=True,
        )
        for _ in range(30):
            await asyncio.sleep(0.5)
            if await self.reachable():
                return True
        return False

    async def installed(self) -> set[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                res = await c.get(f"{self.base}/api/tags")
                return {m["name"] for m in res.json().get("models", [])}
        except Exception:
            return set()

    @staticmethod
    def _has(name: str, installed: set[str]) -> bool:
        return name in installed or f"{name}:latest" in installed

    async def status(self) -> dict[str, Any]:
        up = await self.reachable()
        busy = bool(self._task and not self._task.done())
        if not busy and self.binary() and time.monotonic() - self._last_start > 30:
            # Retry automatically (e.g. Ollama was just installed, or the network came back).
            have = await self.installed() if up else set()
            if not up or any(not self._has(m["name"], have) for m in REQUIRED_MODELS):
                self.start()
        installed = await self.installed() if up else set()
        models = []
        for m in ALL_MODELS:
            p = self.progress[m["name"]]
            optional = m in OPTIONAL_MODELS
            if self._has(m["name"], installed):
                state = "ready"
            elif p["status"] in ("pulling", "queued"):
                state = p["status"]
            elif p["error"]:
                state = "error"
            else:
                state = "missing"
            models.append({**m, "optional": optional, "state": state, "completed": p["completed"],
                           "total": p["total"], "error": p["error"]})
        return {
            "ollama_installed": self.binary() is not None,
            "ollama_running": up,
            "models": models,
            "ready": up and all(x["state"] == "ready" for x in models if not x["optional"]),
            "busy": bool(self._task and not self._task.done()),
        }

    async def _pull(self, name: str) -> None:
        """Pulls with retries; Ollama resumes partial layers, so retrying is cheap."""
        p = self.progress[name]
        for attempt in range(PULL_ATTEMPTS):
            p.update(status="pulling", error=None)
            if await self._pull_once(name):
                return
            await asyncio.sleep(min(30, 2 ** (attempt + 1)))

    async def _pull_once(self, name: str) -> bool:
        p = self.progress[name]
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as c:
                async with c.stream("POST", f"{self.base}/api/pull",
                                    json={"name": name, "stream": True}) as res:
                    res.raise_for_status()
                    async for line in res.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise RuntimeError(chunk["error"])
                        if chunk.get("total"):
                            p.update(completed=chunk.get("completed", 0), total=chunk["total"])
            p.update(status="done", completed=p["total"])
            return True
        except Exception as exc:
            p.update(status="error", error=str(exc) or exc.__class__.__name__)
            return False

    async def _run(self, names: list[str] | None = None) -> None:
        if not await self.ensure_server():
            for p in self.progress.values():
                p["error"] = "Ollama is not installed or could not start"
            return
        installed = await self.installed()
        wanted = names or [m["name"] for m in REQUIRED_MODELS]
        missing = [n for n in wanted if not self._has(n, installed)]
        for name in missing:
            self.progress[name].update(status="queued", error=None)
        for name in missing:
            await self._pull(name)

    def start(self, names: list[str] | None = None) -> None:
        if self._task and not self._task.done():
            return
        self._last_start = time.monotonic()
        self._task = asyncio.create_task(self._run(names))

    def stop(self) -> None:
        if self._server:
            self._server.terminate()


model_manager = ModelManager()

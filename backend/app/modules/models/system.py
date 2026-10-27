from __future__ import annotations

import httpx
import psutil
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/system", tags=["System"])

psutil.cpu_percent(interval=None)


@router.get("")
async def system_stats() -> dict:
    mem = psutil.virtual_memory()
    loaded: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            res = await c.get(f"{settings.ollama_base_url.rstrip('/')}/api/ps")
            loaded = [
                {"name": m.get("name"), "size": m.get("size", 0), "vram": m.get("size_vram", 0)}
                for m in res.json().get("models", [])
            ]
    except Exception:
        pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_percent": mem.percent,
        "ram_used": mem.used,
        "ram_total": mem.total,
        "loaded_models": loaded,
    }

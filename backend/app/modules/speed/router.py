from fastapi import APIRouter
from pydantic import BaseModel
from app.core.ollama_client import ollama_client, NUM_THREADS, KEEP_ALIVE

router = APIRouter(prefix="/speed", tags=["Speed Optimization"])


class SpeedModeRequest(BaseModel):
    mode: str  # "turbo" | "balanced"


class SpeedStatusResponse(BaseModel):
    active_mode: str
    effective_model: str
    cpu_threads: int
    keep_alive: str
    speed_estimate: str
    all_models: list[str]
    selected_model: str | None = None


@router.get("", response_model=SpeedStatusResponse)
async def get_speed_status() -> SpeedStatusResponse:
    effective = await ollama_client.get_effective_model()
    all_models = await ollama_client.get_available_models()
    estimate = "50-80 tokens/sec (Instant)" if "1.5b" in effective or ollama_client.speed_mode == "turbo" else "12-18 tokens/sec (Deep)"

    return SpeedStatusResponse(
        active_mode=ollama_client.speed_mode,
        effective_model=effective,
        cpu_threads=NUM_THREADS,
        keep_alive=KEEP_ALIVE,
        speed_estimate=estimate,
        all_models=all_models,
        selected_model=ollama_client.selected_model,
    )


@router.post("/mode")
async def set_speed_mode(req: SpeedModeRequest) -> dict[str, str]:
    if req.mode in ("turbo", "balanced"):
        ollama_client.speed_mode = req.mode
        ollama_client.selected_model = None
    effective = await ollama_client.get_effective_model()
    return {
        "status": "updated",
        "active_mode": ollama_client.speed_mode,
        "effective_model": effective,
    }

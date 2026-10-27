from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.ollama_client import ollama_client

from app.modules.models.service import model_manager

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("")
async def models_status() -> dict:
    return await model_manager.status()


class SelectRequest(BaseModel):
    name: str | None = None


@router.post("/select")
async def select_model(req: SelectRequest) -> dict:
    """Pins the model used for chat; null returns to the Fast/Deep mode default."""
    if req.name and req.name not in await model_manager.installed():
        raise HTTPException(status_code=400, detail="Model is not downloaded")
    ollama_client.selected_model = req.name
    return {"selected": ollama_client.selected_model, "effective": await ollama_client.get_effective_model()}


@router.post("/pull")
async def pull_missing(name: str | None = None) -> dict:
    model_manager.start([name] if name else None)
    return await model_manager.status()

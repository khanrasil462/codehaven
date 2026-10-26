from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.chat.router import router as chat_router
from app.modules.codegen.router import router as codegen_router
from app.modules.debug.router import router as debug_router
from app.modules.history.router import router as history_router
from app.modules.images.router import router as images_router
from app.modules.interview.router import router as interview_router
from app.modules.rag.router import router as rag_router
from app.modules.runner.router import router as runner_router
from app.modules.speed.router import router as speed_router
from app.modules.voice.router import router as voice_router

app = FastAPI(
    title=settings.app_name,
    description="Offline AI coding assistant for students.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(debug_router, prefix="/api")
app.include_router(codegen_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(runner_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(speed_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(interview_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    try:
        ollama = await ollama_client.health()
    except Exception as exc:
        ollama = {"reachable": False, "error": str(exc), "models": []}

    return {
        "app": settings.app_name,
        "offline_mode": settings.offline_mode,
        "chat_model": settings.chat_model,
        "embed_model": settings.embed_model,
        "ollama": ollama,
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API is running."}

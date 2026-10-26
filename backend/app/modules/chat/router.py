from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are CodeHaven, a fast, helpful offline coding assistant for students. "
    "You specialize in Python, JavaScript (React, Node.js), algorithms, and debugging. "
    "Be concise, direct, and provide clean code examples. Avoid unnecessary conversational fluff."
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse | StreamingResponse:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Sliding window: keep only the last 6 turns to keep prompt small & evaluation ultra-fast
    turns = [m.model_dump() for m in request.messages]
    if len(turns) > 6:
        turns = turns[-6:]
    messages.extend(turns)

    target_model = await ollama_client.get_effective_model(request.model)

    if request.stream:
        async def event_stream():
            try:
                async for token in ollama_client.chat_stream(messages, model=target_model):
                    yield token
            except Exception as exc:
                yield f"\n\n[Error: {exc}]"

        return StreamingResponse(event_stream(), media_type="text/plain")

    try:
        content = await ollama_client.chat(messages, model=target_model)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    return ChatResponse(content=content, model=target_model)

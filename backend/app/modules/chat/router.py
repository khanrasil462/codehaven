from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.chat.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are CodeHaven, a friendly offline assistant running entirely on the user's computer. "
    "Chat naturally like a helpful colleague: greetings, questions and explanations get normal conversational replies. "
    "You are especially strong at programming (Python, JavaScript, TypeScript, HTML/CSS, Java, C/C++, bash). "
    "When the user asks for code, a program, a script or a website, reply with one or two short sentences, then give the "
    "complete, runnable code in a single fenced block tagged with its language (```python, ```html, ```bash ...). "
    "Websites must be one self-contained HTML file with inline CSS and JS, and must work offline: no external images, fonts, CDNs or links (use CSS gradients, emoji or inline SVG instead). "
    "The interface shows Copy and Run buttons under every code block, so never explain how to compile or run it. "
    "Keep replies concise and avoid filler."
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

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.debug.extract import extract_debug_response
from app.modules.debug.prompts import build_debug_messages
from app.modules.debug.schemas import DebugRequest, DebugResponse
from app.modules.debug.traceback_parser import parse_error

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/analyze", response_model=None)
async def analyze_code(request: DebugRequest) -> DebugResponse | StreamingResponse:
    parsed = parse_error(request.error_message or "", request.language.value)
    messages = build_debug_messages(
        request.code,
        request.language.value,
        request.error_message,
        parsed,
    )
    model = await ollama_client.get_effective_model(request.model)

    if request.stream:
        async def event_stream():
            try:
                async for token in ollama_client.chat_stream(messages, model=model):
                    yield token
            except Exception as exc:
                yield f"\n\n[Error: {exc}]"

        return StreamingResponse(event_stream(), media_type="text/plain")

    try:
        raw = await ollama_client.chat(messages, model=model)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    diagnosis, explanation, fixed_code = extract_debug_response(raw)
    return DebugResponse(
        diagnosis=diagnosis,
        explanation=explanation,
        fixed_code=fixed_code,
        language=request.language.value,
        model=model,
    )


@router.get("/status")
async def debug_status() -> dict[str, str]:
    return {
        "status": "ready",
        "languages": "python,javascript,typescript,react",
    }

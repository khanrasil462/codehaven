from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.codegen.extract import extract_code, extract_explanation
from app.modules.codegen.prompts import build_codegen_messages
from app.modules.codegen.schemas import CodegenRequest, CodegenResponse

router = APIRouter(prefix="/codegen", tags=["codegen"])


@router.post("/generate", response_model=None)
async def generate_code(request: CodegenRequest) -> CodegenResponse | StreamingResponse:
    messages = build_codegen_messages(
        request.prompt,
        request.language.value,
        request.include_explanation,
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

    code = extract_code(raw)
    explanation = extract_explanation(raw, code) if request.include_explanation else None
    return CodegenResponse(
        code=code,
        explanation=explanation,
        language=request.language.value,
        model=model,
    )


@router.get("/status")
async def codegen_status() -> dict[str, str]:
    return {
        "status": "ready",
        "languages": "python,javascript,typescript,react",
    }

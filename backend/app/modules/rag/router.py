from __future__ import annotations

import json
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.rag.exam_prompts import build_exam_paper_messages, build_rag_qa_messages
from app.modules.rag.schemas import (
    DocumentInfo,
    ExamGenerateRequest,
    ExamPaperResponse,
    QueryRequest,
    QueryResponse,
    SourceChunk,
)
from app.modules.rag.vector_store import vector_store

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/status")
async def rag_status() -> dict:
    docs = vector_store.list_documents()
    return {
        "status": "ready",
        "documents_count": len(docs),
        "total_chunks": len(vector_store.chunks),
        "embed_model": settings.embed_model,
        "chat_model": settings.chat_model,
    }


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents() -> list[DocumentInfo]:
    return vector_store.list_documents()


@router.post("/upload", response_model=DocumentInfo)
async def upload_document(file: UploadFile = File(...)) -> DocumentInfo:
    filename = file.filename or "uploaded_note.txt"
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")
        doc_info = await vector_store.add_document(content, filename)
        if doc_info.chunk_count == 0:
            raise HTTPException(
                status_code=422,
                detail=f"No text or characters could be extracted from '{filename}'. If it is a scanned image, ensure it contains clear readable text.",
            )
        return doc_info
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to process and index document: {exc}"
        ) from exc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, Any]:
    success = vector_store.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"success": True, "message": "Document deleted successfully."}


@router.post("/search", response_model=list[SourceChunk])
async def search_notes(query: str, doc_id: str | None = None, top_k: int = 4) -> list[SourceChunk]:
    return await vector_store.search(query=query, top_k=top_k, doc_id=doc_id)


@router.post("/query", response_model=None)
async def query_notes(request: QueryRequest) -> QueryResponse | StreamingResponse:
    if not vector_store.chunks:
        raise HTTPException(
            status_code=400,
            detail="No notes have been uploaded yet. Please upload notes first.",
        )

    sources = await vector_store.search(
        query=request.question,
        top_k=request.top_k,
        doc_id=request.doc_id,
    )

    messages = build_rag_qa_messages(request.question, sources)
    model = await ollama_client.get_effective_model(request.model)

    if request.stream:
        async def event_stream():
            try:
                sources_payload = json.dumps([s.model_dump() for s in sources])
                yield f"__SOURCES__:{sources_payload}\n\n"
                async for token in ollama_client.chat_stream(messages, model=model):
                    yield token
            except Exception as exc:
                yield f"\n\n[Error generating answer: {exc}]"

        return StreamingResponse(event_stream(), media_type="text/plain")

    try:
        answer = await ollama_client.chat(messages, model=model)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    return QueryResponse(
        answer=answer,
        sources=sources,
        model=model,
    )


@router.post("/exam/generate", response_model=None)
async def generate_exam(request: ExamGenerateRequest) -> ExamPaperResponse | StreamingResponse:
    if not vector_store.chunks:
        raise HTTPException(
            status_code=400,
            detail="No notes available to generate an exam paper. Please upload notes first.",
        )

    notes_text = vector_store.get_all_notes_text(doc_ids=request.doc_ids)
    if not notes_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No content found in the selected documents.",
        )

    messages = build_exam_paper_messages(request, notes_text)
    model = await ollama_client.get_effective_model(request.model)

    if request.stream:
        async def exam_stream():
            try:
                async for token in ollama_client.chat_stream(messages, model=model):
                    yield token
            except Exception as exc:
                yield f"\n\n[Error generating exam paper: {exc}]"

        return StreamingResponse(exam_stream(), media_type="text/plain")

    try:
        content = await ollama_client.chat(messages, model=model)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    return ExamPaperResponse(
        title=request.title,
        subject=request.subject,
        difficulty=request.difficulty,
        total_marks=request.total_marks,
        duration_minutes=request.duration_minutes,
        content=content,
        model=model,
    )

from __future__ import annotations

import io
import json
import math
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.ollama_client import ollama_client
from app.modules.rag.schemas import DocumentInfo, SourceChunk


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2:
        return 0.0
    if len(v1) != len(v2):
        max_len = max(len(v1), len(v2))
        v1 = v1 + [0.0] * (max_len - len(v1))
        v2 = v2 + [0.0] * (max_len - len(v2))

    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()

    # 1. Standalone image notes (screenshots, scans, photos)
    if ext in IMAGE_EXTENSIONS:
        try:
            from app.core.ocr import ocr_image_bytes
            extracted = ocr_image_bytes(file_bytes)
            if extracted.strip():
                return f"--- Image Note ({filename}) ---\n{extracted.strip()}"
        except Exception:
            pass
        return ""

    # 2. PDF documents (digital or scanned)
    elif ext == ".pdf":
        from pypdf import PdfReader
        from app.core.ocr import ocr_scanned_pdf

        pages_text: list[str] = []
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()
                if text:
                    pages_text.append(f"--- Page {i + 1} ---\n{text}")
        except Exception:
            pages_text = []

        total_digital_text = "\n\n".join(pages_text).strip()
        # If PDF has no digital text or sparse text (< 25 chars per page), run native OCR on scanned pages
        if not total_digital_text or len(total_digital_text) < max(25, len(pages_text) * 20):
            scanned_ocr_text = ocr_scanned_pdf(file_bytes)
            if scanned_ocr_text.strip():
                return scanned_ocr_text

        return total_digital_text

    # 3. Microsoft Word (.docx)
    elif ext == ".docx":
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    # 4. Plain text / Markdown / Source code notes
    else:
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")


def chunk_text(text: str, chunk_size: int = 700, chunk_overlap: int = 100) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    paragraphs = re.split(r"\n\s*\n", cleaned)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue

        if len(para_clean) > chunk_size:
            sentences = re.split(r"(?<=[.?!])\s+", para_clean)
            for s in sentences:
                s_clean = s.strip()
                if not s_clean:
                    continue
                if current_len + len(s_clean) > chunk_size and current_chunk:
                    chunk_str = " ".join(current_chunk)
                    chunks.append(chunk_str)
                    overlap_tokens = chunk_str[-chunk_overlap:] if len(chunk_str) > chunk_overlap else ""
                    if overlap_tokens and " " in overlap_tokens:
                        overlap_tokens = overlap_tokens[overlap_tokens.find(" ") + 1:].strip()
                    current_chunk = [overlap_tokens, s_clean] if overlap_tokens else [s_clean]
                    current_len = sum(len(x) for x in current_chunk)
                else:
                    current_chunk.append(s_clean)
                    current_len += len(s_clean)
        else:
            if current_len + len(para_clean) > chunk_size and current_chunk:
                chunk_str = "\n\n".join(current_chunk)
                chunks.append(chunk_str)
                overlap_tokens = chunk_str[-chunk_overlap:] if len(chunk_str) > chunk_overlap else ""
                if overlap_tokens and " " in overlap_tokens:
                    overlap_tokens = overlap_tokens[overlap_tokens.find(" ") + 1:].strip()
                current_chunk = [overlap_tokens, para_clean] if overlap_tokens else [para_clean]
                current_len = sum(len(x) for x in current_chunk)
            else:
                current_chunk.append(para_clean)
                current_len += len(para_clean)

    if current_chunk:
        chunk_str = "\n\n".join(current_chunk).strip()
        if chunk_str:
            chunks.append(chunk_str)

    return chunks


class VectorStore:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = (storage_dir or settings.data_dir / "notes").resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.docs_file = self.storage_dir / "documents.json"
        self.chunks_file = self.storage_dir / "chunks.json"

        self.documents: dict[str, dict[str, Any]] = {}
        self.chunks: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.docs_file.exists():
            try:
                with open(self.docs_file, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                self.documents = {}

        if self.chunks_file.exists():
            try:
                with open(self.chunks_file, "r", encoding="utf-8") as f:
                    self.chunks = json.load(f)
            except Exception:
                self.chunks = []

    def _save(self) -> None:
        with open(self.docs_file, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, indent=2)

        with open(self.chunks_file, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, indent=2)

    async def _compute_embedding(self, text: str) -> list[float]:
        try:
            emb = await ollama_client.embeddings(text)
            if emb:
                return emb
        except Exception:
            pass

        # Fallback pseudo-embedding (character / term frequency hashing for offline resilience)
        vec = [0.0] * 768
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec
        for word in words:
            h = abs(hash(word)) % 768
            vec[h] += 1.0
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    async def add_document(self, file_bytes: bytes, filename: str) -> DocumentInfo:
        doc_id = str(uuid.uuid4())
        text = extract_text_from_file(file_bytes, filename)
        file_type = Path(filename).suffix.lower() or "txt"

        raw_chunks = chunk_text(text)
        created_at = datetime.now().isoformat()

        doc_record = {
            "id": doc_id,
            "filename": filename,
            "file_type": file_type,
            "size_bytes": len(file_bytes),
            "chunk_count": len(raw_chunks),
            "char_count": len(text),
            "created_at": created_at,
        }

        # Save document original file
        saved_file_path = self.storage_dir / f"{doc_id}_{filename}"
        with open(saved_file_path, "wb") as f:
            f.write(file_bytes)

        # Compute embeddings for all chunks
        for i, chunk_str in enumerate(raw_chunks):
            emb = await self._compute_embedding(chunk_str)
            self.chunks.append({
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i + 1,
                "text": chunk_str,
                "embedding": emb,
            })

        self.documents[doc_id] = doc_record
        self._save()

        return DocumentInfo(**doc_record)

    def list_documents(self) -> list[DocumentInfo]:
        return [DocumentInfo(**doc) for doc in self.documents.values()]

    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self.documents:
            return False

        doc = self.documents.pop(doc_id)
        # Remove file on disk if exists
        saved_file = self.storage_dir / f"{doc_id}_{doc['filename']}"
        if saved_file.exists():
            try:
                saved_file.unlink()
            except Exception:
                pass

        # Filter out chunks
        self.chunks = [c for c in self.chunks if c.get("doc_id") != doc_id]
        self._save()
        return True

    async def search(
        self,
        query: str,
        top_k: int = 4,
        doc_id: str | None = None,
    ) -> list[SourceChunk]:
        if not self.chunks:
            return []

        query_emb = await self._compute_embedding(query)
        candidates = self.chunks
        if doc_id:
            candidates = [c for c in candidates if c.get("doc_id") == doc_id]

        scored: list[tuple[float, dict[str, Any]]] = []
        for c in candidates:
            score = cosine_similarity(query_emb, c.get("embedding", []))
            # Also slight boost for exact keyword occurrences
            query_words = set(re.findall(r"\w{3,}", query.lower()))
            chunk_words = set(re.findall(r"\w{3,}", c.get("text", "").lower()))
            if query_words:
                keyword_overlap = len(query_words.intersection(chunk_words)) / len(query_words)
                score = (0.85 * score) + (0.15 * keyword_overlap)

            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored[:top_k]

        return [
            SourceChunk(
                doc_id=c["doc_id"],
                filename=c["filename"],
                chunk_index=c["chunk_index"],
                similarity=round(score, 4),
                text=c["text"],
            )
            for score, c in top_matches
        ]

    def get_document_content(self, doc_id: str) -> str:
        doc_chunks = [c for c in self.chunks if c.get("doc_id") == doc_id]
        doc_chunks.sort(key=lambda c: c.get("chunk_index", 0))
        return "\n\n".join(c.get("text", "") for c in doc_chunks)

    def get_all_notes_text(self, doc_ids: list[str] | None = None, max_chars: int = 25000) -> str:
        chunks_to_use = self.chunks
        if doc_ids:
            chunks_to_use = [c for c in chunks_to_use if c.get("doc_id") in doc_ids]

        combined = []
        total_len = 0
        for c in chunks_to_use:
            snippet = f"[{c.get('filename')}, Part {c.get('chunk_index')}]:\n{c.get('text')}"
            combined.append(snippet)
            total_len += len(snippet)
            if total_len >= max_chars:
                break

        return "\n\n".join(combined)


vector_store = VectorStore()

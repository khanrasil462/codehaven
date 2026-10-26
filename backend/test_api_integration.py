import asyncio
import io
import httpx
from PIL import Image, ImageDraw
from app.main import app


async def run_integration_tests():
    print("=== Testing CodeHaven FastAPI Endpoints (In-Memory ASGI) ===")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        res = await client.get("/api/health")
        print(f"[PASS] GET /api/health -> Status: {res.status_code}")
        assert res.status_code == 200
        health_data = res.json()
        print(f"       App: {health_data['app']}, Ollama reachable: {health_data['ollama'].get('reachable')}")

        # 2. RAG status
        res = await client.get("/api/rag/status")
        print(f"[PASS] GET /api/rag/status -> Status: {res.status_code}, data: {res.json()}")
        assert res.status_code == 200

        # 3. Upload a sample text document
        sample_doc_content = (
            "Subject: Operating Systems\n\n"
            "Chapter 1: Process Management\n"
            "A process is a program in execution. The Process Control Block (PCB) contains process state, "
            "program counter, CPU registers, and scheduling information.\n\n"
            "Chapter 2: Deadlocks\n"
            "Four Coffman conditions must hold simultaneously for a deadlock to occur: "
            "1. Mutual Exclusion, 2. Hold and Wait, 3. No Preemption, 4. Circular Wait.\n"
            "Banker's Algorithm is used for deadlock avoidance using Resource-Allocation Graphs.\n\n"
            "Chapter 3: Virtual Memory\n"
            "Paging allows physical address space of a process to be non-contiguous. "
            "Page Fault occurs when a referenced page is not present in main memory."
        )

        files = {"file": ("operating_systems_notes.txt", sample_doc_content.encode("utf-8"), "text/plain")}
        res = await client.post("/api/rag/upload", files=files)
        print(f"[PASS] POST /api/rag/upload (text) -> Status: {res.status_code}")
        assert res.status_code == 200
        text_doc_data = res.json()
        text_doc_id = text_doc_data["id"]
        print(f"       Uploaded text doc ID: {text_doc_id}, chunks: {text_doc_data['chunk_count']}")

        # 4. Upload an image document for OCR extraction
        img = Image.new("RGB", (450, 120), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((25, 45), "CodeHaven Operating Systems OCR Ingestion", fill=(0, 0, 0))
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_bytes = img_buf.getvalue()

        img_files = {"file": ("os_diagram_ocr.png", img_bytes, "image/png")}
        res = await client.post("/api/rag/upload", files=img_files)
        print(f"[PASS] POST /api/rag/upload (image OCR) -> Status: {res.status_code}")
        assert res.status_code == 200
        img_doc_data = res.json()
        img_doc_id = img_doc_data["id"]
        print(f"       Uploaded image doc ID: {img_doc_id}, chunks: {img_doc_data['chunk_count']}")

        # 5. List documents
        res = await client.get("/api/rag/documents")
        print(f"[PASS] GET /api/rag/documents -> Found {len(res.json())} document(s)")
        assert any(d["id"] == text_doc_id for d in res.json())
        assert any(d["id"] == img_doc_id for d in res.json())

        # 6. Semantic Search for text notes
        res = await client.post(
            "/api/rag/search",
            params={"query": "What are the four conditions for deadlock?", "top_k": 2},
        )
        print(f"[PASS] POST /api/rag/search (text) -> Status: {res.status_code}, matches: {len(res.json())}")
        assert len(res.json()) > 0
        top_match = res.json()[0]
        print(f"       Top match similarity: {top_match['similarity']:.4f}, doc: {top_match['filename']}")

        # 7. Semantic Search for OCR image notes
        res = await client.post(
            "/api/rag/search",
            params={"query": "Operating Systems OCR Ingestion", "top_k": 2},
        )
        print(f"[PASS] POST /api/rag/search (OCR) -> Status: {res.status_code}, matches: {len(res.json())}")
        assert len(res.json()) > 0
        ocr_match = next((m for m in res.json() if m["doc_id"] == img_doc_id), None)
        assert ocr_match is not None, "OCR image note was not matched in search!"
        print(f"       OCR match score: {ocr_match['similarity']:.4f}, doc: {ocr_match['filename']}")

        # 8. History API verification
        conv_payload = {"title": "OS Revision Session", "mode": "notes_qa"}
        res = await client.post("/api/history/conversations", json=conv_payload)
        print(f"[PASS] POST /api/history/conversations -> Status: {res.status_code}")
        assert res.status_code == 200
        conv_data = res.json()
        conv_id = conv_data["id"]

        msg_payload = {"role": "user", "content": "Explain Coffman conditions"}
        res = await client.post(f"/api/history/conversations/{conv_id}/messages", json=msg_payload)
        print(f"[PASS] POST /api/history/conversations/{conv_id}/messages -> Status: {res.status_code}")
        assert res.status_code == 200

        res = await client.get(f"/api/history/conversations/{conv_id}")
        assert res.status_code == 200
        assert len(res.json()["messages"]) == 1
        print(f"[PASS] GET /api/history/conversations/{conv_id} -> Verified message storage")

        # 9. Clean up test documents and conversation
        res = await client.delete(f"/api/rag/documents/{text_doc_id}")
        assert res.status_code == 200
        res = await client.delete(f"/api/rag/documents/{img_doc_id}")
        assert res.status_code == 200
        res = await client.delete(f"/api/history/conversations/{conv_id}")
        assert res.status_code == 200
        print(f"[PASS] Cleaned up text doc, OCR image doc, and history conversation.")

    print("\nALL FASTAPI INTEGRATION & OCR TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())


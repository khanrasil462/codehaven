import asyncio
from app.modules.rag.vector_store import vector_store
from app.modules.rag.schemas import ExamGenerateRequest
from app.modules.rag.exam_prompts import build_rag_qa_messages, build_exam_paper_messages


async def run_tests():
    print("=== Testing CodeHaven RAG & Exam Generator ===")

    # 1. Ingest test notes
    sample_text = (
        "Unit 1: Data Structures and Algorithms\n\n"
        "1. Binary Search: An algorithm that finds the position of a target value within a sorted array. "
        "Binary search compares the target value to the middle element of the array. "
        "Time complexity is O(log n) in best and worst cases. Space complexity is O(1) iterative.\n\n"
        "2. Quick Sort: A divide-and-conquer algorithm. It works by selecting a 'pivot' element from the array "
        "and partitioning the other elements into two sub-arrays. Average time complexity is O(n log n), "
        "worst case is O(n^2) when array is already sorted and bad pivot is chosen.\n\n"
        "3. Breadth-First Search (BFS): Graph traversal algorithm using a Queue data structure (FIFO). "
        "Time complexity is O(V + E). It finds the shortest path in unweighted graphs.\n\n"
        "4. Depth-First Search (DFS): Uses recursion or a Stack (LIFO). Explores as far as possible along each branch."
    )

    doc = await vector_store.add_document(sample_text.encode("utf-8"), "algorithms_unit1.txt")
    print(f"[PASS] Ingested document: {doc.filename}, ID: {doc.id}, Chunks: {doc.chunk_count}")

    # 2. Search query
    query = "What is the time complexity and worst case of quick sort?"
    results = await vector_store.search(query, top_k=2)
    assert len(results) > 0, "No search results returned!"
    print(f"[PASS] Vector Search returned {len(results)} matches.")
    print(f"  Top Match (Score: {results[0].similarity}): {results[0].text[:90]}...")

    # 3. Test Q&A message builder
    qa_messages = build_rag_qa_messages(query, results)
    assert len(qa_messages) == 2
    assert "algorithms_unit1.txt" in qa_messages[1]["content"]
    print("[PASS] RAG Grounded Q&A prompt constructed successfully with citations.")

    # 4. Test Exam paper prompt builder
    exam_req = ExamGenerateRequest(
        title="Mid-Semester Exam on Algorithms",
        subject="Data Structures & Algorithms",
        difficulty="medium",
        total_marks=50,
        duration_minutes=60,
        include_solutions=True,
    )
    notes_text = vector_store.get_all_notes_text()
    exam_messages = build_exam_paper_messages(exam_req, notes_text)
    assert len(exam_messages) == 2
    assert "SECTION A: MULTIPLE CHOICE QUESTIONS" in exam_messages[1]["content"]
    assert "SECTION D: COMPLETE MARKING SCHEME" in exam_messages[1]["content"]
    print("[PASS] University Reference Exam Paper prompt constructed successfully.")

    # 5. Test OCR Image Ingestion & Search
    import io
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (450, 120), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((25, 45), "CodeHaven Offline OCR Ingestion Test", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    ocr_doc = await vector_store.add_document(img_bytes, "ocr_sample_test.png")
    assert ocr_doc.chunk_count > 0, "OCR document produced 0 chunks!"
    print(f"[PASS] Ingested image via OCR: {ocr_doc.filename}, Chunks: {ocr_doc.chunk_count}")

    ocr_results = await vector_store.search("Offline OCR Ingestion", top_k=1)
    assert len(ocr_results) > 0, "OCR document search returned 0 results!"
    assert ocr_results[0].doc_id == ocr_doc.id, "Top search match was not the OCR document!"
    print(f"[PASS] Vector search matched OCR extracted content: '{ocr_results[0].text[:50]}...'")

    # Clean up test docs
    vector_store.delete_document(doc.id)
    vector_store.delete_document(ocr_doc.id)
    print("[PASS] Cleanup completed.")
    print("\nALL RAG, EXAM & OCR UNIT TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_tests())

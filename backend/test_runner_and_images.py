import asyncio
from app.modules.runner.service import runner_service
from app.modules.runner.schemas import ExecuteRequest
from app.modules.images.service import image_service
from app.modules.images.schemas import ImageGenerateRequest


async def run_tests():
    print("=== Testing CodeHaven Code Execution Runner ===")

    # 1. Available runtimes
    runtimes = runner_service.get_available_runtimes()
    print(f"[PASS] Detected {len(runtimes)} runtimes:")
    for r in runtimes:
        print(f"       - {r.name}: available={r.available}, version={r.version}")
    assert any(r.id == "python" and r.available for r in runtimes), "Python runtime not available!"

    # 2. Run Python script
    req = ExecuteRequest(
        code='print("Hello from CodeHaven Runner!")\nfor i in range(3):\n    print(f"Count: {i}")\n',
        language="python",
    )
    res = await runner_service.execute(req)
    print(f"[PASS] Python execution -> status: {res.status}, time: {res.execution_time_ms}ms")
    assert res.status == "success"
    assert "Hello from CodeHaven Runner!" in res.stdout
    assert "Count: 2" in res.stdout

    # 3. Python Stdin support
    req_stdin = ExecuteRequest(
        code='name = input()\nprint(f"Greeting: Welcome {name}!")\n',
        language="python",
        stdin="Rasil",
    )
    res_stdin = await runner_service.execute(req_stdin)
    print(f"[PASS] Python stdin execution -> status: {res_stdin.status}")
    assert res_stdin.status == "success"
    assert "Greeting: Welcome Rasil!" in res_stdin.stdout

    # 4. Error capture
    req_err = ExecuteRequest(
        code='raise ValueError("Custom student test error")',
        language="python",
    )
    res_err = await runner_service.execute(req_err)
    print(f"[PASS] Python error capture -> status: {res_err.status}")
    assert res_err.status == "error"
    assert "ValueError: Custom student test error" in res_err.stderr

    # 5. Infinite loop timeout
    req_timeout = ExecuteRequest(
        code='import time\nwhile True:\n    time.sleep(0.1)\n',
        language="python",
        timeout_seconds=1.5,
    )
    res_timeout = await runner_service.execute(req_timeout)
    print(f"[PASS] Python timeout handling -> status: {res_timeout.status}")
    assert res_timeout.status == "timeout"

    # 6. Node.js JavaScript execution (if available)
    node_rt = next((r for r in runtimes if r.id == "javascript" and r.available), None)
    if node_rt:
        req_js = ExecuteRequest(
            code='const arr = [1, 2, 3, 4]; console.log("Sum:", arr.reduce((a, b) => a + b, 0));',
            language="javascript",
        )
        res_js = await runner_service.execute(req_js)
        print(f"[PASS] JavaScript execution -> status: {res_js.status}, stdout: {res_js.stdout.strip()}")
        assert res_js.status == "success"
        assert "Sum: 10" in res_js.stdout

    print("\n=== Testing CodeHaven Image & Diagram Studio ===")

    # 7. Fallback / procedural SVG generator
    fallback_svg = image_service._generate_fallback_svg("Microservices Architecture", "architecture", "0 0 1200 675")
    assert "<svg" in fallback_svg and "</svg>" in fallback_svg
    assert "Microservices Architecture" in fallback_svg
    print("[PASS] Fallback SVG generator produces valid scalable XML markup.")

    # 8. List & Catalog check
    images = image_service.list_images()
    print(f"[PASS] Image catalog accessible, currently contains {len(images)} images.")

    print("\nALL RUNNER & IMAGE SERVICE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())

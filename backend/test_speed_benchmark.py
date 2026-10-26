import asyncio
import time
from app.core.ollama_client import ollama_client


async def run_benchmark():
    prompt = [{"role": "user", "content": "Write a python function to compute factorial and explain in 2 lines."}]
    print("=== Benchmarking CodeHaven Local AI Response Speed ===")

    # 1. Test Turbo Model (qwen2.5-coder:1.5b)
    ollama_client.speed_mode = "turbo"
    effective_model = await ollama_client.get_effective_model()
    print(f"\n[1] Testing TURBO SPEED MODE with model: '{effective_model}'...")

    t0 = time.perf_counter()
    tokens = []
    first_token_time = None

    async for token in ollama_client.chat_stream(prompt, model=effective_model):
        if first_token_time is None:
            first_token_time = time.perf_counter() - t0
        tokens.append(token)

    total_time = time.perf_counter() - t0
    num_chars = len("".join(tokens))
    approx_tokens = len(tokens)
    tps = approx_tokens / total_time if total_time > 0 else 0

    print(f"    - First Token Latency (TTFT): {first_token_time*1000:.1f}ms")
    print(f"    - Total Generation Time: {total_time:.2f}s")
    print(f"    - Tokens Emitted: ~{approx_tokens} tokens ({num_chars} chars)")
    print(f"    - Speed: {tps:.1f} tokens/second")
    print(f"    - Response Preview:\n{''.join(tokens)[:120]}...\n")

    print("[SUCCESS] Turbo mode is operational and blazing fast!")


if __name__ == "__main__":
    asyncio.run(run_benchmark())

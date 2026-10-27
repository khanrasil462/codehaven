from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.core.usage import record_usage

# Optimal thread allocation for Intel / AMD multi-core CPUs
# Intel Core Ultra 5 125H has 14 cores (18 threads); 8-10 threads achieves peak throughput without thermal throttling.
NUM_THREADS = max(4, min(12, (os.cpu_count() or 8) - 2))
KEEP_ALIVE = "5m"  # Free the model's RAM shortly after the last request


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._cache: dict[str, str] = {}
        self.speed_mode: str = "turbo"  # "turbo" (1.5B) | "balanced" (7B)
        self.selected_model: str | None = None  # explicit pick from the model dropdown

    def _get_cache_key(self, messages: list[dict[str, str]], model: str) -> str:
        raw = f"{model}::" + json.dumps(messages, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def get_effective_model(self, requested_model: str | None = None) -> str:
        """Determines the fastest available model based on speed mode."""
        if requested_model:
            return requested_model
        if self.selected_model:
            if self.selected_model in await self.get_available_models():
                return self.selected_model
            self.selected_model = None

        if self.speed_mode == "turbo":
            tags = await self.get_available_models()
            # If 1.5b is installed, use it for turbo speed!
            for m in tags:
                if "1.5b" in m:
                    return m
            return settings.chat_model
        # Deep mode: use the large model only if it has been downloaded.
        tags = await self.get_available_models()
        if any(m.split(":")[0] == settings.chat_model.split(":")[0] and m.startswith(settings.chat_model) for m in tags):
            return settings.chat_model
        for m in tags:
            if "1.5b" in m:
                return m
        return settings.chat_model

    async def get_available_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    tags = res.json()
                    return [m.get("name", "") for m in tags.get("models", [])]
        except Exception:
            pass
        return []

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            tags = response.json()
            models = [m.get("name", "") for m in tags.get("models", [])]
            return {
                "reachable": True,
                "models": models,
                "chat_model_available": any(
                    settings.chat_model.split(":")[0] in m for m in models
                ),
                "speed_mode": self.speed_mode,
                "cpu_threads": NUM_THREADS,
            }

    def get_optimized_options(self, custom_options: dict[str, Any] | None = None) -> dict[str, Any]:
        """Tuned Ollama inference options for maximum generation speed on local hardware."""
        is_turbo = self.speed_mode == "turbo"
        opts: dict[str, Any] = {
            "num_thread": NUM_THREADS,
            "num_ctx": 2048 if is_turbo else 3072,  # Compact context prefill is 3x faster
            "temperature": 0.2 if is_turbo else 0.3, # Low temperature reduces sampling hesitation
            "top_k": 40,
            "top_p": 0.9,
            "num_predict": 1024,
        }
        if custom_options:
            opts.update(custom_options)
        return opts

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> AsyncIterator[str]:
        target_model = await self.get_effective_model(model)
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "keep_alive": KEEP_ALIVE,
            "options": self.get_optimized_options(options),
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("done"):
                        record_usage(
                            target_model,
                            int(chunk.get("prompt_eval_count") or 0),
                            int(chunk.get("eval_count") or 0),
                        )
                        break
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> str:
        target_model = await self.get_effective_model(model)
        cache_key = self._get_cache_key(messages, target_model) + ("j" if json_mode else "")
        if cache_key in self._cache:
            return self._cache[cache_key]

        parts: list[str] = []
        async for token in self.chat_stream(messages, model=target_model, options=options, json_mode=json_mode):
            parts.append(token)
        result = "".join(parts)
        if len(self._cache) < 200:
            self._cache[cache_key] = result
        return result

    async def embeddings(
        self,
        prompt: str,
        model: str | None = None,
    ) -> list[float]:
        payload = {
            "model": model or settings.embed_model,
            "prompt": prompt,
            "keep_alive": "1m",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])


ollama_client = OllamaClient()

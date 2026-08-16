"""Thin HTTP client for local Ollama."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings


class OllamaError(Exception):
    def __init__(self, message: str, *, unavailable: bool = False) -> None:
        super().__init__(message)
        self.unavailable = unavailable


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                tags = await client.get(f"{self.base_url}/api/tags")
                tags.raise_for_status()
                return {"status": "up", "models": [m["name"] for m in tags.json().get("models", [])]}
        except Exception as exc:  # noqa: BLE001 — surface as health detail
            return {"status": "down", "models": [], "detail": str(exc)}

    async def list_models(self) -> list[str]:
        info = await self.health()
        if info["status"] != "up":
            raise OllamaError(info.get("detail", "Ollama unavailable"), unavailable=True)
        return info["models"]

    async def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama chat failed: {exc}", unavailable=True) from exc

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        import json

                        data = json.loads(line)
                        if data.get("done"):
                            break
                        content = data.get("message", {}).get("content")
                        if content:
                            yield content
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama stream failed: {exc}", unavailable=True) from exc


ollama_client = OllamaClient()

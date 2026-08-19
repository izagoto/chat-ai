"""Thin HTTP client for local Ollama."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings


def model_is_installed(requested: str, installed: list[str]) -> bool:
    """True if Ollama already has the configured model tag."""
    if not requested:
        return False
    names = set(installed)
    if requested in names or f"{requested}:latest" in names:
        return True
    if ":" not in requested:
        return any(item.startswith(f"{requested}:") for item in names)
    return any(item.startswith(f"{requested}-") for item in names)


class OllamaError(Exception):
    def __init__(self, message: str, *, unavailable: bool = False) -> None:
        super().__init__(message)
        self.unavailable = unavailable


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")

    @property
    def model(self) -> str:
        return settings.ollama_model

    @property
    def embed_model(self) -> str:
        return settings.ollama_embed_model

    @property
    def vision_model(self) -> str:
        return settings.ollama_vision_model

    @property
    def timeout(self) -> float:
        return settings.ollama_timeout_seconds

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                tags = await client.get(f"{self.base_url}/api/tags")
                tags.raise_for_status()
                models = [m["name"] for m in tags.json().get("models", [])]
                result: dict[str, Any] = {"status": "up", "models": models}
                if not model_is_installed(self.model, models):
                    result["detail"] = (
                        f"Chat model {self.model} is not installed. Run: ollama pull {self.model}"
                    )
                return result
        except Exception as exc:  # noqa: BLE001 — surface as health detail
            return {"status": "down", "models": [], "detail": str(exc)}

    async def list_models(self) -> list[str]:
        info = await self.health()
        if info["status"] != "up":
            raise OllamaError(info.get("detail", "Ollama unavailable"), unavailable=True)
        return info["models"]

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", [])
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama embed failed: {exc}", unavailable=True) from exc

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

    async def vision_chat(self, prompt: str, image_b64: str, *, temperature: float = 0.1) -> str:
        payload = {
            "model": self.vision_model,
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
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
            raise OllamaError(f"Ollama vision failed: {exc}", unavailable=True) from exc

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

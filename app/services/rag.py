"""Simple local RAG with keyword scoring (embedding-ready structure)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.ollama import ollama_client


@dataclass
class Chunk:
    file: str
    text: str
    index: int


class RagService:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._loaded = False

    @property
    def docs_root(self) -> Path:
        return Path(settings.docs_path).resolve()

    def rebuild_index(self) -> int:
        chunks: list[Chunk] = []
        root = self.docs_root
        if not root.exists():
            self._chunks = []
            self._loaded = True
            return 0

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            relative = str(path.relative_to(root))
            for i, piece in enumerate(self._chunk_text(text)):
                chunks.append(Chunk(file=relative, text=piece, index=i))

        self._chunks = chunks
        self._loaded = True
        return len(chunks)

    def ensure_index(self) -> None:
        if not self._loaded:
            self.rebuild_index()

    def _chunk_text(self, text: str) -> list[str]:
        size = settings.rag_chunk_size
        overlap = settings.rag_chunk_overlap
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            return []
        pieces: list[str] = []
        start = 0
        while start < len(cleaned):
            end = min(len(cleaned), start + size)
            pieces.append(cleaned[start:end])
            if end == len(cleaned):
                break
            start = max(0, end - overlap)
        return pieces

    def retrieve(self, query: str, top_k: int | None = None) -> list[tuple[Chunk, float]]:
        self.ensure_index()
        k = top_k or settings.rag_top_k
        if not self._chunks:
            return []

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scored: list[tuple[Chunk, float]] = []
        for chunk in self._chunks:
            c_tokens = self._tokenize(chunk.text)
            score = self._overlap_score(q_tokens, c_tokens)
            if score > 0:
                scored.append((chunk, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    async def answer(self, question: str, top_k: int | None = None) -> tuple[str, list[dict]]:
        hits = self.retrieve(question, top_k=top_k)
        if not hits:
            return (
                "I could not find relevant context in the local knowledge base (docs/).",
                [],
            )

        context_blocks = []
        sources: list[dict] = []
        for chunk, score in hits:
            context_blocks.append(f"[{chunk.file}#{chunk.index}]\n{chunk.text}")
            sources.append(
                {
                    "file": chunk.file,
                    "excerpt": chunk.text[:240] + ("…" if len(chunk.text) > 240 else ""),
                    "score": round(score, 4),
                }
            )

        system = (
            "You are Alder AI. "
            "Answer ONLY using the provided context. "
            "If context is insufficient, say so. Reply in the user's language."
        )
        user = f"Context:\n\n{chr(10).join(context_blocks)}\n\nQuestion: {question}"
        content = await ollama_client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
        )
        return content, sources

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-Z0-9_]{2,}", text.lower()) if len(t) > 1}

    @staticmethod
    def _overlap_score(query: set[str], doc: set[str]) -> float:
        if not query or not doc:
            return 0.0
        inter = len(query & doc)
        if inter == 0:
            return 0.0
        # Jaccard-ish with mild length normalization
        return inter / math.sqrt(len(query) * len(doc))


rag_service = RagService()

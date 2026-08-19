from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import settings
from app.services.ollama import ollama_client


@dataclass
class DocumentRecord:
    document_id: str
    filename: str
    artifact_type: str
    sha256: str
    ingested_at: str
    chunk_count: int
    status: str = "ready"
    error: str | None = None
    source_url: str | None = None


@dataclass
class DocumentChunk:
    chunk_id: str
    collection_id: str
    document_id: str
    source_file: str
    artifact_type: str
    text: str
    chunk_index: int
    location: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


class DocumentStore:
    def __init__(self) -> None:
        self._lock = Lock()

    @property
    def root(self) -> Path:
        return Path(settings.documents_path).resolve()

    def collection_dir(self, collection_id: str) -> Path:
        return self.root / collection_id

    def index_path(self, collection_id: str) -> Path:
        return self.collection_dir(collection_id) / "index.json"

    def _load(self, collection_id: str) -> dict[str, Any]:
        path = self.index_path(collection_id)
        if not path.exists():
            return {"collection_id": collection_id, "chunks": [], "documents": []}
        data = json.loads(path.read_text(encoding="utf-8"))
        # Migrate legacy evidence index shape
        if "documents" not in data and "evidence" in data:
            docs = []
            for item in data.get("evidence", []):
                docs.append(
                    {
                        "document_id": item.get("evidence_id") or item.get("document_id"),
                        "filename": item["filename"],
                        "artifact_type": item["artifact_type"],
                        "sha256": item["sha256"],
                        "ingested_at": item["ingested_at"],
                        "chunk_count": item["chunk_count"],
                    }
                )
            data["documents"] = docs
        chunks = []
        for item in data.get("chunks", []):
            if "document_id" not in item and "evidence_id" in item:
                item = {
                    **item,
                    "document_id": item["evidence_id"],
                    "collection_id": item.get("case_id") or collection_id,
                }
            chunks.append(item)
        data["chunks"] = chunks
        data["collection_id"] = collection_id
        return data

    def _save(self, collection_id: str, data: dict[str, Any]) -> None:
        coll_dir = self.collection_dir(collection_id)
        coll_dir.mkdir(parents=True, exist_ok=True)
        (coll_dir / "files").mkdir(exist_ok=True)
        self.index_path(collection_id).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_documents(self, collection_id: str) -> list[DocumentRecord]:
        data = self._load(collection_id)
        return [self._to_record(item) for item in data.get("documents", [])]

    def list_chunks(self, collection_id: str) -> list[DocumentChunk]:
        data = self._load(collection_id)
        return [DocumentChunk(**item) for item in data.get("chunks", [])]

    def get_document(self, collection_id: str, document_id: str) -> DocumentRecord | None:
        with self._lock:
            data = self._load(collection_id)
            for item in data.get("documents", []):
                if item.get("document_id") == document_id:
                    return self._to_record(item)
        return None

    def file_path(self, collection_id: str, document_id: str, filename: str) -> Path:
        return self.collection_dir(collection_id) / "files" / f"{document_id}_{filename}"

    def stage_upload(
        self,
        collection_id: str,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        artifact_type: str,
        source_url: str | None = None,
    ) -> DocumentRecord:
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        ingested_at = datetime.now(UTC).isoformat()
        coll_dir = self.collection_dir(collection_id)
        coll_dir.mkdir(parents=True, exist_ok=True)
        (coll_dir / "files").mkdir(exist_ok=True)
        self.file_path(collection_id, document_id, filename).write_bytes(file_bytes)

        record = DocumentRecord(
            document_id=document_id,
            filename=filename,
            artifact_type=artifact_type,
            sha256=sha256,
            ingested_at=ingested_at,
            chunk_count=0,
            status="processing",
            error=None,
            source_url=source_url,
        )
        with self._lock:
            data = self._load(collection_id)
            documents = [d for d in data.get("documents", []) if d.get("document_id") != document_id]
            documents.append(asdict(record))
            data["documents"] = documents
            data["collection_id"] = collection_id
            self._save(collection_id, data)
        return record

    def mark_failed(self, collection_id: str, document_id: str, error: str) -> DocumentRecord | None:
        with self._lock:
            data = self._load(collection_id)
            updated = None
            documents = []
            for item in data.get("documents", []):
                if item.get("document_id") == document_id:
                    item["status"] = "failed"
                    item["error"] = error[:500]
                    updated = self._to_record(item)
                documents.append(item)
            if not updated:
                return None
            data["documents"] = documents
            self._save(collection_id, data)
            return updated

    def replace_file_bytes(
        self,
        collection_id: str,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        source_url: str | None = None,
    ) -> None:
        self.file_path(collection_id, document_id, filename).write_bytes(file_bytes)
        digest = hashlib.sha256(file_bytes).hexdigest()
        with self._lock:
            data = self._load(collection_id)
            for item in data.get("documents", []):
                if item.get("document_id") == document_id:
                    item["sha256"] = digest
                    if source_url:
                        item["source_url"] = source_url
                    break
            self._save(collection_id, data)

    async def complete_index(
        self,
        collection_id: str,
        document_id: str,
        artifact_type: str,
        segments: list[tuple[str, dict[str, Any]]],
    ) -> DocumentRecord | None:
        existing = self.get_document(collection_id, document_id)
        if not existing:
            return None

        new_chunks: list[DocumentChunk] = []
        for index, (text, location) in enumerate(segments):
            if not text.strip():
                continue
            for piece in self._chunk_text(text):
                chunk = DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    collection_id=collection_id,
                    document_id=document_id,
                    source_file=existing.filename,
                    artifact_type=artifact_type,
                    text=piece,
                    chunk_index=index,
                    location=location,
                )
                if settings.rag_use_embeddings:
                    try:
                        chunk.embedding = await ollama_client.embed(piece)
                    except Exception:  # noqa: BLE001 — fallback to keyword retrieval
                        chunk.embedding = None
                new_chunks.append(chunk)

        with self._lock:
            data = self._load(collection_id)
            documents = data.get("documents", [])
            current = next((d for d in documents if d.get("document_id") == document_id), None)
            if not current:
                return None
            current["artifact_type"] = artifact_type
            current["chunk_count"] = len(new_chunks)
            current["status"] = "ready"
            current["error"] = None
            data["chunks"] = [
                c for c in data.get("chunks", []) if c.get("document_id") != document_id
            ] + [asdict(chunk) for chunk in new_chunks]
            data["documents"] = documents
            data["collection_id"] = collection_id
            self._save(collection_id, data)
            return self._to_record(current)

    async def add_document(
        self,
        collection_id: str,
        document_id: str,
        filename: str,
        artifact_type: str,
        file_bytes: bytes,
        segments: list[tuple[str, dict[str, Any]]],
    ) -> DocumentRecord:
        self.stage_upload(collection_id, document_id, filename, file_bytes, artifact_type)
        record = await self.complete_index(collection_id, document_id, artifact_type, segments)
        assert record is not None
        return record

    @staticmethod
    def _to_record(item: dict[str, Any]) -> DocumentRecord:
        return DocumentRecord(
            document_id=item["document_id"],
            filename=item["filename"],
            artifact_type=item.get("artifact_type") or "file",
            sha256=item.get("sha256") or "",
            ingested_at=item.get("ingested_at") or "",
            chunk_count=int(item.get("chunk_count") or 0),
            status=item.get("status") or "ready",
            error=item.get("error"),
            source_url=item.get("source_url"),
        )

    def delete_document(self, collection_id: str, document_id: str) -> bool:
        data = self._load(collection_id)
        docs = data.get("documents", [])
        found = any(d.get("document_id") == document_id for d in docs)
        if not found:
            return False
        data["documents"] = [d for d in docs if d.get("document_id") != document_id]
        data["chunks"] = [c for c in data.get("chunks", []) if c.get("document_id") != document_id]
        files_dir = self.collection_dir(collection_id) / "files"
        if files_dir.exists():
            for path in files_dir.glob(f"{document_id}_*"):
                path.unlink(missing_ok=True)
        with self._lock:
            self._save(collection_id, data)
        return True

    async def retrieve(
        self, collection_id: str, query: str, top_k: int | None = None
    ) -> list[tuple[DocumentChunk, float]]:
        k = top_k or settings.rag_top_k
        chunks = self.list_chunks(collection_id)
        if not chunks:
            return []

        if settings.rag_use_embeddings:
            try:
                query_vec = await ollama_client.embed(query)
                scored = [
                    (chunk, self._cosine(query_vec, chunk.embedding))
                    for chunk in chunks
                    if chunk.embedding
                ]
                scored = [(c, s) for c, s in scored if s >= settings.rag_embed_min_score]
                if scored:
                    scored.sort(key=lambda item: item[1], reverse=True)
                    return scored[:k]
            except Exception:  # noqa: BLE001
                pass

        return self._keyword_retrieve(chunks, query, k)

    def _keyword_retrieve(
        self, chunks: list[DocumentChunk], query: str, top_k: int
    ) -> list[tuple[DocumentChunk, float]]:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scored: list[tuple[DocumentChunk, float]] = []
        for chunk in chunks:
            score = self._overlap_score(q_tokens, self._tokenize(chunk.text))
            if score >= settings.rag_keyword_min_score:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine(a: list[float], b: list[float] | None) -> float:
        if not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

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

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-Z0-9_+@.-]{2,}", text.lower()) if len(t) > 1}

    @staticmethod
    def _overlap_score(query: set[str], doc: set[str]) -> float:
        if not query or not doc:
            return 0.0
        inter = len(query & doc)
        if inter == 0:
            return 0.0
        return inter / math.sqrt(len(query) * len(doc))

    def chunk_to_source(self, chunk: DocumentChunk, score: float) -> dict[str, Any]:
        loc = chunk.location or {}
        loc_bits = []
        if loc.get("page"):
            loc_bits.append(f"page {loc['page']}")
        if loc.get("sheet"):
            loc_bits.append(f"sheet {loc['sheet']}")
        if loc.get("row_start"):
            loc_bits.append(f"rows {loc['row_start']}-{loc.get('row_end', loc['row_start'])}")
        if loc.get("timestamp"):
            loc_bits.append(str(loc["timestamp"]))
        return {
            "file": chunk.source_file,
            "document_id": chunk.document_id,
            "artifact_type": chunk.artifact_type,
            "location": ", ".join(loc_bits) if loc_bits else None,
            "excerpt": chunk.text[:280] + ("…" if len(chunk.text) > 280 else ""),
            "score": round(score, 4),
        }


document_store = DocumentStore()

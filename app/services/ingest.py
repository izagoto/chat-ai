from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.core.config import settings
from app.services.document_store import DocumentRecord, document_store
from app.services.extractors import extract_file
from app.services.image_analysis import analyze_image_bytes

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

_SUFFIX_TYPE = {
    ".txt": "text",
    ".md": "text",
    ".log": "text",
    ".json": "json",
    ".csv": "csv",
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "excel",
    ".xls": "excel",
}


def guessed_artifact_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return _SUFFIX_TYPE.get(suffix, "file")


async def extract_segments(filename: str, file_bytes: bytes) -> tuple[str, list[tuple[str, dict]]]:
    suffix = Path(filename).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        analysis = await analyze_image_bytes(file_bytes, filename)
        parts: list[str] = []
        if analysis.get("ocr_text"):
            parts.append(f"OCR text:\n{analysis['ocr_text']}")
        if analysis.get("vision_analysis"):
            parts.append(f"Image analysis:\n{analysis['vision_analysis']}")
        meta = analysis.get("metadata") or {}
        if meta:
            parts.append(
                f"Image metadata: format={meta.get('format')}, "
                f"size={meta.get('size')}"
            )
        text = "\n\n".join(parts) if parts else f"(Image file: {filename}; no text extracted)"
        return "image", [(text, {"type": "image", "filename": filename})]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        artifact_type, segments = await asyncio.to_thread(extract_file, tmp_path)
        payload = [(seg.text, seg.location) for seg in segments]
        if not payload:
            payload = [("(empty or unreadable content)", {"type": "empty"})]
        return artifact_type, payload
    finally:
        tmp_path.unlink(missing_ok=True)


async def process_staged_document(collection_id: str, document_id: str) -> DocumentRecord | None:
    record = document_store.get_document(collection_id, document_id)
    if not record or record.status == "ready":
        return record
    try:
        if record.source_url or record.artifact_type == "url":
            from app.services.url_fetch import UrlFetchError, fetch_url

            if not record.source_url:
                return document_store.mark_failed(collection_id, document_id, "URL is missing")
            fetched = await fetch_url(record.source_url)
            document_store.replace_file_bytes(
                collection_id,
                document_id,
                record.filename,
                fetched.body,
                source_url=fetched.final_url,
            )
            updated = await document_store.complete_index(
                collection_id, document_id, fetched.artifact_type, fetched.segments
            )
            if updated is None:
                return None
            return updated

        path = document_store.file_path(collection_id, document_id, record.filename)
        if not path.exists():
            return document_store.mark_failed(collection_id, document_id, "Uploaded file is missing")
        file_bytes = await asyncio.to_thread(path.read_bytes)
        artifact_type, segments = await extract_segments(record.filename, file_bytes)
        updated = await document_store.complete_index(
            collection_id, document_id, artifact_type, segments
        )
        if updated is None:
            return None
        return updated
    except Exception as exc:  # noqa: BLE001 — persist failure on the document
        return document_store.mark_failed(collection_id, document_id, str(exc))


async def ingest_bytes(
    collection_id: str,
    document_id: str,
    filename: str,
    file_bytes: bytes,
) -> DocumentRecord:
    artifact_guess = guessed_artifact_type(filename)
    document_store.stage_upload(collection_id, document_id, filename, file_bytes, artifact_guess)
    record = await process_staged_document(collection_id, document_id)
    assert record is not None
    return record


def default_collection() -> str:
    return settings.default_collection

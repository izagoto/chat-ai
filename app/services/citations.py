from __future__ import annotations

from typing import Any

from app.models.schemas import SourceItem
from app.services.document_store import DocumentChunk


def format_location(location: dict[str, Any] | None) -> str | None:
    if not location:
        return None
    page = location.get("page")
    if page is not None:
        return f"p. {page}"
    kind = location.get("type") or ""
    sheet = location.get("sheet")
    start = location.get("row_start")
    end = location.get("row_end")
    if kind == "excel_sheet" or sheet:
        label = str(sheet or "sheet")
        if start is not None and end is not None:
            return f"{label} · rows {start}–{end}"
        return label
    if kind == "csv_rows" and start is not None and end is not None:
        return f"rows {start}–{end}"
    if kind == "docx_section":
        heading = location.get("heading")
        p_start = location.get("paragraph_start")
        p_end = location.get("paragraph_end")
        if heading:
            return str(heading)
        if p_start is not None and p_end is not None and p_start != p_end:
            return f"¶ {p_start}–{p_end}"
        if p_start is not None:
            return f"¶ {p_start}"
    if kind == "url":
        url = location.get("url") or ""
        host = url.split("://", 1)[-1].split("/", 1)[0]
        return host or "web"
    if kind == "docx_table":
        heading = location.get("heading")
        index = location.get("index")
        label = f"table {index}" if index is not None else "table"
        return f"{heading} · {label}" if heading else label
    key = location.get("key") or location.get("field")
    if key:
        return str(key)
    if kind and kind not in {"full_file", "object", "scalar", "note"}:
        return str(kind).replace("_", " ")
    return None


def sources_from_hits(hits: list[tuple[DocumentChunk, float]]) -> list[SourceItem]:
    seen: set[tuple[str, str]] = set()
    sources: list[SourceItem] = []
    for chunk, score in hits:
        loc = format_location(chunk.location)
        key = (chunk.source_file, loc or "")
        if key in seen:
            continue
        seen.add(key)
        excerpt = " ".join((chunk.text or "").split())[:240]
        sources.append(
            SourceItem(
                file=chunk.source_file,
                excerpt=excerpt,
                score=round(float(score), 4),
                document_id=chunk.document_id,
                evidence_id=chunk.document_id,
                artifact_type=chunk.artifact_type,
                location=loc,
            )
        )
    return sources

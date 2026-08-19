from __future__ import annotations

from pathlib import Path

from app.services.extractors.base import ExtractedSegment

_PARA_BATCH = 25


def extract_docx(path: Path) -> list[ExtractedSegment]:
    try:
        from docx import Document
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise RuntimeError("python-docx required for Word ingest. pip install python-docx") from exc

    document = Document(path)
    segments: list[ExtractedSegment] = []
    heading: str | None = None
    buffer: list[str] = []
    para_index = 0
    para_start = 1
    table_index = 0

    def flush() -> None:
        nonlocal buffer, para_start
        text = "\n".join(part for part in buffer if part).strip()
        if not text:
            buffer = []
            return
        location: dict = {
            "type": "docx_section",
            "paragraph_start": para_start,
            "paragraph_end": max(para_start, para_index),
        }
        if heading:
            location["heading"] = heading
        segments.append(ExtractedSegment(text=text, location=location))
        buffer = []

    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            para_index += 1
            text = (paragraph.text or "").strip()
            style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
            if style_name.startswith("Heading"):
                flush()
                heading = text or heading
                para_start = para_index
                if text:
                    buffer.append(text)
                continue
            if not text:
                continue
            if not buffer:
                para_start = para_index
            buffer.append(text)
            if len(buffer) >= _PARA_BATCH:
                flush()
                para_start = para_index + 1
        elif isinstance(child, CT_Tbl):
            flush()
            table_index += 1
            table_text = _table_text(Table(child, document))
            if table_text:
                prefix = f"{heading}\n" if heading else ""
                location = {"type": "docx_table", "index": table_index}
                if heading:
                    location["heading"] = heading
                segments.append(ExtractedSegment(text=f"{prefix}{table_text}".strip(), location=location))
            para_start = para_index + 1

    flush()
    return segments


def _table_text(table) -> str:
    lines: list[str] = []
    for row in table.rows:
        cells = [" ".join(cell.text.split()) for cell in row.cells]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)

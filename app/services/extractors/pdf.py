from __future__ import annotations

from pathlib import Path

from app.services.extractors.base import ExtractedSegment


def extract_pdf(path: Path) -> list[ExtractedSegment]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF required for PDF ingest. pip install pymupdf") from exc

    segments: list[ExtractedSegment] = []
    with fitz.open(path) as doc:
        for page_index in range(doc.page_count):
            page = doc[page_index]
            raw = page.get_text("text")
            text = str(raw).strip()
            if text:
                segments.append(
                    ExtractedSegment(
                        text=text,
                        location={"type": "pdf_page", "page": page_index + 1},
                    )
                )
    return segments

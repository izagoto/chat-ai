from __future__ import annotations

from pathlib import Path

from app.services.extractors.base import ExtractedSegment
from app.services.extractors.docx import extract_docx
from app.services.extractors.excel import extract_excel
from app.services.extractors.json_csv import extract_csv, extract_json, extract_text
from app.services.extractors.pdf import extract_pdf


def extract_file(path: Path) -> tuple[str, list[ExtractedSegment]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".log"}:
        return "text", extract_text(path)
    if suffix == ".json":
        return "json", extract_json(path)
    if suffix == ".csv":
        return "csv", extract_csv(path)
    if suffix == ".pdf":
        return "pdf", extract_pdf(path)
    if suffix in {".xlsx", ".xls"}:
        return "excel", extract_excel(path)
    if suffix == ".docx":
        return "docx", extract_docx(path)
    if suffix == ".doc":
        raise ValueError("Legacy .doc is not supported. Save the file as .docx and upload again.")
    raise ValueError(f"Unsupported document format: {suffix}")

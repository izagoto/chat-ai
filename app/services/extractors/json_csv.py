from __future__ import annotations

import csv
import json
from pathlib import Path

from app.services.extractors.base import ExtractedSegment


def extract_text(path: Path) -> list[ExtractedSegment]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    if not content.strip():
        return []
    return [ExtractedSegment(text=content, location={"type": "full_file"})]


def extract_json(path: Path) -> list[ExtractedSegment]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    data = json.loads(raw)
    segments: list[ExtractedSegment] = []

    if isinstance(data, list):
        batch_size = 40
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            segments.append(
                ExtractedSegment(
                    text=json.dumps(batch, ensure_ascii=False, indent=2),
                    location={"type": "array_slice", "start": i, "end": min(i + batch_size, len(data))},
                )
            )
    elif isinstance(data, dict):
        if _looks_like_chat_export(data):
            segments.extend(_extract_chat_dict(data))
        else:
            for key, value in data.items():
                segments.append(
                    ExtractedSegment(
                        text=json.dumps({key: value}, ensure_ascii=False, indent=2),
                        location={"type": "object_key", "key": key},
                    )
                )
    else:
        segments.append(ExtractedSegment(text=json.dumps(data, ensure_ascii=False), location={"type": "scalar"}))
    return segments


def _looks_like_chat_export(data: dict) -> bool:
    keys = {k.lower() for k in data.keys()}
    return bool(keys & {"messages", "chats", "conversations", "threads"})


def _extract_chat_dict(data: dict) -> list[ExtractedSegment]:
    segments: list[ExtractedSegment] = []
    for key in ("messages", "chats", "conversations", "threads"):
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, list):
            batch_size = 30
            for i in range(0, len(value), batch_size):
                batch = value[i : i + batch_size]
                segments.append(
                    ExtractedSegment(
                        text=json.dumps(batch, ensure_ascii=False, indent=2),
                        location={"type": "chat_batch", "field": key, "start": i, "end": min(i + batch_size, len(value))},
                    )
                )
        else:
            segments.append(
                ExtractedSegment(
                    text=json.dumps({key: value}, ensure_ascii=False, indent=2),
                    location={"type": "chat_field", "field": key},
                )
            )
    if segments:
        return segments
    return [ExtractedSegment(text=json.dumps(data, ensure_ascii=False, indent=2), location={"type": "object"})]


def extract_csv(path: Path) -> list[ExtractedSegment]:
    segments: list[ExtractedSegment] = []
    with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return segments

    header = rows[0]
    batch_size = 50
    data_rows = rows[1:] if len(rows) > 1 else rows
    for i in range(0, len(data_rows), batch_size):
        batch = data_rows[i : i + batch_size]
        lines = [",".join(header)] if header else []
        lines.extend(",".join(row) for row in batch)
        segments.append(
            ExtractedSegment(
                text="\n".join(lines),
                location={
                    "type": "csv_rows",
                    "row_start": i + 1,
                    "row_end": min(i + batch_size, len(data_rows)),
                },
            )
        )
    return segments

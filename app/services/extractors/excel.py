from __future__ import annotations

from pathlib import Path

from app.services.extractors.base import ExtractedSegment


def extract_excel(path: Path) -> list[ExtractedSegment]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas/openpyxl required for Excel ingest") from exc

    segments: list[ExtractedSegment] = []
    workbook = pd.read_excel(path, sheet_name=None, dtype=str)
    batch_size = 50

    for sheet_name, frame in workbook.items():
        frame = frame.fillna("")
        if frame.empty:
            continue
        records = frame.to_dict(orient="records")
        columns = list(frame.columns)
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            lines = [f"Sheet: {sheet_name}", f"Columns: {', '.join(map(str, columns))}"]
            for idx, row in enumerate(batch, start=i + 1):
                row_text = " | ".join(f"{col}={row.get(col, '')}" for col in columns)
                lines.append(f"Row {idx}: {row_text}")
            segments.append(
                ExtractedSegment(
                    text="\n".join(lines),
                    location={
                        "type": "excel_sheet",
                        "sheet": str(sheet_name),
                        "row_start": i + 1,
                        "row_end": min(i + batch_size, len(records)),
                    },
                )
            )
    return segments

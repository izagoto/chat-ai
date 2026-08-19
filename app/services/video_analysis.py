"""Video analysis via metadata, frame sampling, OCR/vision."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.image_analysis import analyze_image_bytes
from app.services.ollama import ollama_client
from app.services.prompts import VIDEO_TIMELINE_PROMPT


async def analyze_video_bytes(file_bytes: bytes, filename: str, question: str | None = None) -> dict[str, Any]:
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    result: dict[str, Any] = {
        "filename": filename,
        "sha256": sha256,
        "metadata": {},
        "frames": [],
        "timeline_summary": None,
        "tools_available": {
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None,
        },
    }

    if not result["tools_available"]["ffmpeg"] or not result["tools_available"]["ffprobe"]:
        result["error"] = "ffmpeg/ffprobe not found. Install ffmpeg for video analysis."
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / filename
        video_path.write_bytes(file_bytes)
        result["metadata"] = _ffprobe_metadata(video_path)
        frames = _extract_frames(video_path, Path(tmpdir))
        for frame in frames[: settings.video_max_frames]:
            frame_analysis = await analyze_image_bytes(
                frame["bytes"],
                frame["filename"],
                question="Describe visible text, objects, and investigative relevance.",
            )
            result["frames"].append(
                {
                    "timestamp_sec": frame["timestamp_sec"],
                    "filename": frame["filename"],
                    "metadata": frame_analysis.get("metadata"),
                    "ocr_text": frame_analysis.get("ocr_text"),
                    "vision_analysis": frame_analysis.get("vision_analysis"),
                }
            )

    if result["frames"]:
        result["timeline_summary"] = await _summarize_timeline(result, question)

    return result


def _ffprobe_metadata(video_path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or "ffprobe failed"}
    data = json.loads(proc.stdout or "{}")
    fmt = data.get("format", {})
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "duration_sec": float(fmt.get("duration", 0) or 0),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "format_name": fmt.get("format_name"),
        "video_codec": video_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
    }


def _extract_frames(video_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    pattern = out_dir / "frame_%04d.jpg"
    interval = settings.video_frame_interval_sec
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval}",
        "-frames:v",
        str(settings.video_max_frames),
        str(pattern),
    ]
    subprocess.run(cmd, capture_output=True, check=False)
    frames: list[dict[str, Any]] = []
    for idx, frame_path in enumerate(sorted(out_dir.glob("frame_*.jpg"))):
        frames.append(
            {
                "filename": frame_path.name,
                "timestamp_sec": round(idx * interval, 2),
                "bytes": frame_path.read_bytes(),
            }
        )
    return frames


async def _summarize_timeline(result: dict[str, Any], question: str | None) -> str:
    lines = [
        f"Video: {result['filename']}",
        f"Duration: {result.get('metadata', {}).get('duration_sec')} sec",
        "Sampled frames:",
    ]
    for frame in result.get("frames", []):
        lines.append(f"- t={frame['timestamp_sec']}s")
        if frame.get("ocr_text"):
            lines.append(f"  OCR: {frame['ocr_text'][:300]}")
        if frame.get("vision_analysis"):
            lines.append(f"  Vision: {frame['vision_analysis'][:400]}")
    user_q = question or "Summarize this video evidence for an investigator."
    prompt = f"{VIDEO_TIMELINE_PROMPT}\n\n{chr(10).join(lines)}\n\nQuestion: {user_q}"
    try:
        return await ollama_client.chat(
            [{"role": "system", "content": VIDEO_TIMELINE_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.1,
        )
    except Exception as exc:  # noqa: BLE001
        return f"Timeline summary unavailable ({exc}). See sampled frames above."

"""Image analysis: metadata, OCR, vision LLM."""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
from typing import Any

from app.services.ollama import ollama_client
from app.services.prompts import IMAGE_VISION_PROMPT


async def analyze_image_bytes(file_bytes: bytes, filename: str, question: str | None = None) -> dict[str, Any]:
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    result: dict[str, Any] = {
        "filename": filename,
        "sha256": sha256,
        "metadata": {},
        "ocr_text": None,
        "ocr_available": False,
        "vision_analysis": None,
        "vision_available": False,
    }

    try:
        from PIL import Image
    except ImportError:
        result["error"] = "Pillow not installed"
        return result

    image = Image.open(io.BytesIO(file_bytes))
    result["metadata"] = {
        "format": image.format,
        "mode": image.mode,
        "size": {"width": image.width, "height": image.height},
        "exif": _extract_exif(image),
    }

    ocr_text = _run_ocr(image)
    if ocr_text:
        result["ocr_text"] = ocr_text
        result["ocr_available"] = True

    prompt = question or IMAGE_VISION_PROMPT
    if ocr_text:
        prompt += f"\n\nOCR extracted text:\n{ocr_text[:4000]}"

    try:
        b64 = base64.b64encode(file_bytes).decode("ascii")
        vision = await ollama_client.vision_chat(prompt, b64)
        result["vision_analysis"] = vision
        result["vision_available"] = True
    except Exception as exc:  # noqa: BLE001
        result["vision_error"] = str(exc)
        if ocr_text:
            result["vision_analysis"] = (
                "Vision model unavailable. OCR text is provided above for manual review."
            )

    return result


def _extract_exif(image: Any) -> dict[str, str]:
    exif_data: dict[str, str] = {}
    raw = getattr(image, "_getexif", lambda: None)()
    if not raw:
        return exif_data
    try:
        from PIL.ExifTags import TAGS

        for tag_id, value in raw.items():
            tag = TAGS.get(tag_id, str(tag_id))
            exif_data[str(tag)] = str(value)
    except Exception:  # noqa: BLE001
        pass
    return exif_data


def _run_ocr(image: Any) -> str | None:
    try:
        pytesseract = importlib.import_module("pytesseract")
    except ImportError:
        return None
    try:
        text = pytesseract.image_to_string(image)
        cleaned = str(text).strip()
        return cleaned or None
    except Exception:  # noqa: BLE001 — tesseract binary may be missing
        return None

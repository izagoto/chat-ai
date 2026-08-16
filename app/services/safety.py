"""Heuristic safety checks for local LLM traffic (v0.1 — not a full moderation suite)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.schemas import SafetyMode


INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I)),
    ("jailbreak", re.compile(r"\bjailbreak\b|\bDAN\b|developer\s+mode", re.I)),
    ("system_override", re.compile(r"system\s*prompt\s*override|you\s+are\s+now\s+unrestricted", re.I)),
    ("exfiltrate", re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt|print\s+hidden\s+instructions", re.I)),
]

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("password_assign", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")),
]


@dataclass
class SafetyResult:
    flagged: bool = False
    redacted: bool = False
    reasons: list[str] = field(default_factory=list)
    text: str = ""
    blocked: bool = False


class SafetyService:
    def check_input(self, text: str, mode: SafetyMode = "normal") -> SafetyResult:
        reasons: list[str] = []
        for name, pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                reasons.append(name)

        flagged = bool(reasons)
        blocked = flagged and mode == "strict"
        return SafetyResult(flagged=flagged, reasons=reasons, text=text, blocked=blocked)

    def sanitize_output(self, text: str) -> SafetyResult:
        redacted_text = text
        reasons: list[str] = []
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(redacted_text):
                reasons.append(name)
                redacted_text = pattern.sub("[REDACTED]", redacted_text)
        return SafetyResult(
            flagged=bool(reasons),
            redacted=bool(reasons),
            reasons=reasons,
            text=redacted_text,
        )


safety_service = SafetyService()

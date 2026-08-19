from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedSegment:
    text: str
    location: dict[str, Any] = field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class Evidence:
    source: str
    supports: bool
    note: str = ""


@dataclass(slots=True)
class Claim:
    text: str
    confidence: float = 0.0
    status: str = "unverified"
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence: list[Evidence] = field(default_factory=list)

    def recompute(self) -> None:
        if not self.evidence:
            self.status, self.confidence = "unverified", 0.0
            return
        positive = sum(e.supports for e in self.evidence)
        negative = len(self.evidence) - positive
        self.confidence = positive / len(self.evidence)
        self.status = "contested" if positive and negative else ("verified" if positive >= 2 else "partially_verified")

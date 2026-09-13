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
        if positive == 0:
            self.status = "refuted"
        elif negative:
            self.status = "contested"
        elif positive >= 2:
            self.status = "verified"
        else:
            self.status = "partially_verified"

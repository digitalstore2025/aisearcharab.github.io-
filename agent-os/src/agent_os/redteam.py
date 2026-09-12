from __future__ import annotations

from dataclasses import dataclass


SEVERITIES = ("critical", "high", "medium", "low")
DOMAINS = (
    "security", "architecture", "logic", "performance", "scalability",
    "maintainability", "cost", "data_leakage", "prompt_injection", "tool_abuse", "hallucination"
)


@dataclass(slots=True)
class Finding:
    domain: str
    severity: str
    title: str
    evidence: str
    remediation: str

    def validate(self) -> None:
        if self.domain not in DOMAINS:
            raise ValueError(f"Unknown domain: {self.domain}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unknown severity: {self.severity}")
        if not self.evidence.strip():
            raise ValueError("Red-team finding requires evidence")

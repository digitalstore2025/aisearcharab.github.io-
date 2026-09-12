from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class ReviewVerdict:
    approved: bool
    score: float
    issues: list[str]


class IndependentVerifier:
    """Runs a verifier on output/evidence only, not the generator's hidden rationale."""

    def __init__(self, judge: Callable[[dict[str, Any]], ReviewVerdict]):
        self.judge = judge

    def verify(self, *, task: str, output: str, evidence: list[dict[str, Any]]) -> ReviewVerdict:
        payload = {"task": task, "output": output, "evidence": evidence}
        return self.judge(payload)

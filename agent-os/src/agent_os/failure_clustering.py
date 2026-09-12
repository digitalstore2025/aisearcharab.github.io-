from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


CATEGORIES = (
    "routing", "retrieval", "policy", "tool_use", "reasoning",
    "stale_context", "completion", "external_dependency", "unknown"
)

_KEYWORDS = {
    "routing": ("wrong skill", "router", "misroute"),
    "retrieval": ("missing source", "retrieval", "rag", "rerank"),
    "policy": ("denied", "approval", "permission", "policy"),
    "tool_use": ("tool failed", "bad argument", "invalid schema", "tool call"),
    "reasoning": ("hallucination", "incorrect conclusion", "logic"),
    "stale_context": ("stale", "outdated", "expired"),
    "completion": ("stopped early", "definition of done", "incomplete"),
    "external_dependency": ("timeout", "rate limit", "upstream", "service unavailable"),
}


@dataclass(slots=True)
class Failure:
    case_id: str
    message: str
    category: str = "unknown"


def classify(message: str) -> str:
    text = message.casefold()
    scores = Counter()
    for category, keywords in _KEYWORDS.items():
        scores[category] = sum(k in text for k in keywords)
    if not scores or max(scores.values()) == 0:
        return "unknown"
    return scores.most_common(1)[0][0]


def cluster(failures: list[Failure]) -> dict[str, list[Failure]]:
    out: dict[str, list[Failure]] = {c: [] for c in CATEGORIES}
    for f in failures:
        f.category = classify(f.message)
        out[f.category].append(f)
    return {k: v for k, v in out.items() if v}

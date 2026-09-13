from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class RetrievedChunk:
    id: str
    text: str
    source: str
    lexical_score: float = 0.0
    vector_score: float = 0.0
    rerank_score: float = 0.0
    freshness: float = 1.0

    @property
    def hybrid_score(self) -> float:
        return 0.35 * self.lexical_score + 0.35 * self.vector_score + 0.25 * self.rerank_score + 0.05 * self.freshness


def dedupe_and_rank(chunks: Iterable[RetrievedChunk], k: int = 8) -> list[RetrievedChunk]:
    best: dict[tuple[str, str], RetrievedChunk] = {}
    for c in chunks:
        key = (c.source, " ".join(c.text.casefold().split()))
        if key not in best or c.hybrid_score > best[key].hybrid_score:
            best[key] = c
    return sorted(best.values(), key=lambda c: c.hybrid_score, reverse=True)[:k]


def citation_precision(claim_citations: list[bool]) -> float:
    return sum(claim_citations) / len(claim_citations) if claim_citations else 0.0

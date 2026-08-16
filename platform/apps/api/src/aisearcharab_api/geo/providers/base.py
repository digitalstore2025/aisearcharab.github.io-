from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ProviderCitation:
    url: str
    title: str | None = None
    position: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider: str
    model: str
    query: str
    answer_text: str
    citations: tuple[ProviderCitation, ...]
    raw_payload: str
    raw_reference: str | None = None
    latency_ms: int | None = None


class GeoProvider(Protocol):
    name: str

    def run_query(self, query: str, *, locale: str = "ar") -> ProviderResult:
        """Execute one provider query and return normalized evidence.

        Implementations must keep credentials server-side, preserve enough raw
        upstream payload for hashing/reproducibility, and must not silently
        fabricate citations when the upstream provider returns none.
        """
        ...

    def capabilities(self) -> Sequence[str]:
        ...

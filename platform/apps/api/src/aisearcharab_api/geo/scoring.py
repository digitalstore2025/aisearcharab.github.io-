from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_MIN_SAMPLE_SIZE = 10


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    name: str
    value: float
    weight: float
    sample_size: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError("component value must be between 0 and 100")
        if not 0 < self.weight <= 1:
            raise ValueError("component weight must be greater than 0 and at most 1")
        if self.sample_size < 0:
            raise ValueError("sample_size must be non-negative")


@dataclass(frozen=True, slots=True)
class GeoScore:
    score: float | None
    status: str
    sample_size: int
    components: tuple[ScoreComponent, ...]


def calculate_geo_score(components: Iterable[ScoreComponent], *, min_sample_size: int = _MIN_SAMPLE_SIZE) -> GeoScore:
    parts = tuple(components)
    if not parts:
        return GeoScore(score=None, status="insufficient_data", sample_size=0, components=())

    total_weight = sum(part.weight for part in parts)
    if total_weight <= 0:
        raise ValueError("total component weight must be positive")

    sample_size = min(part.sample_size for part in parts)
    if sample_size < min_sample_size:
        return GeoScore(score=None, status="insufficient_data", sample_size=sample_size, components=parts)

    weighted = sum(part.value * part.weight for part in parts) / total_weight
    return GeoScore(
        score=round(weighted, 2),
        status="scored",
        sample_size=sample_size,
        components=parts,
    )

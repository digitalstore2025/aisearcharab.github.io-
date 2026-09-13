from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import load_json


@dataclass(slots=True)
class ModelChoice:
    tier: str
    model: str
    reason: str


class ModelRouter:
    def __init__(self, catalog: dict):
        self.catalog = catalog

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelRouter":
        return cls(load_json(path))

    def choose(self, *, complexity: str, risk: str, requires_tools: bool = False) -> ModelChoice:
        rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if complexity not in rank:
            raise ValueError(f"Unsupported complexity: {complexity}")
        if risk not in rank:
            raise ValueError(f"Unsupported risk: {risk}")
        score = max(rank[complexity], rank[risk])
        if score >= 3:
            tier = "critical"
        elif score == 2:
            tier = "strong"
        elif score == 1:
            tier = "standard"
        else:
            tier = "economy"
        entry = self.catalog["tiers"][tier]
        if requires_tools and not entry.get("tool_capable", True):
            fallback = self.catalog["tiers"].get("standard")
            if not fallback or not fallback.get("tool_capable", True):
                raise ValueError("No tool-capable model tier is configured")
            entry = fallback
            tier = "standard"
        return ModelChoice(tier, entry["model"], f"complexity={complexity}, risk={risk}, tools={requires_tools}")

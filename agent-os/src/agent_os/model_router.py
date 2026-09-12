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
        c = rank.get(complexity, 1)
        r = rank.get(risk, 1)
        score = max(c, r)
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
            entry = self.catalog["tiers"]["standard"]
            tier = "standard"
        return ModelChoice(tier, entry["model"], f"complexity={complexity}, risk={risk}, tools={requires_tools}")

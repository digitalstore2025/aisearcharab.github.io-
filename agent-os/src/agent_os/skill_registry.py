from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import load_json


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    triggers: tuple[str, ...]
    risk: str
    cost: str
    requires: tuple[str, ...] = ()


class SkillRegistry:
    def __init__(self, skills: Iterable[Skill]):
        self.skills = {s.name: s for s in skills}

    @classmethod
    def from_file(cls, path: str | Path) -> "SkillRegistry":
        data = load_json(path)
        return cls(
            Skill(
                name=s["name"],
                description=s["description"],
                triggers=tuple(s.get("triggers", [])),
                risk=s.get("risk", "low"),
                cost=s.get("cost", "low"),
                requires=tuple(s.get("requires", [])),
            )
            for s in data["skills"]
        )

    def route(self, task: str, max_skills: int = 2) -> list[Skill]:
        t = task.casefold()
        scored: list[tuple[int, Skill]] = []
        for skill in self.skills.values():
            score = sum(1 for trig in skill.triggers if trig.casefold() in t)
            if score:
                scored.append((score, skill))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        return [s for _, s in scored[:max_skills]]

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class AgentDefinition:
    name: str
    kind: str
    phase: str
    priority: int
    description: str
    triggers: tuple[str, ...]
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    instructions: str
    portfolio: bool = False

class AgentRegistry:
    """Validated deterministic registry for bounded multi-agent routing."""

    def __init__(self, agents: list[AgentDefinition], portfolio_triggers: tuple[str, ...] = ()):
        names = [a.name for a in agents]
        if len(names) != len(set(names)):
            raise ValueError("Agent names must be unique")
        if len([a for a in agents if a.kind == "coordinator"]) != 1:
            raise ValueError("Registry must contain exactly one coordinator")
        if len([a for a in agents if a.kind == "reviewer"]) != 1:
            raise ValueError("Registry must contain exactly one independent reviewer")
        self.agents = tuple(agents)
        self.portfolio_triggers = portfolio_triggers
        self._by_name = {a.name: a for a in agents}

    @classmethod
    def from_file(cls, path: str | Path) -> "AgentRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        allowed_kinds = {"coordinator", "specialist", "verifier", "reviewer"}
        allowed_phases = {"plan", "build", "verify", "release"}
        agents = []
        for raw in data["agents"]:
            if raw["kind"] not in allowed_kinds:
                raise ValueError(f"Unsupported agent kind: {raw['kind']}")
            if raw["phase"] not in allowed_phases:
                raise ValueError(f"Unsupported agent phase: {raw['phase']}")
            agents.append(AgentDefinition(
                name=raw["name"], kind=raw["kind"], phase=raw["phase"],
                priority=int(raw.get("priority", 0)), description=raw["description"],
                triggers=tuple(str(x).lower() for x in raw.get("triggers", [])),
                capabilities=tuple(raw.get("capabilities", [])),
                allowed_tools=tuple(raw.get("allowed_tools", [])),
                instructions=str(raw["instructions"]).strip(),
                portfolio=bool(raw.get("portfolio", False)),
            ))
        if not all(agent.instructions for agent in agents):
            raise ValueError("Every agent must define non-empty instructions")
        return cls(
            agents,
            tuple(str(x).lower() for x in data.get("portfolio_triggers", [])),
        )

    def get(self, name: str) -> AgentDefinition:
        if name not in self._by_name:
            raise KeyError(f"Unknown agent: {name}")
        return self._by_name[name]

    @property
    def coordinator(self) -> AgentDefinition:
        return next(a for a in self.agents if a.kind == "coordinator")

    @property
    def reviewer(self) -> AgentDefinition:
        return next(a for a in self.agents if a.kind == "reviewer")

    def is_portfolio_task(self, task: str) -> bool:
        text = task.lower()
        return any(t in text for t in self.portfolio_triggers)

    @staticmethod
    def _trigger_matches(trigger: str, text: str) -> bool:
        if not trigger:
            return False
        if any(ord(ch) > 127 for ch in trigger) or not trigger.replace("-", "").isalnum():
            return trigger in text
        return re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", text) is not None

    @classmethod
    def _score(cls, agent: AgentDefinition, text: str) -> int:
        return sum(1 for trigger in agent.triggers if cls._trigger_matches(trigger, text))

    def route_specialists(self, task: str, *, max_specialists: int = 5) -> list[AgentDefinition]:
        if max_specialists < 1:
            raise ValueError("max_specialists must be >= 1")
        text = task.lower()
        candidates = [a for a in self.agents if a.kind == "specialist"]
        if self.is_portfolio_task(task):
            phase_rank = {"plan": 0, "build": 1, "release": 2, "verify": 3}
            return sorted([a for a in candidates if a.portfolio], key=lambda a: (phase_rank[a.phase], -a.priority, a.name))
        scored = [(self._score(a, text), a) for a in candidates]
        matched = [item for item in scored if item[0] > 0]
        matched.sort(key=lambda item: (-item[0], -item[1].priority, item[1].name))
        return [a for _, a in matched[:max_specialists]]

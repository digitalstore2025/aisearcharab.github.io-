from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    @staticmethod
    def _string_list(value: Any, field: str) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
            raise ValueError(f"{field} must be a list of non-empty strings")
        return tuple(x.strip() for x in value)

    @classmethod
    def from_file(cls, path: str | Path) -> "AgentRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            raise ValueError("Agent registry must contain an agents list")

        allowed_kinds = {"coordinator", "specialist", "verifier", "reviewer"}
        allowed_phases = {"plan", "build", "verify", "release"}
        agents: list[AgentDefinition] = []
        for raw in data["agents"]:
            if not isinstance(raw, dict):
                raise ValueError("Each agent definition must be an object")
            name = raw.get("name")
            kind = raw.get("kind")
            phase = raw.get("phase")
            description = raw.get("description")
            instructions = raw.get("instructions")
            priority = raw.get("priority", 0)
            portfolio = raw.get("portfolio", False)
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Agent name must be a non-empty string")
            if kind not in allowed_kinds:
                raise ValueError(f"Unsupported agent kind: {kind}")
            if phase not in allowed_phases:
                raise ValueError(f"Unsupported agent phase: {phase}")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"Agent {name} must define a non-empty description")
            if not isinstance(instructions, str) or not instructions.strip():
                raise ValueError(f"Agent {name} must define non-empty instructions")
            if type(priority) is not int:
                raise ValueError(f"Agent {name} priority must be an integer")
            if type(portfolio) is not bool:
                raise ValueError(f"Agent {name} portfolio must be a JSON boolean")

            agents.append(AgentDefinition(
                name=name.strip(),
                kind=kind,
                phase=phase,
                priority=priority,
                description=description.strip(),
                triggers=tuple(x.lower() for x in cls._string_list(raw.get("triggers", []), f"Agent {name} triggers")),
                capabilities=cls._string_list(raw.get("capabilities", []), f"Agent {name} capabilities"),
                allowed_tools=cls._string_list(raw.get("allowed_tools", []), f"Agent {name} allowed_tools"),
                instructions=instructions.strip(),
                portfolio=portfolio,
            ))

        portfolio_triggers = cls._string_list(data.get("portfolio_triggers", []), "portfolio_triggers")
        return cls(agents, tuple(x.lower() for x in portfolio_triggers))

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

    def matches(self, name: str, task: str) -> bool:
        return self._score(self.get(name), task.lower()) > 0

    def is_portfolio_task(self, task: str) -> bool:
        text = task.lower()
        return any(self._trigger_matches(trigger, text) for trigger in self.portfolio_triggers)

    def route_specialists(self, task: str, *, max_specialists: int = 5) -> list[AgentDefinition]:
        if max_specialists < 1:
            raise ValueError("max_specialists must be >= 1")
        text = task.lower()
        candidates = [a for a in self.agents if a.kind == "specialist"]
        if self.is_portfolio_task(task):
            phase_rank = {"plan": 0, "build": 1, "release": 2, "verify": 3}
            return sorted(
                [a for a in candidates if a.portfolio],
                key=lambda a: (phase_rank[a.phase], -a.priority, a.name),
            )
        scored = [(self._score(a, text), a) for a in candidates]
        matched = [item for item in scored if item[0] > 0]
        matched.sort(key=lambda item: (-item[0], -item[1].priority, item[1].name))
        return [a for _, a in matched[:max_specialists]]

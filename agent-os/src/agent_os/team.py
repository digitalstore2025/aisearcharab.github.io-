from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .agent_registry import AgentDefinition, AgentRegistry

_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

@dataclass(frozen=True, slots=True)
class AgentAssignment:
    agent: str
    phase: str
    objective: str
    allowed_tools: tuple[str, ...]
    independent: bool = False

@dataclass(frozen=True, slots=True)
class Handoff:
    source: str
    target: str
    artifact: str

@dataclass(frozen=True, slots=True)
class TeamPlan:
    task: str
    portfolio_mode: bool
    assignments: tuple[AgentAssignment, ...]
    handoffs: tuple[Handoff, ...]
    waves: tuple[tuple[str, ...], ...]

    @property
    def agents(self) -> tuple[str, ...]:
        return tuple(item.agent for item in self.assignments)

class TeamPlanner:
    """Build a bounded, phase-aware team and explicit handoff graph."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    @staticmethod
    def _dedupe(agents: Iterable[AgentDefinition]) -> list[AgentDefinition]:
        result, seen = [], set()
        for agent in agents:
            if agent.name not in seen:
                result.append(agent)
                seen.add(agent.name)
        return result

    def plan(self, task: str, *, complexity: str = "medium", risk: str = "medium",
             max_specialists: int = 5, wave_size: int = 4,
             profile_allowed_tools: tuple[str, ...] | None = None) -> TeamPlan:
        if complexity not in _RANK or risk not in _RANK:
            raise ValueError("Unsupported complexity or risk")
        if wave_size < 1:
            raise ValueError("wave_size must be >= 1")

        portfolio = self.registry.is_portfolio_task(task)
        specialists = self.registry.route_specialists(task, max_specialists=max_specialists)
        if _RANK[complexity] >= _RANK["high"]:
            specialists.insert(0, self.registry.get("software-architect"))

        verifiers = [self.registry.get("qa-reliability")]
        if portfolio or _RANK[risk] >= _RANK["high"]:
            verifiers.append(self.registry.get("security-redteam"))

        ordered = self._dedupe([self.registry.coordinator, *specialists, *verifiers, self.registry.reviewer])
        profile_tools = set(profile_allowed_tools) if profile_allowed_tools is not None else None
        assignments = tuple(
            AgentAssignment(
                a.name, a.phase, a.description,
                tuple(tool for tool in a.allowed_tools if profile_tools is None or tool in profile_tools),
                a.kind == "reviewer",
            )
            for a in ordered
        )

        phase_names = {p: [a.name for a in ordered if a.phase == p] for p in ("plan","build","release","verify")}
        waves = []
        if phase_names["plan"]:
            waves.append(tuple(phase_names["plan"]))
        for i in range(0, len(phase_names["build"]), wave_size):
            waves.append(tuple(phase_names["build"][i:i+wave_size]))
        if phase_names["release"]:
            waves.append(tuple(phase_names["release"]))
        if phase_names["verify"]:
            waves.append(tuple(phase_names["verify"]))

        handoffs = []
        coordinator = self.registry.coordinator.name
        for a in ordered:
            if a.name == coordinator:
                continue
            artifact = {"plan":"scope-and-decision-contract","build":"implementation-or-domain-artifact",
                        "verify":"verification-evidence","release":"release-readiness-evidence"}[a.phase]
            handoffs.append(Handoff(coordinator, a.name, artifact))
        reviewer = self.registry.reviewer.name
        for a in ordered:
            if a.name not in {coordinator, reviewer}:
                handoffs.append(Handoff(a.name, reviewer, "evidence-and-open-risks"))

        return TeamPlan(task, portfolio, assignments, tuple(handoffs), tuple(waves))

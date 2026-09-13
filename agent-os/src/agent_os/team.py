from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .agent_registry import AgentDefinition, AgentRegistry
from .tracing import JsonlTracer

_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True, slots=True)
class AgentAssignment:
    agent: str
    phase: str
    objective: str
    instructions: str
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

    def __init__(self, registry: AgentRegistry, tracer: JsonlTracer | None = None):
        self.registry = registry
        self.tracer = tracer

    @staticmethod
    def _dedupe(agents: Iterable[AgentDefinition]) -> list[AgentDefinition]:
        result, seen = [], set()
        for agent in agents:
            if agent.name not in seen:
                result.append(agent)
                seen.add(agent.name)
        return result

    @staticmethod
    def _chunk(names: list[str], size: int) -> list[tuple[str, ...]]:
        return [tuple(names[i:i + size]) for i in range(0, len(names), size)]

    def plan(
        self,
        task: str,
        *,
        complexity: str = "medium",
        risk: str = "medium",
        max_specialists: int = 5,
        wave_size: int = 4,
        profile_allowed_tools: tuple[str, ...] | None = None,
    ) -> TeamPlan:
        if complexity not in _RANK or risk not in _RANK:
            raise ValueError("Unsupported complexity or risk")
        if max_specialists < 1:
            raise ValueError("max_specialists must be >= 1")
        if wave_size < 1:
            raise ValueError("wave_size must be >= 1")

        portfolio = self.registry.is_portfolio_task(task)
        specialists = self.registry.route_specialists(task, max_specialists=max_specialists)

        architect = self.registry.find_by_capability("architecture")
        if not portfolio and architect is not None and _RANK[complexity] >= _RANK["high"]:
            specialists = self._dedupe([architect, *specialists])[:max_specialists]

        qa = self.registry.find_by_capability("qa")
        if qa is None:
            raise ValueError("Every team plan requires a qa-capable verifier")
        verifiers: list[AgentDefinition] = [qa]

        security = self.registry.find_by_capability("security")
        security_required = portfolio or _RANK[risk] >= _RANK["high"]
        if security is not None and self.registry.agent_matches(security, task):
            security_required = True
        if security_required:
            if security is None:
                raise ValueError("High-risk or security-scoped work requires a security-capable verifier")
            verifiers.append(security)

        ordered = self._dedupe([
            self.registry.coordinator,
            *specialists,
            *verifiers,
            self.registry.reviewer,
        ])
        profile_tools = set(profile_allowed_tools) if profile_allowed_tools is not None else None
        assignments = tuple(
            AgentAssignment(
                agent=a.name,
                phase=a.phase,
                objective=a.description,
                instructions=a.instructions,
                allowed_tools=tuple(
                    tool for tool in a.allowed_tools
                    if profile_tools is None or tool in profile_tools
                ),
                independent=a.kind == "reviewer",
            )
            for a in ordered
        )

        reviewer = self.registry.reviewer.name
        waves: list[tuple[str, ...]] = []
        for phase in ("plan", "build", "release"):
            names = [a.name for a in ordered if a.phase == phase and a.name != reviewer]
            waves.extend(self._chunk(names, wave_size))
        verify_names = [a.name for a in ordered if a.phase == "verify" and a.name != reviewer]
        waves.extend(self._chunk(verify_names, wave_size))
        waves.append((reviewer,))

        handoffs: list[Handoff] = []
        coordinator = self.registry.coordinator.name
        for agent in ordered:
            if agent.name == coordinator:
                continue
            artifact = {
                "plan": "scope-and-decision-contract",
                "build": "implementation-or-domain-artifact",
                "verify": "verification-evidence",
                "release": "release-readiness-evidence",
            }[agent.phase]
            handoffs.append(Handoff(coordinator, agent.name, artifact))

        for agent in ordered:
            if agent.name not in {coordinator, reviewer}:
                handoffs.append(Handoff(agent.name, reviewer, "evidence-and-open-risks"))

        plan = TeamPlan(task, portfolio, assignments, tuple(handoffs), tuple(waves))
        if self.tracer:
            task_bytes = task.encode("utf-8")
            self.tracer.emit(
                "team.plan.created",
                task_sha256=hashlib.sha256(task_bytes).hexdigest(),
                task_chars=len(task),
                agents=list(plan.agents),
                waves=[list(wave) for wave in plan.waves],
                portfolio_mode=portfolio,
                complexity=complexity,
                risk=risk,
            )
        return plan

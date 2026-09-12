from __future__ import annotations

from dataclasses import dataclass

from .model_router import ModelChoice, ModelRouter
from .policy import PolicyEngine
from .skill_registry import SkillRegistry
from .tracing import JsonlTracer


@dataclass(slots=True)
class Plan:
    task: str
    skills: list[str]
    model: ModelChoice
    profile: str


class Orchestrator:
    """Deterministic control-plane planner; model execution remains adapter-specific."""

    def __init__(self, skills: SkillRegistry, models: ModelRouter, policy: PolicyEngine, tracer: JsonlTracer | None = None):
        self.skills = skills
        self.models = models
        self.policy = policy
        self.tracer = tracer

    def plan(self, task: str, *, complexity: str = "medium", risk: str = "medium", profile: str = "base", requires_tools: bool = True) -> Plan:
        selected = self.skills.route(task)
        model = self.models.choose(complexity=complexity, risk=risk, requires_tools=requires_tools)
        plan = Plan(task, [s.name for s in selected], model, profile)
        if self.tracer:
            self.tracer.emit("plan.created", task=task, skills=plan.skills, model=model.model, tier=model.tier, profile=profile)
        return plan

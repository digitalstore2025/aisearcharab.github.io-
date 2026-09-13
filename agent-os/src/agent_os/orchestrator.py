from __future__ import annotations

import hashlib
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
    mode: str = "standard"
    allowed_tools: tuple[str, ...] = ()
    production_mutations: bool = False


class Orchestrator:
    """Deterministic control-plane planner; model execution remains adapter-specific."""

    def __init__(self, skills: SkillRegistry, models: ModelRouter, policy: PolicyEngine, tracer: JsonlTracer | None = None):
        self.skills = skills
        self.models = models
        self.policy = policy
        self.tracer = tracer

    def plan(
        self,
        task: str,
        *,
        complexity: str = "medium",
        risk: str = "medium",
        profile: str = "base",
        profile_mode: str = "standard",
        allowed_tools: tuple[str, ...] = (),
        production_mutations: bool = False,
        requires_tools: bool = True,
    ) -> Plan:
        selected = self.skills.route(task)
        model = self.models.choose(complexity=complexity, risk=risk, requires_tools=requires_tools)
        plan = Plan(task, [s.name for s in selected], model, profile, profile_mode, allowed_tools, production_mutations)
        if self.tracer:
            task_bytes = task.encode("utf-8")
            self.tracer.emit(
                "plan.created",
                task_sha256=hashlib.sha256(task_bytes).hexdigest(),
                task_chars=len(task),
                skills=plan.skills,
                model=model.model,
                tier=model.tier,
                profile=profile,
                mode=profile_mode,
                allowed_tools=list(allowed_tools),
                production_mutations=production_mutations,
            )
        return plan

from __future__ import annotations

import argparse
import json

from .agent_registry import AgentRegistry
from .config import config_root, load_profile
from .model_router import ModelRouter
from .policy import PolicyEngine
from .skill_registry import SkillRegistry
from .orchestrator import Orchestrator
from .team import TeamPlanner
from .tracing import JsonlTracer


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("task")
    parser.add_argument("--complexity", choices=("low", "medium", "high", "critical"))
    parser.add_argument("--risk", choices=("low", "medium", "high", "critical"))
    parser.add_argument("--profile", default="base")


def main() -> None:
    p = argparse.ArgumentParser(prog="agent-os")
    sub = p.add_subparsers(dest="cmd", required=True)
    plan_p = sub.add_parser("plan")
    _add_common_args(plan_p)
    team_p = sub.add_parser("team-plan")
    _add_common_args(team_p)
    team_p.add_argument("--max-specialists", type=int, default=5)
    team_p.add_argument("--wave-size", type=int, default=4)
    team_p.add_argument("--trace-jsonl", help="Optional sanitized JSONL trace output path")
    args = p.parse_args()

    root = config_root()
    profile = load_profile(args.profile, root)
    complexity = args.complexity or profile.default_complexity
    risk = args.risk or profile.default_risk

    if args.cmd == "plan":
        orchestrator = Orchestrator(
            SkillRegistry.from_file(root / "skills/registry.json"),
            ModelRouter.from_file(root / "models/catalog.json"),
            PolicyEngine.from_file(root / "policies/default.json"),
        )
        plan = orchestrator.plan(
            args.task,
            complexity=complexity,
            risk=risk,
            profile=profile.name,
            profile_mode=profile.mode,
            allowed_tools=profile.allowed_tools,
            production_mutations=profile.production_mutations,
        )
        print(json.dumps({
            "task": plan.task,
            "skills": plan.skills,
            "model": plan.model.model,
            "tier": plan.model.tier,
            "profile": plan.profile,
            "mode": plan.mode,
            "allowed_tools": list(plan.allowed_tools),
            "production_mutations": plan.production_mutations,
        }, ensure_ascii=False, indent=2))
        return

    tracer = JsonlTracer(args.trace_jsonl) if args.trace_jsonl else None
    planner = TeamPlanner(
        AgentRegistry.from_file(root / "agents/registry.json"),
        tracer=tracer,
    )
    team = planner.plan(
        args.task,
        complexity=complexity,
        risk=risk,
        max_specialists=args.max_specialists,
        wave_size=args.wave_size,
        profile_allowed_tools=profile.allowed_tools,
    )
    print(json.dumps({
        "task": team.task,
        "profile": profile.name,
        "portfolio_mode": team.portfolio_mode,
        "assignments": [
            {
                "agent": a.agent,
                "phase": a.phase,
                "objective": a.objective,
                "instructions": a.instructions,
                "allowed_tools": list(a.allowed_tools),
                "independent": a.independent,
            }
            for a in team.assignments
        ],
        "waves": [list(wave) for wave in team.waves],
        "handoffs": [
            {"from": h.source, "to": h.target, "artifact": h.artifact}
            for h in team.handoffs
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

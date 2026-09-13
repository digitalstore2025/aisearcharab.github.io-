from __future__ import annotations

import argparse
import json

from .config import config_root, load_profile
from .model_router import ModelRouter
from .policy import PolicyEngine
from .skill_registry import SkillRegistry
from .orchestrator import Orchestrator


def main() -> None:
    p = argparse.ArgumentParser(prog="agent-os")
    sub = p.add_subparsers(dest="cmd", required=True)
    plan_p = sub.add_parser("plan")
    plan_p.add_argument("task")
    plan_p.add_argument("--complexity", choices=("low", "medium", "high", "critical"))
    plan_p.add_argument("--risk", choices=("low", "medium", "high", "critical"))
    plan_p.add_argument("--profile", default="base")
    args = p.parse_args()

    if args.cmd == "plan":
        root = config_root()
        profile = load_profile(args.profile, root)
        complexity = args.complexity or profile.default_complexity
        risk = args.risk or profile.default_risk
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


if __name__ == "__main__":
    main()

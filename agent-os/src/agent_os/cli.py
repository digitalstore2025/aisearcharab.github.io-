from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model_router import ModelRouter
from .policy import PolicyEngine
from .skill_registry import SkillRegistry
from .orchestrator import Orchestrator


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    p = argparse.ArgumentParser(prog="agent-os")
    sub = p.add_subparsers(dest="cmd", required=True)
    plan_p = sub.add_parser("plan")
    plan_p.add_argument("task")
    plan_p.add_argument("--complexity", default="medium")
    plan_p.add_argument("--risk", default="medium")
    plan_p.add_argument("--profile", default="base")
    args = p.parse_args()

    if args.cmd == "plan":
        root = _root()
        orchestrator = Orchestrator(
            SkillRegistry.from_file(root / "config/skills/registry.json"),
            ModelRouter.from_file(root / "config/models/catalog.json"),
            PolicyEngine.from_file(root / "config/policies/default.json"),
        )
        plan = orchestrator.plan(args.task, complexity=args.complexity, risk=args.risk, profile=args.profile)
        print(json.dumps({"task": plan.task, "skills": plan.skills, "model": plan.model.model, "tier": plan.model.tier, "profile": plan.profile}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

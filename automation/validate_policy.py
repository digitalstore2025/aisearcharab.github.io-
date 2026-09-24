#!/usr/bin/env python3
"""Validate automation project policy files.

This is intentionally standard-library only so it can run in GitHub Actions,
local shells, Codex, or restricted CI without extra dependencies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {
    "project_id",
    "min_quality",
    "min_evidence",
    "max_task_cost_usd",
    "routes",
    "human_approval_actions",
    "blocked_autonomous_actions",
}

REQUIRED_ROUTES = {"deterministic", "ai_workflow", "agentic"}
DANGEROUS_ACTION_TERMS = {
    "publish",
    "production_deploy",
    "delete",
    "301",
    "410",
    "canonical_change",
    "secret_change",
    "billing_change",
    "destructive_migration",
    "public_knowledge_release",
    "sensitive_source_inclusion",
}


def fail(message: str) -> None:
    print(f"POLICY_VALIDATION_FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def as_list(value: Any, field: str) -> list[str]:
    require(isinstance(value, list), f"{field} must be a list")
    require(all(isinstance(item, str) and item.strip() for item in value), f"{field} must contain non-empty strings")
    require(len(value) == len(set(value)), f"{field} must not contain duplicates")
    return value


def validate_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")

    missing = REQUIRED_TOP_LEVEL - set(policy)
    require(not missing, f"missing required fields: {sorted(missing)}")

    require(isinstance(policy["project_id"], str) and policy["project_id"].strip(), "project_id must be a non-empty string")
    require(isinstance(policy["min_quality"], (int, float)), "min_quality must be numeric")
    require(0.0 <= float(policy["min_quality"]) <= 1.0, "min_quality must be between 0 and 1")
    require(float(policy["min_quality"]) >= 0.85, "min_quality must be at least 0.85")
    require(isinstance(policy["min_evidence"], int) and policy["min_evidence"] >= 1, "min_evidence must be an integer >= 1")
    require(isinstance(policy["max_task_cost_usd"], (int, float)) and policy["max_task_cost_usd"] > 0, "max_task_cost_usd must be positive")

    routes = policy["routes"]
    require(isinstance(routes, dict), "routes must be an object")
    require(REQUIRED_ROUTES <= set(routes), f"routes must include {sorted(REQUIRED_ROUTES)}")
    for route in REQUIRED_ROUTES:
        as_list(routes[route], f"routes.{route}")

    human_approval_actions = set(as_list(policy["human_approval_actions"], "human_approval_actions"))
    blocked_autonomous_actions = set(as_list(policy["blocked_autonomous_actions"], "blocked_autonomous_actions"))

    missing_approval = sorted(action for action in DANGEROUS_ACTION_TERMS if action in str(policy) and action not in human_approval_actions and f"auto_{action}" not in blocked_autonomous_actions)
    require(not missing_approval, f"dangerous actions must be gated or blocked: {missing_approval}")

    auto_actions = [action for action in blocked_autonomous_actions if not action.startswith("auto_") and not action.startswith("publish_unverified") and not action.startswith("store_sensitive")]
    require(not auto_actions, f"blocked autonomous actions should be explicit autonomous actions: {auto_actions}")

    return policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("policy", nargs="?", default="automation/project-policy.json")
    args = parser.parse_args()

    policy = validate_policy(Path(args.policy))
    print(json.dumps({"status": "ok", "project_id": policy["project_id"], "min_quality": policy["min_quality"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

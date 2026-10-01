#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class RoutingDecision:
    task_id: str
    task_type: str
    route: str
    workflow: str
    status: str
    reason: str
    human_approval_required: bool
    blocked: bool
    evidence_count: int
    failures: list[str]
    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "route": self.route,
            "workflow": self.workflow,
            "status": self.status,
            "reason": self.reason,
            "human_approval_required": self.human_approval_required,
            "blocked": self.blocked,
            "evidence_count": self.evidence_count,
            "failures": self.failures,
        }

def fail(message: str) -> None:
    print(f"SEO_ROUTER_FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)

def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"{path} must contain a JSON object")
    return data

def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

def evidence_count(task: dict[str, Any]) -> int:
    return len(as_list(task.get("evidence")))

def normalize_action(action: Any) -> str:
    return str(action or "analysis").strip()

def infer_workflow(task: dict[str, Any]) -> str:
    task_type = str(task.get("task_type", "")).strip()
    metrics = task.get("metrics") if isinstance(task.get("metrics"), dict) else {}
    signals = task.get("page_signals") if isinstance(task.get("page_signals"), dict) else {}
    if task_type:
        return task_type
    if metrics.get("indexed") is False:
        return "indexation_diagnosis"
    if metrics.get("position") is not None:
        try:
            position = float(metrics["position"])
        except (TypeError, ValueError):
            position = 0.0
        if 4 <= position <= 20:
            return "gsc_threshold_routing"
    if signals.get("duplicate_title") or signals.get("duplicate_meta"):
        return "duplicate_detection"
    if any(key in signals for key in ("missing_title", "title_length", "missing_h1", "missing_canonical", "missing_alt")):
        return "technical_seo_checks"
    return "technical_seo_checks"

def route_task(policy: dict[str, Any], task: dict[str, Any]) -> RoutingDecision:
    routes = policy.get("routes") if isinstance(policy.get("routes"), dict) else {}
    deterministic = set(as_list(routes.get("deterministic")))
    ai_workflow = set(as_list(routes.get("ai_workflow")))
    agentic = set(as_list(routes.get("agentic")))
    human_actions = set(as_list(policy.get("human_approval_actions")))
    blocked_actions = set(as_list(policy.get("blocked_autonomous_actions")))
    task_id = str(task.get("task_id") or task.get("url") or "unidentified-task")
    requested_action = normalize_action(task.get("requested_action"))
    workflow = infer_workflow(task)
    ev_count = evidence_count(task)
    failures: list[str] = []
    try:
        estimated_cost = float(task.get("estimated_cost_usd", 0.0))
    except (TypeError, ValueError):
        failures.append("invalid_estimated_cost_usd")
        estimated_cost = 0.0
    max_cost = float(policy.get("max_task_cost_usd", 0.0))
    if max_cost and estimated_cost > max_cost:
        failures.append("cost_limit_exceeded")
    if requested_action in blocked_actions:
        return RoutingDecision(task_id, workflow, "blocked", workflow, "blocked", f"requested_action '{requested_action}' is autonomously blocked by policy", True, True, ev_count, failures)
    if requested_action in human_actions:
        return RoutingDecision(task_id, workflow, "manual_review", workflow, "requires_human_approval", f"requested_action '{requested_action}' requires human approval", True, False, ev_count, failures)
    metrics = task.get("metrics") if isinstance(task.get("metrics"), dict) else {}
    if metrics.get("indexed") is False:
        workflow = "indexation_diagnosis"
    if workflow in agentic or task.get("unknown_next_step") is True:
        route = "agentic"
        min_evidence = int(policy.get("min_evidence", 1))
        if ev_count < min_evidence:
            failures.append("insufficient_evidence_for_agentic_route")
        reason = "open-ended diagnosis requires evidence-driven next-step selection"
    elif workflow in ai_workflow or task.get("semantic_needed") is True:
        route = "ai_workflow"
        reason = "semantic interpretation is required"
    elif workflow in deterministic:
        route = "deterministic"
        reason = "rule-based SEO/GSC workflow"
    else:
        route = "manual_review"
        failures.append("unknown_workflow")
        reason = "workflow is not registered in project policy"
    status = "routed" if not failures else "routed_with_failures"
    return RoutingDecision(task_id, workflow, route, workflow, status, reason, route == "manual_review", False, ev_count, failures)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="automation/project-policy.json")
    parser.add_argument("--task", required=True)
    args = parser.parse_args()
    policy = load_json(Path(args.policy))
    task = load_json(Path(args.task))
    decision = route_task(policy, task)
    print(json.dumps(decision.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    if decision.blocked or any(failure in {"cost_limit_exceeded", "unknown_workflow"} for failure in decision.failures):
        raise SystemExit(2)

if __name__ == "__main__":
    main()

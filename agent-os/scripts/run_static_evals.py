from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_os.agent_registry import AgentRegistry
from agent_os.dod import code_dod, research_dod
from agent_os.injection import assess_untrusted_text
from agent_os.policy import PolicyEngine
from agent_os.skill_registry import SkillRegistry
from agent_os.team import TeamPlanner
from agent_os.types import Action


def rows(name: str):
    with (ROOT / "evals/cases" / name).open("r", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main() -> int:
    failures = []
    total = passed = 0
    policy = PolicyEngine.from_file(ROOT / "config/policies/default.json")
    registry = SkillRegistry.from_file(ROOT / "config/skills/registry.json")
    team = TeamPlanner(AgentRegistry.from_file(ROOT / "config/agents/registry.json"))

    for c in rows("policy.jsonl"):
        total += 1
        got = policy.evaluate(Action(c["action"], resource=c.get("resource", ""), environment=c["environment"])).decision.value
        if got == c["expected"]:
            passed += 1
        else:
            failures.append(f"{c['id']}: policy {got} != {c['expected']}")

    for c in rows("injection.jsonl"):
        total += 1
        got = assess_untrusted_text(c["text"]).suspicious
        if got == c["suspicious"]:
            passed += 1
        else:
            failures.append(f"{c['id']}: injection {got} != {c['suspicious']}")

    for c in rows("routing.jsonl"):
        total += 1
        got = [s.name for s in registry.route(c["task"])]
        if set(got) == set(c["expected"]) and len(got) == len(c["expected"]):
            passed += 1
        else:
            failures.append(f"{c['id']}: routing {got} != {c['expected']}")

    for c in rows("agents.jsonl"):
        total += 1
        plan = team.plan(
            c["task"],
            complexity=c.get("complexity", "medium"),
            risk=c.get("risk", "medium"),
            max_specialists=c.get("max_specialists", 5),
        )
        got = list(plan.agents)
        expected = c["expected_agents"]
        if got == expected:
            passed += 1
        else:
            failures.append(f"{c['id']}: ordered agents {got} != {expected}")

    for c in rows("completion.jsonl"):
        total += 1
        dod = code_dod() if c["type"] == "code" else research_dod()
        for check in dod.checks:
            check.passed = check.name in c["passed"]
        if dod.complete == c["complete"]:
            passed += 1
        else:
            failures.append(f"{c['id']}: completion {dod.complete} != {c['complete']}")

    print(f"STATIC EVALS: {passed}/{total} ({passed/total:.1%})")
    for failure in failures:
        print("FAIL:", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

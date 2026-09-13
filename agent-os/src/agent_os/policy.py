from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable

from .config import load_json
from .types import Action, Decision, PolicyResult


@dataclass(slots=True)
class Rule:
    id: str
    action: str
    environment: str
    decision: Decision
    reason: str
    resource: str = "*"

    def matches(self, action: Action) -> bool:
        return (
            fnmatch(action.name, self.action)
            and fnmatch(action.environment, self.environment)
            and fnmatch(action.resource, self.resource)
        )


class PolicyEngine:
    """Deny/approval/allow engine. First matching rule wins; default is deny."""

    def __init__(self, rules: Iterable[Rule]):
        self.rules = list(rules)

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        data = load_json(path)
        rules = [
            Rule(
                id=r["id"],
                action=r["action"],
                environment=r.get("environment", "*"),
                decision=Decision(r["decision"]),
                reason=r["reason"],
                resource=r.get("resource", "*"),
            )
            for r in data["rules"]
        ]
        return cls(rules)

    def evaluate(self, action: Action) -> PolicyResult:
        for rule in self.rules:
            if rule.matches(action):
                return PolicyResult(rule.decision, rule.reason, rule.id)
        return PolicyResult(Decision.DENY, "No policy rule authorizes this action.", "default-deny")

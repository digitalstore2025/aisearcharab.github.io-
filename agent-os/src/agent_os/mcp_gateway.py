from __future__ import annotations

from dataclasses import dataclass

from .injection import assess_untrusted_text
from .policy import PolicyEngine
from .types import Action, Decision, ToolCall, TrustLevel


@dataclass(slots=True)
class GatewayResult:
    allowed: bool
    approval_required: bool
    reason: str
    rule_id: str


class MCPGateway:
    """Preflight gate. It does not execute MCP calls; it decides whether they may proceed."""

    def __init__(self, policy: PolicyEngine):
        self.policy = policy

    def authorize(self, call: ToolCall, *, environment: str = "local", retrieved_text: str | None = None) -> GatewayResult:
        # Retrieved content is inspected unless the caller explicitly marked the
        # source as trusted. ToolCall defaults to UNTRUSTED so omitted labels do
        # not silently bypass the prompt-injection boundary.
        if retrieved_text and call.source_trust != TrustLevel.TRUSTED:
            assessment = assess_untrusted_text(retrieved_text)
            if assessment.suspicious:
                return GatewayResult(False, False, f"Blocked prompt-injection signals: {', '.join(assessment.signals)}", "prompt-injection")

        result = self.policy.evaluate(Action(name=call.action, resource=call.tool, environment=environment, metadata=call.arguments))
        if result.decision == Decision.DENY:
            return GatewayResult(False, False, result.reason, result.rule_id)
        if result.decision == Decision.APPROVAL:
            return GatewayResult(False, True, result.reason, result.rule_id)
        return GatewayResult(True, False, result.reason, result.rule_id)

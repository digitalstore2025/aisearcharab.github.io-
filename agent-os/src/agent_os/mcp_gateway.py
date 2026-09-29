from __future__ import annotations

from dataclasses import dataclass

from .approval import ApprovalEnforcer, ApprovalGrant
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
    """Preflight gate for MCP/tool calls.

    The gateway never treats a caller-provided approval flag as sufficient.
    Approval-gated actions are executable only when an ApprovalEnforcer backed
    by an external authenticated authority validates a short-lived grant bound
    to the exact action, resource, environment and arguments.
    """

    def __init__(self, policy: PolicyEngine, approval_enforcer: ApprovalEnforcer | None = None):
        self.policy = policy
        self.approval_enforcer = approval_enforcer

    def authorize(
        self,
        call: ToolCall,
        *,
        environment: str = "local",
        retrieved_text: str | None = None,
        approval: ApprovalGrant | None = None,
    ) -> GatewayResult:
        # Retrieved content is inspected unless the caller explicitly marked the
        # source as trusted. ToolCall defaults to UNTRUSTED so omitted labels do
        # not silently bypass the prompt-injection boundary. Approval never
        # overrides this content-security check.
        if retrieved_text and call.source_trust != TrustLevel.TRUSTED:
            assessment = assess_untrusted_text(retrieved_text)
            if assessment.suspicious:
                return GatewayResult(
                    False,
                    False,
                    f"Blocked prompt-injection signals: {', '.join(assessment.signals)}",
                    "prompt-injection",
                )

        result = self.policy.evaluate(
            Action(
                name=call.action,
                resource=call.tool,
                environment=environment,
                metadata=call.arguments,
            )
        )
        if result.decision == Decision.DENY:
            return GatewayResult(False, False, result.reason, result.rule_id)

        if result.decision == Decision.APPROVAL:
            if approval is None or self.approval_enforcer is None:
                return GatewayResult(False, True, result.reason, result.rule_id)

            check = self.approval_enforcer.validate(
                approval,
                call,
                environment=environment,
            )
            if not check.valid:
                return GatewayResult(
                    False,
                    True,
                    f"{result.reason} {check.reason}",
                    result.rule_id,
                )
            return GatewayResult(
                True,
                False,
                f"{result.reason} {check.reason}",
                result.rule_id,
            )

        return GatewayResult(True, False, result.reason, result.rule_id)

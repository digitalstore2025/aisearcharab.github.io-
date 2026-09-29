from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
import json
import time
from typing import Protocol

from .types import ToolCall


def tool_call_digest(call: ToolCall) -> str:
    """Return a stable digest binding an approval to one exact tool call."""
    payload = {
        "tool": call.tool,
        "action": call.action,
        "arguments": call.arguments,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    """Authenticated approval envelope supplied by an external human-approval authority."""

    approval_id: str
    action: str
    resource: str
    environment: str
    call_digest: str
    issued_at: float
    expires_at: float


@dataclass(frozen=True, slots=True)
class ApprovalCheck:
    valid: bool
    reason: str


class ApprovalAuthority(Protocol):
    """Verifies the authenticity/status of an approval grant.

    Implementations belong at the deployment boundary (for example a signed
    approval service, GitHub Environment gate, or authenticated operator UI).
    The core package deliberately does not trust a caller-provided boolean.
    """

    def verify(self, grant: ApprovalGrant) -> bool: ...


class ApprovalEnforcer:
    """Fail-closed approval validation bound to an exact call and short time window."""

    def __init__(
        self,
        authority: ApprovalAuthority,
        *,
        max_ttl_seconds: float = 900.0,
        clock_skew_seconds: float = 30.0,
    ):
        if max_ttl_seconds <= 0:
            raise ValueError("max_ttl_seconds must be positive")
        if clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds must be non-negative")
        self.authority = authority
        self.max_ttl_seconds = max_ttl_seconds
        self.clock_skew_seconds = clock_skew_seconds

    def validate(
        self,
        grant: ApprovalGrant,
        call: ToolCall,
        *,
        environment: str,
        now: float | None = None,
    ) -> ApprovalCheck:
        current = time.time() if now is None else now

        if not self.authority.verify(grant):
            return ApprovalCheck(False, "Approval authority rejected the grant.")
        if grant.expires_at <= grant.issued_at:
            return ApprovalCheck(False, "Approval window is invalid.")
        if grant.expires_at - grant.issued_at > self.max_ttl_seconds:
            return ApprovalCheck(False, "Approval TTL exceeds the configured maximum.")
        if current + self.clock_skew_seconds < grant.issued_at:
            return ApprovalCheck(False, "Approval is not valid yet.")
        if current - self.clock_skew_seconds > grant.expires_at:
            return ApprovalCheck(False, "Approval has expired.")
        if grant.action != call.action:
            return ApprovalCheck(False, "Approval action does not match the requested action.")
        if grant.resource != call.tool:
            return ApprovalCheck(False, "Approval resource does not match the requested tool.")
        if grant.environment != environment:
            return ApprovalCheck(False, "Approval environment does not match the requested environment.")
        if not compare_digest(grant.call_digest, tool_call_digest(call)):
            return ApprovalCheck(False, "Approval is not bound to the exact tool-call arguments.")

        return ApprovalCheck(True, "Authenticated approval is valid for this exact tool call.")

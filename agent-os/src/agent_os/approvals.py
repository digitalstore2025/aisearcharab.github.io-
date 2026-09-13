from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from .types import ToolCall


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    grant_id: str
    action: str
    resource: str
    environment: str
    expires_at: float | None = None

    def active(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return self.expires_at is None or current < self.expires_at


class ApprovalLedger:
    """One-time, exact-scope approval grants. Agents cannot mint grants themselves."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}

    def grant(
        self,
        *,
        action: str,
        resource: str,
        environment: str,
        ttl_seconds: int | None = 900,
    ) -> ApprovalGrant:
        if not action or not resource or not environment:
            raise ValueError("Approval scope fields must be non-empty")
        if "*" in {action, resource, environment}:
            raise ValueError("Wildcard approvals are prohibited")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive or None")
        expires_at = None if ttl_seconds is None else time.time() + ttl_seconds
        grant = ApprovalGrant(uuid.uuid4().hex, action, resource, environment, expires_at)
        self._grants[grant.grant_id] = grant
        return grant

    def consume(self, call: ToolCall, *, environment: str) -> ApprovalGrant | None:
        now = time.time()
        expired = [gid for gid, grant in self._grants.items() if not grant.active(now)]
        for gid in expired:
            self._grants.pop(gid, None)

        for gid, grant in tuple(self._grants.items()):
            if (
                grant.action == call.action
                and grant.resource == call.tool
                and grant.environment == environment
                and grant.active(now)
            ):
                self._grants.pop(gid, None)
                return grant
        return None

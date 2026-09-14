from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .types import ToolCall, validate_execution_environment


def _arguments_digest(arguments: dict[str, Any] | None) -> str:
    if arguments is None:
        payload: dict[str, Any] = {}
    elif isinstance(arguments, dict):
        payload = arguments
    else:
        raise ValueError("Approval arguments must be a JSON object")
    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Approval arguments must be JSON-serializable") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    grant_id: str
    action: str
    resource: str
    environment: str
    arguments_sha256: str
    expires_at: float | None = None

    def active(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return self.expires_at is None or current < self.expires_at


class ApprovalLedger:
    """One-time, exact-scope approval grants. Agents cannot mint grants themselves."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}
        self._lock = threading.Lock()

    def grant(
        self,
        *,
        action: str,
        resource: str,
        environment: str,
        arguments: dict[str, Any] | None = None,
        ttl_seconds: int | None = 900,
    ) -> ApprovalGrant:
        environment = validate_execution_environment(environment)
        if not action or not resource:
            raise ValueError("Approval scope fields must be non-empty")
        if "*" in {action, resource, environment}:
            raise ValueError("Wildcard approvals are prohibited")
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive or None")
        expires_at = None if ttl_seconds is None else time.time() + ttl_seconds
        grant = ApprovalGrant(
            uuid.uuid4().hex,
            action,
            resource,
            environment,
            _arguments_digest(arguments),
            expires_at,
        )
        with self._lock:
            self._grants[grant.grant_id] = grant
        return grant

    def consume(self, call: ToolCall, *, environment: str) -> ApprovalGrant | None:
        environment = validate_execution_environment(environment)
        now = time.time()
        arguments_sha256 = _arguments_digest(call.arguments)
        with self._lock:
            expired = [gid for gid, grant in self._grants.items() if not grant.active(now)]
            for gid in expired:
                self._grants.pop(gid, None)

            for gid, grant in tuple(self._grants.items()):
                if (
                    grant.action == call.action
                    and grant.resource == call.tool
                    and grant.environment == environment
                    and grant.arguments_sha256 == arguments_sha256
                    and grant.active(now)
                ):
                    self._grants.pop(gid, None)
                    return grant
        return None

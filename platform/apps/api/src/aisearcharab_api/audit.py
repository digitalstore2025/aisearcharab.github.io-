from __future__ import annotations

import json
from collections.abc import Mapping

from sqlalchemy.orm import Session

from .models import AuditEvent

_SENSITIVE_FRAGMENTS = ("password", "token", "secret", "cookie", "authorization", "query")


def sanitize_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in (metadata or {}).items():
        normalized_key = str(key).strip()[:80]
        if not normalized_key or any(fragment in normalized_key.casefold() for fragment in _SENSITIVE_FRAGMENTS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[normalized_key] = value if not isinstance(value, str) else value[:500]
    return cleaned


def record_audit(
    session: Session,
    *,
    action: str,
    outcome: str,
    actor_user_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action[:120],
        outcome=outcome[:24],
        target_type=(target_type or "")[:80] or None,
        target_id=(target_id or "")[:180] or None,
        request_id=(request_id or "")[:128] or None,
        metadata_json=json.dumps(sanitize_metadata(metadata), ensure_ascii=False, sort_keys=True),
    )
    session.add(event)
    return event

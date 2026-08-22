from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import record_audit
from .models import AuditEvent, User

_RESERVATION_ACTION = "generated_answer.request"
_RATE_LIMIT_ACTION = "generated_answer.rate_limited"
_RESULT_ACTION = "generated_answer.result"


@dataclass(frozen=True, slots=True)
class GenerationQuotaExceeded(RuntimeError):
    retry_after_seconds: int


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def reserve_generation_quota(
    session: Session,
    *,
    user_id: str,
    request_id: str,
    max_requests: int,
    window_seconds: int,
) -> None:
    """Atomically reserve one generation request for a user.

    PostgreSQL serializes reservations for the same user by locking the user row.
    The reservation is committed before any provider network call, so the database
    connection is not retained during model latency or retries.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)

    locked_user_id = session.scalar(select(User.id).where(User.id == user_id).with_for_update())
    if locked_user_id is None:
        session.rollback()
        raise RuntimeError("authenticated user no longer exists")

    filters = (
        AuditEvent.actor_user_id == user_id,
        AuditEvent.action == _RESERVATION_ACTION,
        AuditEvent.outcome == "success",
        AuditEvent.created_at >= window_start,
    )
    used = int(session.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0)
    if used >= max_requests:
        oldest = session.scalar(
            select(AuditEvent.created_at).where(*filters).order_by(AuditEvent.created_at.asc()).limit(1)
        )
        retry_after = 1
        if oldest is not None:
            retry_after = max(1, int((_aware(oldest) + timedelta(seconds=window_seconds) - now).total_seconds()) + 1)
        record_audit(
            session,
            action=_RATE_LIMIT_ACTION,
            outcome="denied",
            actor_user_id=user_id,
            request_id=request_id,
            metadata={"limit": max_requests, "window_seconds": window_seconds, "retry_after_seconds": retry_after},
        )
        session.commit()
        raise GenerationQuotaExceeded(retry_after)

    record_audit(
        session,
        action=_RESERVATION_ACTION,
        outcome="success",
        actor_user_id=user_id,
        request_id=request_id,
        metadata={"limit": max_requests, "window_seconds": window_seconds},
    )
    session.commit()


def record_generation_result(
    session: Session,
    *,
    user_id: str,
    request_id: str,
    outcome: str,
    model: str,
    latency_ms: float,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    uncertainty: str | None = None,
    failure_class: str | None = None,
) -> None:
    metadata: dict[str, object] = {
        "model": model,
        "latency_ms": round(max(0.0, latency_ms), 3),
    }
    # audit.sanitize_metadata intentionally drops keys containing "token" to
    # protect credentials. Store numeric model-usage counters under neutral names
    # rather than weakening that repository-wide secret filter.
    if input_tokens is not None:
        metadata["input_units"] = max(0, input_tokens)
    if output_tokens is not None:
        metadata["output_units"] = max(0, output_tokens)
    if total_tokens is not None:
        metadata["total_units"] = max(0, total_tokens)
    if uncertainty is not None:
        metadata["uncertainty"] = uncertainty
    if failure_class is not None:
        metadata["failure_class"] = failure_class

    record_audit(
        session,
        action=_RESULT_ACTION,
        outcome=outcome,
        actor_user_id=user_id,
        request_id=request_id,
        metadata=metadata,
    )
    session.commit()

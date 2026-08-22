from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.generation_quota import (
    GenerationQuotaExceeded,
    record_generation_result,
    reserve_generation_quota,
)
from aisearcharab_api.models import AuditEvent, User
from conftest import OWNER_EMAIL


def test_generation_quota_is_persistent_per_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        user_id = session.scalar(select(User.id).where(User.email == OWNER_EMAIL))
        assert user_id is not None

        reserve_generation_quota(
            session,
            user_id=user_id,
            request_id="req-1",
            max_requests=1,
            window_seconds=3600,
        )

        with pytest.raises(GenerationQuotaExceeded) as exc_info:
            reserve_generation_quota(
                session,
                user_id=user_id,
                request_id="req-2",
                max_requests=1,
                window_seconds=3600,
            )

        assert exc_info.value.retry_after_seconds >= 1
        reservations = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_user_id == user_id,
                    AuditEvent.action == "generated_answer.request",
                    AuditEvent.outcome == "success",
                )
            )
        )
        denials = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_user_id == user_id,
                    AuditEvent.action == "generated_answer.rate_limited",
                    AuditEvent.outcome == "denied",
                )
            )
        )
        assert len(reservations) == 1
        assert len(denials) == 1


def test_generation_result_audit_keeps_safe_usage_metrics(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        user_id = session.scalar(select(User.id).where(User.email == OWNER_EMAIL))
        assert user_id is not None

        record_generation_result(
            session,
            user_id=user_id,
            request_id="req-usage",
            outcome="success",
            model="gpt-5.6-terra",
            latency_ms=123.4567,
            input_tokens=41,
            output_tokens=17,
            total_tokens=58,
            uncertainty="low",
        )

        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.actor_user_id == user_id,
                AuditEvent.action == "generated_answer.result",
                AuditEvent.request_id == "req-usage",
            )
        )
        assert event is not None
        metadata = json.loads(event.metadata_json)
        assert metadata["input_units"] == 41
        assert metadata["output_units"] == 17
        assert metadata["total_units"] == 58
        assert metadata["model"] == "gpt-5.6-terra"
        assert metadata["uncertainty"] == "low"
        assert "input_tokens" not in metadata

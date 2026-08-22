from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import aisearcharab_api.routes_generated_answers as generated_routes
from aisearcharab_api.config import Settings
from aisearcharab_api.database import get_db
from aisearcharab_api.generated_answers import GroundedAnswerResponse, GroundedCitation, TokenUsage
from aisearcharab_api.generation_quota import (
    GenerationQuotaExceeded,
    record_generation_result,
    reserve_generation_quota,
)
from aisearcharab_api.main import create_app
from aisearcharab_api.models import AuditEvent, User
from conftest import OWNER_EMAIL, csrf_from_client


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


def test_http_generation_quota_blocks_before_second_provider_call(
    session_factory: sessionmaker[Session],
    settings: Settings,
    owner_credentials: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_settings = replace(
        settings,
        generated_answers_enabled=True,
        openai_api_key="test-key-not-a-production-secret",
        generated_answer_max_requests=1,
        generated_answer_window_seconds=3600,
    )
    app = create_app(runtime_settings)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    calls = 0

    def fake_generate(query: str, evidence, **kwargs) -> GroundedAnswerResponse:
        nonlocal calls
        calls += 1
        first = evidence[0]
        return GroundedAnswerResponse(
            answer="إجابة اختبارية مرتبطة بالدليل.",
            citations=[
                GroundedCitation(
                    evidence_id=first.evidence_id,
                    title=first.title,
                    url=first.url,
                    source_urls=list(first.source_urls),
                )
            ],
            uncertainty="low",
            limitations=[],
            model=kwargs["model"],
            request_id=kwargs["request_id"],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(generated_routes, "generate_grounded_answer", fake_generate)

    with TestClient(app) as client:
        assert client.post("/v1/auth/login", json=owner_credentials).status_code == 200
        headers = {"X-CSRF-Token": csrf_from_client(client)}

        first = client.post("/v1/answers/grounded", headers=headers, json={"query": "GPT-5"})
        assert first.status_code == 200

        second = client.post("/v1/answers/grounded", headers=headers, json={"query": "GPT-5"})
        assert second.status_code == 429
        assert second.json()["detail"] == "generated answer quota exceeded"
        assert int(second.headers["Retry-After"]) >= 1

    assert calls == 1

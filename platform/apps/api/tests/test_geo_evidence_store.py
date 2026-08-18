import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from aisearcharab_api.geo.evidence_models import Citation, GeoQuery, ProviderRun
from aisearcharab_api.geo.evidence_store import (
    MAX_CITATIONS,
    MAX_RAW_PAYLOAD_BYTES,
    MalformedProviderOutput,
    append_provider_result,
)
from aisearcharab_api.geo.providers.base import ProviderCitation, ProviderResult
from conftest import csrf_from_client


def _query_id(client: TestClient, owner_credentials: dict[str, str]) -> tuple[str, str, str]:
    assert client.post("/v1/auth/login", json=owner_credentials).status_code == 200
    headers = {"X-CSRF-Token": csrf_from_client(client)}
    org = client.post("/v1/geo/organizations", headers=headers, json={"slug": "evidence-org", "name": "Evidence Org"})
    org_id = org.json()["id"]
    project = client.post(
        f"/v1/geo/organizations/{org_id}/projects",
        headers=headers,
        json={"slug": "site", "name": "Site", "domain": "example.com"},
    )
    project_id = project.json()["id"]
    query_set = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets",
        headers=headers,
        json={"slug": "core", "name": "Core"},
    )
    query = client.post(
        f"/v1/geo/organizations/{org_id}/projects/{project_id}/query-sets/{query_set.json()['id']}/queries",
        headers=headers,
        json={"text": "best arabic ai platform", "language": "en"},
    )
    assert query.status_code == 201
    return org_id, project_id, query.json()["id"]


def test_append_provider_result_is_hashed_raw_payload_is_retained_and_citations_are_preserved(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    raw = '{"answer":"Example","citations":["https://example.org/source"]}'
    result = ProviderResult(
        provider="test-provider",
        model="test-model-1",
        query="best arabic ai platform",
        answer_text="Example answer",
        citations=(ProviderCitation(url="https://example.org/source", title="Primary source", position=1),),
        raw_payload=raw,
        latency_ms=123,
    )
    with session_factory() as db:
        run = append_provider_result(
            db,
            organization_id=org_id,
            project_id=project_id,
            query_id=query_id,
            result=result,
        )
        assert run.raw_response_sha256 == hashlib.sha256(raw.encode()).hexdigest()
        stored = db.query(ProviderRun).filter_by(id=run.id).one()
        assert stored.provider == "test-provider"
        assert stored.raw_response_payload == raw
        assert hashlib.sha256(stored.raw_response_payload.encode()).hexdigest() == stored.raw_response_sha256
        citations = db.query(Citation).filter_by(run_id=run.id).all()
        assert [(c.url, c.position) for c in citations] == [("https://example.org/source", 1)]


def test_malformed_provider_output_is_rejected_before_run_insert(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    bad = ProviderResult(
        provider="provider",
        model="model",
        query="different query",
        answer_text="answer",
        citations=(ProviderCitation(url="file:///etc/passwd"),),
        raw_payload="{}",
    )
    with session_factory() as db:
        before = db.query(ProviderRun).count()
        with pytest.raises(MalformedProviderOutput):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad)
        assert db.query(ProviderRun).count() == before


def test_missing_raw_payload_is_rejected(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    with session_factory() as db:
        query = db.query(GeoQuery).filter_by(id=query_id).one()
        bad = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=(),
            raw_payload="",
        )
        with pytest.raises(MalformedProviderOutput):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad)


def test_oversized_raw_payload_and_citation_fanout_are_rejected(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    with session_factory() as db:
        query = db.query(GeoQuery).filter_by(id=query_id).one()
        too_large = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=(),
            raw_payload="x" * (MAX_RAW_PAYLOAD_BYTES + 1),
        )
        with pytest.raises(MalformedProviderOutput, match="payload exceeds"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=too_large)

        too_many = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=tuple(ProviderCitation(url=f"https://example.org/{i}") for i in range(MAX_CITATIONS + 1)),
            raw_payload="{}",
        )
        with pytest.raises(MalformedProviderOutput, match="citation count"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=too_many)


def test_provider_and_model_identifier_bounds_are_enforced(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    with session_factory() as db:
        query = db.query(GeoQuery).filter_by(id=query_id).one()
        bad = ProviderResult(
            provider="p" * 81,
            model="m" * 121,
            query=query.text,
            answer_text="answer",
            citations=(),
            raw_payload="{}",
        )
        with pytest.raises(MalformedProviderOutput, match="provider name"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad)


def test_wrong_runtime_types_fail_closed_as_malformed_output(
    client: TestClient,
    owner_credentials: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    org_id, project_id, query_id = _query_id(client, owner_credentials)
    with session_factory() as db:
        query = db.query(GeoQuery).filter_by(id=query_id).one()

        bad_payload = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=(),
            raw_payload={"unexpected": "mapping"},  # type: ignore[arg-type]
        )
        with pytest.raises(MalformedProviderOutput, match="raw provider payload must be a string"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad_payload)

        bad_citation = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=(ProviderCitation(url=123),),  # type: ignore[arg-type]
            raw_payload="{}",
        )
        with pytest.raises(MalformedProviderOutput, match="citation URL must be a string"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad_citation)

        bad_latency = ProviderResult(
            provider="provider",
            model="model",
            query=query.text,
            answer_text="answer",
            citations=(),
            raw_payload="{}",
            latency_ms=True,  # type: ignore[arg-type]
        )
        with pytest.raises(MalformedProviderOutput, match="latency must be an integer"):
            append_provider_result(db, organization_id=org_id, project_id=project_id, query_id=query_id, result=bad_latency)

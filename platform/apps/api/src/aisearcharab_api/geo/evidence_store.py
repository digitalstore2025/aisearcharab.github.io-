from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .evidence_models import Citation, GeoQuery, ProviderRun
from .providers.base import ProviderResult

MAX_RAW_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ANSWER_BYTES = 1024 * 1024
MAX_CITATIONS = 100
MAX_CITATION_URL_LENGTH = 4096
MAX_CITATION_TITLE_LENGTH = 500


class MalformedProviderOutput(ValueError):
    pass


def _citation_url(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_CITATION_URL_LENGTH:
        raise MalformedProviderOutput("citation URL is empty or too long")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MalformedProviderOutput("citation must be an absolute http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise MalformedProviderOutput("citation URL credentials are forbidden")
    return normalized


def _validate_result(query: GeoQuery, result: ProviderResult) -> None:
    provider = result.provider.strip()
    model = result.model.strip()
    if not provider or len(provider) > 80:
        raise MalformedProviderOutput("provider name is required and must be at most 80 characters")
    if not model or len(model) > 120:
        raise MalformedProviderOutput("provider model is required and must be at most 120 characters")
    if result.query.strip() != query.text.strip():
        raise MalformedProviderOutput("provider result query does not match stored query")
    if not result.raw_payload:
        raise MalformedProviderOutput("raw provider payload is required")
    if len(result.raw_payload.encode("utf-8")) > MAX_RAW_PAYLOAD_BYTES:
        raise MalformedProviderOutput("raw provider payload exceeds size limit")
    if len(result.answer_text.encode("utf-8")) > MAX_ANSWER_BYTES:
        raise MalformedProviderOutput("provider answer exceeds size limit")
    if len(result.citations) > MAX_CITATIONS:
        raise MalformedProviderOutput("provider citation count exceeds limit")
    if result.latency_ms is not None and result.latency_ms < 0:
        raise MalformedProviderOutput("latency cannot be negative")
    for citation in result.citations:
        _citation_url(citation.url)
        if citation.title is not None and len(citation.title.strip()) > MAX_CITATION_TITLE_LENGTH:
            raise MalformedProviderOutput("citation title exceeds size limit")
        if citation.position is not None and citation.position < 0:
            raise MalformedProviderOutput("citation position cannot be negative")


def append_provider_result(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    query_id: str,
    result: ProviderResult,
) -> ProviderRun:
    """Persist one normalized provider result and citations as append-only evidence.

    The raw upstream payload is stored together with its SHA-256 digest so later
    verification can reproduce the provenance check. Untrusted provider output is
    bounded before persistence. This module intentionally exposes no update/delete
    operation for provider evidence.
    """
    query = db.scalar(
        select(GeoQuery).where(
            GeoQuery.id == query_id,
            GeoQuery.organization_id == organization_id,
            GeoQuery.project_id == project_id,
        )
    )
    if query is None:
        raise MalformedProviderOutput("query not found in tenant/project scope")
    _validate_result(query, result)

    run = ProviderRun(
        organization_id=organization_id,
        project_id=project_id,
        query_id=query.id,
        provider=result.provider.strip(),
        model=result.model.strip(),
        status="completed",
        answer_text=result.answer_text,
        raw_response_payload=result.raw_payload,
        raw_response_sha256=hashlib.sha256(result.raw_payload.encode("utf-8")).hexdigest(),
        latency_ms=result.latency_ms,
    )
    db.add(run)
    db.flush()

    for citation in result.citations:
        db.add(
            Citation(
                organization_id=organization_id,
                project_id=project_id,
                run_id=run.id,
                url=_citation_url(citation.url),
                title=citation.title.strip() if citation.title else None,
                position=citation.position,
            )
        )
    db.commit()
    db.refresh(run)
    return run

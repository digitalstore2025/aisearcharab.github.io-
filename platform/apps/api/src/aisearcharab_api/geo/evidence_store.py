from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .evidence_models import Citation, GeoQuery, ProviderRun
from .providers.base import ProviderResult


class MalformedProviderOutput(ValueError):
    pass


def _citation_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MalformedProviderOutput("citation must be an absolute http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise MalformedProviderOutput("citation URL credentials are forbidden")
    return value.strip()


def _validate_result(query: GeoQuery, result: ProviderResult) -> None:
    if not result.provider.strip():
        raise MalformedProviderOutput("provider name is required")
    if not result.model.strip():
        raise MalformedProviderOutput("provider model is required for reproducibility")
    if result.query.strip() != query.text.strip():
        raise MalformedProviderOutput("provider result query does not match stored query")
    if not result.raw_payload:
        raise MalformedProviderOutput("raw provider payload is required")
    if result.latency_ms is not None and result.latency_ms < 0:
        raise MalformedProviderOutput("latency cannot be negative")
    for citation in result.citations:
        _citation_url(citation.url)
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

    No update/delete operation is provided by this module. A transaction either
    stores the run and all normalized citations or stores nothing.
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

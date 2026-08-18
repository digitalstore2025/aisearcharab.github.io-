from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .evidence_models import Citation, GeoQuery, Mention, ProviderRun
from .providers.base import ProviderCitation, ProviderMention, ProviderResult

MAX_RAW_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ANSWER_BYTES = 1024 * 1024
MAX_CITATIONS = 100
MAX_MENTIONS = 200
MAX_CITATION_URL_LENGTH = 4096
MAX_CITATION_TITLE_LENGTH = 500
MAX_MENTION_ENTITY_KEY_LENGTH = 180
MAX_MENTION_DISPLAY_TEXT_LENGTH = 300


class MalformedProviderOutput(ValueError):
    pass


def _require_string(value: object, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise MalformedProviderOutput(f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise MalformedProviderOutput(f"{field_name} is required")
    return value


def _citation_url(value: object) -> str:
    raw = _require_string(value, "citation URL")
    normalized = raw.strip()
    if len(normalized) > MAX_CITATION_URL_LENGTH:
        raise MalformedProviderOutput("citation URL is too long")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MalformedProviderOutput("citation must be an absolute http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise MalformedProviderOutput("citation URL credentials are forbidden")
    return normalized


def _validated_position(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MalformedProviderOutput(f"{field_name} must be an integer")
    if value < 0:
        raise MalformedProviderOutput(f"{field_name} cannot be negative")
    return value


def _validate_result(query: GeoQuery, result: ProviderResult) -> None:
    if not isinstance(result, ProviderResult):
        raise MalformedProviderOutput("provider result must use the ProviderResult contract")

    provider = _require_string(result.provider, "provider name").strip()
    model = _require_string(result.model, "provider model").strip()
    result_query = _require_string(result.query, "provider query").strip()
    answer_text = _require_string(result.answer_text, "provider answer", allow_empty=True)
    raw_payload = _require_string(result.raw_payload, "raw provider payload")

    if len(provider) > 80:
        raise MalformedProviderOutput("provider name is required and must be at most 80 characters")
    if len(model) > 120:
        raise MalformedProviderOutput("provider model is required and must be at most 120 characters")
    if result_query != query.text.strip():
        raise MalformedProviderOutput("provider result query does not match stored query")
    if len(raw_payload.encode("utf-8")) > MAX_RAW_PAYLOAD_BYTES:
        raise MalformedProviderOutput("raw provider payload exceeds size limit")
    if len(answer_text.encode("utf-8")) > MAX_ANSWER_BYTES:
        raise MalformedProviderOutput("provider answer exceeds size limit")

    if not isinstance(result.citations, tuple):
        raise MalformedProviderOutput("provider citations must be a tuple")
    if len(result.citations) > MAX_CITATIONS:
        raise MalformedProviderOutput("provider citation count exceeds limit")
    if not isinstance(result.mentions, tuple):
        raise MalformedProviderOutput("provider mentions must be a tuple")
    if len(result.mentions) > MAX_MENTIONS:
        raise MalformedProviderOutput("provider mention count exceeds limit")

    if result.latency_ms is not None:
        _validated_position(result.latency_ms, "latency")

    for citation in result.citations:
        if not isinstance(citation, ProviderCitation):
            raise MalformedProviderOutput("provider citations must use the ProviderCitation contract")
        _citation_url(citation.url)
        if citation.title is not None:
            title = _require_string(citation.title, "citation title", allow_empty=True).strip()
            if len(title) > MAX_CITATION_TITLE_LENGTH:
                raise MalformedProviderOutput("citation title exceeds size limit")
        _validated_position(citation.position, "citation position")

    for mention in result.mentions:
        if not isinstance(mention, ProviderMention):
            raise MalformedProviderOutput("provider mentions must use the ProviderMention contract")
        entity_key = _require_string(mention.entity_key, "mention entity key").strip()
        display_text = _require_string(mention.display_text, "mention display text").strip()
        if len(entity_key) > MAX_MENTION_ENTITY_KEY_LENGTH:
            raise MalformedProviderOutput("mention entity key exceeds size limit")
        if len(display_text) > MAX_MENTION_DISPLAY_TEXT_LENGTH:
            raise MalformedProviderOutput("mention display text exceeds size limit")
        _validated_position(mention.position, "mention position")


def append_provider_result(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    query_id: str,
    result: ProviderResult,
) -> ProviderRun:
    """Stage normalized provider evidence in the caller-owned transaction.

    The raw upstream payload is stored together with its SHA-256 digest so later
    verification can reproduce the provenance check. Untrusted provider output is
    bounded and type-checked before persistence. This helper flushes the staged
    run/mention/citation rows but deliberately does not commit: the request or
    service boundary owns commit/rollback so evidence can participate atomically
    with audit and other business changes.
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

    for mention in result.mentions:
        db.add(
            Mention(
                organization_id=organization_id,
                project_id=project_id,
                run_id=run.id,
                entity_key=mention.entity_key.strip(),
                display_text=mention.display_text.strip(),
                position=mention.position,
            )
        )

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
    db.flush()
    db.refresh(run)
    return run

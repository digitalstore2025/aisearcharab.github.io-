from __future__ import annotations

import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import Principal, require_mutation
from .database import get_db
from .generated_answers import (
    GroundedAnswerRequest,
    GroundedAnswerResponse,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
    generate_grounded_answer,
    retrieve_evidence,
    revalidate_selected_evidence,
)
from .generation_quota import GenerationQuotaExceeded, record_generation_result, reserve_generation_quota

router = APIRouter(prefix="/answers", tags=["generated-answers"])
logger = logging.getLogger(__name__)


def _record_result_safely(
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
    try:
        record_generation_result(
            session,
            user_id=user_id,
            request_id=request_id,
            outcome=outcome,
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            uncertainty=uncertainty,
            failure_class=failure_class,
        )
    except SQLAlchemyError:
        session.rollback()
        logger.exception("generation result audit failed request_id=%s", request_id)


@router.post("/grounded", response_model=GroundedAnswerResponse)
def grounded_answer(
    payload: GroundedAnswerRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_mutation("content:read"))],
) -> GroundedAnswerResponse:
    settings = request.app.state.settings
    if not settings.generated_answers_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="generated answers are disabled",
        )

    user_id = principal.user.id
    request_id = str(uuid.uuid4())
    max_sources = min(payload.max_sources or settings.generated_answer_max_sources, settings.generated_answer_max_sources)
    evidence = retrieve_evidence(
        session,
        payload.query,
        candidate_limit=settings.search_candidate_limit,
        max_sources=max_sources,
        max_evidence_chars=settings.generated_answer_max_evidence_chars,
    )
    # Evidence is materialized into immutable dataclasses. End the read transaction
    # before quota work and, critically, before waiting on the model provider.
    session.rollback()
    if not evidence:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="insufficient indexed evidence")

    try:
        reserve_generation_quota(
            session,
            user_id=user_id,
            request_id=request_id,
            max_requests=settings.generated_answer_max_requests,
            window_seconds=settings.generated_answer_window_seconds,
        )
    except GenerationQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="generated answer quota exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    started = time.perf_counter()
    try:
        result = generate_grounded_answer(
            payload.query,
            evidence,
            request_id=request_id,
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
            max_output_tokens=settings.openai_max_output_tokens,
        )
    except UpstreamUnavailableError as exc:
        _record_result_safely(
            session,
            user_id=user_id,
            request_id=request_id,
            outcome="failure",
            model=settings.openai_model,
            latency_ms=(time.perf_counter() - started) * 1000,
            failure_class="provider_unavailable",
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="generation provider unavailable") from exc
    except UpstreamInvalidResponseError as exc:
        _record_result_safely(
            session,
            user_id=user_id,
            request_id=request_id,
            outcome="failure",
            model=settings.openai_model,
            latency_ms=(time.perf_counter() - started) * 1000,
            failure_class="invalid_provider_output",
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="generation provider returned invalid output") from exc

    # Reacquire the database only after provider latency and verify that every
    # selected claim is still on the same published/indexed content revision.
    try:
        evidence_is_current = revalidate_selected_evidence(session, evidence, result)
    except SQLAlchemyError as exc:
        session.rollback()
        _record_result_safely(
            session,
            user_id=user_id,
            request_id=request_id,
            outcome="failure",
            model=result.model,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            uncertainty=result.uncertainty,
            failure_class="evidence_revalidation_unavailable",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="evidence revalidation unavailable",
        ) from exc

    if not evidence_is_current:
        session.rollback()
        _record_result_safely(
            session,
            user_id=user_id,
            request_id=request_id,
            outcome="failure",
            model=result.model,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            uncertainty=result.uncertainty,
            failure_class="evidence_changed",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="evidence changed during generation; retry",
        )

    _record_result_safely(
        session,
        user_id=user_id,
        request_id=request_id,
        outcome="success",
        model=result.model,
        latency_ms=(time.perf_counter() - started) * 1000,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        total_tokens=result.usage.total_tokens,
        uncertainty=result.uncertainty,
    )
    return result

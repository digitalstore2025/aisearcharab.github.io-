from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .auth import Principal, require_mutation
from .database import get_db
from .generated_answers import (
    GroundedAnswerRequest,
    GroundedAnswerResponse,
    NoEvidenceError,
    UpstreamInvalidResponseError,
    UpstreamUnavailableError,
    generate_grounded_answer,
)

router = APIRouter(prefix="/answers", tags=["generated-answers"])


@router.post("/grounded", response_model=GroundedAnswerResponse)
def grounded_answer(
    payload: GroundedAnswerRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    _: Annotated[Principal, Depends(require_mutation("content:read"))],
) -> GroundedAnswerResponse:
    settings = request.app.state.settings
    if not settings.generated_answers_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="generated answers are disabled",
        )

    max_sources = min(payload.max_sources or settings.generated_answer_max_sources, settings.generated_answer_max_sources)
    try:
        return generate_grounded_answer(
            session,
            payload.query,
            api_key=settings.openai_api_key or "",
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
            max_output_tokens=settings.openai_max_output_tokens,
            candidate_limit=settings.search_candidate_limit,
            max_sources=max_sources,
            max_evidence_chars=settings.generated_answer_max_evidence_chars,
        )
    except NoEvidenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="insufficient indexed evidence") from exc
    except UpstreamUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="generation provider unavailable") from exc
    except UpstreamInvalidResponseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="generation provider returned invalid output") from exc

from __future__ import annotations

import time

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import __version__
from .arabic import normalize_text
from .config import Settings, get_settings
from .database import get_db
from .middleware import SecurityHeadersMiddleware
from .models import SearchQueryEvent
from .privacy import hash_query
from .repository import get_published_content, list_indexed_content
from .schemas import CapabilitiesResponse, ContentDetail, HealthResponse, SearchResponse, SearchResult
from .search import rank_items


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    app = FastAPI(
        title="AISearcharab API",
        version=__version__,
        description="Arabic-first retrieval API. Phase 2 is retrieval-only and does not generate answers.",
        docs_url="/docs" if not runtime_settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not runtime_settings.is_production else None,
    )
    app.state.settings = runtime_settings
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    @app.get("/health/live", response_model=HealthResponse, tags=["health"])
    def liveness() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/health/ready", response_model=HealthResponse, tags=["health"])
    def readiness(session: Session = Depends(get_db)) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from exc
        return HealthResponse(status="ready", version=__version__)

    @app.get(f"{runtime_settings.api_prefix}/meta/capabilities", response_model=CapabilitiesResponse, tags=["meta"])
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(api_version=__version__)

    @app.get(f"{runtime_settings.api_prefix}/content/{{slug}}", response_model=ContentDetail, tags=["content"])
    def content_detail(slug: str, session: Session = Depends(get_db)) -> ContentDetail:
        if len(slug) > 180:
            raise HTTPException(status_code=400, detail="invalid slug")
        item = get_published_content(session, slug)
        if item is None:
            raise HTTPException(status_code=404, detail="content not found")
        return ContentDetail.model_validate(item)

    @app.get(f"{runtime_settings.api_prefix}/search", response_model=SearchResponse, tags=["search"])
    def search_content(
        q: str = Query(min_length=2, max_length=120),
        limit: int = Query(default=10, ge=1),
        offset: int = Query(default=0, ge=0, le=10_000),
        session: Session = Depends(get_db),
    ) -> SearchResponse:
        if limit > runtime_settings.max_search_limit:
            raise HTTPException(status_code=400, detail=f"limit must not exceed {runtime_settings.max_search_limit}")
        started = time.perf_counter()
        normalized_query = normalize_text(q)
        if len(normalized_query) < 2:
            raise HTTPException(status_code=422, detail="query is too short after normalization")

        ranked = rank_items(q, list_indexed_content(session))
        total = len(ranked)
        page = ranked[offset : offset + limit]
        took_ms = round((time.perf_counter() - started) * 1000, 3)

        if runtime_settings.log_queries:
            try:
                session.add(
                    SearchQueryEvent(
                        query_hash=hash_query(normalized_query, runtime_settings.query_hash_key or ""),
                        result_count=total,
                        latency_ms=took_ms,
                    )
                )
                session.commit()
            except SQLAlchemyError:
                session.rollback()

        return SearchResponse(
            query=q,
            normalized_query=normalized_query,
            total=total,
            limit=limit,
            offset=offset,
            took_ms=took_ms,
            results=[
                SearchResult(
                    slug=result.item.slug,
                    title=result.item.title,
                    summary=result.item.summary,
                    section=result.item.section,
                    language=result.item.language,
                    published_at=result.item.published_at,
                    score=result.score,
                    matched_fields=list(result.matched_fields),
                    source_authority=result.item.source_authority,
                )
                for result in page
            ],
        )

    return app


app = create_app()

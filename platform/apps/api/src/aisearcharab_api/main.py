from __future__ import annotations

import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .arabic import normalize_text
from .config import Settings, get_settings
from .database import get_db
from .geo.routes import router as geo_router
from .middleware import RequestBodyLimitMiddleware, SecurityHeadersMiddleware
from .models import SearchQueryEvent
from .privacy import hash_query
from .repository import count_indexed_matches, get_published_content, list_indexed_content
from .routes_admin import router as admin_router
from .routes_admin_detail import router as admin_detail_router
from .routes_auth import router as auth_router
from .routes_mfa import router as mfa_router
from .schemas import CapabilitiesResponse, HealthResponse, PublicClaimSummary, PublicContentDetail, SearchResponse, SearchResult, SourceSummary
from .search import rank_items

ADMIN_STATIC = Path(__file__).resolve().parent / "admin_static"
_PUBLIC_CLAIM_STATES = {"reviewed", "published"}
EXPECTED_ALEMBIC_REVISION = "20260816_0008"


def _public_content(item) -> PublicContentDetail:
    return PublicContentDetail.model_validate(
        {
            "slug": item.slug,
            "url_path": item.url_path,
            "title": item.title,
            "summary": item.summary,
            "body": item.body,
            "section": item.section,
            "language": item.language,
            "published_at": item.published_at,
            "updated_at": item.updated_at,
            "sources": [SourceSummary.model_validate(source) for source in item.sources],
            "claims": [
                PublicClaimSummary.model_validate(claim)
                for claim in item.claims
                if claim.review_status in _PUBLIC_CLAIM_STATES
            ],
        }
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    app = FastAPI(
        title="AISearcharab API",
        version=__version__,
        description="Arabic-first retrieval and governed editorial API. Generated answers and payments are not enabled.",
        docs_url="/docs" if not runtime_settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not runtime_settings.is_production else None,
    )
    app.state.settings = runtime_settings
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=runtime_settings.max_request_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(runtime_settings.allowed_hosts))

    app.include_router(auth_router, prefix=runtime_settings.api_prefix)
    app.include_router(mfa_router, prefix=runtime_settings.api_prefix)
    app.include_router(admin_router, prefix=runtime_settings.api_prefix)
    app.include_router(admin_detail_router, prefix=runtime_settings.api_prefix)
    app.include_router(geo_router, prefix=runtime_settings.api_prefix)

    @app.get("/health/live", response_model=HealthResponse, tags=["health"])
    def liveness() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/api/health", response_model=HealthResponse, include_in_schema=False)
    @app.get("/health/ready", response_model=HealthResponse, tags=["health"])
    def readiness(session: Session = Depends(get_db)) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
            if runtime_settings.environment in {"staging", "production"}:
                revision = session.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != EXPECTED_ALEMBIC_REVISION:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="database schema revision mismatch",
                    )
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from exc
        return HealthResponse(status="ready", version=__version__)

    @app.get(f"{runtime_settings.api_prefix}/meta/capabilities", response_model=CapabilitiesResponse, tags=["meta"])
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(api_version=__version__)

    @app.get(f"{runtime_settings.api_prefix}/content/{{slug}}", response_model=PublicContentDetail, tags=["content"])
    def content_detail(slug: str, session: Session = Depends(get_db)) -> PublicContentDetail:
        if len(slug) > 180:
            raise HTTPException(status_code=400, detail="invalid slug")
        item = get_published_content(session, slug)
        if item is None:
            raise HTTPException(status_code=404, detail="content not found")
        return _public_content(item)

    @app.get(f"{runtime_settings.api_prefix}/search", response_model=SearchResponse, tags=["search"])
    def search_content(
        q: str = Query(min_length=2, max_length=120),
        limit: int = Query(default=10, ge=1),
        offset: int = Query(default=0, ge=0, le=10_000),
        session: Session = Depends(get_db),
    ) -> SearchResponse:
        if limit > runtime_settings.max_search_limit:
            raise HTTPException(status_code=400, detail=f"limit must not exceed {runtime_settings.max_search_limit}")
        if offset + limit > runtime_settings.search_candidate_limit:
            raise HTTPException(
                status_code=400,
                detail=f"offset + limit must not exceed the ranked candidate window ({runtime_settings.search_candidate_limit})",
            )
        started = time.perf_counter()
        normalized_query = normalize_text(q)
        if len(normalized_query) < 2:
            raise HTTPException(status_code=422, detail="query is too short after normalization")

        candidates = list_indexed_content(session, q, candidate_limit=runtime_settings.search_candidate_limit)
        ranked = rank_items(q, candidates)
        database_total = count_indexed_matches(session, q)
        total = database_total if database_total is not None else len(ranked)
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
                    url=result.item.url_path,
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

    @app.get("/admin", include_in_schema=False)
    def admin_redirect() -> RedirectResponse:
        return RedirectResponse(url="/admin/", status_code=307)

    app.mount("/admin", StaticFiles(directory=ADMIN_STATIC, html=True), name="admin-console")
    return app


app = create_app()
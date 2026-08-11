from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HealthResponse(BaseModel):
    status: str
    service: str = "aisearcharab-api"
    version: str


class CapabilitiesResponse(BaseModel):
    api_version: str
    retrieval_mode: str = "lexical-v1"
    generated_answers: bool = False
    rag: bool = False
    authentication: bool = False
    payments: bool = False
    crawling: bool = False


class SourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_key: str
    title: str
    publisher: str
    url: HttpUrl
    archive_url: HttpUrl | None = None
    source_type: str
    reliability: str


class ClaimSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_key: str
    text: str
    claim_type: str
    confidence: str
    review_status: str
    verified_at: datetime | None = None


class ContentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    summary: str
    body: str
    section: str
    language: str
    status: str
    published_at: datetime | None = None
    updated_at: datetime
    sources: list[SourceSummary] = Field(default_factory=list)
    claims: list[ClaimSummary] = Field(default_factory=list)


class SearchResult(BaseModel):
    slug: str
    title: str
    summary: str
    section: str
    language: str
    published_at: datetime | None = None
    score: float
    matched_fields: list[str]
    source_authority: float


class SearchResponse(BaseModel):
    query: str
    normalized_query: str
    algorithm_version: str = "lexical-v1"
    retrieval_mode: str = "retrieval-only"
    total: int
    limit: int
    offset: int
    took_ms: float
    results: list[SearchResult]

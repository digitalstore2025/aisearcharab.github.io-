from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class HealthResponse(BaseModel):
    status: str
    service: str = "aisearcharab-api"
    version: str


class CapabilitiesResponse(BaseModel):
    api_version: str
    retrieval_mode: str = "lexical-v1"
    generated_answers: bool = False
    rag: bool = False
    authentication: bool = True
    admin_console: bool = True
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

    id: str | None = None
    claim_key: str
    text: str
    claim_type: str
    confidence: str
    review_status: str
    verified_at: datetime | None = None


class PublicClaimSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_key: str
    text: str
    claim_type: str
    confidence: str
    verified_at: datetime | None = None


class ContentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    slug: str
    url_path: str
    title: str
    summary: str
    body: str
    section: str
    language: str
    status: str
    is_indexed: bool
    published_at: datetime | None = None
    updated_at: datetime
    sources: list[SourceSummary] = Field(default_factory=list)
    claims: list[ClaimSummary] = Field(default_factory=list)


class PublicContentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    url_path: str
    title: str
    summary: str
    body: str
    section: str
    language: str
    published_at: datetime
    updated_at: datetime
    sources: list[SourceSummary] = Field(default_factory=list)
    claims: list[PublicClaimSummary] = Field(default_factory=list)


class SearchResult(BaseModel):
    slug: str
    url: str
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


RoleName = Literal["owner", "admin", "editor", "reviewer", "publisher", "analyst"]
ContentStatus = Literal["draft", "reviewed", "published", "archived"]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: RoleName
    is_active: bool
    permissions: list[str] = Field(default_factory=list)
    last_login_at: datetime | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    user: UserPublic
    expires_at: datetime


class StepUpRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class StepUpResponse(BaseModel):
    elevated_until: datetime


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=160)
    role: RoleName
    password: str = Field(min_length=12, max_length=256)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: RoleName | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


class ContentAdminSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    url_path: str
    title: str
    section: str
    language: str
    status: ContentStatus
    is_indexed: bool
    source_authority: float
    published_at: datetime | None = None
    updated_at: datetime
    source_count: int = 0
    claim_count: int = 0


class ContentCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9][a-z0-9-]*$")
    url_path: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=3, max_length=300)
    summary: str = Field(min_length=10, max_length=2000)
    body: str = Field(min_length=20, max_length=200_000)
    section: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    language: str = Field(default="ar", min_length=2, max_length=12)
    source_authority: float = Field(default=0.0, ge=0, le=10)

    @field_validator("url_path")
    @classmethod
    def validate_url_path(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//") or "://" in value:
            raise ValueError("url_path must be a local absolute path")
        return value


class ContentUpdate(BaseModel):
    url_path: str | None = Field(default=None, min_length=1, max_length=500)
    title: str | None = Field(default=None, min_length=3, max_length=300)
    summary: str | None = Field(default=None, min_length=10, max_length=2000)
    body: str | None = Field(default=None, min_length=20, max_length=200_000)
    section: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    language: str | None = Field(default=None, min_length=2, max_length=12)
    source_authority: float | None = Field(default=None, ge=0, le=10)

    @field_validator("url_path")
    @classmethod
    def validate_optional_url_path(cls, value: str | None) -> str | None:
        if value is not None and (not value.startswith("/") or value.startswith("//") or "://" in value):
            raise ValueError("url_path must be a local absolute path")
        return value


class ContentTransitionRequest(BaseModel):
    status: ContentStatus


class SourceCreate(BaseModel):
    source_key: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=3, max_length=500)
    publisher: str = Field(min_length=2, max_length=250)
    url: HttpUrl
    archive_url: HttpUrl | None = None
    source_type: str = Field(min_length=2, max_length=64)
    language: str = Field(default="ar", min_length=2, max_length=12)
    reliability: Literal["primary", "secondary", "tertiary", "unverified"] = "unverified"


class ClaimCreate(BaseModel):
    claim_key: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9][a-z0-9-]*$")
    text: str = Field(min_length=5, max_length=5000)
    claim_type: Literal["verified-fact", "estimate", "inference", "third-party-claim"]
    confidence: Literal["high", "medium", "low", "unverified"] = "unverified"


class ClaimReviewRequest(BaseModel):
    review_status: Literal["reviewed", "published", "rejected"]
    confidence: Literal["high", "medium", "low", "unverified"]


class AuditEventPublic(BaseModel):
    id: str
    actor_user_id: str | None = None
    action: str
    outcome: str
    target_type: str | None = None
    target_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, object]
    created_at: datetime

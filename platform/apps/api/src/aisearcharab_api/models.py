from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


content_sources = Table(
    "content_sources",
    Base.metadata,
    Column("content_id", String(36), ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", String(36), ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_items_status_indexed", "status", "is_indexed"),
        CheckConstraint("status IN ('draft','reviewed','published','archived')", name="ck_content_status"),
        CheckConstraint("source_authority >= 0 AND source_authority <= 10", name="ck_content_authority"),
        CheckConstraint("revision >= 1", name="ck_content_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    url_path: Mapped[str] = mapped_column(String(500), nullable=False, default="/")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    section: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="ar")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    is_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_authority: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_modified_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __mapper_args__ = {"version_id_col": revision}

    sources: Mapped[list[Source]] = relationship(
        secondary=content_sources,
        back_populates="content_items",
        lazy="selectin",
    )
    claims: Mapped[list[Claim]] = relationship(
        back_populates="content_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("reliability IN ('primary','secondary','tertiary','unverified')", name="ck_source_reliability"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str] = mapped_column(String(250), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    archive_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="ar")
    reliability: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    content_items: Mapped[list[ContentItem]] = relationship(
        secondary=content_sources,
        back_populates="sources",
    )


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("claim_type IN ('verified-fact','estimate','inference','third-party-claim')", name="ck_claim_type"),
        CheckConstraint("confidence IN ('high','medium','low','unverified')", name="ck_claim_confidence"),
        CheckConstraint("review_status IN ('draft','reviewed','published','rejected')", name="ck_claim_review_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    content_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    content_item: Mapped[ContentItem] = relationship(back_populates="claims")


class SearchQueryEvent(Base):
    __tablename__ = "search_query_events"
    __table_args__ = (
        Index("ix_search_query_events_created_at", "created_at"),
        CheckConstraint("result_count >= 0", name="ck_search_result_count"),
        CheckConstraint("latency_ms >= 0", name="ck_search_latency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('owner','admin','editor','reviewer','publisher','analyst')", name="ck_user_role"),
        Index("ix_users_active_role", "is_active", "role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_pending_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_last_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    sessions: Mapped[list[AdminSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="actor")
    recovery_codes: Mapped[list[MfaRecoveryCode]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        Index("ix_admin_sessions_user_active", "user_id", "revoked_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    elevated_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")


class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"
    __table_args__ = (
        Index("ix_mfa_recovery_codes_user_unused", "user_id", "used_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="recovery_codes")


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    __table_args__ = (
        CheckConstraint("failure_count >= 0", name="ck_login_throttle_failure_count"),
        Index("ix_login_throttles_updated_at", "updated_at"),
    )

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("outcome IN ('success','failure','denied')", name="ck_audit_outcome"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    actor: Mapped[User | None] = relationship(back_populates="audit_events")

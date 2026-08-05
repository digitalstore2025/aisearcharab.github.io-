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
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    section: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="ar")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    is_indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_authority: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

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

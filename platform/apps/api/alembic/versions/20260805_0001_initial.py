"""Create Phase 2 retrieval schema.

Revision ID: 20260805_0001
Revises:
Create Date: 2026-08-05
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("section", sa.String(length=80), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_indexed", sa.Boolean(), nullable=False),
        sa.Column("source_authority", sa.Float(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_authority >= 0 AND source_authority <= 10", name="ck_content_authority"),
        sa.CheckConstraint("status IN ('draft','reviewed','published','archived')", name="ck_content_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_content_items_section", "content_items", ["section"], unique=False)
    op.create_index("ix_content_items_status_indexed", "content_items", ["status", "is_indexed"], unique=False)

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_key", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=250), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("archive_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("reliability", sa.String(length=24), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reliability IN ('primary','secondary','tertiary','unverified')", name="ck_source_reliability"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )

    op.create_table(
        "content_sources",
        sa.Column("content_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "source_id"),
    )

    op.create_table(
        "claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("content_id", sa.String(length=36), nullable=False),
        sa.Column("claim_key", sa.String(length=180), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.String(length=24), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("claim_type IN ('verified-fact','estimate','inference','third-party-claim')", name="ck_claim_type"),
        sa.CheckConstraint("confidence IN ('high','medium','low','unverified')", name="ck_claim_confidence"),
        sa.CheckConstraint("review_status IN ('draft','reviewed','published','rejected')", name="ck_claim_review_status"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_key"),
    )
    op.create_index("ix_claims_content_id", "claims", ["content_id"], unique=False)

    op.create_table(
        "search_query_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("result_count >= 0", name="ck_search_result_count"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_search_latency"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_query_events_query_hash", "search_query_events", ["query_hash"], unique=False)
    op.create_index("ix_search_query_events_created_at", "search_query_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_search_query_events_created_at", table_name="search_query_events")
    op.drop_index("ix_search_query_events_query_hash", table_name="search_query_events")
    op.drop_table("search_query_events")
    op.drop_index("ix_claims_content_id", table_name="claims")
    op.drop_table("claims")
    op.drop_table("content_sources")
    op.drop_table("sources")
    op.drop_index("ix_content_items_status_indexed", table_name="content_items")
    op.drop_index("ix_content_items_section", table_name="content_items")
    op.drop_table("content_items")

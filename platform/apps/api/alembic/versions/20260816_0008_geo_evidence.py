"""add GEO query and immutable evidence tables

Revision ID: 20260816_0008
Revises: 20260816_0007
"""

from alembic import op
import sqlalchemy as sa

revision = "20260816_0008"
down_revision = "20260816_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geo_query_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "slug", name="uq_geo_query_sets_project_slug"),
    )
    op.create_index("ix_geo_query_sets_organization_id", "geo_query_sets", ["organization_id"])
    op.create_index("ix_geo_query_sets_project_id", "geo_query_sets", ["project_id"])

    op.create_table(
        "geo_queries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_set_id", sa.String(36), sa.ForeignKey("geo_query_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("language IN ('ar','en','tr')", name="ck_geo_query_language"),
    )
    op.create_index("ix_geo_queries_organization_id", "geo_queries", ["organization_id"])
    op.create_index("ix_geo_queries_project_id", "geo_queries", ["project_id"])
    op.create_index("ix_geo_queries_query_set_id", "geo_queries", ["query_set_id"])
    op.create_index("ix_geo_queries_set_active", "geo_queries", ["query_set_id", "is_active"])

    op.create_table(
        "geo_provider_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("geo_queries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_response_sha256", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_geo_provider_run_status"),
    )
    op.create_index("ix_geo_provider_runs_organization_id", "geo_provider_runs", ["organization_id"])
    op.create_index("ix_geo_provider_runs_project_id", "geo_provider_runs", ["project_id"])
    op.create_index("ix_geo_provider_runs_query_id", "geo_provider_runs", ["query_id"])
    op.create_index("ix_geo_runs_project_created", "geo_provider_runs", ["project_id", "created_at"])

    op.create_table(
        "geo_evidence_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("geo_provider_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "content_sha256", name="uq_geo_evidence_run_hash"),
    )
    op.create_index("ix_geo_evidence_snapshots_organization_id", "geo_evidence_snapshots", ["organization_id"])
    op.create_index("ix_geo_evidence_snapshots_project_id", "geo_evidence_snapshots", ["project_id"])
    op.create_index("ix_geo_evidence_snapshots_run_id", "geo_evidence_snapshots", ["run_id"])

    op.create_table(
        "geo_mentions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("geo_provider_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_key", sa.String(180), nullable=False),
        sa.Column("display_text", sa.String(300), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_geo_mentions_organization_id", "geo_mentions", ["organization_id"])
    op.create_index("ix_geo_mentions_project_id", "geo_mentions", ["project_id"])
    op.create_index("ix_geo_mentions_run_id", "geo_mentions", ["run_id"])
    op.create_index("ix_geo_mentions_run_entity", "geo_mentions", ["run_id", "entity_key"])

    op.create_table(
        "geo_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("geo_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("geo_provider_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("evidence_snapshot_id", sa.String(36), sa.ForeignKey("geo_evidence_snapshots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_geo_citations_organization_id", "geo_citations", ["organization_id"])
    op.create_index("ix_geo_citations_project_id", "geo_citations", ["project_id"])
    op.create_index("ix_geo_citations_run_id", "geo_citations", ["run_id"])
    op.create_index("ix_geo_citations_run_position", "geo_citations", ["run_id", "position"])


def downgrade() -> None:
    op.drop_table("geo_citations")
    op.drop_table("geo_mentions")
    op.drop_table("geo_evidence_snapshots")
    op.drop_table("geo_provider_runs")
    op.drop_table("geo_queries")
    op.drop_table("geo_query_sets")

"""Add editorial concurrency/provenance controls and PostgreSQL search index.

Revision ID: 20260807_0003
Revises: 20260805_0002
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0003"
down_revision: str | None = "20260805_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ARABIC_TRANSLATE_FROM = (
    "إأآٱىؤئـ"
    + "".join(chr(codepoint) for codepoint in range(0x0610, 0x061B))
    + "".join(chr(codepoint) for codepoint in range(0x064B, 0x0660))
    + "\u0670"
    + "".join(chr(codepoint) for codepoint in range(0x06D6, 0x06EE))
)
_ARABIC_TRANSLATE_TO = "اااايوي"


def upgrade() -> None:
    with op.batch_alter_table("content_items") as batch:
        batch.add_column(sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("last_modified_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("published_by_user_id", sa.String(length=36), nullable=True))
        batch.create_check_constraint("ck_content_revision", "revision >= 1")
        batch.create_foreign_key("fk_content_created_by", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_content_last_modified_by", "users", ["last_modified_by_user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_content_reviewed_by", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_content_published_by", "users", ["published_by_user_id"], ["id"], ondelete="SET NULL")

    with op.batch_alter_table("claims") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_claim_created_by", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_claim_reviewed_by", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            f"""
            CREATE INDEX IF NOT EXISTS ix_content_items_search_fts
            ON content_items USING GIN (
              to_tsvector(
                'simple',
                translate(
                  lower(coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(body, '') || ' ' || coalesce(section, '')),
                  '{_ARABIC_TRANSLATE_FROM}',
                  '{_ARABIC_TRANSLATE_TO}'
                )
              )
            )
            WHERE status = 'published' AND is_indexed = true
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_content_items_search_fts")

    with op.batch_alter_table("claims") as batch:
        batch.drop_constraint("fk_claim_reviewed_by", type_="foreignkey")
        batch.drop_constraint("fk_claim_created_by", type_="foreignkey")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("created_by_user_id")

    with op.batch_alter_table("content_items") as batch:
        batch.drop_constraint("fk_content_published_by", type_="foreignkey")
        batch.drop_constraint("fk_content_reviewed_by", type_="foreignkey")
        batch.drop_constraint("fk_content_last_modified_by", type_="foreignkey")
        batch.drop_constraint("fk_content_created_by", type_="foreignkey")
        batch.drop_constraint("ck_content_revision", type_="check")
        batch.drop_column("published_by_user_id")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("last_modified_by_user_id")
        batch.drop_column("created_by_user_id")
        batch.drop_column("revision")

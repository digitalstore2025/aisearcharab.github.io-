"""Add privacy-preserving distributed login throttling.

Revision ID: 20260816_0006
Revises: 20260808_0005
Create Date: 2026-08-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0006"
down_revision: str | None = "20260808_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("failure_count >= 0", name="ck_login_throttle_failure_count"),
        sa.PrimaryKeyConstraint("key_hash"),
    )
    op.create_index("ix_login_throttles_updated_at", "login_throttles", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_throttles_updated_at", table_name="login_throttles")
    op.drop_table("login_throttles")

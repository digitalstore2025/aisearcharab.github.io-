"""Add short-lived step-up authentication assurance to admin sessions.

Revision ID: 20260807_0004
Revises: 20260807_0003
Create Date: 2026-08-07
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0004"
down_revision: str | None = "20260807_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admin_sessions") as batch:
        batch.add_column(sa.Column("elevated_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("admin_sessions") as batch:
        batch.drop_column("elevated_until")

"""Add encrypted TOTP MFA state, recovery codes and session verification.

Revision ID: 20260808_0005
Revises: 20260807_0004
Create Date: 2026-08-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0005"
down_revision: str | None = "20260807_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("mfa_pending_secret_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("mfa_pending_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("mfa_enabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("mfa_last_counter", sa.Integer(), nullable=False, server_default=sa.text("-1")))

    with op.batch_alter_table("admin_sessions") as batch:
        batch.add_column(sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mfa_recovery_codes_code_hash", "mfa_recovery_codes", ["code_hash"], unique=True)
    op.create_index("ix_mfa_recovery_codes_user_unused", "mfa_recovery_codes", ["user_id", "used_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mfa_recovery_codes_user_unused", table_name="mfa_recovery_codes")
    op.drop_index("ix_mfa_recovery_codes_code_hash", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")

    with op.batch_alter_table("admin_sessions") as batch:
        batch.drop_column("mfa_verified_at")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_last_counter")
        batch.drop_column("mfa_enabled_at")
        batch.drop_column("mfa_pending_expires_at")
        batch.drop_column("mfa_pending_secret_encrypted")
        batch.drop_column("mfa_secret_encrypted")

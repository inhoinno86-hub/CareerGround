"""Add explicitly scoped, expiring profiling workspace tables.

Revision ID: 20260927_0003
Revises: 20260927_0002
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0003"
down_revision = "20260927_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_career_profile_owner_pair", "career_profiles", ["id", "account_id"]
    )
    op.create_table(
        "profiling_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", name="uq_profiling_session_owner_pair"),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profiling_session_owned_profile",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'EXPIRED', 'DELETING', 'ERASED')",
            name="ck_profiling_sessions_status",
        ),
        sa.CheckConstraint("base_profile_version >= 0", name="ck_profiling_sessions_base_version"),
        sa.CheckConstraint(
            "retention_expires_at > last_activity_at", name="ck_profiling_sessions_retention"
        ),
    )
    op.create_index("ix_profiling_sessions_account_id", "profiling_sessions", ["account_id"])
    op.create_table(
        "profiling_inputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("content_kind", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_input_owned_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_profiling_input_idempotency"),
        sa.CheckConstraint(
            "content_kind IN ('USER_STATEMENT', 'SELECTED_CHAT_EXCERPT', "
            "'PASTED_DOCUMENT_EXCERPT', 'CORRECTION')",
            name="ck_profiling_inputs_kind",
        ),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 20000", name="ck_profiling_inputs_body_size"
        ),
    )
    op.create_index("ix_profiling_inputs_account_id", "profiling_inputs", ["account_id"])
    op.create_index("ix_profiling_inputs_session_id", "profiling_inputs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_profiling_inputs_session_id", table_name="profiling_inputs")
    op.drop_index("ix_profiling_inputs_account_id", table_name="profiling_inputs")
    op.drop_table("profiling_inputs")
    op.drop_index("ix_profiling_sessions_account_id", table_name="profiling_sessions")
    op.drop_table("profiling_sessions")
    op.drop_constraint("uq_career_profile_owner_pair", "career_profiles", type_="unique")

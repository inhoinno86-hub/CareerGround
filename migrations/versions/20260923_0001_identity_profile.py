"""Create the first account, verified identity and profile-owner tables.

Revision ID: 20260923_0001
Revises:
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_accounts_status"),
    )
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_auth_identity_issuer_subject"),
    )
    op.create_index("ix_auth_identities_account_id", "auth_identities", ["account_id"])
    op.create_table(
        "career_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", name="uq_career_profiles_account_id"),
        sa.CheckConstraint("version >= 0", name="ck_career_profiles_version"),
    )
    op.create_index("ix_career_profiles_account_id", "career_profiles", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_career_profiles_account_id", table_name="career_profiles")
    op.drop_table("career_profiles")
    op.drop_index("ix_auth_identities_account_id", table_name="auth_identities")
    op.drop_table("auth_identities")
    op.drop_table("accounts")

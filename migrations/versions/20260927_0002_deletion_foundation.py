"""Reserve deletion states and restricted request/work-item tracking.

Revision ID: 20260927_0002
Revises: 20260923_0001
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0002"
down_revision = "20260923_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_accounts_status", "accounts", type_="check")
    op.create_check_constraint(
        "ck_accounts_status",
        "accounts",
        "status IN ('ACTIVE', 'DISABLED', 'DELETING', 'ERASED')",
    )
    op.add_column(
        "career_profiles",
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
    )
    op.create_check_constraint(
        "ck_career_profiles_status",
        "career_profiles",
        "status IN ('ACTIVE', 'DELETING', 'ERASED')",
    )
    op.create_table(
        "deletion_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("impact_digest", sa.String(96), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('ACCOUNT', 'PROFILE')", name="ck_deletion_requests_scope"),
        sa.CheckConstraint(
            "status IN ('DELETING', 'ERASED', 'FAILED')", name="ck_deletion_requests_status"
        ),
    )
    op.create_index("ix_deletion_requests_account_id", "deletion_requests", ["account_id"])
    op.create_table(
        "deletion_work_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(36),
            sa.ForeignKey("deletion_requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(512), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint(
            "request_id", "kind", "target_id", "action", name="uq_deletion_work_item_target"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'DONE', 'FAILED')", name="ck_deletion_work_items_status"
        ),
    )
    op.create_index("ix_deletion_work_items_request_id", "deletion_work_items", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_deletion_work_items_request_id", table_name="deletion_work_items")
    op.drop_table("deletion_work_items")
    op.drop_index("ix_deletion_requests_account_id", table_name="deletion_requests")
    op.drop_table("deletion_requests")
    op.drop_constraint("ck_career_profiles_status", "career_profiles", type_="check")
    op.drop_column("career_profiles", "status")
    op.drop_constraint("ck_accounts_status", "accounts", type_="check")
    op.create_check_constraint("ck_accounts_status", "accounts", "status IN ('ACTIVE', 'DISABLED')")

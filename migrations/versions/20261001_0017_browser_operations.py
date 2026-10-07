"""Expiring browser-confirmed operation metadata for a local MCP connection."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0017"
down_revision = "20260930_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "browser_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("connection_key", sa.String(64), nullable=False),
        sa.Column("client_id", sa.String(128), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("browser_key", sa.String(64)),
        sa.Column("confirmation_key", sa.String(64)),
        sa.Column("result_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_browser_operation_owned_profile",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("request_key", name="uq_browser_operation_request"),
        sa.CheckConstraint(
            "action IN ('FACT_REVIEW', 'WORDING_REVIEW', 'PROFILE_EXPORT', 'RESUME_EXPORT')",
            name="ck_browser_operation_action",
        ),
        sa.CheckConstraint(
            "status IN ('WAITING', 'DONE', 'CONSUMED')", name="ck_browser_operation_status"
        ),
        sa.CheckConstraint("profile_version >= 0", name="ck_browser_operation_version"),
        sa.CheckConstraint("expires_at > created_at", name="ck_browser_operation_expiry"),
        sa.CheckConstraint(
            "format IN ('NONE', 'JSON', 'MARKDOWN')", name="ck_browser_operation_format"
        ),
        sa.CheckConstraint(
            "(status = 'WAITING' AND browser_key IS NULL AND confirmation_key IS NULL AND result_json IS NULL) OR (status IN ('DONE', 'CONSUMED') AND browser_key IS NOT NULL AND confirmation_key IS NOT NULL AND result_json IS NOT NULL)",
            name="ck_browser_operation_completion",
        ),
    )
    for column in ("account_id", "profile_id", "expires_at"):
        op.create_index("ix_browser_operations_" + column, "browser_operations", [column])


def downgrade() -> None:
    op.drop_table("browser_operations")

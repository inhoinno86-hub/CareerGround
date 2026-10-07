"""Shared short-lived request counters without raw account or source data."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_0016"
down_revision = "20260929_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_limit_buckets",
        sa.Column("bucket_key", sa.String(64), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("requests >= 1", name="ck_request_limit_requests"),
        sa.CheckConstraint("window_start >= 0", name="ck_request_limit_window"),
        sa.CheckConstraint("expires_at > window_start", name="ck_request_limit_expiry"),
        sa.PrimaryKeyConstraint("bucket_key", "window_start"),
    )
    op.create_index("ix_request_limit_buckets_expires_at", "request_limit_buckets", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_request_limit_buckets_expires_at", table_name="request_limit_buckets")
    op.drop_table("request_limit_buckets")

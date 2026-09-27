"""Reference-only transactional outbox and idempotent handler receipts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0004"
down_revision = "20260927_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("handler_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("handler_id", name="uq_outbox_handler_id"),
        sa.CheckConstraint(
            "event_type IN ('RETENTION_SWEEP', 'DELETION_WORK')", name="ck_outbox_event_type"
        ),
        sa.CheckConstraint("status IN ('PENDING', 'DONE', 'DEAD')", name="ck_outbox_status"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 5", name="ck_outbox_attempts"),
    )
    op.create_index("ix_outbox_pending", "outbox_events", ["status", "next_attempt_at", "id"])
    op.create_table(
        "outbox_receipts",
        sa.Column("handler_id", sa.String(128), primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outbox_receipts")
    op.drop_index("ix_outbox_pending", table_name="outbox_events")
    op.drop_table("outbox_events")

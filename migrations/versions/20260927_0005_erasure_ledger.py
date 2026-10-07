"""Independent minimal erasure deny list for restore quarantine."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0005"
down_revision = "20260927_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erasure_ledger",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.CheckConstraint("scope IN ('ACCOUNT', 'PROFILE')", name="ck_erasure_ledger_scope"),
    )
    op.create_index("ix_erasure_ledger_account_id", "erasure_ledger", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_erasure_ledger_account_id", table_name="erasure_ledger")
    op.drop_table("erasure_ledger")

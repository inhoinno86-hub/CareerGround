"""Separate positive Claim use review from fact confirmation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260929_0015"
down_revision = "20260927_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim_use_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("consistency_attested", sa.Boolean(), nullable=False),
        sa.Column("use_authorized", sa.Boolean(), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_use_review_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "profile_version = base_profile_version + 1", name="ck_use_review_version"
        ),
        sa.CheckConstraint(
            "consistency_attested = true AND use_authorized = true",
            name="ck_use_review_explicit_choices",
        ),
    )
    op.create_index("ix_claim_use_reviews_account_id", "claim_use_reviews", ["account_id"])
    op.create_index("ix_claim_use_reviews_profile_id", "claim_use_reviews", ["profile_id"])


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT 1 FROM claim_use_reviews LIMIT 1")):
        raise RuntimeError("cannot downgrade while Claim use reviews exist")
    op.drop_index("ix_claim_use_reviews_profile_id", table_name="claim_use_reviews")
    op.drop_index("ix_claim_use_reviews_account_id", table_name="claim_use_reviews")
    op.drop_table("claim_use_reviews")

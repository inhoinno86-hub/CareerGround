"""Reserve reviewed R1 resume wording and exact artifact review journal."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0012"
down_revision = "20260927_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_artifact_status", "artifacts", type_="check")
    op.create_check_constraint(
        "ck_artifact_status",
        "artifacts",
        "status IN ('DRAFT', 'REVIEW_REQUIRED', 'WORDING_REVIEWED', 'UNAVAILABLE_DUE_TO_ERASURE')",
    )
    op.drop_constraint("ck_artifact_unit_review", "artifact_units", type_="check")
    op.create_check_constraint(
        "ck_artifact_unit_review",
        "artifact_units",
        "review_status IN ('DRAFT', 'REVIEW_REQUIRED', 'WORDING_REVIEWED')",
    )
    op.create_table(
        "artifact_wording_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id", "account_id", "profile_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.profile_id"],
            name="fk_wording_review_owned_artifact",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("artifact_id", name="uq_wording_review_artifact"),
        sa.CheckConstraint("action IN ('ACCEPT_R1')", name="ck_wording_review_action"),
        sa.CheckConstraint(
            "artifact_version >= 1 AND profile_version >= 0", name="ck_wording_review_versions"
        ),
    )
    op.create_index(
        "ix_artifact_wording_reviews_account_id", "artifact_wording_reviews", ["account_id"]
    )
    op.create_index(
        "ix_artifact_wording_reviews_profile_id", "artifact_wording_reviews", ["profile_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_wording_reviews_profile_id", table_name="artifact_wording_reviews")
    op.drop_index("ix_artifact_wording_reviews_account_id", table_name="artifact_wording_reviews")
    op.drop_table("artifact_wording_reviews")
    op.drop_constraint("ck_artifact_unit_review", "artifact_units", type_="check")
    op.create_check_constraint(
        "ck_artifact_unit_review",
        "artifact_units",
        "review_status IN ('DRAFT', 'REVIEW_REQUIRED')",
    )
    op.drop_constraint("ck_artifact_status", "artifacts", type_="check")
    op.create_check_constraint(
        "ck_artifact_status",
        "artifacts",
        "status IN ('DRAFT', 'REVIEW_REQUIRED', 'UNAVAILABLE_DUE_TO_ERASURE')",
    )

"""Record exact, owner-scoped use-boundary changes without silent publication."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0011"
down_revision = "20260927_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_evidence_claim_link_owner_scope",
        "evidence_claim_links",
        ["id", "account_id", "profile_id"],
    )
    op.add_column(
        "claim_constraints",
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
    )
    op.create_check_constraint(
        "ck_claim_constraint_status",
        "claim_constraints",
        "status IN ('ACTIVE', 'REVOKED')",
    )
    op.create_unique_constraint(
        "uq_claim_constraint_owner_scope",
        "claim_constraints",
        ["id", "account_id", "profile_id"],
    )
    op.create_table(
        "claim_boundary_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("constraint_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("allowed_wording", sa.Text(), nullable=False),
        sa.Column("remaining_prohibited_expansion", sa.Text(), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_boundary_review_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["constraint_id", "account_id", "profile_id"],
            [
                "claim_constraints.id",
                "claim_constraints.account_id",
                "claim_constraints.profile_id",
            ],
            name="fk_boundary_review_owned_constraint",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "account_id", "profile_id"],
            ["evidence_items.id", "evidence_items.account_id", "evidence_items.profile_id"],
            name="fk_boundary_review_owned_evidence",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("action IN ('ADD', 'REVOKE')", name="ck_boundary_review_action"),
        sa.CheckConstraint(
            "profile_version = base_profile_version + 1", name="ck_boundary_review_version"
        ),
        sa.CheckConstraint(
            "length(allowed_wording) BETWEEN 1 AND 20000", name="ck_boundary_allowed_wording"
        ),
        sa.CheckConstraint(
            "length(remaining_prohibited_expansion) BETWEEN 1 AND 20000",
            name="ck_boundary_remaining_prohibition",
        ),
    )
    op.create_index(
        "ix_claim_boundary_reviews_account_id", "claim_boundary_reviews", ["account_id"]
    )
    op.create_index(
        "ix_claim_boundary_reviews_profile_id", "claim_boundary_reviews", ["profile_id"]
    )
    op.create_table(
        "claim_conflict_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("conflict_link_id", sa.String(36), nullable=False),
        sa.Column("resolution", sa.String(24), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_conflict_review_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conflict_link_id", "account_id", "profile_id"],
            [
                "evidence_claim_links.id",
                "evidence_claim_links.account_id",
                "evidence_claim_links.profile_id",
            ],
            name="fk_conflict_review_owned_link",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "resolution IN ('KEEP_EXISTING', 'ACCEPT_CORRECTION', 'KEEP_BOTH_SCOPED', 'REMAIN_UNCERTAIN')",
            name="ck_conflict_review_resolution",
        ),
        sa.CheckConstraint(
            "profile_version = base_profile_version + 1", name="ck_conflict_review_version"
        ),
        sa.CheckConstraint(
            "length(explanation) BETWEEN 1 AND 20000", name="ck_conflict_explanation"
        ),
    )
    op.create_index(
        "ix_claim_conflict_reviews_account_id", "claim_conflict_reviews", ["account_id"]
    )
    op.create_index(
        "ix_claim_conflict_reviews_profile_id", "claim_conflict_reviews", ["profile_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_claim_conflict_reviews_profile_id", table_name="claim_conflict_reviews")
    op.drop_index("ix_claim_conflict_reviews_account_id", table_name="claim_conflict_reviews")
    op.drop_table("claim_conflict_reviews")
    op.drop_index("ix_claim_boundary_reviews_profile_id", table_name="claim_boundary_reviews")
    op.drop_index("ix_claim_boundary_reviews_account_id", table_name="claim_boundary_reviews")
    op.drop_table("claim_boundary_reviews")
    op.drop_constraint("uq_claim_constraint_owner_scope", "claim_constraints", type_="unique")
    op.drop_constraint("ck_claim_constraint_status", "claim_constraints", type_="check")
    op.drop_column("claim_constraints", "status")
    op.drop_constraint("uq_evidence_claim_link_owner_scope", "evidence_claim_links", type_="unique")

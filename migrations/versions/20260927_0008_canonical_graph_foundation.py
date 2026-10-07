"""Owner-scoped canonical Claim, Evidence and profile change history foundation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0008"
down_revision = "20260927_0007"
branch_labels = None
depends_on = None


def _profile_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["profile_id", "account_id"],
        ["career_profiles.id", "career_profiles.account_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _owner_indexes(table: str) -> None:
    op.create_index(f"ix_{table}_account_id", table, ["account_id"])
    op.create_index(f"ix_{table}_profile_id", table, ["profile_id"])


def upgrade() -> None:
    op.create_table(
        "profile_change_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("version_before", sa.Integer(), nullable=False),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("review_batch_id", sa.String(36), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _profile_fk("fk_profile_change_set_owned_profile"),
        sa.UniqueConstraint("profile_id", "version_after", name="uq_profile_change_set_version"),
        sa.UniqueConstraint("review_batch_id", name="uq_profile_change_set_review_batch"),
        sa.CheckConstraint("version_before >= 0", name="ck_profile_change_set_before"),
        sa.CheckConstraint("version_after = version_before + 1", name="ck_profile_change_set_step"),
    )
    _owner_indexes("profile_change_sets")
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False),
        sa.Column("canonical_text", sa.Text(), nullable=False),
        sa.Column("created_in_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_claim_owner_scope"),
        _profile_fk("fk_claim_owned_profile"),
        sa.CheckConstraint("length(canonical_text) BETWEEN 1 AND 20000", name="ck_claim_text"),
        sa.CheckConstraint("created_in_version >= 1", name="ck_claim_created_version"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ERASED')", name="ck_claim_status"),
    )
    _owner_indexes("claims")
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(36), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_in_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "id", "account_id", "profile_id", name="uq_evidence_source_owner_scope"
        ),
        _profile_fk("fk_evidence_source_owned_profile"),
        sa.CheckConstraint(
            "source_type IN ('EXPLICIT_PROFILING_INPUT')", name="ck_evidence_source_type"
        ),
    )
    _owner_indexes("evidence_sources")
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_in_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_evidence_item_owner_scope"),
        sa.ForeignKeyConstraint(
            ["source_id", "account_id", "profile_id"],
            ["evidence_sources.id", "evidence_sources.account_id", "evidence_sources.profile_id"],
            name="fk_evidence_item_owned_source",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "length(content_text) BETWEEN 1 AND 20000", name="ck_evidence_item_text"
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'ERASED')", name="ck_evidence_item_status"),
    )
    _owner_indexes("evidence_items")
    op.create_table(
        "evidence_claim_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("relation_type", sa.String(16), nullable=False),
        sa.Column("created_in_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id", "account_id", "profile_id"],
            ["evidence_items.id", "evidence_items.account_id", "evidence_items.profile_id"],
            name="fk_evidence_claim_link_owned_evidence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_evidence_claim_link_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "evidence_id", "claim_id", "relation_type", name="uq_evidence_claim_link"
        ),
        sa.CheckConstraint(
            "relation_type IN ('SUPPORTS', 'CONTRADICTS', 'QUALIFIES', 'CONTEXTUALIZES')",
            name="ck_evidence_claim_link_relation",
        ),
    )
    _owner_indexes("evidence_claim_links")
    op.create_table(
        "claim_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("knowledge_status", sa.String(24), nullable=False),
        sa.Column("consistency_status", sa.String(24), nullable=False),
        sa.Column("usage_policy", sa.String(24), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_claim_assessment_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "knowledge_status IN ('USER_CONFIRMED', 'USER_CLAIMED', 'INFERRED', 'UNKNOWN')",
            name="ck_claim_assessment_knowledge",
        ),
        sa.CheckConstraint(
            "consistency_status IN ('CONSISTENT', 'CONTRADICTED', 'DISPUTED', 'NOT_EVALUATED')",
            name="ck_claim_assessment_consistency",
        ),
        sa.CheckConstraint(
            "usage_policy IN ('ALLOWED', 'REVIEW_REQUIRED', 'DO_NOT_CLAIM')",
            name="ck_claim_assessment_usage",
        ),
    )
    _owner_indexes("claim_assessments")
    op.create_table(
        "claim_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("review_batch_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(36), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("review_purpose", sa.String(24), nullable=False),
        sa.Column("review_action", sa.String(16), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_claim_review_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "review_purpose IN ('FACT_CONFIRMATION')", name="ck_claim_review_purpose"
        ),
        sa.CheckConstraint("review_action IN ('ACCEPT')", name="ck_claim_review_action"),
    )
    _owner_indexes("claim_reviews")
    op.create_table(
        "claim_constraints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("constraint_type", sa.String(16), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("review_batch_id", sa.String(36), nullable=False),
        sa.Column("review_item_id", sa.String(36), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("created_in_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _profile_fk("fk_claim_constraint_owned_profile"),
        sa.CheckConstraint(
            "constraint_type IN ('NOT_TRUE', 'DO_NOT_USE')", name="ck_claim_constraint_type"
        ),
        sa.CheckConstraint(
            "length(exact_text) BETWEEN 1 AND 20000", name="ck_claim_constraint_text"
        ),
    )
    _owner_indexes("claim_constraints")


def downgrade() -> None:
    for table in (
        "claim_constraints",
        "claim_reviews",
        "claim_assessments",
        "evidence_claim_links",
        "evidence_items",
        "evidence_sources",
        "claims",
        "profile_change_sets",
    ):
        op.drop_index(f"ix_{table}_profile_id", table_name=table)
        op.drop_index(f"ix_{table}_account_id", table_name=table)
        op.drop_table(table)

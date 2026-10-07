"""Temporary atomic drafts and exact bounded review snapshots."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0007"
down_revision = "20260927_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_profiling_input_owner_pair", "profiling_inputs", ["id", "account_id"]
    )
    op.create_unique_constraint(
        "uq_profiling_input_scope_pair", "profiling_inputs", ["id", "account_id", "session_id"]
    )
    op.create_table(
        "profiling_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("source_input_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("source_content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", name="uq_profiling_draft_owner_pair"),
        sa.UniqueConstraint(
            "id", "account_id", "session_id", "scope_key", name="uq_profiling_draft_scope_pair"
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_draft_owned_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_input_id", "account_id", "session_id"],
            ["profiling_inputs.id", "profiling_inputs.account_id", "profiling_inputs.session_id"],
            name="fk_profiling_draft_owned_input",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'EDIT_REQUIRED', 'EXCLUDED', 'PROMOTED')",
            name="ck_profiling_drafts_status",
        ),
        sa.CheckConstraint(
            "length(exact_text) BETWEEN 1 AND 20000", name="ck_profiling_drafts_text"
        ),
    )
    op.create_index("ix_profiling_drafts_account_id", "profiling_drafts", ["account_id"])
    op.create_index("ix_profiling_drafts_session_id", "profiling_drafts", ["session_id"])
    op.create_table(
        "profiling_review_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("base_profile_version", sa.Integer(), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "account_id", name="uq_profiling_review_batch_owner_pair"),
        sa.UniqueConstraint(
            "id",
            "account_id",
            "session_id",
            "scope_key",
            name="uq_profiling_review_batch_scope_pair",
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_review_batch_owned_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profiling_review_batch_owned_profile",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('PREPARED', 'SUBMITTED', 'EXPIRED')",
            name="ck_profiling_review_batches_status",
        ),
        sa.CheckConstraint("base_profile_version >= 0", name="ck_profiling_review_batches_version"),
        sa.CheckConstraint("expires_at > created_at", name="ck_profiling_review_batches_expiry"),
    )
    op.create_index(
        "ix_profiling_review_batches_account_id", "profiling_review_batches", ["account_id"]
    )
    op.create_index(
        "ix_profiling_review_batches_session_id", "profiling_review_batches", ["session_id"]
    )
    op.create_table(
        "profiling_review_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("source_input_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("source_content_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(24)),
        sa.ForeignKeyConstraint(
            ["batch_id", "account_id", "session_id", "scope_key"],
            [
                "profiling_review_batches.id",
                "profiling_review_batches.account_id",
                "profiling_review_batches.session_id",
                "profiling_review_batches.scope_key",
            ],
            name="fk_profiling_review_item_owned_batch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "account_id", "session_id", "scope_key"],
            [
                "profiling_drafts.id",
                "profiling_drafts.account_id",
                "profiling_drafts.session_id",
                "profiling_drafts.scope_key",
            ],
            name="fk_profiling_review_item_owned_draft",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("batch_id", "position", name="uq_profiling_review_item_position"),
        sa.UniqueConstraint("batch_id", "draft_id", name="uq_profiling_review_item_draft"),
        sa.CheckConstraint("position BETWEEN 1 AND 5", name="ck_profiling_review_items_position"),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('ACCEPT', 'EDIT', 'FOLLOW_UP', "
            "'EXCLUDE_NOT_TRUE', 'EXCLUDE_DO_NOT_USE')",
            name="ck_profiling_review_items_decision",
        ),
    )
    op.create_index(
        "ix_profiling_review_items_account_id", "profiling_review_items", ["account_id"]
    )
    op.create_index("ix_profiling_review_items_batch_id", "profiling_review_items", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_profiling_review_items_batch_id", table_name="profiling_review_items")
    op.drop_index("ix_profiling_review_items_account_id", table_name="profiling_review_items")
    op.drop_table("profiling_review_items")
    op.drop_index("ix_profiling_review_batches_session_id", table_name="profiling_review_batches")
    op.drop_index("ix_profiling_review_batches_account_id", table_name="profiling_review_batches")
    op.drop_table("profiling_review_batches")
    op.drop_index("ix_profiling_drafts_session_id", table_name="profiling_drafts")
    op.drop_index("ix_profiling_drafts_account_id", table_name="profiling_drafts")
    op.drop_table("profiling_drafts")
    op.drop_constraint("uq_profiling_input_owner_pair", "profiling_inputs", type_="unique")
    op.drop_constraint("uq_profiling_input_scope_pair", "profiling_inputs", type_="unique")

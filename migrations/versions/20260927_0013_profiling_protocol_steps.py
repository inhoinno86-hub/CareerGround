"""Persist temporary question delivery and source-linked protocol observations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0013"
down_revision = "20260927_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiling_protocol_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("asked_count", sa.Integer(), nullable=False),
        sa.Column("first_delivery_key", sa.String(128)),
        sa.Column("second_delivery_key", sa.String(128)),
        sa.Column("observation_status", sa.String(16)),
        sa.Column("source_input_id", sa.String(36)),
        sa.Column("reason", sa.String(1000)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "state", name="uq_profiling_protocol_step_state"),
        sa.ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_protocol_step_owned_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_input_id", "account_id", "session_id"],
            ["profiling_inputs.id", "profiling_inputs.account_id", "profiling_inputs.session_id"],
            name="fk_profiling_protocol_step_owned_input",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "state IN ('CONTEXT_DISCOVERY', 'ROLE_DISCOVERY', 'PROJECT_DISCOVERY', "
            "'RESPONSIBILITY_DISCOVERY', 'CONTRIBUTION_DISCOVERY', 'OWNERSHIP_PROBING', "
            "'TECHNICAL_DEPTH_PROBING', 'VALIDATION_PROBING', 'OUTCOME_PROBING', "
            "'EVIDENCE_CAPTURE', 'CLAIM_DRAFTING', 'CLAIM_CONFIRMATION', 'BOUNDARY_CHECK')",
            name="ck_profiling_protocol_step_state",
        ),
        sa.CheckConstraint("asked_count BETWEEN 0 AND 2", name="ck_profiling_protocol_step_count"),
        sa.CheckConstraint(
            "observation_status IS NULL OR observation_status IN "
            "('SATISFIED', 'UNKNOWN', 'CONFLICT')",
            name="ck_profiling_protocol_step_observation",
        ),
        sa.CheckConstraint(
            "(asked_count = 0 AND first_delivery_key IS NULL AND second_delivery_key IS NULL) "
            "OR (asked_count = 1 AND first_delivery_key IS NOT NULL "
            "AND second_delivery_key IS NULL) OR (asked_count = 2 "
            "AND first_delivery_key IS NOT NULL AND second_delivery_key IS NOT NULL)",
            name="ck_profiling_protocol_step_delivery",
        ),
        sa.CheckConstraint(
            "observation_status IS NULL OR observation_status = 'UNKNOWN' "
            "OR source_input_id IS NOT NULL",
            name="ck_profiling_protocol_step_source",
        ),
        sa.CheckConstraint(
            "observation_status NOT IN ('UNKNOWN', 'CONFLICT') OR "
            "(reason IS NOT NULL AND length(reason) BETWEEN 1 AND 1000)",
            name="ck_profiling_protocol_step_reason",
        ),
    )
    op.create_index(
        "ix_profiling_protocol_steps_account_id", "profiling_protocol_steps", ["account_id"]
    )
    op.create_index(
        "ix_profiling_protocol_steps_session_id", "profiling_protocol_steps", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_profiling_protocol_steps_session_id", table_name="profiling_protocol_steps")
    op.drop_index("ix_profiling_protocol_steps_account_id", table_name="profiling_protocol_steps")
    op.drop_table("profiling_protocol_steps")

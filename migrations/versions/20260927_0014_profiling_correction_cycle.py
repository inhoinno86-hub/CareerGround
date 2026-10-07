"""Separate protocol questions and sources after an explicit correction."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0014"
down_revision = "20260927_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiling_sessions",
        sa.Column("protocol_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_profiling_sessions_cycle", "profiling_sessions", "protocol_cycle >= 0"
    )
    op.add_column(
        "profiling_inputs",
        sa.Column("protocol_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_profiling_inputs_cycle", "profiling_inputs", "protocol_cycle >= 0"
    )
    op.create_unique_constraint(
        "uq_profiling_input_cycle_pair",
        "profiling_inputs",
        ["id", "account_id", "session_id", "protocol_cycle"],
    )
    op.drop_constraint(
        "fk_profiling_protocol_step_owned_input", "profiling_protocol_steps", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_profiling_protocol_step_state", "profiling_protocol_steps", type_="unique"
    )
    op.add_column(
        "profiling_protocol_steps",
        sa.Column("protocol_cycle", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_profiling_protocol_step_cycle", "profiling_protocol_steps", "protocol_cycle >= 0"
    )
    op.create_unique_constraint(
        "uq_profiling_protocol_step_state",
        "profiling_protocol_steps",
        ["session_id", "protocol_cycle", "state"],
    )
    op.create_foreign_key(
        "fk_profiling_protocol_step_owned_input",
        "profiling_protocol_steps",
        "profiling_inputs",
        ["source_input_id", "account_id", "session_id", "protocol_cycle"],
        ["id", "account_id", "session_id", "protocol_cycle"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT 1 FROM profiling_sessions WHERE protocol_cycle <> 0 LIMIT 1")
    ):
        raise RuntimeError("cannot downgrade while corrected profiling sessions exist")
    op.drop_constraint(
        "fk_profiling_protocol_step_owned_input", "profiling_protocol_steps", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_profiling_protocol_step_state", "profiling_protocol_steps", type_="unique"
    )
    op.drop_constraint(
        "ck_profiling_protocol_step_cycle", "profiling_protocol_steps", type_="check"
    )
    op.drop_column("profiling_protocol_steps", "protocol_cycle")
    op.create_unique_constraint(
        "uq_profiling_protocol_step_state", "profiling_protocol_steps", ["session_id", "state"]
    )
    op.create_foreign_key(
        "fk_profiling_protocol_step_owned_input",
        "profiling_protocol_steps",
        "profiling_inputs",
        ["source_input_id", "account_id", "session_id"],
        ["id", "account_id", "session_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("uq_profiling_input_cycle_pair", "profiling_inputs", type_="unique")
    op.drop_constraint("ck_profiling_inputs_cycle", "profiling_inputs", type_="check")
    op.drop_column("profiling_inputs", "protocol_cycle")
    op.drop_constraint("ck_profiling_sessions_cycle", "profiling_sessions", type_="check")
    op.drop_column("profiling_sessions", "protocol_cycle")

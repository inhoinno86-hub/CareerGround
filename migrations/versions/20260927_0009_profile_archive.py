"""Store owner-scoped canonical snapshots by exact profile version."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0009"
down_revision = "20260927_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_archives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profile_archive_owned_profile",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("profile_id", "profile_version", name="uq_profile_archive_version"),
        sa.CheckConstraint("profile_version >= 0", name="ck_profile_archive_version"),
        sa.CheckConstraint("length(snapshot_json) > 0", name="ck_profile_archive_content"),
    )
    op.create_index("ix_profile_archives_account_id", "profile_archives", ["account_id"])
    op.create_index("ix_profile_archives_profile_id", "profile_archives", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_profile_archives_profile_id", table_name="profile_archives")
    op.drop_index("ix_profile_archives_account_id", table_name="profile_archives")
    op.drop_table("profile_archives")

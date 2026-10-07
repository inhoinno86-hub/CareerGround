"""Private object and per-provider-version metadata for synthetic lifecycle work."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0006"
down_revision = "20260927_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_outbox_event_type", "outbox_events", type_="check")
    op.create_check_constraint(
        "ck_outbox_event_type",
        "outbox_events",
        "event_type IN ('RETENTION_SWEEP', 'DELETION_WORK', 'PRIVATE_OBJECT_DELETE')",
    )
    op.create_table(
        "private_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("object_class", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("retention_anchor_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", name="uq_private_object_owner_pair"),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_private_object_owned_profile",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "object_class IN ('UPLOAD_ORIGINAL', 'OPTIONAL_RECORDING')",
            name="ck_private_objects_class",
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'DELETING')", name="ck_private_objects_status"),
        sa.CheckConstraint(
            "retention_expires_at > retention_anchor_at", name="ck_private_objects_retention"
        ),
    )
    op.create_index("ix_private_objects_account_id", "private_objects", ["account_id"])
    op.create_index("ix_private_objects_profile_id", "private_objects", ["profile_id"])
    op.create_table(
        "private_object_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("provider_version_id", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id", "account_id"],
            ["private_objects.id", "private_objects.account_id"],
            name="fk_private_object_version_owned_object",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "object_id", "provider_version_id", name="uq_private_object_provider_version"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'DELETE_PENDING', 'DELETED')",
            name="ck_private_object_versions_status",
        ),
    )
    op.create_index(
        "ix_private_object_versions_object_id", "private_object_versions", ["object_id"]
    )
    op.create_index(
        "ix_private_object_versions_account_id", "private_object_versions", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_private_object_versions_account_id", table_name="private_object_versions")
    op.drop_index("ix_private_object_versions_object_id", table_name="private_object_versions")
    op.drop_table("private_object_versions")
    op.drop_index("ix_private_objects_profile_id", table_name="private_objects")
    op.drop_index("ix_private_objects_account_id", table_name="private_objects")
    op.drop_table("private_objects")
    op.drop_constraint("ck_outbox_event_type", "outbox_events", type_="check")
    op.create_check_constraint(
        "ck_outbox_event_type",
        "outbox_events",
        "event_type IN ('RETENTION_SWEEP', 'DELETION_WORK')",
    )

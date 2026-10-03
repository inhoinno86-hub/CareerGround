"""Explicit export choices, R2 lineage, and scoped partial erasure metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_0020"
down_revision = "20261001_0019"
branch_labels = None
depends_on = None

OLD_SCOPES = "scope IN ('ACCOUNT', 'PROFILE')"
NEW_SCOPES = "scope IN ('ACCOUNT', 'PROFILE', 'SESSION', 'EVIDENCE', 'PROJECT')"


def _scope(table, constraint, expression):
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(constraint, type_="check")
        batch.create_check_constraint(constraint, expression)


def upgrade():
    op.add_column("browser_operations", sa.Column("export_options_json", sa.Text()))
    op.add_column("erasure_ledger", sa.Column("profile_id", sa.String(36)))
    op.add_column("erasure_ledger", sa.Column("profile_version_after", sa.Integer()))
    _scope("deletion_requests", "ck_deletion_requests_scope", NEW_SCOPES)
    _scope("erasure_ledger", "ck_erasure_ledger_scope", NEW_SCOPES)
    with op.batch_alter_table("artifacts") as batch:
        batch.add_column(sa.Column("source_artifact_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_artifact_owned_source",
            "artifacts",
            ["source_artifact_id", "account_id", "profile_id"],
            ["id", "account_id", "profile_id"],
            ondelete="RESTRICT",
        )
    with op.batch_alter_table("artifact_units") as batch:
        batch.add_column(sa.Column("source_artifact_unit_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_artifact_unit_owned_source",
            "artifact_units",
            ["source_artifact_unit_id", "account_id", "profile_id"],
            ["id", "account_id", "profile_id"],
            ondelete="RESTRICT",
        )
    with op.batch_alter_table("artifact_wording_reviews") as batch:
        batch.drop_constraint("ck_wording_review_action", type_="check")
        batch.create_check_constraint(
            "ck_wording_review_action", "action IN ('ACCEPT_R1', 'ACCEPT_R2')"
        )
    op.create_table(
        "project_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_project_scope_owned_profile",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("account_id", "profile_id", "scope_key", name="uq_project_scope_key"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DELETING')", name="ck_project_scope_status"),
        sa.CheckConstraint("length(scope_key) BETWEEN 1 AND 64", name="ck_project_scope_key"),
    )
    op.create_index("ix_project_scopes_account_id", "project_scopes", ["account_id"])
    op.create_index("ix_project_scopes_profile_id", "project_scopes", ["profile_id"])


def downgrade():
    # Never silently discard newly stored choices, R2 provenance, or erasure
    # records. Rollback is permitted only for an unused migration.
    connection = op.get_bind()
    for query in (
        "SELECT 1 FROM browser_operations WHERE export_options_json IS NOT NULL LIMIT 1",
        "SELECT 1 FROM artifacts WHERE source_artifact_id IS NOT NULL LIMIT 1",
        "SELECT 1 FROM artifact_units WHERE source_artifact_unit_id IS NOT NULL LIMIT 1",
        "SELECT 1 FROM artifact_wording_reviews WHERE action='ACCEPT_R2' LIMIT 1",
        "SELECT 1 FROM deletion_requests WHERE scope NOT IN ('ACCOUNT','PROFILE') LIMIT 1",
        "SELECT 1 FROM erasure_ledger WHERE profile_id IS NOT NULL OR profile_version_after IS NOT NULL LIMIT 1",
        "SELECT 1 FROM project_scopes LIMIT 1",
    ):
        if connection.execute(sa.text(query)).first() is not None:
            raise RuntimeError("Local contract metadata must be retained; downgrade refused")
    op.drop_table("project_scopes")
    with op.batch_alter_table("artifact_wording_reviews") as batch:
        batch.drop_constraint("ck_wording_review_action", type_="check")
        batch.create_check_constraint("ck_wording_review_action", "action IN ('ACCEPT_R1')")
    with op.batch_alter_table("artifact_units") as batch:
        batch.drop_constraint("fk_artifact_unit_owned_source", type_="foreignkey")
        batch.drop_column("source_artifact_unit_id")
    with op.batch_alter_table("artifacts") as batch:
        batch.drop_constraint("fk_artifact_owned_source", type_="foreignkey")
        batch.drop_column("source_artifact_id")
    _scope("deletion_requests", "ck_deletion_requests_scope", OLD_SCOPES)
    _scope("erasure_ledger", "ck_erasure_ledger_scope", OLD_SCOPES)
    op.drop_column("erasure_ledger", "profile_version_after")
    op.drop_column("erasure_ledger", "profile_id")
    op.drop_column("browser_operations", "export_options_json")

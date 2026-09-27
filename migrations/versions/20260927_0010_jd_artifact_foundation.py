"""Owner-scoped JD excerpts and exact-version resume artifact metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260927_0010"
down_revision = "20260927_0009"
branch_labels = None
depends_on = None


def _owner_indexes(table: str, *, extras: tuple[str, ...] = ()) -> None:
    for column in ("account_id", "profile_id", *extras):
        op.create_index(f"ix_{table}_{column}", table, [column])


def _owned_profile(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["profile_id", "account_id"],
        ["career_profiles.id", "career_profiles.account_id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_claim_assessment_version", "claim_assessments", ["claim_id", "profile_version"]
    )
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("jd_version", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_length", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(200)),
        sa.Column("job_title", sa.String(200)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_jd_owner_scope"),
        sa.UniqueConstraint("profile_id", "jd_version", name="uq_jd_profile_version"),
        _owned_profile("fk_jd_owned_profile"),
        sa.CheckConstraint("jd_version >= 1", name="ck_jd_version"),
        sa.CheckConstraint("source_kind IN ('PASTED_TEXT')", name="ck_jd_source_kind"),
        sa.CheckConstraint("source_length BETWEEN 1 AND 200000", name="ck_jd_source_length"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DELETING')", name="ck_jd_status"),
    )
    _owner_indexes("job_descriptions")
    op.create_table(
        "jd_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("jd_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("requirement_type", sa.String(32), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_jd_requirement_owner_scope"),
        sa.UniqueConstraint("jd_id", "ordinal", name="uq_jd_requirement_ordinal"),
        sa.ForeignKeyConstraint(
            ["jd_id", "account_id", "profile_id"],
            ["job_descriptions.id", "job_descriptions.account_id", "job_descriptions.profile_id"],
            name="fk_jd_requirement_owned_jd",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("ordinal >= 1", name="ck_jd_requirement_ordinal"),
        sa.CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_jd_requirement_text"),
        sa.CheckConstraint(
            "source_start >= 0 AND source_end > source_start", name="ck_jd_requirement_span"
        ),
        sa.CheckConstraint(
            "length(exact_text) = source_end - source_start", name="ck_jd_requirement_span_text"
        ),
    )
    _owner_indexes("jd_requirements", extras=("jd_id",))
    op.create_table(
        "requirement_claim_maps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("mapping_type", sa.String(16), nullable=False),
        sa.Column("coverage_level", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_id", "account_id", "profile_id"],
            ["jd_requirements.id", "jd_requirements.account_id", "jd_requirements.profile_id"],
            name="fk_requirement_map_owned_requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_requirement_map_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id", "profile_version"],
            ["profile_archives.profile_id", "profile_archives.profile_version"],
            name="fk_requirement_map_exact_archive",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "requirement_id", "claim_id", "profile_version", name="uq_requirement_claim_map"
        ),
        sa.CheckConstraint("mapping_type IN ('RELATED')", name="ck_requirement_map_type"),
        sa.CheckConstraint("coverage_level IN ('POTENTIAL')", name="ck_requirement_map_coverage"),
    )
    _owner_indexes("requirement_claim_maps")
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("artifact_type", sa.String(24), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("jd_id", sa.String(36)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_artifact_owner_scope"),
        sa.UniqueConstraint(
            "profile_id", "artifact_type", "artifact_version", name="uq_artifact_profile_version"
        ),
        _owned_profile("fk_artifact_owned_profile"),
        sa.ForeignKeyConstraint(
            ["profile_id", "profile_version"],
            ["profile_archives.profile_id", "profile_archives.profile_version"],
            name="fk_artifact_exact_archive",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["jd_id", "account_id", "profile_id"],
            ["job_descriptions.id", "job_descriptions.account_id", "job_descriptions.profile_id"],
            name="fk_artifact_owned_jd",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("artifact_type IN ('RESUME_TEXT')", name="ck_artifact_type"),
        sa.CheckConstraint(
            "artifact_version >= 1 AND profile_version >= 0", name="ck_artifact_versions"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'REVIEW_REQUIRED', 'UNAVAILABLE_DUE_TO_ERASURE')",
            name="ck_artifact_status",
        ),
    )
    _owner_indexes("artifacts")
    op.create_table(
        "artifact_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("unit_type", sa.String(24), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
        sa.Column("wording_level", sa.String(2), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.UniqueConstraint("id", "account_id", "profile_id", name="uq_artifact_unit_owner_scope"),
        sa.UniqueConstraint("artifact_id", "ordinal", name="uq_artifact_unit_ordinal"),
        sa.ForeignKeyConstraint(
            ["artifact_id", "account_id", "profile_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.profile_id"],
            name="fk_artifact_unit_owned_artifact",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("ordinal >= 1", name="ck_artifact_unit_ordinal"),
        sa.CheckConstraint(
            "unit_type IN ('RESUME_BULLET', 'SUMMARY_SENTENCE', 'SKILL_ENTRY')",
            name="ck_artifact_unit_type",
        ),
        sa.CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_artifact_unit_text"),
        sa.CheckConstraint("wording_level IN ('R1', 'R2', 'R3')", name="ck_artifact_unit_wording"),
        sa.CheckConstraint(
            "review_status IN ('DRAFT', 'REVIEW_REQUIRED')", name="ck_artifact_unit_review"
        ),
    )
    _owner_indexes("artifact_units", extras=("artifact_id",))
    op.create_table(
        "artifact_claim_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("artifact_unit_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("link_role", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_unit_id", "account_id", "profile_id"],
            ["artifact_units.id", "artifact_units.account_id", "artifact_units.profile_id"],
            name="fk_artifact_claim_link_owned_unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_artifact_claim_link_owned_claim",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("artifact_unit_id", "claim_id", name="uq_artifact_claim_link"),
        sa.CheckConstraint("link_role IN ('FACTUAL_BASIS')", name="ck_artifact_claim_link_role"),
    )
    _owner_indexes("artifact_claim_links")


def downgrade() -> None:
    for table, extras in (
        ("artifact_claim_links", ()),
        ("artifact_units", ("artifact_id",)),
        ("artifacts", ()),
        ("requirement_claim_maps", ()),
        ("jd_requirements", ("jd_id",)),
        ("job_descriptions", ()),
    ):
        for column in ("account_id", "profile_id", *extras):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    op.drop_constraint("uq_claim_assessment_version", "claim_assessments", type_="unique")

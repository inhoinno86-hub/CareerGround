"""Owner-scoped JD excerpt and version-bound resume artifact storage foundation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from careerground.storage.models import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_jd_owner_scope"),
        UniqueConstraint("profile_id", "jd_version", name="uq_jd_profile_version"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_jd_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint("jd_version >= 1", name="ck_jd_version"),
        CheckConstraint("source_kind IN ('PASTED_TEXT')", name="ck_jd_source_kind"),
        CheckConstraint("source_length BETWEEN 1 AND 200000", name="ck_jd_source_length"),
        CheckConstraint("status IN ('ACTIVE', 'DELETING')", name="ck_jd_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    jd_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_length: Mapped[int] = mapped_column(Integer, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JDRequirement(Base):
    __tablename__ = "jd_requirements"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_jd_requirement_owner_scope"),
        UniqueConstraint("jd_id", "ordinal", name="uq_jd_requirement_ordinal"),
        ForeignKeyConstraint(
            ["jd_id", "account_id", "profile_id"],
            ["job_descriptions.id", "job_descriptions.account_id", "job_descriptions.profile_id"],
            name="fk_jd_requirement_owned_jd",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal >= 1", name="ck_jd_requirement_ordinal"),
        CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_jd_requirement_text"),
        CheckConstraint(
            "source_start >= 0 AND source_end > source_start", name="ck_jd_requirement_span"
        ),
        CheckConstraint(
            "length(exact_text) = source_end - source_start", name="ck_jd_requirement_span_text"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    jd_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_end: Mapped[int] = mapped_column(Integer, nullable=False)


class RequirementClaimMap(Base):
    __tablename__ = "requirement_claim_maps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id", "account_id", "profile_id"],
            ["jd_requirements.id", "jd_requirements.account_id", "jd_requirements.profile_id"],
            name="fk_requirement_map_owned_requirement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_requirement_map_owned_claim",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["profile_id", "profile_version"],
            ["profile_archives.profile_id", "profile_archives.profile_version"],
            name="fk_requirement_map_exact_archive",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "requirement_id", "claim_id", "profile_version", name="uq_requirement_claim_map"
        ),
        CheckConstraint("mapping_type IN ('RELATED')", name="ck_requirement_map_type"),
        CheckConstraint("coverage_level IN ('POTENTIAL')", name="ck_requirement_map_coverage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    requirement_id: Mapped[str] = mapped_column(String(36), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(16), nullable=False)
    coverage_level: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_artifact_owner_scope"),
        UniqueConstraint(
            "profile_id", "artifact_type", "artifact_version", name="uq_artifact_profile_version"
        ),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_artifact_owned_profile",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["profile_id", "profile_version"],
            ["profile_archives.profile_id", "profile_archives.profile_version"],
            name="fk_artifact_exact_archive",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["jd_id", "account_id", "profile_id"],
            ["job_descriptions.id", "job_descriptions.account_id", "job_descriptions.profile_id"],
            name="fk_artifact_owned_jd",
            ondelete="RESTRICT",
        ),
        CheckConstraint("artifact_type IN ('RESUME_TEXT')", name="ck_artifact_type"),
        ForeignKeyConstraint(
            ["source_artifact_id", "account_id", "profile_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.profile_id"],
            name="fk_artifact_owned_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "artifact_version >= 1 AND profile_version >= 0", name="ck_artifact_versions"
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'REVIEW_REQUIRED', 'WORDING_REVIEWED', 'UNAVAILABLE_DUE_TO_ERASURE')",
            name="ck_artifact_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(24), nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    jd_id: Mapped[str | None] = mapped_column(String(36))
    source_artifact_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactUnit(Base):
    __tablename__ = "artifact_units"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_artifact_unit_owner_scope"),
        UniqueConstraint("artifact_id", "ordinal", name="uq_artifact_unit_ordinal"),
        ForeignKeyConstraint(
            ["artifact_id", "account_id", "profile_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.profile_id"],
            name="fk_artifact_unit_owned_artifact",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal >= 1", name="ck_artifact_unit_ordinal"),
        ForeignKeyConstraint(
            ["source_artifact_unit_id", "account_id", "profile_id"],
            ["artifact_units.id", "artifact_units.account_id", "artifact_units.profile_id"],
            name="fk_artifact_unit_owned_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "unit_type IN ('RESUME_BULLET', 'SUMMARY_SENTENCE', 'SKILL_ENTRY')",
            name="ck_artifact_unit_type",
        ),
        CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_artifact_unit_text"),
        CheckConstraint("wording_level IN ('R1', 'R2', 'R3')", name="ck_artifact_unit_wording"),
        CheckConstraint(
            "review_status IN ('DRAFT', 'REVIEW_REQUIRED', 'WORDING_REVIEWED')",
            name="ck_artifact_unit_review",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_artifact_unit_id: Mapped[str | None] = mapped_column(String(36))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(24), nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    wording_level: Mapped[str] = mapped_column(String(2), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)


class ArtifactClaimLink(Base):
    __tablename__ = "artifact_claim_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_unit_id", "account_id", "profile_id"],
            ["artifact_units.id", "artifact_units.account_id", "artifact_units.profile_id"],
            name="fk_artifact_claim_link_owned_unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_artifact_claim_link_owned_claim",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("artifact_unit_id", "claim_id", name="uq_artifact_claim_link"),
        CheckConstraint("link_role IN ('FACTUAL_BASIS')", name="ck_artifact_claim_link_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_unit_id: Mapped[str] = mapped_column(String(36), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    link_role: Mapped[str] = mapped_column(String(24), nullable=False)


class ArtifactWordingReview(Base):
    """Exact R1 wording review for one fixed artifact version."""

    __tablename__ = "artifact_wording_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "account_id", "profile_id"],
            ["artifacts.id", "artifacts.account_id", "artifacts.profile_id"],
            name="fk_wording_review_owned_artifact",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("artifact_id", name="uq_wording_review_artifact"),
        CheckConstraint("action IN ('ACCEPT_R1', 'ACCEPT_R2')", name="ck_wording_review_action"),
        CheckConstraint(
            "artifact_version >= 1 AND profile_version >= 0", name="ck_wording_review_versions"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

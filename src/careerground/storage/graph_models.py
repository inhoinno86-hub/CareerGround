"""Versioned, owner-scoped canonical Claim and Evidence foundation."""

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


class ProfileChangeSet(Base):
    __tablename__ = "profile_change_sets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profile_change_set_owned_profile",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("profile_id", "version_after", name="uq_profile_change_set_version"),
        UniqueConstraint("review_batch_id", name="uq_profile_change_set_review_batch"),
        CheckConstraint("version_before >= 0", name="ck_profile_change_set_before"),
        CheckConstraint("version_after = version_before + 1", name="ck_profile_change_set_step"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    review_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_claim_owner_scope"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_claim_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(canonical_text) BETWEEN 1 AND 20000", name="ck_claim_text"),
        CheckConstraint("created_in_version >= 1", name="ck_claim_created_version"),
        CheckConstraint("status IN ('ACTIVE', 'ERASED')", name="ck_claim_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_in_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_evidence_source_owner_scope"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_evidence_source_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_type IN ('EXPLICIT_PROFILING_INPUT')", name="ck_evidence_source_type"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(36), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_in_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_evidence_item_owner_scope"),
        ForeignKeyConstraint(
            ["source_id", "account_id", "profile_id"],
            ["evidence_sources.id", "evidence_sources.account_id", "evidence_sources.profile_id"],
            name="fk_evidence_item_owned_source",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(content_text) BETWEEN 1 AND 20000", name="ck_evidence_item_text"),
        CheckConstraint("status IN ('ACTIVE', 'ERASED')", name="ck_evidence_item_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_in_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceClaimLink(Base):
    __tablename__ = "evidence_claim_links"
    __table_args__ = (
        UniqueConstraint(
            "id", "account_id", "profile_id", name="uq_evidence_claim_link_owner_scope"
        ),
        ForeignKeyConstraint(
            ["evidence_id", "account_id", "profile_id"],
            ["evidence_items.id", "evidence_items.account_id", "evidence_items.profile_id"],
            name="fk_evidence_claim_link_owned_evidence",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_evidence_claim_link_owned_claim",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("evidence_id", "claim_id", "relation_type", name="uq_evidence_claim_link"),
        CheckConstraint(
            "relation_type IN ('SUPPORTS', 'CONTRADICTS', 'QUALIFIES', 'CONTEXTUALIZES')",
            name="ck_evidence_claim_link_relation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_in_version: Mapped[int] = mapped_column(Integer, nullable=False)


class ClaimAssessment(Base):
    __tablename__ = "claim_assessments"
    __table_args__ = (
        UniqueConstraint("claim_id", "profile_version", name="uq_claim_assessment_version"),
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_claim_assessment_owned_claim",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "knowledge_status IN ('USER_CONFIRMED', 'USER_CLAIMED', 'INFERRED', 'UNKNOWN')",
            name="ck_claim_assessment_knowledge",
        ),
        CheckConstraint(
            "consistency_status IN ('CONSISTENT', 'CONTRADICTED', 'DISPUTED', 'NOT_EVALUATED')",
            name="ck_claim_assessment_consistency",
        ),
        CheckConstraint(
            "usage_policy IN ('ALLOWED', 'REVIEW_REQUIRED', 'DO_NOT_CLAIM')",
            name="ck_claim_assessment_usage",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    knowledge_status: Mapped[str] = mapped_column(String(24), nullable=False)
    consistency_status: Mapped[str] = mapped_column(String(24), nullable=False)
    usage_policy: Mapped[str] = mapped_column(String(24), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimReview(Base):
    __tablename__ = "claim_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_claim_review_owned_claim",
            ondelete="RESTRICT",
        ),
        CheckConstraint("review_purpose IN ('FACT_CONFIRMATION')", name="ck_claim_review_purpose"),
        CheckConstraint("review_action IN ('ACCEPT')", name="ck_claim_review_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    review_purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    review_action: Mapped[str] = mapped_column(String(16), nullable=False)
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimConstraint(Base):
    __tablename__ = "claim_constraints"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "profile_id", name="uq_claim_constraint_owner_scope"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_claim_constraint_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "constraint_type IN ('NOT_TRUE', 'DO_NOT_USE')", name="ck_claim_constraint_type"
        ),
        CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_claim_constraint_text"),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="ck_claim_constraint_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(16), nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    review_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_in_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimBoundaryReview(Base):
    """Exact, explicit approval journal for adding or revoking one use boundary."""

    __tablename__ = "claim_boundary_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_boundary_review_owned_claim",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["constraint_id", "account_id", "profile_id"],
            [
                "claim_constraints.id",
                "claim_constraints.account_id",
                "claim_constraints.profile_id",
            ],
            name="fk_boundary_review_owned_constraint",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "account_id", "profile_id"],
            ["evidence_items.id", "evidence_items.account_id", "evidence_items.profile_id"],
            name="fk_boundary_review_owned_evidence",
            ondelete="RESTRICT",
        ),
        CheckConstraint("action IN ('ADD', 'REVOKE')", name="ck_boundary_review_action"),
        CheckConstraint(
            "profile_version = base_profile_version + 1", name="ck_boundary_review_version"
        ),
        CheckConstraint(
            "length(allowed_wording) BETWEEN 1 AND 20000", name="ck_boundary_allowed_wording"
        ),
        CheckConstraint(
            "length(remaining_prohibited_expansion) BETWEEN 1 AND 20000",
            name="ck_boundary_remaining_prohibition",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    constraint_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_wording: Mapped[str] = mapped_column(Text, nullable=False)
    remaining_prohibited_expansion: Mapped[str] = mapped_column(Text, nullable=False)
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimConflictReview(Base):
    """Explicit review of one contradicting Evidence link; source stays intact."""

    __tablename__ = "claim_conflict_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_conflict_review_owned_claim",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conflict_link_id", "account_id", "profile_id"],
            [
                "evidence_claim_links.id",
                "evidence_claim_links.account_id",
                "evidence_claim_links.profile_id",
            ],
            name="fk_conflict_review_owned_link",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "resolution IN ('KEEP_EXISTING', 'ACCEPT_CORRECTION', 'KEEP_BOTH_SCOPED', 'REMAIN_UNCERTAIN')",
            name="ck_conflict_review_resolution",
        ),
        CheckConstraint(
            "profile_version = base_profile_version + 1", name="ck_conflict_review_version"
        ),
        CheckConstraint("length(explanation) BETWEEN 1 AND 20000", name="ck_conflict_explanation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    conflict_link_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resolution: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClaimUseReview(Base):
    """Separate owner attestation for consistent, permitted R1 use of one Claim."""

    __tablename__ = "claim_use_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["claim_id", "account_id", "profile_id"],
            ["claims.id", "claims.account_id", "claims.profile_id"],
            name="fk_use_review_owned_claim",
            ondelete="RESTRICT",
        ),
        CheckConstraint("profile_version = base_profile_version + 1", name="ck_use_review_version"),
        CheckConstraint(
            "consistency_attested = true AND use_authorized = true",
            name="ck_use_review_explicit_choices",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(36), nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consistency_attested: Mapped[bool] = mapped_column(nullable=False)
    use_authorized: Mapped[bool] = mapped_column(nullable=False)
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfileArchive(Base):
    """Immutable-by-service exact canonical snapshot for one profile version."""

    __tablename__ = "profile_archives"
    __table_args__ = (
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profile_archive_owned_profile",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("profile_id", "profile_version", name="uq_profile_archive_version"),
        CheckConstraint("profile_version >= 0", name="ck_profile_archive_version"),
        CheckConstraint("length(snapshot_json) > 0", name="ck_profile_archive_content"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

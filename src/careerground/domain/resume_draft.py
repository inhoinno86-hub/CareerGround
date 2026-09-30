"""Synthetic exact-wording resume drafts and owner-scoped source trace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careerground.domain.jd_mapping import JDMappingRejected, require_eligible_claim_trace
from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactClaimLink,
    ArtifactUnit,
    JDRequirement,
    JobDescription,
    RequirementClaimMap,
)
from careerground.storage.models import Account, CareerProfile


class ResumeDraftUnavailable(Exception):
    """The owner, source version, eligible Claim or draft trace is unavailable."""


@dataclass(frozen=True)
class ResumeUnitTrace:
    unit_id: str
    exact_text: str
    claim_id: str
    evidence_ids: tuple[str, ...]
    evidence_excerpts: tuple[str, ...]
    original_input_refs: tuple[str, ...]
    wording_level: str
    review_status: str


@dataclass(frozen=True)
class ResumeTrace:
    artifact_id: str
    artifact_version: int
    profile_version: int
    jd_id: str
    stale_relative_to_current_profile: bool
    units: tuple[ResumeUnitTrace, ...]


def generate_resume_draft(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    jd_id: str,
    claim_ids: tuple[str, ...],
    now: datetime,
    artifact_id: str | None = None,
) -> Artifact:
    """Copy 1–5 exact eligible Claim strings into a review-required text draft.

    This is an internal deterministic R1 path. It neither rewrites facts nor
    approves wording, exports content, or calls an external generator.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware timestamp required")
    if (
        isinstance(profile_version, bool)
        or not isinstance(profile_version, int)
        or not isinstance(claim_ids, tuple)
        or not 1 <= len(claim_ids) <= 5
        or any(not isinstance(value, str) or not value for value in claim_ids)
        or len(set(claim_ids)) != len(claim_ids)
        or (artifact_id is not None and (not isinstance(artifact_id, str) or not artifact_id))
    ):
        raise ResumeDraftUnavailable
    account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
    profile = session.scalar(
        select(CareerProfile)
        .where(CareerProfile.id == profile_id, CareerProfile.account_id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    jd = session.scalar(
        select(JobDescription).where(
            JobDescription.id == jd_id,
            JobDescription.account_id == account_id,
            JobDescription.profile_id == profile_id,
            JobDescription.status == "ACTIVE",
        )
    )
    if (
        account is None
        or account.status != "ACTIVE"
        or profile is None
        or profile.status != "ACTIVE"
        or profile.version != profile_version
        or jd is None
    ):
        raise ResumeDraftUnavailable
    try:
        read_profile_archive(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=profile_version,
        )
    except ArchiveUnavailable as exc:
        raise ResumeDraftUnavailable from exc
    traces = []
    for claim_id in claim_ids:
        claim = session.scalar(
            select(Claim).where(
                Claim.id == claim_id,
                Claim.account_id == account_id,
                Claim.profile_id == profile_id,
                Claim.status == "ACTIVE",
            )
        )
        mapping = session.scalar(
            select(RequirementClaimMap)
            .join(JDRequirement, JDRequirement.id == RequirementClaimMap.requirement_id)
            .where(
                RequirementClaimMap.account_id == account_id,
                RequirementClaimMap.profile_id == profile_id,
                RequirementClaimMap.claim_id == claim_id,
                RequirementClaimMap.profile_version == profile_version,
                RequirementClaimMap.coverage_level == "POTENTIAL",
                JDRequirement.jd_id == jd_id,
            )
        )
        if claim is None or mapping is None:
            raise ResumeDraftUnavailable
        try:
            trace = require_eligible_claim_trace(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile_version,
                claim_id=claim_id,
            )
        except JDMappingRejected as exc:
            raise ResumeDraftUnavailable from exc
        if claim.canonical_text != trace.claim.exact_text:
            raise ResumeDraftUnavailable
        traces.append(trace)
    if artifact_id is not None:
        existing = session.get(Artifact, artifact_id)
        if existing is not None:
            if (
                existing.account_id != account_id
                or existing.profile_id != profile_id
                or existing.profile_version != profile_version
                or existing.jd_id != jd_id
                or tuple(
                    unit.claim_id
                    for unit in get_resume_trace(
                        session, account_id=account_id, artifact_id=artifact_id
                    ).units
                )
                != claim_ids
            ):
                raise ResumeDraftUnavailable
            return existing
    current = session.scalar(
        select(func.max(Artifact.artifact_version)).where(
            Artifact.account_id == account_id,
            Artifact.profile_id == profile_id,
            Artifact.artifact_type == "RESUME_TEXT",
        )
    )
    artifact = Artifact(
        id=artifact_id or str(uuid4()),
        account_id=account_id,
        profile_id=profile_id,
        artifact_type="RESUME_TEXT",
        artifact_version=(current or 0) + 1,
        profile_version=profile_version,
        jd_id=jd_id,
        status="REVIEW_REQUIRED",
        created_at=now.astimezone(UTC),
    )
    session.add(artifact)
    session.flush()
    for ordinal, trace in enumerate(traces, start=1):
        unit = ArtifactUnit(
            id=str(uuid4()),
            account_id=account_id,
            profile_id=profile_id,
            artifact_id=artifact.id,
            ordinal=ordinal,
            unit_type="RESUME_BULLET",
            exact_text=trace.claim.exact_text,
            wording_level="R1",
            review_status="REVIEW_REQUIRED",
        )
        session.add(unit)
        session.flush()
        session.add(
            ArtifactClaimLink(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile_id,
                artifact_unit_id=unit.id,
                claim_id=trace.claim.claim_id,
                link_role="FACTUAL_BASIS",
            )
        )
    session.flush()
    return artifact


def get_resume_trace(session: Session, *, account_id: str, artifact_id: str) -> ResumeTrace:
    """Return only a fully resolvable draft with its exact source references."""

    artifact = session.scalar(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.account_id == account_id)
    )
    if (
        artifact is None
        or artifact.status not in {"DRAFT", "REVIEW_REQUIRED", "WORDING_REVIEWED"}
        or not artifact.jd_id
    ):
        raise ResumeDraftUnavailable
    jd = session.scalar(
        select(JobDescription).where(
            JobDescription.id == artifact.jd_id,
            JobDescription.account_id == account_id,
            JobDescription.profile_id == artifact.profile_id,
            JobDescription.status == "ACTIVE",
        )
    )
    if jd is None:
        raise ResumeDraftUnavailable
    try:
        read_profile_archive(
            session,
            account_id=account_id,
            profile_id=artifact.profile_id,
            profile_version=artifact.profile_version,
        )
    except ArchiveUnavailable as exc:
        raise ResumeDraftUnavailable from exc
    profile = session.scalar(
        select(CareerProfile).where(
            CareerProfile.id == artifact.profile_id,
            CareerProfile.account_id == account_id,
        )
    )
    if profile is None:
        raise ResumeDraftUnavailable
    units = tuple(
        session.scalars(
            select(ArtifactUnit)
            .where(
                ArtifactUnit.artifact_id == artifact.id,
                ArtifactUnit.account_id == account_id,
                ArtifactUnit.profile_id == artifact.profile_id,
            )
            .order_by(ArtifactUnit.ordinal)
        )
    )
    if not 1 <= len(units) <= 5:
        raise ResumeDraftUnavailable
    results = []
    for unit in units:
        links = tuple(
            session.scalars(
                select(ArtifactClaimLink).where(
                    ArtifactClaimLink.artifact_unit_id == unit.id,
                    ArtifactClaimLink.account_id == account_id,
                    ArtifactClaimLink.profile_id == artifact.profile_id,
                )
            )
        )
        if len(links) != 1 or unit.wording_level != "R1":
            raise ResumeDraftUnavailable
        claim = session.scalar(
            select(Claim).where(
                Claim.id == links[0].claim_id,
                Claim.account_id == account_id,
                Claim.profile_id == artifact.profile_id,
                Claim.status == "ACTIVE",
            )
        )
        if claim is None:
            raise ResumeDraftUnavailable
        mapping = session.scalar(
            select(RequirementClaimMap)
            .join(JDRequirement, JDRequirement.id == RequirementClaimMap.requirement_id)
            .where(
                RequirementClaimMap.account_id == account_id,
                RequirementClaimMap.profile_id == artifact.profile_id,
                RequirementClaimMap.claim_id == claim.id,
                RequirementClaimMap.profile_version == artifact.profile_version,
                RequirementClaimMap.coverage_level == "POTENTIAL",
                JDRequirement.jd_id == artifact.jd_id,
            )
        )
        if mapping is None:
            raise ResumeDraftUnavailable
        try:
            trace = require_eligible_claim_trace(
                session,
                account_id=account_id,
                profile_id=artifact.profile_id,
                profile_version=artifact.profile_version,
                claim_id=claim.id,
            )
        except JDMappingRejected as exc:
            raise ResumeDraftUnavailable from exc
        if unit.exact_text != trace.claim.exact_text or claim.canonical_text != unit.exact_text:
            raise ResumeDraftUnavailable
        supporting = tuple(item for item in trace.evidence if item.relation_type == "SUPPORTS")
        results.append(
            ResumeUnitTrace(
                unit_id=unit.id,
                exact_text=unit.exact_text,
                claim_id=claim.id,
                evidence_ids=tuple(item.evidence_id for item in supporting),
                evidence_excerpts=tuple(item.exact_excerpt for item in supporting),
                original_input_refs=tuple(item.original_input_ref for item in supporting),
                wording_level=unit.wording_level,
                review_status=unit.review_status,
            )
        )
    return ResumeTrace(
        artifact_id=artifact.id,
        artifact_version=artifact.artifact_version,
        profile_version=artifact.profile_version,
        jd_id=artifact.jd_id,
        stale_relative_to_current_profile=profile.version != artifact.profile_version,
        units=tuple(results),
    )

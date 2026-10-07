"""Explicit, version-bound JD to Claim links for synthetic internal use."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.graph_projection import (
    ClaimEvidenceView,
    GraphUnavailable,
    get_claim_evidence,
)
from careerground.domain.jd_analysis import JDUnavailable, get_jd_analysis
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import (
    JDRequirement,
    JobDescription,
    RequirementClaimMap,
)
from careerground.storage.models import Account, CareerProfile


class JDMappingRejected(Exception):
    """The exact owner, version, requirement or eligible Claim is unavailable."""


@dataclass(frozen=True)
class JDRequirementLinks:
    requirement_id: str
    exact_text: str
    linked_claim_ids: tuple[str, ...]
    gap_status: str


@dataclass(frozen=True)
class JDMappingView:
    jd_id: str
    jd_version: int
    profile_version: int
    stale_relative_to_current_profile: bool
    requirements: tuple[JDRequirementLinks, ...]


def link_jd_requirement_to_claim(
    session: Session,
    *,
    account_id: str,
    jd_id: str,
    requirement_id: str,
    claim_id: str,
    profile_version: int,
    now: datetime,
) -> RequirementClaimMap:
    """Record an explicit potential relationship, with no inference or Graph mutation.

    The caller chooses a requirement/Claim pair. This function checks publication
    eligibility against the exact current archive; it does not judge semantic fit.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware timestamp required")
    if isinstance(profile_version, bool) or not isinstance(profile_version, int):
        raise JDMappingRejected
    account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
    jd = session.scalar(
        select(JobDescription).where(
            JobDescription.id == jd_id, JobDescription.account_id == account_id
        )
    )
    if account is None or account.status != "ACTIVE" or jd is None or jd.status != "ACTIVE":
        raise JDMappingRejected
    profile = session.scalar(
        select(CareerProfile)
        .where(CareerProfile.id == jd.profile_id, CareerProfile.account_id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if profile is None or profile.status != "ACTIVE" or profile.version != profile_version:
        raise JDMappingRejected
    requirement = session.scalar(
        select(JDRequirement).where(
            JDRequirement.id == requirement_id,
            JDRequirement.jd_id == jd.id,
            JDRequirement.account_id == account_id,
            JDRequirement.profile_id == profile.id,
        )
    )
    claim = session.scalar(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.account_id == account_id,
            Claim.profile_id == profile.id,
            Claim.status == "ACTIVE",
        )
    )
    if requirement is None or claim is None:
        raise JDMappingRejected
    try:
        analysis = get_jd_analysis(session, account_id=account_id, jd_id=jd_id)
        if requirement.ordinal not in {row[0] for row in analysis.requirements}:
            raise JDMappingRejected
        require_eligible_claim_trace(
            session,
            account_id=account_id,
            profile_id=profile.id,
            profile_version=profile_version,
            claim_id=claim_id,
        )
    except (JDUnavailable, GraphUnavailable) as exc:
        raise JDMappingRejected from exc

    existing = session.scalar(
        select(RequirementClaimMap).where(
            RequirementClaimMap.account_id == account_id,
            RequirementClaimMap.profile_id == profile.id,
            RequirementClaimMap.requirement_id == requirement_id,
            RequirementClaimMap.claim_id == claim_id,
            RequirementClaimMap.profile_version == profile_version,
        )
    )
    if existing is not None:
        return existing
    mapping = RequirementClaimMap(
        id=str(uuid4()),
        account_id=account_id,
        profile_id=profile.id,
        requirement_id=requirement_id,
        claim_id=claim_id,
        profile_version=profile_version,
        mapping_type="RELATED",
        coverage_level="POTENTIAL",
        created_at=now.astimezone(UTC),
    )
    session.add(mapping)
    session.flush()
    return mapping


def require_eligible_claim_trace(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    claim_id: str,
) -> ClaimEvidenceView:
    """Resolve a supported, reviewed Claim from one exact archive version."""

    try:
        trace = get_claim_evidence(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=profile_version,
            claim_id=claim_id,
        )
    except GraphUnavailable as exc:
        raise JDMappingRejected from exc
    if (
        trace.claim.knowledge_status != "USER_CONFIRMED"
        or trace.claim.consistency_status != "CONSISTENT"
        or trace.claim.usage_policy != "ALLOWED"
        or not trace.reviewed
        or trace.constraints
        or not any(item.relation_type == "SUPPORTS" for item in trace.evidence)
        or any(item.relation_type == "CONTRADICTS" for item in trace.evidence)
    ):
        raise JDMappingRejected
    return trace


def get_jd_mapping(
    session: Session, *, account_id: str, jd_id: str, profile_version: int
) -> JDMappingView:
    """Show recorded potential links and explicit gaps for one exact version."""

    if isinstance(profile_version, bool) or not isinstance(profile_version, int):
        raise JDMappingRejected
    try:
        analysis = get_jd_analysis(session, account_id=account_id, jd_id=jd_id)
    except JDUnavailable as exc:
        raise JDMappingRejected from exc
    jd = session.get(JobDescription, jd_id)
    profile = session.scalar(
        select(CareerProfile).where(
            CareerProfile.id == jd.profile_id, CareerProfile.account_id == account_id
        )
    )
    if profile is None or profile_version > profile.version or profile_version < 0:
        raise JDMappingRejected
    # Even a version with no links must exist; no latest-version fallback.
    from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive

    try:
        read_profile_archive(
            session,
            account_id=account_id,
            profile_id=profile.id,
            profile_version=profile_version,
        )
    except ArchiveUnavailable as exc:
        raise JDMappingRejected from exc
    rows = tuple(
        session.scalars(
            select(RequirementClaimMap).where(
                RequirementClaimMap.account_id == account_id,
                RequirementClaimMap.profile_id == profile.id,
                RequirementClaimMap.profile_version == profile_version,
            )
        )
    )
    by_requirement: dict[str, list[str]] = {}
    for row in rows:
        by_requirement.setdefault(row.requirement_id, []).append(row.claim_id)
    requirements = tuple(
        session.scalars(
            select(JDRequirement)
            .where(JDRequirement.jd_id == jd_id, JDRequirement.account_id == account_id)
            .order_by(JDRequirement.ordinal)
        )
    )
    return JDMappingView(
        jd_id=jd_id,
        jd_version=analysis.jd_version,
        profile_version=profile_version,
        stale_relative_to_current_profile=profile.version != profile_version,
        requirements=tuple(
            JDRequirementLinks(
                requirement_id=item.id,
                exact_text=item.exact_text,
                linked_claim_ids=tuple(sorted(by_requirement.get(item.id, ()))),
                gap_status=(
                    "POTENTIAL_LINK_RECORDED"
                    if by_requirement.get(item.id)
                    else "NO_ELIGIBLE_LINK_RECORDED"
                ),
            )
            for item in requirements
        ),
    )

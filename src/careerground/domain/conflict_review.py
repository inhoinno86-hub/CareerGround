"""Synthetic exact review of a Claim's contradicting Evidence link."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.profile_archive import ArchiveUnavailable, ensure_profile_archive
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimConflictReview,
    EvidenceClaimLink,
    EvidenceItem,
    ProfileChangeSet,
)
from careerground.storage.models import Account, CareerProfile

REVIEW_TTL = timedelta(minutes=10)
RESOLUTIONS = frozenset(
    {"KEEP_EXISTING", "ACCEPT_CORRECTION", "KEEP_BOTH_SCOPED", "REMAIN_UNCERTAIN"}
)


class ConflictReviewRejected(Exception):
    """The exact conflict, owner, evidence or approval is unavailable."""


@dataclass(frozen=True)
class ConflictReviewView:
    review_id: str
    account_id: str
    profile_id: str
    claim_id: str
    claim_text: str
    conflict_link_id: str
    opposing_evidence_id: str
    opposing_evidence_text: str
    knowledge_status: str
    consistency_status: str
    usage_policy: str
    resolution: str
    explanation: str
    base_profile_version: int
    expires_at: datetime
    review_digest: str


@dataclass(frozen=True)
class VerifiedConflictApproval:
    """Future trusted confirmation output, not a model supplied argument."""

    account_id: str
    review_id: str
    resolution: str
    review_digest: str
    expires_at: datetime


class ConflictReviewService:
    def __init__(self, signing_secret: bytes) -> None:
        if len(signing_secret) < 32:
            raise ValueError("conflict signing secret too short")
        self._secret = signing_secret

    def prepare(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        claim_id: str,
        conflict_link_id: str,
        resolution: str,
        explanation: str,
        now: datetime,
    ) -> ConflictReviewView:
        """Show one exact opposing proposition without changing the Graph."""

        now = _utc(now)
        if (
            resolution not in RESOLUTIONS
            or not isinstance(explanation, str)
            or not 1 <= len(explanation) <= 20_000
            or not explanation.strip()
        ):
            raise ConflictReviewRejected
        return self._view(
            session,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            conflict_link_id=conflict_link_id,
            resolution=resolution,
            explanation=explanation,
            review_id=str(uuid4()),
            expires_at=now + REVIEW_TTL,
        )

    def submit(
        self,
        session: Session,
        *,
        view: ConflictReviewView,
        approval: VerifiedConflictApproval,
        now: datetime,
    ) -> ClaimConflictReview:
        """Append a scoped, conservative assessment and exact new archive."""

        now = _utc(now)
        if (
            type(view) is not ConflictReviewView
            or type(approval) is not VerifiedConflictApproval
            or approval.expires_at.tzinfo is None
            or _utc(approval.expires_at) <= now
            or _utc(view.expires_at) <= now
            or approval.account_id != view.account_id
            or approval.review_id != view.review_id
            or approval.resolution != view.resolution
            or not hmac.compare_digest(approval.review_digest, view.review_digest)
            or _utc(approval.expires_at) != _utc(view.expires_at)
        ):
            raise ConflictReviewRejected
        account = session.scalar(
            select(Account)
            .where(Account.id == view.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        profile = session.scalar(
            select(CareerProfile)
            .where(
                CareerProfile.id == view.profile_id,
                CareerProfile.account_id == view.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
        ):
            raise ConflictReviewRejected
        existing = session.get(ClaimConflictReview, view.review_id)
        if existing is not None:
            if (
                existing.account_id != view.account_id
                or existing.profile_id != view.profile_id
                or existing.claim_id != view.claim_id
                or existing.conflict_link_id != view.conflict_link_id
                or existing.resolution != view.resolution
                or not hmac.compare_digest(existing.review_digest, view.review_digest)
            ):
                raise ConflictReviewRejected
            return existing
        if profile.version != view.base_profile_version:
            raise ConflictReviewRejected
        current = self._view(
            session,
            account_id=view.account_id,
            profile_id=view.profile_id,
            claim_id=view.claim_id,
            conflict_link_id=view.conflict_link_id,
            resolution=view.resolution,
            explanation=view.explanation,
            review_id=view.review_id,
            expires_at=view.expires_at,
        )
        if current != view:
            raise ConflictReviewRejected
        try:
            ensure_profile_archive(
                session,
                account_id=view.account_id,
                profile_id=view.profile_id,
                profile_version=profile.version,
                now=now,
            )
        except ArchiveUnavailable as exc:
            raise ConflictReviewRejected from exc
        next_version = profile.version + 1
        corrected = view.resolution == "ACCEPT_CORRECTION"
        review = ClaimConflictReview(
            id=view.review_id,
            account_id=view.account_id,
            profile_id=view.profile_id,
            claim_id=view.claim_id,
            conflict_link_id=view.conflict_link_id,
            resolution=view.resolution,
            explanation=view.explanation,
            review_digest=view.review_digest,
            base_profile_version=profile.version,
            profile_version=next_version,
            reviewed_at=now,
        )
        session.add(review)
        session.add(
            ClaimAssessment(
                id=str(uuid4()),
                account_id=view.account_id,
                profile_id=view.profile_id,
                claim_id=view.claim_id,
                knowledge_status="UNKNOWN" if corrected else view.knowledge_status,
                consistency_status="CONTRADICTED" if corrected else "DISPUTED",
                usage_policy="DO_NOT_CLAIM" if corrected else "REVIEW_REQUIRED",
                profile_version=next_version,
                assessed_at=now,
            )
        )
        session.add(
            ProfileChangeSet(
                id=str(uuid4()),
                account_id=view.account_id,
                profile_id=view.profile_id,
                version_before=profile.version,
                version_after=next_version,
                review_batch_id=view.review_id,
                review_digest=view.review_digest,
                reason="CONFLICT_REVIEW",
                created_at=now,
            )
        )
        profile.version = next_version
        session.flush()
        ensure_profile_archive(
            session,
            account_id=view.account_id,
            profile_id=view.profile_id,
            profile_version=next_version,
            now=now,
        )
        return review

    def _view(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        claim_id: str,
        conflict_link_id: str,
        resolution: str,
        explanation: str,
        review_id: str,
        expires_at: datetime,
    ) -> ConflictReviewView:
        account = session.get(Account, account_id, populate_existing=True)
        profile = session.scalar(
            select(CareerProfile)
            .where(CareerProfile.id == profile_id, CareerProfile.account_id == account_id)
            .execution_options(populate_existing=True)
        )
        claim = session.scalar(
            select(Claim)
            .where(
                Claim.id == claim_id,
                Claim.account_id == account_id,
                Claim.profile_id == profile_id,
                Claim.status == "ACTIVE",
            )
            .execution_options(populate_existing=True)
        )
        link = session.scalar(
            select(EvidenceClaimLink)
            .where(
                EvidenceClaimLink.id == conflict_link_id,
                EvidenceClaimLink.account_id == account_id,
                EvidenceClaimLink.profile_id == profile_id,
                EvidenceClaimLink.claim_id == claim_id,
                EvidenceClaimLink.relation_type == "CONTRADICTS",
            )
            .execution_options(populate_existing=True)
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
            or claim is None
            or link is None
        ):
            raise ConflictReviewRejected
        if claim.created_in_version > profile.version or link.created_in_version > profile.version:
            raise ConflictReviewRejected
        evidence = session.scalar(
            select(EvidenceItem)
            .where(
                EvidenceItem.id == link.evidence_id,
                EvidenceItem.account_id == account_id,
                EvidenceItem.profile_id == profile_id,
                EvidenceItem.status == "ACTIVE",
            )
            .execution_options(populate_existing=True)
        )
        assessment = session.scalar(
            select(ClaimAssessment)
            .where(
                ClaimAssessment.account_id == account_id,
                ClaimAssessment.profile_id == profile_id,
                ClaimAssessment.claim_id == claim_id,
            )
            .order_by(ClaimAssessment.profile_version.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if (
            evidence is None
            or assessment is None
            or hashlib.sha256(evidence.content_text.encode()).hexdigest() != evidence.content_hash
        ):
            raise ConflictReviewRejected
        if (
            evidence.created_in_version > profile.version
            or assessment.profile_version > profile.version
        ):
            raise ConflictReviewRejected
        payload = {
            "purpose": "CONFLICT_REVIEW",
            "review_id": review_id,
            "account_id": account_id,
            "profile_id": profile_id,
            "claim_id": claim_id,
            "claim_text": claim.canonical_text,
            "conflict_link_id": conflict_link_id,
            "opposing_evidence_id": evidence.id,
            "opposing_evidence_text": evidence.content_text,
            "opposing_evidence_hash": evidence.content_hash,
            "knowledge_status": assessment.knowledge_status,
            "consistency_status": assessment.consistency_status,
            "usage_policy": assessment.usage_policy,
            "resolution": resolution,
            "explanation": explanation,
            "base_profile_version": profile.version,
            "expires_at": _utc(expires_at).isoformat(),
        }
        digest = hmac.new(
            self._secret,
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        return ConflictReviewView(
            review_id=review_id,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            claim_text=claim.canonical_text,
            conflict_link_id=conflict_link_id,
            opposing_evidence_id=evidence.id,
            opposing_evidence_text=evidence.content_text,
            knowledge_status=assessment.knowledge_status,
            consistency_status=assessment.consistency_status,
            usage_policy=assessment.usage_policy,
            resolution=resolution,
            explanation=explanation,
            base_profile_version=profile.version,
            expires_at=_utc(expires_at),
            review_digest=digest,
        )


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return value.astimezone(UTC)

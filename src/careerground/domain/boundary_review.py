"""Synthetic exact-review path for adding or revoking a use boundary."""

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
    ClaimBoundaryReview,
    ClaimConstraint,
    EvidenceClaimLink,
    EvidenceItem,
    ProfileChangeSet,
)
from careerground.storage.models import Account, CareerProfile

REVIEW_TTL = timedelta(minutes=10)


class BoundaryReviewRejected(Exception):
    """The owner, exact context, evidence or approval is unavailable."""


@dataclass(frozen=True)
class BoundaryReviewView:
    review_id: str
    account_id: str
    profile_id: str
    claim_id: str
    claim_text: str
    knowledge_status: str
    consistency_status: str
    usage_policy: str
    evidence_id: str
    evidence_text: str
    action: str
    constraint_id: str | None
    old_boundary_text: str | None
    proposed_boundary_text: str | None
    allowed_wording: str
    remaining_prohibited_expansion: str
    base_profile_version: int
    expires_at: datetime
    review_digest: str


@dataclass(frozen=True)
class VerifiedBoundaryApproval:
    """Future trusted confirmation adapter output, never a model/tool argument."""

    account_id: str
    review_id: str
    action: str
    review_digest: str
    expires_at: datetime


class BoundaryReviewService:
    def __init__(self, signing_secret: bytes) -> None:
        if len(signing_secret) < 32:
            raise ValueError("boundary signing secret too short")
        self._secret = signing_secret

    def prepare(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        claim_id: str,
        evidence_id: str,
        action: str,
        constraint_id: str | None,
        proposed_boundary_text: str | None,
        allowed_wording: str,
        remaining_prohibited_expansion: str,
        now: datetime,
    ) -> BoundaryReviewView:
        """Render one exact review; preparation makes no canonical change."""

        now = _utc(now)
        if action not in {"ADD", "REVOKE"}:
            raise BoundaryReviewRejected
        for value in (allowed_wording, remaining_prohibited_expansion):
            if not isinstance(value, str) or not 1 <= len(value) <= 20_000 or not value.strip():
                raise BoundaryReviewRejected
        if action == "ADD":
            if constraint_id is not None or not _bounded_text(proposed_boundary_text):
                raise BoundaryReviewRejected
        elif constraint_id is None or proposed_boundary_text is not None:
            raise BoundaryReviewRejected
        return self._view(
            session,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            evidence_id=evidence_id,
            action=action,
            constraint_id=constraint_id,
            proposed_boundary_text=proposed_boundary_text,
            allowed_wording=allowed_wording,
            remaining_prohibited_expansion=remaining_prohibited_expansion,
            review_id=str(uuid4()),
            expires_at=now + REVIEW_TTL,
        )

    def submit(
        self,
        session: Session,
        *,
        view: BoundaryReviewView,
        approval: VerifiedBoundaryApproval,
        now: datetime,
    ) -> ClaimBoundaryReview:
        """Append one reviewed change and new archive in the caller's transaction."""

        now = _utc(now)
        if (
            type(view) is not BoundaryReviewView
            or type(approval) is not VerifiedBoundaryApproval
            or approval.expires_at.tzinfo is None
            or _utc(approval.expires_at) <= now
            or _utc(view.expires_at) <= now
            or approval.account_id != view.account_id
            or approval.review_id != view.review_id
            or approval.action != view.action
            or not hmac.compare_digest(approval.review_digest, view.review_digest)
            or _utc(approval.expires_at) != _utc(view.expires_at)
        ):
            raise BoundaryReviewRejected
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
            raise BoundaryReviewRejected
        existing = session.get(ClaimBoundaryReview, view.review_id)
        if existing is not None:
            if (
                existing.account_id != view.account_id
                or existing.profile_id != view.profile_id
                or existing.claim_id != view.claim_id
                or existing.action != view.action
                or not hmac.compare_digest(existing.review_digest, view.review_digest)
            ):
                raise BoundaryReviewRejected
            return existing
        if profile.version != view.base_profile_version:
            raise BoundaryReviewRejected
        current = self._view(
            session,
            account_id=view.account_id,
            profile_id=view.profile_id,
            claim_id=view.claim_id,
            evidence_id=view.evidence_id,
            action=view.action,
            constraint_id=view.constraint_id,
            proposed_boundary_text=view.proposed_boundary_text,
            allowed_wording=view.allowed_wording,
            remaining_prohibited_expansion=view.remaining_prohibited_expansion,
            review_id=view.review_id,
            expires_at=view.expires_at,
        )
        if current != view:
            raise BoundaryReviewRejected
        try:
            ensure_profile_archive(
                session,
                account_id=view.account_id,
                profile_id=view.profile_id,
                profile_version=profile.version,
                now=now,
            )
        except ArchiveUnavailable as exc:
            raise BoundaryReviewRejected from exc
        next_version = profile.version + 1
        if view.action == "ADD":
            constraint = ClaimConstraint(
                id=str(uuid4()),
                account_id=view.account_id,
                profile_id=view.profile_id,
                scope_key=session.get(Claim, view.claim_id).scope_key,
                constraint_type="DO_NOT_USE",
                exact_text=view.proposed_boundary_text,
                status="ACTIVE",
                review_batch_id=view.review_id,
                review_item_id=view.review_id,
                review_digest=view.review_digest,
                created_in_version=next_version,
                created_at=now,
            )
            session.add(constraint)
        else:
            constraint = session.get(ClaimConstraint, view.constraint_id)
            if constraint is None or constraint.status != "ACTIVE":
                raise BoundaryReviewRejected
            constraint.status = "REVOKED"
        session.flush()
        review = ClaimBoundaryReview(
            id=view.review_id,
            account_id=view.account_id,
            profile_id=view.profile_id,
            claim_id=view.claim_id,
            constraint_id=constraint.id,
            evidence_id=view.evidence_id,
            action=view.action,
            review_digest=view.review_digest,
            allowed_wording=view.allowed_wording,
            remaining_prohibited_expansion=view.remaining_prohibited_expansion,
            base_profile_version=profile.version,
            profile_version=next_version,
            reviewed_at=now,
        )
        session.add(review)
        session.add(
            ProfileChangeSet(
                id=str(uuid4()),
                account_id=view.account_id,
                profile_id=view.profile_id,
                version_before=profile.version,
                version_after=next_version,
                review_batch_id=view.review_id,
                review_digest=view.review_digest,
                reason="BOUNDARY_CHANGE",
                created_at=now,
            )
        )
        affected = tuple(
            session.scalars(
                select(Claim).where(
                    Claim.account_id == view.account_id,
                    Claim.profile_id == view.profile_id,
                    Claim.scope_key == constraint.scope_key,
                    Claim.status == "ACTIVE",
                )
            )
        )
        for claim in affected:
            latest = session.scalar(
                select(ClaimAssessment)
                .where(
                    ClaimAssessment.account_id == view.account_id,
                    ClaimAssessment.profile_id == view.profile_id,
                    ClaimAssessment.claim_id == claim.id,
                )
                .order_by(ClaimAssessment.profile_version.desc())
                .limit(1)
            )
            session.add(
                ClaimAssessment(
                    id=str(uuid4()),
                    account_id=view.account_id,
                    profile_id=view.profile_id,
                    claim_id=claim.id,
                    knowledge_status=latest.knowledge_status if latest else "UNKNOWN",
                    consistency_status=latest.consistency_status if latest else "NOT_EVALUATED",
                    usage_policy="REVIEW_REQUIRED",
                    profile_version=next_version,
                    assessed_at=now,
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
        evidence_id: str,
        action: str,
        constraint_id: str | None,
        proposed_boundary_text: str | None,
        allowed_wording: str,
        remaining_prohibited_expansion: str,
        review_id: str,
        expires_at: datetime,
    ) -> BoundaryReviewView:
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
        evidence = session.scalar(
            select(EvidenceItem)
            .where(
                EvidenceItem.id == evidence_id,
                EvidenceItem.account_id == account_id,
                EvidenceItem.profile_id == profile_id,
                EvidenceItem.status == "ACTIVE",
            )
            .execution_options(populate_existing=True)
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
            or claim is None
            or evidence is None
        ):
            raise BoundaryReviewRejected
        if (
            claim.created_in_version > profile.version
            or evidence.created_in_version > profile.version
        ):
            raise BoundaryReviewRejected
        if hashlib.sha256(evidence.content_text.encode()).hexdigest() != evidence.content_hash:
            raise BoundaryReviewRejected
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
        if assessment is None:
            raise BoundaryReviewRejected
        if assessment.profile_version > profile.version:
            raise BoundaryReviewRejected
        relation = session.scalar(
            select(EvidenceClaimLink)
            .where(
                EvidenceClaimLink.evidence_id == evidence_id,
                EvidenceClaimLink.claim_id == claim_id,
                EvidenceClaimLink.account_id == account_id,
                EvidenceClaimLink.profile_id == profile_id,
                EvidenceClaimLink.relation_type
                == ("SUPPORTS" if action == "REVOKE" else "CONTRADICTS"),
            )
            .execution_options(populate_existing=True)
        )
        if relation is None:
            raise BoundaryReviewRejected
        if relation.created_in_version > profile.version:
            raise BoundaryReviewRejected
        constraint = None
        if action == "REVOKE":
            constraint = session.scalar(
                select(ClaimConstraint)
                .where(
                    ClaimConstraint.id == constraint_id,
                    ClaimConstraint.account_id == account_id,
                    ClaimConstraint.profile_id == profile_id,
                    ClaimConstraint.scope_key == claim.scope_key,
                    ClaimConstraint.constraint_type == "DO_NOT_USE",
                    ClaimConstraint.status == "ACTIVE",
                )
                .execution_options(populate_existing=True)
            )
            if constraint is None or evidence.created_in_version <= constraint.created_in_version:
                raise BoundaryReviewRejected
            if constraint.created_in_version > profile.version:
                raise BoundaryReviewRejected
        else:
            duplicate = session.scalar(
                select(ClaimConstraint)
                .where(
                    ClaimConstraint.account_id == account_id,
                    ClaimConstraint.profile_id == profile_id,
                    ClaimConstraint.scope_key == claim.scope_key,
                    ClaimConstraint.constraint_type == "DO_NOT_USE",
                    ClaimConstraint.exact_text == proposed_boundary_text,
                    ClaimConstraint.status == "ACTIVE",
                )
                .execution_options(populate_existing=True)
            )
            if duplicate is not None:
                raise BoundaryReviewRejected
        payload = {
            "purpose": "BOUNDARY_CHANGE",
            "review_id": review_id,
            "account_id": account_id,
            "profile_id": profile_id,
            "claim_id": claim_id,
            "claim_text": claim.canonical_text,
            "knowledge_status": assessment.knowledge_status,
            "consistency_status": assessment.consistency_status,
            "usage_policy": assessment.usage_policy,
            "evidence_id": evidence_id,
            "evidence_text": evidence.content_text,
            "evidence_hash": evidence.content_hash,
            "relation_id": relation.id,
            "action": action,
            "constraint_id": constraint.id if constraint else None,
            "old_boundary_text": constraint.exact_text if constraint else None,
            "proposed_boundary_text": proposed_boundary_text,
            "allowed_wording": allowed_wording,
            "remaining_prohibited_expansion": remaining_prohibited_expansion,
            "base_profile_version": profile.version,
            "expires_at": _utc(expires_at).isoformat(),
        }
        digest = hmac.new(
            self._secret,
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        return BoundaryReviewView(
            review_id=review_id,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            claim_text=claim.canonical_text,
            knowledge_status=assessment.knowledge_status,
            consistency_status=assessment.consistency_status,
            usage_policy=assessment.usage_policy,
            evidence_id=evidence_id,
            evidence_text=evidence.content_text,
            action=action,
            constraint_id=constraint.id if constraint else None,
            old_boundary_text=constraint.exact_text if constraint else None,
            proposed_boundary_text=proposed_boundary_text,
            allowed_wording=allowed_wording,
            remaining_prohibited_expansion=remaining_prohibited_expansion,
            base_profile_version=profile.version,
            expires_at=_utc(expires_at),
            review_digest=digest,
        )


def _bounded_text(value: str | None) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 20_000 and bool(value.strip())


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return value.astimezone(UTC)

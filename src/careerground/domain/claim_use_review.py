"""Separate exact owner approval for a fact-confirmed Claim's R1 use."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.graph_projection import (
    ClaimEvidenceView,
    GraphUnavailable,
    get_claim_evidence,
)
from careerground.domain.profile_archive import ArchiveUnavailable, ensure_profile_archive
from careerground.storage.graph_models import ClaimAssessment, ClaimUseReview, ProfileChangeSet
from careerground.storage.models import Account, CareerProfile

USE_REVIEW_TTL = timedelta(minutes=3)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profile_id",
        "claim_id",
        "base_profile_version",
        "review_id",
        "review_digest",
        "expires_at",
    }
)


class ClaimUseReviewRejected(Exception):
    """The exact owner, source, review intent or eligibility is unavailable."""


@dataclass(frozen=True)
class ClaimUseReviewPresentation:
    profile_id: str
    claim_id: str
    base_profile_version: int
    trace: ClaimEvidenceView
    blockers: tuple[str, ...]
    approval_token: str | None


class ClaimUseReviewService:
    def __init__(self, review_secret: bytes, presentation_secret: bytes) -> None:
        if not isinstance(review_secret, bytes) or len(review_secret) < 32:
            raise ValueError("review signing secret too short")
        self._review_secret = review_secret
        self._tokens = BrowserFormTokenCodec(presentation_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profile_id: str,
        claim_id: str,
        now: datetime,
    ) -> ClaimUseReviewPresentation:
        now = _utc(now)
        _identity(account_id, browser_session_id, profile_id, claim_id)
        profile = _profile(session, account_id, profile_id, lock=False)
        if profile is None:
            raise ClaimUseReviewRejected
        review_id = str(uuid4())
        expires_at = now + USE_REVIEW_TTL
        trace, blockers, digest = self._view(
            session,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            base_profile_version=profile.version,
            review_id=review_id,
            expires_at=expires_at,
        )
        token = None
        if not blockers:
            token = self._tokens.sign(
                {
                    "purpose": "CLAIM_R1_USE_REVIEW_V1",
                    "account_id": account_id,
                    "browser_session_id": browser_session_id,
                    "profile_id": profile_id,
                    "claim_id": claim_id,
                    "base_profile_version": profile.version,
                    "review_id": review_id,
                    "review_digest": digest,
                    "expires_at": expires_at.isoformat(),
                }
            )
        return ClaimUseReviewPresentation(
            profile_id, claim_id, profile.version, trace, blockers, token
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profile_id: str,
        claim_id: str,
        approval_token: str,
        consistency_attested: bool,
        use_authorized: bool,
        now: datetime,
    ) -> ClaimUseReview:
        now = _utc(now)
        _identity(account_id, browser_session_id, profile_id, claim_id)
        if consistency_attested is not True or use_authorized is not True:
            raise ClaimUseReviewRejected
        try:
            payload = self._tokens.verify(approval_token, expected_keys=_TOKEN_KEYS)
            expires_at = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ClaimUseReviewRejected from exc
        if (
            payload["purpose"] != "CLAIM_R1_USE_REVIEW_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profile_id"] != profile_id
            or payload["claim_id"] != claim_id
            or type(payload["base_profile_version"]) is not int
            or payload["base_profile_version"] < 0
            or type(payload["review_id"]) is not str
            or type(payload["review_digest"]) is not str
            or len(payload["review_digest"]) != 64
            or expires_at <= now
        ):
            raise ClaimUseReviewRejected
        account = session.scalar(
            select(Account)
            .where(Account.id == account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        profile = _profile(session, account_id, profile_id, lock=True)
        if account is None or account.status != "ACTIVE" or profile is None:
            raise ClaimUseReviewRejected
        existing = session.get(ClaimUseReview, payload["review_id"])
        if existing is not None:
            if (
                existing.account_id != account_id
                or existing.profile_id != profile_id
                or existing.claim_id != claim_id
                or existing.base_profile_version != payload["base_profile_version"]
                or not hmac.compare_digest(existing.review_digest, payload["review_digest"])
            ):
                raise ClaimUseReviewRejected
            return existing
        if profile.version != payload["base_profile_version"]:
            raise ClaimUseReviewRejected
        trace, blockers, digest = self._view(
            session,
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            base_profile_version=profile.version,
            review_id=payload["review_id"],
            expires_at=expires_at,
        )
        if blockers or not hmac.compare_digest(digest, payload["review_digest"]):
            raise ClaimUseReviewRejected
        try:
            ensure_profile_archive(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile.version,
                now=now,
            )
        except ArchiveUnavailable as exc:
            raise ClaimUseReviewRejected from exc
        next_version = profile.version + 1
        review = ClaimUseReview(
            id=payload["review_id"],
            account_id=account_id,
            profile_id=profile_id,
            claim_id=claim_id,
            review_digest=digest,
            consistency_attested=True,
            use_authorized=True,
            base_profile_version=profile.version,
            profile_version=next_version,
            reviewed_at=now,
        )
        session.add_all(
            [
                review,
                ClaimAssessment(
                    id=str(uuid4()),
                    account_id=account_id,
                    profile_id=profile_id,
                    claim_id=claim_id,
                    knowledge_status=trace.claim.knowledge_status,
                    consistency_status="CONSISTENT",
                    usage_policy="ALLOWED",
                    profile_version=next_version,
                    assessed_at=now,
                ),
                ProfileChangeSet(
                    id=str(uuid4()),
                    account_id=account_id,
                    profile_id=profile_id,
                    version_before=profile.version,
                    version_after=next_version,
                    review_batch_id=review.id,
                    review_digest=digest,
                    reason="CLAIM_USE_REVIEW",
                    created_at=now,
                ),
            ]
        )
        profile.version = next_version
        session.flush()
        try:
            ensure_profile_archive(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=next_version,
                now=now,
            )
        except ArchiveUnavailable as exc:
            raise ClaimUseReviewRejected from exc
        return review

    def _view(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        claim_id: str,
        base_profile_version: int,
        review_id: str,
        expires_at: datetime,
    ) -> tuple[ClaimEvidenceView, tuple[str, ...], str]:
        try:
            trace = get_claim_evidence(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=base_profile_version,
                claim_id=claim_id,
            )
        except GraphUnavailable as exc:
            raise ClaimUseReviewRejected from exc
        blockers = []
        if trace.claim.knowledge_status != "USER_CONFIRMED" or not trace.reviewed:
            blockers.append("FACT_REVIEW_REQUIRED")
        if not any(item.relation_type == "SUPPORTS" for item in trace.evidence):
            blockers.append("SUPPORT_REQUIRED")
        if any(item.relation_type == "CONTRADICTS" for item in trace.evidence):
            blockers.append("OPPOSING_EVIDENCE")
        if trace.constraints:
            blockers.append("ACTIVE_BOUNDARY")
        if trace.claim.consistency_status in {"DISPUTED", "CONTRADICTED"}:
            blockers.append("UNRESOLVED_CONSISTENCY")
        if trace.claim.usage_policy == "DO_NOT_CLAIM":
            blockers.append("USE_PROHIBITED")
        if trace.claim.usage_policy == "ALLOWED":
            blockers.append("ALREADY_ALLOWED")
        context = {
            "purpose": "CLAIM_R1_USE_REVIEW_V1",
            "account_id": account_id,
            "profile_id": profile_id,
            "claim_id": claim_id,
            "base_profile_version": base_profile_version,
            "review_id": review_id,
            "expires_at": expires_at.isoformat(),
            "claim": vars(trace.claim),
            "reviewed": trace.reviewed,
            "evidence": [vars(item) for item in trace.evidence],
            "constraints": trace.constraints,
        }
        body = json.dumps(
            context, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        digest = hmac.new(self._review_secret, body, hashlib.sha256).hexdigest()
        return trace, tuple(blockers), digest


def _profile(
    session: Session, account_id: str, profile_id: str, *, lock: bool
) -> CareerProfile | None:
    statement = select(CareerProfile).where(
        CareerProfile.id == profile_id,
        CareerProfile.account_id == account_id,
        CareerProfile.status == "ACTIVE",
    )
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return session.scalar(statement)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ClaimUseReviewRejected
    return value.astimezone(UTC)


def _identity(account_id: str, browser_session_id: str, profile_id: str, claim_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(profile_id, str)
        or not profile_id
        or not isinstance(claim_id, str)
        or not claim_id
    ):
        raise ClaimUseReviewRejected

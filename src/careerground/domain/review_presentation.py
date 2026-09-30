"""Local browser review presentation and short-lived approval boundary.

Only a trusted browser-session adapter may supply the account and session IDs.
This module does not create a public route or authenticate a browser itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.claim_review_submission import (
    DECISIONS,
    ReviewSubmissionRejected,
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewStale,
    ReviewUnavailable,
    _stored_utc,
)
from careerground.storage.graph_models import ProfileChangeSet
from careerground.storage.models import CareerProfile

PRESENTATION_TTL = timedelta(minutes=3)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "batch_id",
        "review_digest",
        "base_profile_version",
        "item_ids",
        "expires_at",
    }
)


class ReviewPresentationRejected(Exception):
    """A review is unavailable, stale, or lacks exact browser approval."""


@dataclass(frozen=True)
class ReviewDisplayItem:
    item_id: str
    position: int
    exact_text: str
    claim_type: str
    scope_key: str


@dataclass(frozen=True)
class ReviewPresentation:
    batch_id: str
    profile_id: str
    scope_key: str
    base_profile_version: int
    review_digest: str
    expires_at: datetime
    items: tuple[ReviewDisplayItem, ...]
    approval_token: str


class ReviewPresentationService:
    """Issue a session-bound form token and convert its choices to trusted approval."""

    def __init__(self, preparation: ClaimReviewPreparation, signing_secret: bytes) -> None:
        self._preparation = preparation
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        batch_id: str,
        now: datetime,
    ) -> ReviewPresentation:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        try:
            batch, items = self._preparation.get(
                session, account_id=account_id, batch_id=batch_id, now=now
            )
        except (ReviewUnavailable, ReviewStale) as exc:
            raise ReviewPresentationRejected from exc
        profile = session.scalar(
            select(CareerProfile).where(
                CareerProfile.id == batch.profile_id,
                CareerProfile.account_id == account_id,
                CareerProfile.status == "ACTIVE",
            )
        )
        if profile is None or profile.version != batch.base_profile_version:
            raise ReviewPresentationRejected
        expires_at = min(_stored_utc(batch.expires_at), now + PRESENTATION_TTL)
        payload = {
            "purpose": "CLAIM_REVIEW_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "batch_id": batch.id,
            "review_digest": batch.review_digest,
            "base_profile_version": batch.base_profile_version,
            "item_ids": [item.id for item in items],
            "expires_at": expires_at.isoformat(),
        }
        return ReviewPresentation(
            batch_id=batch.id,
            profile_id=batch.profile_id,
            scope_key=batch.scope_key,
            base_profile_version=batch.base_profile_version,
            review_digest=batch.review_digest,
            expires_at=expires_at,
            items=tuple(
                ReviewDisplayItem(
                    item_id=item.id,
                    position=item.position,
                    exact_text=item.exact_text,
                    claim_type=item.claim_type,
                    scope_key=item.scope_key,
                )
                for item in items
            ),
            approval_token=self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        batch_id: str,
        approval_token: str,
        decisions: tuple[tuple[str, str], ...],
        now: datetime,
    ) -> ProfileChangeSet | None:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(approval_token, expected_keys=_TOKEN_KEYS)
        except BrowserFormTokenRejected as exc:
            raise ReviewPresentationRejected from exc
        if (
            payload["purpose"] != "CLAIM_REVIEW_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["batch_id"] != batch_id
            or type(payload["base_profile_version"]) is not int
            or payload["base_profile_version"] < 0
            or not isinstance(payload["review_digest"], str)
            or not isinstance(payload["item_ids"], list)
            or not 1 <= len(payload["item_ids"]) <= 5
            or any(not isinstance(item_id, str) or not item_id for item_id in payload["item_ids"])
            or len(set(payload["item_ids"])) != len(payload["item_ids"])
            or type(decisions) is not tuple
            or len(decisions) != len(payload["item_ids"])
            or any(type(pair) is not tuple or len(pair) != 2 for pair in decisions)
            or tuple(item_id for item_id, _ in decisions) != tuple(payload["item_ids"])
            or any(
                type(decision) is not str or decision not in DECISIONS for _, decision in decisions
            )
        ):
            raise ReviewPresentationRejected
        try:
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (TypeError, ValueError) as exc:
            raise ReviewPresentationRejected from exc
        if expires_at <= now:
            raise ReviewPresentationRejected
        approval = VerifiedReviewApproval(
            account_id=account_id,
            batch_id=batch_id,
            review_digest=payload["review_digest"],
            decisions=decisions,
            expires_at=expires_at,
        )
        try:
            return submit_synthetic_review(
                session,
                preparation=self._preparation,
                approval=approval,
                now=now,
            )
        except (ReviewSubmissionRejected, ReviewStale) as exc:
            raise ReviewPresentationRejected from exc


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReviewPresentationRejected
    return value.astimezone(UTC)


def _require_browser_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise ReviewPresentationRejected

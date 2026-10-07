"""Session-bound exact R1 wording display and approval for a synthetic browser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.resume_wording_review import (
    WordingReviewRejected,
    WordingReviewService,
    WordingReviewView,
)
from careerground.storage.jd_artifact_models import ArtifactWordingReview

WORDING_FORM_TTL = timedelta(minutes=3)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "artifact_id",
        "review_id",
        "review_digest",
        "review_expires_at",
        "form_expires_at",
    }
)


class WordingPresentationRejected(Exception):
    """The displayed R1 wording or user confirmation is unavailable."""


@dataclass(frozen=True)
class WordingPresentation:
    review: WordingReviewView
    approval_token: str


class WordingPresentationService:
    def __init__(self, wording_service: WordingReviewService, signing_secret: bytes) -> None:
        self._wording = wording_service
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        artifact_id: str,
        now: datetime,
    ) -> WordingPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, artifact_id)
        try:
            view = self._wording.prepare(
                session, account_id=account_id, artifact_id=artifact_id, now=now
            )
        except WordingReviewRejected as exc:
            raise WordingPresentationRejected from exc
        payload = {
            "purpose": "R1_WORDING_REVIEW_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "artifact_id": artifact_id,
            "review_id": view.review_id,
            "review_digest": view.review_digest,
            "review_expires_at": view.expires_at.isoformat(),
            "form_expires_at": min(now + WORDING_FORM_TTL, view.expires_at).isoformat(),
        }
        return WordingPresentation(view, self._tokens.sign(payload))

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        artifact_id: str,
        approval_token: str,
        now: datetime,
    ) -> ArtifactWordingReview:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, artifact_id)
        try:
            payload = self._tokens.verify(approval_token, expected_keys=_TOKEN_KEYS)
            review_expires_at = _aware_utc(datetime.fromisoformat(payload["review_expires_at"]))
            form_expires_at = _aware_utc(datetime.fromisoformat(payload["form_expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise WordingPresentationRejected from exc
        if (
            payload["purpose"] != "R1_WORDING_REVIEW_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["artifact_id"] != artifact_id
            or type(payload["review_id"]) is not str
            or not payload["review_id"]
            or type(payload["review_digest"]) is not str
            or form_expires_at <= now
            or review_expires_at <= now
            or form_expires_at > review_expires_at
        ):
            raise WordingPresentationRejected
        try:
            return self._wording.submit_prepared(
                session,
                account_id=account_id,
                artifact_id=artifact_id,
                review_id=payload["review_id"],
                review_digest=payload["review_digest"],
                expires_at=review_expires_at,
                now=now,
            )
        except WordingReviewRejected as exc:
            raise WordingPresentationRejected from exc


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise WordingPresentationRejected
    return value.astimezone(UTC)


def _require_identity(account_id: str, browser_session_id: str, artifact_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(artifact_id, str)
        or not artifact_id
    ):
        raise WordingPresentationRejected

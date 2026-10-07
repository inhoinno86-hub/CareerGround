"""Explicit synthetic browser intent to prepare one exact draft scope for review."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewIdempotencyConflict,
    ReviewStale,
    ReviewUnavailable,
)
from careerground.domain.profiling_workspace import (
    ProfilingExpired,
    ProfilingUnavailable,
    _as_utc,
    _owned_work,
    get_profiling_session,
)
from careerground.storage.models import ProfilingDraft, ProfilingReviewBatch, ProfilingReviewItem

PREPARE_TOKEN_TTL = timedelta(minutes=3)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profiling_session_id",
        "scope_key",
        "base_profile_version",
        "draft_digest",
        "idempotency_key",
        "expires_at",
    }
)


class ReviewPreparePresentationRejected(Exception):
    """The exact displayed draft scope or browser preparation intent changed."""


@dataclass(frozen=True)
class ReviewPrepareDraft:
    claim_type: str
    exact_text: str


@dataclass(frozen=True)
class ReviewPreparePresentation:
    profiling_session_id: str
    scope_key: str
    base_profile_version: int
    drafts: tuple[ReviewPrepareDraft, ...]
    prepare_token: str


class ReviewPreparePresentationService:
    def __init__(self, preparation: ClaimReviewPreparation, signing_secret: bytes) -> None:
        self._preparation = preparation
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        scope_key: str,
        now: datetime,
    ) -> ReviewPreparePresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profiling_session_id, scope_key)
        try:
            work = get_profiling_session(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                now=now,
            )
        except (ProfilingUnavailable, ProfilingExpired) as exc:
            raise ReviewPreparePresentationRejected from exc
        if work.base_profile_version != work.current_profile_version:
            raise ReviewPreparePresentationRejected
        drafts = _drafts(session, account_id, profiling_session_id, scope_key)
        if not 1 <= len(drafts) <= 5:
            raise ReviewPreparePresentationRejected
        payload = {
            "purpose": "CLAIM_REVIEW_PREPARE_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profiling_session_id": profiling_session_id,
            "scope_key": scope_key,
            "base_profile_version": work.base_profile_version,
            "draft_digest": _digest(drafts),
            "idempotency_key": secrets.token_urlsafe(18),
            "expires_at": min(now + PREPARE_TOKEN_TTL, work.retention_expires_at).isoformat(),
        }
        return ReviewPreparePresentation(
            profiling_session_id,
            scope_key,
            work.base_profile_version,
            tuple(ReviewPrepareDraft(draft.claim_type, draft.exact_text) for draft in drafts),
            self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        scope_key: str,
        prepare_token: str,
        now: datetime,
    ) -> ProfilingReviewBatch:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profiling_session_id, scope_key)
        try:
            payload = self._tokens.verify(prepare_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ReviewPreparePresentationRejected from exc
        if (
            payload["purpose"] != "CLAIM_REVIEW_PREPARE_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profiling_session_id"] != profiling_session_id
            or payload["scope_key"] != scope_key
            or type(payload["base_profile_version"]) is not int
            or payload["base_profile_version"] < 0
            or type(payload["draft_digest"]) is not str
            or len(payload["draft_digest"]) != 64
            or type(payload["idempotency_key"]) is not str
            or expires_at <= now
        ):
            raise ReviewPreparePresentationRejected
        try:
            work, profile = _owned_work(session, account_id, profiling_session_id)
            if (
                work.status not in {"ACTIVE", "PAUSED"}
                or _as_utc(work.retention_expires_at) <= now
                or profile.version != payload["base_profile_version"]
                or work.base_profile_version != payload["base_profile_version"]
            ):
                raise ReviewPreparePresentationRejected
            batch = self._preparation.prepare_for_scope(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                scope_key=scope_key,
                base_profile_version=payload["base_profile_version"],
                idempotency_key=payload["idempotency_key"],
                now=now,
            )
            items = tuple(
                session.scalars(
                    select(ProfilingReviewItem)
                    .where(ProfilingReviewItem.batch_id == batch.id)
                    .order_by(ProfilingReviewItem.position)
                )
            )
            if _digest(items) != payload["draft_digest"]:
                raise ReviewPreparePresentationRejected
            return batch
        except (
            ProfilingUnavailable,
            ReviewUnavailable,
            ReviewStale,
            ReviewIdempotencyConflict,
            ValueError,
        ) as exc:
            raise ReviewPreparePresentationRejected from exc


def _drafts(
    session: Session, account_id: str, profiling_session_id: str, scope_key: str
) -> tuple[ProfilingDraft, ...]:
    return tuple(
        session.scalars(
            select(ProfilingDraft)
            .where(
                ProfilingDraft.account_id == account_id,
                ProfilingDraft.session_id == profiling_session_id,
                ProfilingDraft.scope_key == scope_key,
                ProfilingDraft.status == "DRAFT",
            )
            .order_by(ProfilingDraft.created_at, ProfilingDraft.id)
            .limit(6)
        )
    )


def _digest(rows: tuple[ProfilingDraft, ...] | tuple[ProfilingReviewItem, ...]) -> str:
    body = [
        {
            "draft_id": row.id if isinstance(row, ProfilingDraft) else row.draft_id,
            "source_input_id": row.source_input_id,
            "claim_type": row.claim_type,
            "exact_text": row.exact_text,
            "source_content_hash": row.source_content_hash,
        }
        for row in rows
    ]
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReviewPreparePresentationRejected
    return value.astimezone(UTC)


def _require_identity(
    account_id: str, browser_session_id: str, profiling_session_id: str, scope_key: str
) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(profiling_session_id, str)
        or not profiling_session_id
        or not isinstance(scope_key, str)
        or not scope_key
    ):
        raise ReviewPreparePresentationRejected

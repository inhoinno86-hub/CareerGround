"""Synthetic browser form for explicitly turning user bullets into temporary drafts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.claim_review_workspace import ReviewUnavailable
from careerground.domain.profiling_draft_extraction import (
    DraftSpanRejected,
    extract_explicit_bullet_spans,
    propose_explicit_bullet_drafts_once,
    validate_draft_spans,
)
from careerground.domain.profiling_workspace import (
    ProfilingExpired,
    ProfilingUnavailable,
    get_profiling_session,
)
from careerground.storage.models import ProfilingDraft, ProfilingInput

BULLET_TOKEN_TTL = timedelta(minutes=3)
_SCOPE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profiling_session_id",
        "source_input_id",
        "source_hash",
        "protocol_cycle",
        "base_profile_version",
        "expires_at",
    }
)


class BulletPresentationRejected(Exception):
    """The source, selected scope or explicit browser intent is unavailable."""


@dataclass(frozen=True)
class BulletPresentation:
    profiling_session_id: str
    source_input_id: str
    exact_bullets: tuple[str, ...]
    bullet_token: str


class BulletPresentationService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        source_input_id: str,
        now: datetime,
    ) -> BulletPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profiling_session_id, source_input_id)
        try:
            work = get_profiling_session(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                now=now,
            )
        except (ProfilingExpired, ProfilingUnavailable) as exc:
            raise BulletPresentationRejected from exc
        if work.base_profile_version != work.current_profile_version:
            raise BulletPresentationRejected
        source = _source(session, account_id, profiling_session_id, source_input_id)
        if source is None or source.protocol_cycle != work.protocol_cycle:
            raise BulletPresentationRejected
        try:
            candidates = validate_draft_spans(
                source.body, extract_explicit_bullet_spans(source.body)
            )
        except DraftSpanRejected as exc:
            raise BulletPresentationRejected from exc
        payload = {
            "purpose": "EXPLICIT_BULLET_DRAFT_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profiling_session_id": profiling_session_id,
            "source_input_id": source_input_id,
            "source_hash": hashlib.sha256(source.body.encode()).hexdigest(),
            "protocol_cycle": work.protocol_cycle,
            "base_profile_version": work.base_profile_version,
            "expires_at": min(now + BULLET_TOKEN_TTL, work.retention_expires_at).isoformat(),
        }
        return BulletPresentation(
            profiling_session_id,
            source_input_id,
            tuple(candidate.exact_text for candidate in candidates),
            self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        source_input_id: str,
        scope_key: str,
        bullet_token: str,
        now: datetime,
    ) -> tuple[ProfilingDraft, ...]:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profiling_session_id, source_input_id)
        if not isinstance(scope_key, str) or not _SCOPE.fullmatch(scope_key):
            raise BulletPresentationRejected
        try:
            payload = self._tokens.verify(bullet_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise BulletPresentationRejected from exc
        if (
            payload["purpose"] != "EXPLICIT_BULLET_DRAFT_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profiling_session_id"] != profiling_session_id
            or payload["source_input_id"] != source_input_id
            or type(payload["source_hash"]) is not str
            or type(payload["protocol_cycle"]) is not int
            or type(payload["base_profile_version"]) is not int
            or expires_at <= now
        ):
            raise BulletPresentationRejected
        try:
            work = get_profiling_session(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                now=now,
            )
        except (ProfilingExpired, ProfilingUnavailable) as exc:
            raise BulletPresentationRejected from exc
        source = _source(session, account_id, profiling_session_id, source_input_id)
        if (
            source is None
            or source.protocol_cycle != payload["protocol_cycle"]
            or work.protocol_cycle != payload["protocol_cycle"]
            or work.base_profile_version != payload["base_profile_version"]
            or work.current_profile_version != payload["base_profile_version"]
            or hashlib.sha256(source.body.encode()).hexdigest() != payload["source_hash"]
        ):
            raise BulletPresentationRejected
        try:
            return propose_explicit_bullet_drafts_once(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                source_input_id=source_input_id,
                scope_key=scope_key,
                now=now,
            )
        except (ReviewUnavailable, DraftSpanRejected, ValueError) as exc:
            raise BulletPresentationRejected from exc


def _source(
    session: Session, account_id: str, profiling_session_id: str, source_input_id: str
) -> ProfilingInput | None:
    return session.scalar(
        select(ProfilingInput).where(
            ProfilingInput.id == source_input_id,
            ProfilingInput.account_id == account_id,
            ProfilingInput.session_id == profiling_session_id,
            ProfilingInput.content_kind == "USER_STATEMENT",
        )
    )


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise BulletPresentationRejected
    return value.astimezone(UTC)


def _require_identity(
    account_id: str, browser_session_id: str, profiling_session_id: str, source_input_id: str
) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(profiling_session_id, str)
        or not profiling_session_id
        or not isinstance(source_input_id, str)
        or not source_input_id
    ):
        raise BulletPresentationRejected

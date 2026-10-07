"""Explicit single-input browser form for a temporary synthetic task session."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.profiling_workspace import (
    InputKind,
    ProfilingExpired,
    ProfilingIdempotencyConflict,
    ProfilingPaused,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    append_explicit_profiling_input,
    get_profiling_session,
)
from careerground.storage.models import ProfilingInput

INPUT_TOKEN_TTL = timedelta(minutes=10)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profiling_session_id",
        "content_kind",
        "base_profile_version",
        "idempotency_key",
        "expires_at",
    }
)


class ProfilingInputFormRejected(Exception):
    """The task input form or active workspace is unavailable."""


@dataclass(frozen=True)
class ProfilingInputForm:
    profiling_session_id: str
    content_kind: InputKind
    base_profile_version: int
    retention_expires_at: datetime
    input_token: str


class ProfilingInputFormService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        content_kind: InputKind = InputKind.USER_STATEMENT,
        now: datetime,
    ) -> ProfilingInputForm:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        if type(content_kind) is not InputKind or content_kind not in {
            InputKind.USER_STATEMENT,
            InputKind.CORRECTION,
        }:
            raise ProfilingInputFormRejected
        try:
            view = get_profiling_session(
                session, account_id=account_id, profiling_session_id=profiling_session_id, now=now
            )
        except (ProfilingUnavailable, ProfilingExpired) as exc:
            raise ProfilingInputFormRejected from exc
        if view.status != "ACTIVE" or view.base_profile_version != view.current_profile_version:
            raise ProfilingInputFormRejected
        payload = {
            "purpose": "PROFILING_INPUT_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profiling_session_id": profiling_session_id,
            "content_kind": content_kind.value,
            "base_profile_version": view.base_profile_version,
            "idempotency_key": secrets.token_urlsafe(18),
            "expires_at": min(now + INPUT_TOKEN_TTL, view.retention_expires_at).isoformat(),
        }
        return ProfilingInputForm(
            profiling_session_id,
            content_kind,
            view.base_profile_version,
            view.retention_expires_at,
            self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        content_kind: InputKind = InputKind.USER_STATEMENT,
        input_token: str,
        content: str,
        now: datetime,
    ) -> ProfilingInput:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        if type(content_kind) is not InputKind or content_kind not in {
            InputKind.USER_STATEMENT,
            InputKind.CORRECTION,
        }:
            raise ProfilingInputFormRejected
        try:
            payload = self._tokens.verify(input_token, expected_keys=_TOKEN_KEYS)
        except BrowserFormTokenRejected as exc:
            raise ProfilingInputFormRejected from exc
        if (
            payload["purpose"] != "PROFILING_INPUT_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profiling_session_id"] != profiling_session_id
            or payload["content_kind"] != content_kind.value
            or type(payload["base_profile_version"]) is not int
            or payload["base_profile_version"] < 0
            or type(payload["idempotency_key"]) is not str
        ):
            raise ProfilingInputFormRejected
        try:
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (TypeError, ValueError) as exc:
            raise ProfilingInputFormRejected from exc
        if expires_at <= now:
            raise ProfilingInputFormRejected
        try:
            return append_explicit_profiling_input(
                session,
                account_id=account_id,
                profiling_session_id=profiling_session_id,
                base_profile_version=payload["base_profile_version"],
                content=content,
                content_kind=content_kind,
                idempotency_key=payload["idempotency_key"],
                now=now,
            )
        except (
            ProfilingUnavailable,
            ProfilingExpired,
            ProfilingPaused,
            ProfilingValidationError,
            ProfilingVersionConflict,
            ProfilingIdempotencyConflict,
        ) as exc:
            raise ProfilingInputFormRejected from exc


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProfilingInputFormRejected
    return value.astimezone(UTC)


def _require_browser_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise ProfilingInputFormRejected

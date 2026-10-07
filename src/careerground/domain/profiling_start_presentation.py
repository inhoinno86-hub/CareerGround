"""Explicit browser-start intent for synthetic temporary profiling sessions."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.profiling_workspace import (
    ProfilingExpired,
    ProfilingIdempotencyConflict,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    start_profiling_session,
)
from careerground.storage.models import Account, CareerProfile, ProfilingSession

START_TOKEN_TTL = timedelta(minutes=10)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profile_id",
        "profile_version",
        "idempotency_key",
        "expires_at",
    }
)


class ProfilingStartRejected(Exception):
    """The start form, active profile or browser intent is unavailable."""


@dataclass(frozen=True)
class ExistingProfilingSession:
    session_id: str
    status: str
    retention_expires_at: datetime


@dataclass(frozen=True)
class ProfilingStartView:
    profile_id: str
    profile_version: int
    existing_sessions: tuple[ExistingProfilingSession, ...]
    start_token: str


class ProfilingStartService:
    """Bind one explicit start action to a browser session and profile version."""

    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        now: datetime,
    ) -> ProfilingStartView:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        profile = _active_profile(session, account_id)
        if profile is None:
            raise ProfilingStartRejected
        existing = tuple(
            ExistingProfilingSession(work.id, work.status, _stored_utc(work.retention_expires_at))
            for work in session.scalars(
                select(ProfilingSession)
                .where(
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.profile_id == profile.id,
                    ProfilingSession.status.in_(("ACTIVE", "PAUSED")),
                    ProfilingSession.retention_expires_at > now,
                )
                .order_by(ProfilingSession.created_at.desc(), ProfilingSession.id)
                .limit(10)
            )
        )
        payload = {
            "purpose": "PROFILING_START_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profile_id": profile.id,
            "profile_version": profile.version,
            "idempotency_key": secrets.token_urlsafe(18),
            "expires_at": (now + START_TOKEN_TTL).isoformat(),
        }
        return ProfilingStartView(profile.id, profile.version, existing, self._tokens.sign(payload))

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        start_token: str,
        now: datetime,
    ) -> ProfilingSession:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(start_token, expected_keys=_TOKEN_KEYS)
        except BrowserFormTokenRejected as exc:
            raise ProfilingStartRejected from exc
        if (
            payload["purpose"] != "PROFILING_START_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or type(payload["profile_id"]) is not str
            or not payload["profile_id"]
            or type(payload["profile_version"]) is not int
            or payload["profile_version"] < 0
            or type(payload["idempotency_key"]) is not str
        ):
            raise ProfilingStartRejected
        try:
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (TypeError, ValueError) as exc:
            raise ProfilingStartRejected from exc
        if expires_at <= now:
            raise ProfilingStartRejected
        try:
            return start_profiling_session(
                session,
                account_id=account_id,
                profile_id=payload["profile_id"],
                base_profile_version=payload["profile_version"],
                idempotency_key=payload["idempotency_key"],
                now=now,
            )
        except (
            ProfilingUnavailable,
            ProfilingExpired,
            ProfilingIdempotencyConflict,
            ProfilingValidationError,
            ProfilingVersionConflict,
        ) as exc:
            raise ProfilingStartRejected from exc


def _active_profile(session: Session, account_id: str) -> CareerProfile | None:
    return session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
    )


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProfilingStartRejected
    return value.astimezone(UTC)


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _require_browser_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise ProfilingStartRejected

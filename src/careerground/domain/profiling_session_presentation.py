"""Explicit pause and resume forms for an isolated synthetic browser session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.profiling_workspace import (
    AUTO_PAUSE_AFTER,
    ProfilingExpired,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    _as_utc,
    _ensure_available,
    _owned_work,
    get_profiling_session,
    pause_profiling_session,
    resume_profiling_session,
)

SESSION_ACTION_TOKEN_TTL = timedelta(minutes=10)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "action",
        "account_id",
        "browser_session_id",
        "profiling_session_id",
        "base_profile_version",
        "last_activity_at",
        "expires_at",
    }
)


class ProfilingSessionActionRejected(Exception):
    """The browser intent or owned temporary session is unavailable."""


@dataclass(frozen=True)
class ProfilingSessionActionForm:
    action: str
    token: str


class ProfilingSessionActionService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        now: datetime,
    ) -> ProfilingSessionActionForm:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        try:
            view = get_profiling_session(
                session, account_id=account_id, profiling_session_id=profiling_session_id, now=now
            )
        except (ProfilingUnavailable, ProfilingExpired) as exc:
            raise ProfilingSessionActionRejected from exc
        if view.base_profile_version != view.current_profile_version:
            raise ProfilingSessionActionRejected
        action = "pause" if view.status == "ACTIVE" else "resume"
        if view.status not in {"ACTIVE", "PAUSED"}:
            raise ProfilingSessionActionRejected
        payload = {
            "purpose": "PROFILING_SESSION_ACTION_V1",
            "action": action,
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profiling_session_id": profiling_session_id,
            "base_profile_version": view.base_profile_version,
            "last_activity_at": view.last_activity_at.isoformat(),
            "expires_at": min(
                now + SESSION_ACTION_TOKEN_TTL, view.retention_expires_at
            ).isoformat(),
        }
        return ProfilingSessionActionForm(action, self._tokens.sign(payload))

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profiling_session_id: str,
        action: str,
        action_token: str,
        now: datetime,
    ) -> None:
        now = _aware_utc(now)
        _require_browser_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(action_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
            previous_activity = _aware_utc(datetime.fromisoformat(payload["last_activity_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ProfilingSessionActionRejected from exc
        if (
            payload["purpose"] != "PROFILING_SESSION_ACTION_V1"
            or action not in {"pause", "resume"}
            or payload["action"] != action
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profiling_session_id"] != profiling_session_id
            or type(payload["base_profile_version"]) is not int
            or payload["base_profile_version"] < 0
            or expires_at <= now
        ):
            raise ProfilingSessionActionRejected
        try:
            work, profile = _owned_work(session, account_id, profiling_session_id)
            _ensure_available(work, now)
            if (
                profile.version != payload["base_profile_version"]
                or work.base_profile_version != payload["base_profile_version"]
                or _as_utc(work.last_activity_at) != previous_activity
            ):
                raise ProfilingSessionActionRejected
            if action == "pause":
                pause_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=now,
                )
            else:
                if work.status == "ACTIVE" and now - previous_activity < AUTO_PAUSE_AFTER:
                    raise ProfilingSessionActionRejected
                resume_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    base_profile_version=payload["base_profile_version"],
                    now=now,
                )
        except (
            ProfilingUnavailable,
            ProfilingExpired,
            ProfilingValidationError,
            ProfilingVersionConflict,
        ) as exc:
            raise ProfilingSessionActionRejected from exc


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProfilingSessionActionRejected
    return value.astimezone(UTC)


def _require_browser_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise ProfilingSessionActionRejected

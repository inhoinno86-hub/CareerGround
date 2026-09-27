"""Explicit profiling-session lifecycle and query-time temporary-data guards."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.storage.models import Account, CareerProfile, ProfilingInput, ProfilingSession

RETENTION = timedelta(days=90)
AUTO_PAUSE_AFTER = timedelta(minutes=30)
MAX_INPUT_CHARS = 20_000
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")


class InputKind(StrEnum):
    USER_STATEMENT = "USER_STATEMENT"
    SELECTED_CHAT_EXCERPT = "SELECTED_CHAT_EXCERPT"
    PASTED_DOCUMENT_EXCERPT = "PASTED_DOCUMENT_EXCERPT"
    CORRECTION = "CORRECTION"


class ProfilingUnavailable(Exception):
    """Session/profile is absent from this active account's view."""


class ProfilingExpired(Exception):
    """Temporary session data is no longer available by retention policy."""


class ProfilingPaused(Exception):
    """Explicit resume is required before new input is accepted."""


class ProfilingVersionConflict(Exception):
    """The current profile version differs from the session's base version."""


class ProfilingValidationError(Exception):
    """Input is not a bounded, explicitly submitted task statement."""


class ProfilingIdempotencyConflict(Exception):
    """A reused idempotency key refers to different content."""


@dataclass(frozen=True)
class ProfilingSessionView:
    """Owner-scoped metadata only; never includes an input body or chat history."""

    id: str
    profile_id: str
    status: str
    base_profile_version: int
    current_profile_version: int
    last_activity_at: datetime
    retention_expires_at: datetime


def start_profiling_session(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    base_profile_version: int,
    now: datetime,
) -> ProfilingSession:
    """Create a workspace only for an explicit start request from an authenticated adapter."""

    now = _require_utc(now)
    try:
        profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
    except ResourceNotFound as exc:
        raise ProfilingUnavailable from exc
    if profile.version != base_profile_version:
        raise ProfilingVersionConflict
    work = ProfilingSession(
        id=str(uuid4()),
        account_id=account_id,
        profile_id=profile_id,
        status="ACTIVE",
        base_profile_version=profile.version,
        created_at=now,
        last_activity_at=now,
        retention_expires_at=now + RETENTION,
    )
    session.add(work)
    return work


def append_explicit_profiling_input(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    base_profile_version: int,
    content: str,
    content_kind: InputKind,
    idempotency_key: str,
    now: datetime,
) -> ProfilingInput:
    """Accept one task-scoped input; never accepts a general-chat message array."""

    now = _require_utc(now)
    if (
        not isinstance(content, str)
        or not content.strip()
        or len(content) > MAX_INPUT_CHARS
        or not isinstance(idempotency_key, str)
        or not _IDEMPOTENCY_KEY.fullmatch(idempotency_key)
    ):
        raise ProfilingValidationError
    try:
        kind = InputKind(content_kind)
    except (TypeError, ValueError) as exc:
        raise ProfilingValidationError from exc
    work, profile = _owned_work(session, account_id, profiling_session_id)
    _ensure_available(work, now)
    if profile.version != base_profile_version or work.base_profile_version != base_profile_version:
        raise ProfilingVersionConflict
    existing = session.scalar(
        select(ProfilingInput).where(
            ProfilingInput.session_id == work.id,
            ProfilingInput.account_id == account_id,
            ProfilingInput.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.body != content or existing.content_kind != kind.value:
            raise ProfilingIdempotencyConflict
        return existing
    if work.status != "ACTIVE" or now - _as_utc(work.last_activity_at) >= AUTO_PAUSE_AFTER:
        raise ProfilingPaused

    item = ProfilingInput(
        id=str(uuid4()),
        account_id=account_id,
        session_id=work.id,
        idempotency_key=idempotency_key,
        content_kind=kind.value,
        body=content,
        created_at=now,
    )
    session.add(item)
    work.last_activity_at = now
    work.retention_expires_at = now + RETENTION
    return item


def resume_profiling_session(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    base_profile_version: int,
    now: datetime,
) -> ProfilingSession:
    """An explicit resume counts as activity; automatic pause does not."""

    now = _require_utc(now)
    work, profile = _owned_work(session, account_id, profiling_session_id)
    _ensure_available(work, now)
    if profile.version != base_profile_version or work.base_profile_version != base_profile_version:
        raise ProfilingVersionConflict
    if work.status == "ACTIVE" and now - _as_utc(work.last_activity_at) < AUTO_PAUSE_AFTER:
        raise ProfilingValidationError("session is not paused")
    work.status = "ACTIVE"
    work.last_activity_at = now
    work.retention_expires_at = now + RETENTION
    return work


def list_profiling_inputs(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> list[ProfilingInput]:
    """Deny expired/deleting data at query time, even before a cleanup worker runs."""

    work, _profile = _owned_work(session, account_id, profiling_session_id)
    _ensure_available(work, _require_utc(now))
    return list(
        session.scalars(
            select(ProfilingInput)
            .where(
                ProfilingInput.account_id == account_id,
                ProfilingInput.session_id == profiling_session_id,
            )
            .order_by(ProfilingInput.created_at, ProfilingInput.id)
        )
    )


def get_profiling_session(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> ProfilingSessionView:
    """Read only task metadata and report the effective inactivity pause."""

    now = _require_utc(now)
    work, profile = _owned_work(session, account_id, profiling_session_id, for_update=False)
    _ensure_available(work, now)
    status = work.status
    if status == "ACTIVE" and now - _as_utc(work.last_activity_at) >= AUTO_PAUSE_AFTER:
        status = "PAUSED"
    return ProfilingSessionView(
        id=work.id,
        profile_id=work.profile_id,
        status=status,
        base_profile_version=work.base_profile_version,
        current_profile_version=profile.version,
        last_activity_at=_as_utc(work.last_activity_at),
        retention_expires_at=_as_utc(work.retention_expires_at),
    )


def pause_profiling_session(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> ProfilingSession:
    """Explicit user pause; repeated pauses do not extend temporary-data retention."""

    now = _require_utc(now)
    work, _profile = _owned_work(session, account_id, profiling_session_id)
    _ensure_available(work, now)
    work.status = "PAUSED"
    return work


def pause_inactive_sessions(session: Session, *, now: datetime) -> int:
    """Scheduler transition; never changes last_activity_at or retention_expires_at."""

    now = _require_utc(now)
    result = session.execute(
        update(ProfilingSession)
        .where(
            ProfilingSession.status == "ACTIVE",
            ProfilingSession.last_activity_at <= now - AUTO_PAUSE_AFTER,
            ProfilingSession.retention_expires_at > now,
        )
        .values(status="PAUSED")
    )
    return result.rowcount or 0


def _owned_work(
    session: Session, account_id: str, profiling_session_id: str, *, for_update: bool = True
) -> tuple[ProfilingSession, CareerProfile]:
    statement = (
        select(ProfilingSession, CareerProfile)
        .join(Account, Account.id == ProfilingSession.account_id)
        .join(CareerProfile, CareerProfile.id == ProfilingSession.profile_id)
        .where(
            ProfilingSession.id == profiling_session_id,
            ProfilingSession.account_id == account_id,
            CareerProfile.account_id == account_id,
            Account.status == "ACTIVE",
            CareerProfile.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update(of=ProfilingSession)
    row = session.execute(statement).first()
    if row is None:
        raise ProfilingUnavailable
    return row[0], row[1]


def _ensure_available(work: ProfilingSession, now: datetime) -> None:
    if work.status in {"DELETING", "ERASED"}:
        raise ProfilingUnavailable
    if work.status == "EXPIRED" or now >= _as_utc(work.retention_expires_at):
        raise ProfilingExpired


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProfilingValidationError("aware UTC datetime required")
    return value.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    # SQLite test doubles drop tzinfo; production PostgreSQL preserves it.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

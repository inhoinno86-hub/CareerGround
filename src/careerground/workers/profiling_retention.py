"""Bounded physical expiry of temporary profiling data, without a scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from careerground.storage.models import ProfilingInput, ProfilingSession

MAX_BATCH_SIZE = 1_000


@dataclass(frozen=True)
class ExpiryBatchResult:
    sessions_deleted: int
    inputs_deleted: int


def delete_expired_profiling_batch(
    session: Session, *, now: datetime, limit: int = 100
) -> ExpiryBatchResult:
    """Delete one bounded batch within the caller's transaction; never commit here.

    Only independently expired temporary workspaces are eligible. A future
    account/profile deletion worker owns sessions already marked DELETING.
    PostgreSQL skips rows locked by a concurrent input/resume transaction.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError("limit must be between 1 and 1000")
    now = now.astimezone(UTC)
    ids = list(
        session.scalars(
            select(ProfilingSession.id)
            .where(
                ProfilingSession.status.in_(("ACTIVE", "PAUSED", "EXPIRED")),
                ProfilingSession.retention_expires_at <= now,
            )
            .order_by(ProfilingSession.retention_expires_at, ProfilingSession.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    if not ids:
        return ExpiryBatchResult(sessions_deleted=0, inputs_deleted=0)

    inputs = session.execute(delete(ProfilingInput).where(ProfilingInput.session_id.in_(ids)))
    workspaces = session.execute(delete(ProfilingSession).where(ProfilingSession.id.in_(ids)))
    return ExpiryBatchResult(
        sessions_deleted=workspaces.rowcount or 0,
        inputs_deleted=inputs.rowcount or 0,
    )

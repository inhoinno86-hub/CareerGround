"""Offline synthetic version deletion; no network/provider adapter is installed."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.private_objects import (
    PrivateObjectInventoryMismatch,
    SyntheticVersionStore,
)
from careerground.storage.models import PrivateObject, PrivateObjectVersion
from careerground.workers.outbox import apply_event, due_events, record_failure


def apply_synthetic_version_delete(
    session: Session, *, version_id: str, adapter: SyntheticVersionStore
) -> None:
    """Idempotent in-process rehearsal; never pass a real network adapter here."""

    version = session.get(PrivateObjectVersion, version_id)
    if version is None:
        raise ValueError("object version is missing")
    obj = session.get(PrivateObject, version.object_id)
    if obj is None or obj.status != "DELETING" or version.status != "DELETE_PENDING":
        raise ValueError("object version is not pending deletion")
    known = set(
        session.scalars(
            select(PrivateObjectVersion.provider_version_id).where(
                PrivateObjectVersion.object_id == obj.id
            )
        )
    )
    actual = adapter.list_versions(obj.id)
    if not actual.issubset(known):
        raise PrivateObjectInventoryMismatch
    if version.provider_version_id in actual:
        adapter.delete_version(obj.id, version.provider_version_id)
    if version.provider_version_id in adapter.list_versions(obj.id):
        raise PrivateObjectInventoryMismatch
    version.status = "DELETED"


def run_synthetic_version_cycle(
    session_factory: Callable[[], Session],
    *,
    adapter: SyntheticVersionStore,
    now: datetime,
    limit: int = 20,
) -> tuple[int, int]:
    """Bounded local fake-worker loop; event, receipt and metadata commit together."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware datetime required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("invalid object-worker limit")
    now = now.astimezone(UTC)
    done = failed = 0
    for _ in range(limit):
        with session_factory() as session:
            events = due_events(session, now=now, limit=1, event_type="PRIVATE_OBJECT_DELETE")
            if not events:
                break
            event_id = events[0].id
            try:
                apply_event(
                    session,
                    events[0],
                    now=now,
                    handlers={
                        "PRIVATE_OBJECT_DELETE": lambda db, ref: apply_synthetic_version_delete(
                            db, version_id=ref, adapter=adapter
                        )
                    },
                )
                session.commit()
                done += 1
            except Exception:  # noqa: BLE001 - synthetic failure still needs durable retry state
                session.rollback()
                with session_factory() as retry:
                    record_failure(retry, event_id=event_id, now=now)
                    retry.commit()
                failed += 1
    return done, failed

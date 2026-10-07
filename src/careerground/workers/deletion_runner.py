"""Bounded internal processor for synthetic local deletion work."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from careerground.domain.deletion_execution import apply_deletion_work
from careerground.storage.models import DeletionRequest, DeletionWorkItem, OutboxEvent
from careerground.workers.outbox import apply_event, due_events, record_failure


def run_deletion_cycle(
    session_factory: Callable[[], Session], *, now: datetime, limit: int = 20
) -> tuple[int, int]:
    """Each event commits its local mutation and receipt together; no provider calls."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware datetime required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("invalid deletion work limit")
    now = now.astimezone(UTC)
    done = failed = 0
    for _ in range(limit):
        with session_factory() as session:
            events = due_events(session, now=now, limit=1, event_type="DELETION_WORK")
            if not events:
                break
            event_id = events[0].id
            try:
                apply_event(
                    session,
                    events[0],
                    now=now,
                    handlers={"DELETION_WORK": apply_deletion_work},
                )
                session.commit()
                done += 1
            except Exception:  # noqa: BLE001 - any failed handler must be retried
                session.rollback()
                with session_factory() as retry:
                    event = record_failure(retry, event_id=event_id, now=now)
                    if event.status == "DEAD":
                        _mark_failed_work(retry, event)
                    retry.commit()
                failed += 1
    return done, failed


def _mark_failed_work(session: Session, event: OutboxEvent) -> None:
    item = session.get(DeletionWorkItem, event.target_id)
    if item is None:
        return
    item.status = "FAILED"
    request = session.get(DeletionRequest, item.request_id)
    if request is not None:
        request.status = "FAILED"

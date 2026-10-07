"""Reference-only outbox delivery within caller-owned database transactions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.models import OutboxEvent, OutboxReceipt

MAX_ATTEMPTS = 5
MAX_CLAIM = 100
EVENT_TYPES = frozenset({"RETENTION_SWEEP", "DELETION_WORK", "PRIVATE_OBJECT_DELETE"})


def enqueue_event(
    session: Session,
    *,
    event_type: str,
    target_id: str,
    handler_id: str,
    now: datetime,
) -> OutboxEvent:
    """Stage an event alongside domain writes; the caller must commit or roll back."""

    now = _utc(now)
    if (
        event_type not in EVENT_TYPES
        or not isinstance(target_id, str)
        or not isinstance(handler_id, str)
    ):
        raise ValueError("unsupported event reference")
    if event_type in {"DELETION_WORK", "PRIVATE_OBJECT_DELETE"}:
        try:
            canonical_id = str(UUID(target_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("deletion target must be an opaque UUID") from exc
        expected_prefix = "deletion" if event_type == "DELETION_WORK" else "private-object"
        if canonical_id != target_id or handler_id != f"{expected_prefix}:{target_id}":
            raise ValueError("invalid handler reference")
    elif target_id != "profiling" or not _retention_handler(handler_id):
        raise ValueError("invalid retention handler reference")
    event = OutboxEvent(
        id=str(uuid4()),
        event_type=event_type,
        target_id=target_id,
        handler_id=handler_id,
        status="PENDING",
        attempts=0,
        next_attempt_at=now,
        created_at=now,
    )
    session.add(event)
    return event


def due_events(
    session: Session, *, now: datetime, limit: int = 20, event_type: str | None = None
) -> list[OutboxEvent]:
    """Lock a bounded batch; locks remain held until the caller ends its transaction."""

    now = _utc(now)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_CLAIM:
        raise ValueError("invalid outbox batch limit")
    if event_type is not None and event_type not in EVENT_TYPES:
        raise ValueError("unsupported event type")
    statement = select(OutboxEvent).where(
        OutboxEvent.status == "PENDING", OutboxEvent.next_attempt_at <= now
    )
    if event_type is not None:
        statement = statement.where(OutboxEvent.event_type == event_type)
    return list(
        session.scalars(
            statement.order_by(OutboxEvent.next_attempt_at, OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
    )


def apply_event(
    session: Session,
    event: OutboxEvent,
    *,
    now: datetime,
    handlers: Mapping[str, Callable[[Session, str], None]],
) -> bool:
    """Apply one handler and receipt atomically; never commit or call providers here."""

    now = _utc(now)
    if event.status != "PENDING" or event.next_attempt_at.replace(tzinfo=UTC) > now:
        raise ValueError("event is not due")
    if session.get(OutboxReceipt, event.handler_id) is not None:
        event.status = "DONE"
        return False
    handler = handlers.get(event.event_type)
    if handler is None:
        raise ValueError("unsupported event handler")
    handler(session, event.target_id)
    session.add(OutboxReceipt(handler_id=event.handler_id, applied_at=now))
    event.status = "DONE"
    return True


def record_failure(session: Session, *, event_id: str, now: datetime) -> OutboxEvent:
    """After rolling back a failed handler transaction, record a bounded retry."""

    now = _utc(now)
    event = session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if event is None or event.status != "PENDING":
        raise ValueError("pending event required")
    event.attempts += 1
    if event.attempts >= MAX_ATTEMPTS:
        event.status = "DEAD"
    else:
        event.next_attempt_at = now + timedelta(seconds=min(3600, 2**event.attempts * 10))
    return event


def dead_events(session: Session, *, limit: int = 100) -> list[OutboxEvent]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_CLAIM:
        raise ValueError("invalid dead-letter limit")
    return list(
        session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "DEAD")
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(limit)
        )
    )


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware datetime required")
    return value.astimezone(UTC)


def _retention_handler(handler_id: str) -> bool:
    parts = handler_id.split(":")
    return (
        len(parts) == 3
        and parts[0] == "retention"
        and parts[1].isdigit()
        and parts[2].isdigit()
        and len(parts[1]) <= 12
        and len(parts[2]) <= 2
    )

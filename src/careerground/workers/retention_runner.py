"""Test-database-only scheduler boundary for bounded profiling expiry."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from careerground.storage.models import OutboxEvent
from careerground.workers.outbox import apply_event, due_events, enqueue_event, record_failure
from careerground.workers.profiling_retention import delete_expired_profiling_batch

MAX_BATCHES = 10
MAX_PER_BATCH = 100
SLOT_SECONDS = 3600


def schedule_retention(session: Session, *, now: datetime, batches: int = 1) -> list[OutboxEvent]:
    """Caller commits scheduled batches; one slot can contain at most ten sweeps."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware datetime required")
    if isinstance(batches, bool) or not isinstance(batches, int) or not 1 <= batches <= MAX_BATCHES:
        raise ValueError("invalid batch count")
    slot = int(now.astimezone(UTC).timestamp()) // SLOT_SECONDS
    scheduled = []
    for index in range(batches):
        handler_id = f"retention:{slot}:{index}"
        existing = session.scalar(select(OutboxEvent).where(OutboxEvent.handler_id == handler_id))
        if existing is not None:
            scheduled.append(existing)
        else:
            try:
                with session.begin_nested():
                    candidate = enqueue_event(
                        session,
                        event_type="RETENTION_SWEEP",
                        target_id="profiling",
                        handler_id=handler_id,
                        now=now,
                    )
                    session.flush()
                scheduled.append(candidate)
            except IntegrityError:
                # Another scheduler committed this slot while our savepoint waited.
                scheduled.append(
                    session.scalar(select(OutboxEvent).where(OutboxEvent.handler_id == handler_id))
                )
    return scheduled


def run_retention_cycle(
    session_factory: Callable[[], Session],
    *,
    now: datetime,
    batches: int = 1,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Internal entrypoint. Only reference/count status leaves the transaction."""

    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= 100
    ):
        raise ValueError("invalid batch size")
    with session_factory() as session:
        schedule_retention(session, now=now, batches=batches)
        session.commit()
    done = failed = 0
    for _ in range(batches):
        with session_factory() as session:
            events = due_events(session, now=now, limit=1, event_type="RETENTION_SWEEP")
            if not events:
                break
            event_id = events[0].id
            try:
                apply_event(
                    session,
                    events[0],
                    now=now,
                    handlers={
                        "RETENTION_SWEEP": lambda db, target: (
                            delete_expired_profiling_batch(db, now=now, limit=batch_size)
                            if target == "profiling"
                            else _unsupported_target()
                        )
                    },
                )
                session.commit()
                done += 1
            except Exception:  # noqa: BLE001 - persist a retry after any failed database handler
                session.rollback()
                with session_factory() as retry:
                    record_failure(retry, event_id=event_id, now=now)
                    retry.commit()
                failed += 1
    return done, failed


def _unsupported_target() -> None:
    raise ValueError("unsupported retention target")


def main() -> None:
    """A deliberate local-only CLI; refuses production and non-test databases."""

    raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL", "")
    if not raw_url:
        raise RuntimeError("explicit CAREERGROUND_TEST_DATABASE_URL required")
    url = make_url(raw_url)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").endswith("_test")
    ):
        raise RuntimeError("refusing non-loopback or non-test database")
    engine = create_engine(url)
    try:
        done, failed = run_retention_cycle(lambda: Session(engine), now=datetime.now(UTC))
        print(f"retention batches_done={done} batches_failed={failed}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""Synthetic transaction, crash, retry and idempotency checks."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.storage.models import Account, Base, OutboxEvent, OutboxReceipt
from careerground.workers.outbox import (
    apply_event,
    dead_events,
    due_events,
    enqueue_event,
    record_failure,
)


class OutboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, tzinfo=UTC)
        self.target = str(uuid4())

    def tearDown(self) -> None:
        self.engine.dispose()

    def enqueue(self, session: Session) -> OutboxEvent:
        session.add(Account(id="acct-a", status="ACTIVE"))
        return enqueue_event(
            session,
            event_type="DELETION_WORK",
            target_id=self.target,
            handler_id=f"deletion:{self.target}",
            now=self.now,
        )

    def test_domain_write_and_event_rollback_or_survive_restart(self) -> None:
        with Session(self.engine) as session:
            self.enqueue(session)
            session.rollback()
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Account)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(OutboxEvent)), 0)
            self.enqueue(session)
            session.commit()
        with Session(self.engine) as restarted:
            self.assertEqual(len(due_events(restarted, now=self.now)), 1)

    def test_crash_during_handler_rolls_back_mutation_and_receipt(self) -> None:
        with Session(self.engine) as session:
            self.enqueue(session)
            session.commit()
        with Session(self.engine) as session:
            event = due_events(session, now=self.now)[0]
            apply_event(
                session,
                event,
                now=self.now,
                handlers={
                    "DELETION_WORK": lambda db, _ref: setattr(
                        db.get(Account, "acct-a"), "status", "DELETING"
                    )
                },
            )
            session.rollback()
        with Session(self.engine) as restarted:
            self.assertEqual(restarted.get(Account, "acct-a").status, "ACTIVE")
            self.assertEqual(restarted.scalar(select(func.count()).select_from(OutboxReceipt)), 0)
            event = due_events(restarted, now=self.now)[0]
            calls = []
            apply_event(
                restarted,
                event,
                now=self.now,
                handlers={
                    "DELETION_WORK": lambda db, _ref: (
                        calls.append(1),
                        setattr(db.get(Account, "acct-a"), "status", "DELETING"),
                    )
                },
            )
            restarted.commit()
        with Session(self.engine) as session:
            event = session.scalar(select(OutboxEvent))
            event.status = "PENDING"  # Simulate a duplicate delivery after a committed receipt.
            session.commit()
            self.assertFalse(
                apply_event(
                    session,
                    due_events(session, now=self.now)[0],
                    now=self.now,
                    handlers={"DELETION_WORK": lambda _db, _ref: calls.append(1)},
                )
            )
            session.commit()
            self.assertEqual(calls, [1])

    def test_retry_backoff_and_dead_letter_are_reference_only(self) -> None:
        with Session(self.engine) as session:
            self.enqueue(session)
            session.commit()
        clock = self.now
        for attempt in range(1, 6):
            with Session(self.engine) as session:
                event = due_events(session, now=clock)[0]
                event_id = event.id
                with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                    apply_event(
                        session,
                        event,
                        now=clock,
                        handlers={
                            "DELETION_WORK": lambda _db, _ref: (_ for _ in ()).throw(
                                RuntimeError("synthetic failure")
                            )
                        },
                    )
                session.rollback()
            with Session(self.engine) as session:
                event = record_failure(session, event_id=event_id, now=clock)
                self.assertEqual(event.attempts, attempt)
                if attempt < 5:
                    clock += timedelta(seconds=2**attempt * 10)
                session.commit()
        with Session(self.engine) as session:
            self.assertEqual(len(dead_events(session)), 1)
            self.assertEqual(due_events(session, now=clock + timedelta(days=1)), [])
            self.assertNotIn("synthetic failure", repr(dead_events(session)[0].__dict__))

    def test_event_contract_rejects_raw_payload_and_unknown_type(self) -> None:
        self.assertEqual(
            {column["name"] for column in inspect(self.engine).get_columns("outbox_events")},
            {
                "id",
                "event_type",
                "target_id",
                "handler_id",
                "status",
                "attempts",
                "next_attempt_at",
                "created_at",
            },
        )
        with Session(self.engine) as session:
            with self.assertRaises(ValueError):
                enqueue_event(
                    session,
                    event_type="PROVIDER_DELETE",
                    target_id=self.target,
                    handler_id=f"deletion:{self.target}",
                    now=self.now,
                )
            with self.assertRaises(ValueError):
                enqueue_event(
                    session,
                    event_type="DELETION_WORK",
                    target_id="raw career sentence with spaces",
                    handler_id="deletion:00000000-0000-4000-8000-000000000001",
                    now=self.now,
                )


if __name__ == "__main__":
    unittest.main()

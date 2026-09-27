"""Bounded retention orchestration on synthetic local rows."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    OutboxEvent,
    ProfilingInput,
    ProfilingSession,
)
from careerground.workers.retention_runner import main, run_retention_cycle


class RetentionRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add(Account(id="acct-a", status="ACTIVE"))
            session.add(CareerProfile(id="profile-a", account_id="acct-a", version=0))
            session.flush()
            for index, (status, offset) in enumerate(
                (("ACTIVE", 0), ("PAUSED", -1), ("ACTIVE", 1), ("DELETING", 0))
            ):
                expiry = self.now + timedelta(days=offset)
                session.add(
                    ProfilingSession(
                        id=f"session-{index}",
                        account_id="acct-a",
                        profile_id="profile-a",
                        status=status,
                        base_profile_version=0,
                        created_at=expiry - timedelta(days=90),
                        last_activity_at=expiry - timedelta(days=90),
                        retention_expires_at=expiry,
                    )
                )
                session.flush()
                session.add(
                    ProfilingInput(
                        id=f"input-{index}",
                        account_id="acct-a",
                        session_id=f"session-{index}",
                        idempotency_key=f"synthetic_input_{index:04d}",
                        content_kind="USER_STATEMENT",
                        body="synthetic source",
                        created_at=expiry - timedelta(days=90),
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_boundary_exclusions_and_repeat_slot(self) -> None:
        factory = lambda: Session(self.engine)
        self.assertEqual(
            run_retention_cycle(factory, now=self.now, batches=2, batch_size=1), (2, 0)
        )
        with factory() as session:
            self.assertEqual(
                set(session.scalars(select(ProfilingSession.id))), {"session-2", "session-3"}
            )
            self.assertEqual(
                set(session.scalars(select(ProfilingInput.id))), {"input-2", "input-3"}
            )
        self.assertEqual(
            run_retention_cycle(factory, now=self.now, batches=2, batch_size=1), (0, 0)
        )
        with factory() as session:
            self.assertEqual(len(list(session.scalars(select(OutboxEvent)))), 2)

    def test_invalid_limits_fail_before_write(self) -> None:
        with self.assertRaises(ValueError):
            run_retention_cycle(lambda: Session(self.engine), now=self.now, batches=11)
        with self.assertRaises(ValueError):
            run_retention_cycle(lambda: Session(self.engine), now=self.now, batch_size=101)

    def test_command_refuses_non_test_or_remote_database(self) -> None:
        for url in (
            "postgresql+psycopg://user:password@127.0.0.1/careerground_prod",
            "postgresql+psycopg://user:password@example.invalid/careerground_test",
            "sqlite:///unsafe_test",
        ):
            with (
                self.subTest(url=url),
                patch.dict("os.environ", {"CAREERGROUND_TEST_DATABASE_URL": url}),
                self.assertRaises(RuntimeError),
            ):
                main()


if __name__ == "__main__":
    unittest.main()

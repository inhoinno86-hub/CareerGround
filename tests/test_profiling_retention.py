"""Synthetic expiry-worker tests; no scheduler or actual user data involved."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)
from careerground.workers.profiling_retention import (
    ExpiryBatchResult,
    delete_expired_profiling_batch,
)


class ProfilingRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add_all(
                [
                    Account(id="acct-a", status="ACTIVE"),
                    Account(id="acct-b", status="ACTIVE"),
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=1),
                ]
            )
            session.flush()
            workspaces = (
                ("expired-a", "acct-a", "profile-a", "ACTIVE", self.now - timedelta(days=1), 2),
                ("expired-b", "acct-b", "profile-b", "PAUSED", self.now, 1),
                ("current-a", "acct-a", "profile-a", "ACTIVE", self.now + timedelta(days=1), 1),
                ("deleting-a", "acct-a", "profile-a", "DELETING", self.now, 1),
            )
            for work_id, account_id, profile_id, status, expiry, _input_count in workspaces:
                session.add(
                    ProfilingSession(
                        id=work_id,
                        account_id=account_id,
                        profile_id=profile_id,
                        status=status,
                        base_profile_version=1,
                        created_at=expiry - timedelta(days=90),
                        last_activity_at=expiry - timedelta(days=90),
                        retention_expires_at=expiry,
                    )
                )
            session.flush()
            for work_id, account_id, _profile_id, _status, expiry, input_count in workspaces:
                for index in range(input_count):
                    session.add(
                        ProfilingInput(
                            id=f"{work_id}-{index}",
                            account_id=account_id,
                            session_id=work_id,
                            idempotency_key=f"synthetic_input_{index:04d}",
                            content_kind="USER_STATEMENT",
                            body="synthetic private statement",
                            created_at=expiry - timedelta(days=90),
                        )
                    )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_bounded_expiry_removes_inputs_and_sessions_only_at_deadline(self) -> None:
        with Session(self.engine) as session:
            first = delete_expired_profiling_batch(session, now=self.now, limit=1)
            self.assertEqual(first, ExpiryBatchResult(sessions_deleted=1, inputs_deleted=2))
            session.commit()

            second = delete_expired_profiling_batch(session, now=self.now, limit=1)
            self.assertEqual(second, ExpiryBatchResult(sessions_deleted=1, inputs_deleted=1))
            session.commit()

            self.assertEqual(
                delete_expired_profiling_batch(session, now=self.now),
                ExpiryBatchResult(sessions_deleted=0, inputs_deleted=0),
            )
            self.assertEqual(
                set(session.scalars(select(ProfilingSession.id))),
                {"current-a", "deleting-a"},
            )
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(CareerProfile)), 2)

    def test_caller_rollback_restores_whole_batch(self) -> None:
        with Session(self.engine) as session:
            self.assertEqual(
                delete_expired_profiling_batch(session, now=self.now),
                ExpiryBatchResult(sessions_deleted=2, inputs_deleted=3),
            )
            session.rollback()
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 4)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 5)

    def test_invalid_clock_or_batch_size_does_not_delete(self) -> None:
        with Session(self.engine) as session:
            for clock, limit in (
                (self.now.replace(tzinfo=None), 1),
                (self.now, 0),
                (self.now, True),
                (self.now, 1_001),
            ):
                with self.subTest(clock=clock, limit=limit), self.assertRaises(ValueError):
                    delete_expired_profiling_batch(session, now=clock, limit=limit)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 4)


if __name__ == "__main__":
    unittest.main()

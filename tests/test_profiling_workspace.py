"""Synthetic explicit-input and 90-day profiling workspace lifecycle checks."""

from __future__ import annotations

import unittest
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.profiling_workspace import (
    AUTO_PAUSE_AFTER,
    RETENTION,
    InputKind,
    ProfilingExpired,
    ProfilingIdempotencyConflict,
    ProfilingPaused,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    append_explicit_profiling_input,
    get_profiling_session,
    list_profiling_inputs,
    pause_inactive_sessions,
    pause_profiling_session,
    resume_profiling_session,
    start_profiling_session,
)
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)


class ProfilingWorkspaceTests(unittest.TestCase):
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
        with Session(self.engine) as session:
            session.add_all(
                [
                    Account(id="acct-a", status="ACTIVE"),
                    Account(id="acct-b", status="ACTIVE"),
                    CareerProfile(id="profile-a", account_id="acct-a", version=2),
                    CareerProfile(id="profile-b", account_id="acct-b", version=4),
                ]
            )
            session.commit()
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)

    def tearDown(self) -> None:
        self.engine.dispose()

    def start(self, session: Session) -> ProfilingSession:
        work = start_profiling_session(
            session,
            account_id="acct-a",
            profile_id="profile-a",
            base_profile_version=2,
            now=self.now,
        )
        session.flush()
        return work

    def append(
        self,
        session: Session,
        work_id: str,
        *,
        now: datetime,
        content: str = "Synthetic career statement",
        key: str = "synthetic_input_0001",
    ) -> ProfilingInput:
        return append_explicit_profiling_input(
            session,
            account_id="acct-a",
            profiling_session_id=work_id,
            base_profile_version=2,
            content=content,
            content_kind=InputKind.USER_STATEMENT,
            idempotency_key=key,
            now=now,
        )

    def test_only_explicit_input_is_stored_and_retry_does_not_extend_retention(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 0)
            first = self.append(session, work.id, now=self.now + timedelta(minutes=10))
            session.commit()
            expected_expiry = self.now + timedelta(minutes=10) + RETENTION
            self.assertEqual(work.retention_expires_at.replace(tzinfo=UTC), expected_expiry)
            retry = self.append(session, work.id, now=self.now + timedelta(minutes=20))
            self.assertEqual(retry.id, first.id)
            self.assertEqual(work.retention_expires_at.replace(tzinfo=UTC), expected_expiry)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 1)
            with self.assertRaises(ProfilingIdempotencyConflict):
                self.append(
                    session,
                    work.id,
                    now=self.now + timedelta(minutes=20),
                    content="Different text",
                )

    def test_start_retry_keeps_one_session_and_original_retention(self) -> None:
        key = "synthetic_start_0001"
        with Session(self.engine) as session:
            first = start_profiling_session(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                base_profile_version=2,
                now=self.now,
                idempotency_key=key,
            )
            session.commit()
            original_expiry = first.retention_expires_at
            retry = start_profiling_session(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                base_profile_version=2,
                now=self.now + timedelta(minutes=5),
                idempotency_key=key,
            )
            self.assertEqual(retry.id, first.id)
            self.assertEqual(retry.retention_expires_at, original_expiry)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 1)
            session.get(CareerProfile, "profile-a").version = 3
            session.flush()
            with self.assertRaises(ProfilingIdempotencyConflict):
                start_profiling_session(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    base_profile_version=3,
                    now=self.now + timedelta(minutes=5),
                    idempotency_key=key,
                )

    def test_auto_pause_does_not_refresh_expiry_and_resume_is_explicit(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            original_expiry = work.retention_expires_at
            self.assertEqual(pause_inactive_sessions(session, now=self.now + AUTO_PAUSE_AFTER), 1)
            session.refresh(work)
            self.assertEqual(work.status, "PAUSED")
            self.assertEqual(work.retention_expires_at.replace(tzinfo=UTC), original_expiry)
            with self.assertRaises(ProfilingPaused):
                self.append(
                    session,
                    work.id,
                    now=self.now + AUTO_PAUSE_AFTER + timedelta(seconds=1),
                )
            resumed_at = self.now + timedelta(minutes=31)
            resume_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                base_profile_version=2,
                now=resumed_at,
            )
            self.assertEqual(work.status, "ACTIVE")
            self.assertEqual(work.retention_expires_at, resumed_at + RETENTION)
            self.append(session, work.id, now=resumed_at + timedelta(minutes=1))
            session.commit()

    def test_explicit_pause_is_idempotent_and_does_not_refresh_retention(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            self.append(session, work.id, now=self.now + timedelta(minutes=1))
            session.flush()
            last_activity = work.last_activity_at
            expiry = work.retention_expires_at
            original_version = session.get(CareerProfile, "profile-a").version

            pause_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                now=self.now + timedelta(minutes=2),
            )
            pause_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                now=self.now + timedelta(minutes=3),
            )
            self.assertEqual(work.status, "PAUSED")
            self.assertEqual(work.last_activity_at.replace(tzinfo=UTC), last_activity)
            self.assertEqual(work.retention_expires_at.replace(tzinfo=UTC), expiry)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, original_version)
            with self.assertRaises(ProfilingPaused):
                self.append(
                    session,
                    work.id,
                    now=self.now + timedelta(minutes=4),
                    key="synthetic_input_0002",
                )
            self.assertEqual(
                len(
                    list_profiling_inputs(
                        session,
                        account_id="acct-a",
                        profiling_session_id=work.id,
                        now=self.now + timedelta(minutes=4),
                    )
                ),
                1,
            )
            with self.assertRaises(ProfilingUnavailable):
                pause_profiling_session(
                    session,
                    account_id="acct-b",
                    profiling_session_id=work.id,
                    now=self.now + timedelta(minutes=5),
                )

    def test_session_metadata_is_read_only_scoped_and_content_free(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            self.append(session, work.id, now=self.now + timedelta(minutes=1))
            session.commit()
            before = get_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                now=self.now + timedelta(minutes=30),
            )
            self.assertEqual(before.status, "ACTIVE")
            after = get_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                now=self.now + timedelta(minutes=31),
            )
            self.assertEqual(after.status, "PAUSED")
            self.assertEqual(after.base_profile_version, 2)
            self.assertEqual(after.current_profile_version, 2)
            self.assertNotIn("body", asdict(after))
            self.assertEqual(work.status, "ACTIVE")
            self.assertEqual(
                work.retention_expires_at.replace(tzinfo=UTC), after.retention_expires_at
            )
            with self.assertRaises(ProfilingUnavailable):
                get_profiling_session(
                    session,
                    account_id="acct-b",
                    profiling_session_id=work.id,
                    now=self.now,
                )
            with self.assertRaises(ProfilingExpired):
                get_profiling_session(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work.id,
                    now=after.retention_expires_at,
                )

    def test_expired_or_deleting_workspace_is_denied_at_query_time(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            self.append(session, work.id, now=self.now + timedelta(minutes=1))
            session.commit()
            with self.assertRaises(ProfilingExpired):
                list_profiling_inputs(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work.id,
                    now=self.now + timedelta(minutes=1) + RETENTION,
                )
            work.status = "DELETING"
            session.commit()
            with self.assertRaises(ProfilingUnavailable):
                list_profiling_inputs(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work.id,
                    now=self.now + timedelta(days=1),
                )

    def test_cross_account_and_stale_profile_version_are_rejected(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(ProfilingUnavailable):
                start_profiling_session(
                    session,
                    account_id="acct-a",
                    profile_id="profile-b",
                    base_profile_version=4,
                    now=self.now,
                )
            work = self.start(session)
            with self.assertRaises(ProfilingUnavailable):
                list_profiling_inputs(
                    session,
                    account_id="acct-b",
                    profiling_session_id=work.id,
                    now=self.now,
                )
            session.get(CareerProfile, "profile-a").version = 3
            session.commit()
            with self.assertRaises(ProfilingVersionConflict):
                self.append(session, work.id, now=self.now + timedelta(minutes=1))

    def test_input_is_bounded_and_owner_constraints_reject_cross_account_rows(self) -> None:
        with Session(self.engine) as session:
            work = self.start(session)
            for content, key in (
                ("", "synthetic_input_0001"),
                ("x" * 20_001, "synthetic_input_0001"),
                ("ok", "short"),
            ):
                with (
                    self.subTest(content_length=len(content), key=key),
                    self.assertRaises(ProfilingValidationError),
                ):
                    self.append(session, work.id, now=self.now, content=content, key=key)
            with self.assertRaises(ProfilingValidationError):
                append_explicit_profiling_input(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work.id,
                    base_profile_version=2,
                    content=["general", "chat"],
                    content_kind=InputKind.USER_STATEMENT,
                    idempotency_key="synthetic_input_0001",
                    now=self.now,
                )
            session.add(
                ProfilingInput(
                    id="cross-account-input",
                    account_id="acct-b",
                    session_id=work.id,
                    idempotency_key="synthetic_input_0002",
                    content_kind="USER_STATEMENT",
                    body="not owned",
                    created_at=self.now,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()

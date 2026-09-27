"""Real PostgreSQL smoke test, skipped unless an explicitly local test DB is configured."""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)
from careerground.workers.profiling_retention import (
    ExpiryBatchResult,
    delete_expired_profiling_batch,
)


class PostgreSQLFoundationTests(unittest.TestCase):
    def test_migration_and_tenant_scope_on_local_postgresql(self) -> None:
        raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw_url:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("CI requires an explicit local PostgreSQL test URL")
            self.skipTest("local test PostgreSQL URL is not configured")
        url = make_url(raw_url)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing to run this test outside a local *_test PostgreSQL database")

        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    self.assertEqual(
                        connection.scalar(text("SELECT version_num FROM alembic_version")),
                        "20260927_0003",
                    )
                    with Session(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as session:
                        session.add_all(
                            [
                                Account(id="acct-ci-a", status="ACTIVE"),
                                Account(id="acct-ci-b", status="ACTIVE"),
                                AuthIdentity(
                                    id="identity-ci-a",
                                    account_id="acct-ci-a",
                                    issuer="https://ci.example",
                                    subject="sub-a",
                                ),
                                CareerProfile(id="profile-ci-b", account_id="acct-ci-b", version=0),
                                CareerProfile(id="profile-ci-a", account_id="acct-ci-a", version=0),
                            ]
                        )
                        session.flush()
                        account_id = resolve_account_id(
                            session, VerifiedIdentity("https://ci.example", "sub-a")
                        )
                        self.assertEqual(account_id, "acct-ci-a")
                        with self.assertRaises(ResourceNotFound):
                            get_owned_profile(
                                session, account_id=account_id, profile_id="profile-ci-b"
                            )
                        now = datetime(2026, 9, 27, 12, tzinfo=UTC)
                        for work_id, expiry in (
                            ("work-ci-expired", now),
                            ("work-ci-current", now + timedelta(days=1)),
                        ):
                            session.add(
                                ProfilingSession(
                                    id=work_id,
                                    account_id="acct-ci-a",
                                    profile_id="profile-ci-a",
                                    status="ACTIVE",
                                    base_profile_version=0,
                                    created_at=now - timedelta(days=90),
                                    last_activity_at=now - timedelta(days=90),
                                    retention_expires_at=expiry,
                                )
                            )
                        session.flush()
                        for work_id in ("work-ci-expired", "work-ci-current"):
                            session.add(
                                ProfilingInput(
                                    id=f"input-{work_id}",
                                    account_id="acct-ci-a",
                                    session_id=work_id,
                                    idempotency_key=f"synthetic_{work_id}",
                                    content_kind="USER_STATEMENT",
                                    body="synthetic private statement",
                                    created_at=now - timedelta(days=90),
                                )
                            )
                        session.flush()
                        self.assertEqual(
                            delete_expired_profiling_batch(session, now=now),
                            ExpiryBatchResult(sessions_deleted=1, inputs_deleted=1),
                        )
                        self.assertIsNone(session.get(ProfilingSession, "work-ci-expired"))
                        self.assertIsNotNone(session.get(ProfilingSession, "work-ci-current"))
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

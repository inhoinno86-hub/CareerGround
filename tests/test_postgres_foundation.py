"""Real PostgreSQL smoke test, skipped unless an explicitly local test DB is configured."""

from __future__ import annotations

import os
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.storage.models import Account, AuthIdentity, CareerProfile


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
                        "20260923_0001",
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
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

"""Concurrent first-use admission on the explicitly disposable local test DB."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import VerifiedIdentity
from careerground.storage.graph_models import ProfileArchive
from careerground.storage.models import Account, AuthIdentity, CareerProfile


class PostgreSQLAccountInitializationTests(unittest.TestCase):
    def setUp(self):
        raw = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("required local PostgreSQL test URL is absent")
            self.skipTest("local PostgreSQL test URL is not configured")
        url = make_url(raw)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing a non-local or non-test database")
        self.engine = create_engine(url, hide_parameters=True)
        self.addCleanup(self.engine.dispose)
        self.account_id = str(uuid4())
        self.identity = VerifiedIdentity("https://synthetic-admission.example", str(uuid4()))
        self.addCleanup(self.cleanup_rows)

    def cleanup_rows(self):
        with self.engine.begin() as conn:
            for model in (ProfileArchive, CareerProfile, AuthIdentity):
                conn.execute(delete(model).where(model.account_id == self.account_id))
            conn.execute(delete(Account).where(Account.id == self.account_id))

    def concurrent_initialize(self):
        barrier = Barrier(2)

        def run():
            with Session(self.engine) as session:
                session.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=5)
                profile = initialize_account_profile(
                    session,
                    identity=self.identity,
                    enrollment_account_id=self.account_id,
                )
                result = profile.id
                session.commit()
                return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            ids = [future.result(timeout=10) for future in futures]
        self.assertEqual(ids[0], ids[1])
        with Session(self.engine) as session:
            for model in (AuthIdentity, CareerProfile, ProfileArchive):
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(model)
                        .where(model.account_id == self.account_id)
                    ),
                    1,
                )
            profile = session.get(CareerProfile, ids[0])
            self.assertEqual(profile.version, 0)
            self.assertEqual(profile.status, "ACTIVE")

    def test_new_identity_enrollment_has_one_profile_and_archive(self):
        self.concurrent_initialize()

    def test_existing_identity_without_profile_serializes_first_use(self):
        with Session(self.engine) as session:
            session.add(Account(id=self.account_id))
            session.flush()
            session.add(
                AuthIdentity(
                    id=str(uuid4()),
                    account_id=self.account_id,
                    issuer=self.identity.issuer,
                    subject=self.identity.subject,
                )
            )
            session.commit()
        self.concurrent_initialize()

"""Actual local PostgreSQL serialization for synthetic demo operations only."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from careerground.domain.jd_analysis_adapter import MockJDAnalyzer, prepare_jd_analysis
from careerground.domain.jd_paste_presentation import JDPastePresentationService
from careerground.domain.synthetic_deletion_journey import (
    MockDeletionJourney,
    MockDeletionJourneyRejected,
)
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import JobDescription
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    OutboxEvent,
)

PREVIEW_SECRET = b"synthetic-pg-journey-preview-secret-32-byte"
LEDGER_SECRET = b"synthetic-pg-journey-ledger-secret-32-byte"
STATUS_SECRET = b"synthetic-pg-journey-status-secret-32-byte"
PASTE_SECRET = b"synthetic-pg-jd-paste-secret-32-bytes"


class PostgreSQLDemoOperationTests(unittest.TestCase):
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
        self.engine = create_engine(url, hide_parameters=True, pool_size=5, max_overflow=0)
        self.addCleanup(self.engine.dispose)
        suffix = uuid4().hex
        self.account_a = f"a-{suffix}"
        self.account_b = f"b-{suffix}"
        self.profile_a = f"p-{suffix}"
        self.profile_b = f"q-{suffix}"
        self.identity_a = f"i-{suffix}"
        self.claim_a = f"c-{suffix}"
        self.claim_b = f"d-{suffix}"
        self.now = datetime(2026, 10, 1, 12, tzinfo=UTC)
        self.journey = MockDeletionJourney(PREVIEW_SECRET, LEDGER_SECRET, STATUS_SECRET)
        self.addCleanup(self.cleanup_rows)
        with Session(self.engine) as session:
            if session.scalar(
                select(Account.id).where(Account.id.in_([self.account_a, self.account_b]))
            ):
                self.fail("synthetic fixture already exists")
            session.add_all([Account(id=self.account_a), Account(id=self.account_b)])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id=self.profile_a, account_id=self.account_a, version=1),
                    CareerProfile(id=self.profile_b, account_id=self.account_b, version=1),
                    AuthIdentity(
                        id=self.identity_a,
                        account_id=self.account_a,
                        issuer="synthetic",
                        subject=self.identity_a,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id=self.claim_a,
                        account_id=self.account_a,
                        profile_id=self.profile_a,
                        scope_key="a",
                        claim_type="CONTRIBUTION",
                        canonical_text="synthetic owned text",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    Claim(
                        id=self.claim_b,
                        account_id=self.account_b,
                        profile_id=self.profile_b,
                        scope_key="b",
                        claim_type="CONTRIBUTION",
                        canonical_text="synthetic other text",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.commit()

    def cleanup_rows(self):
        accounts = (self.account_a, self.account_b)
        with self.engine.begin() as connection:
            request_ids = select(DeletionRequest.id).where(DeletionRequest.account_id.in_(accounts))
            item_ids = tuple(
                connection.scalars(
                    select(DeletionWorkItem.id).where(DeletionWorkItem.request_id.in_(request_ids))
                )
            )
            if item_ids:
                connection.execute(delete(OutboxEvent).where(OutboxEvent.target_id.in_(item_ids)))
            connection.execute(
                delete(DeletionWorkItem).where(DeletionWorkItem.request_id.in_(request_ids))
            )
            for table in reversed(Base.metadata.sorted_tables):
                if "account_id" in table.c:
                    connection.execute(table.delete().where(table.c.account_id.in_(accounts)))
            connection.execute(delete(Account).where(Account.id.in_(accounts)))
            for table in Base.metadata.sorted_tables:
                if "account_id" in table.c:
                    self.assertEqual(
                        connection.scalar(
                            select(func.count())
                            .select_from(table)
                            .where(table.c.account_id.in_(accounts))
                        ),
                        0,
                    )

    def test_same_step_concurrent_execution_returns_one_request_and_proof(self):
        with Session(self.engine) as session:
            view = self.journey.preview(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                scope="ACCOUNT",
                now=self.now,
            )
            other_scope = self.journey.preview(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                scope="PROFILE",
                now=self.now,
            )
        with Session(self.engine) as session:
            step = self.journey.reauthenticate(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )
            other_step = self.journey.reauthenticate(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                preview_token=other_scope.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )
        barrier = Barrier(2)

        def execute_same():
            with Session(self.engine) as session:
                session.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=5)
                result = self.journey.execute(
                    session,
                    account_id=self.account_a,
                    profile_id=self.profile_a,
                    browser_session_id="synthetic-browser-session-1",
                    step_up_token=step,
                    confirmed=True,
                    now=self.now + timedelta(seconds=2),
                )
                session.commit()
                return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(execute_same) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0], results[1])
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(DeletionRequest)
                    .where(DeletionRequest.account_id == self.account_a)
                ),
                1,
            )
            self.assertIsNone(session.get(Claim, self.claim_a))
            self.assertIsNotNone(session.get(Claim, self.claim_b))
            self.assertEqual(
                self.journey.read_status(
                    session,
                    capability=results[0].status_capability,
                    now=self.now + timedelta(seconds=3),
                ).status,
                "DELETING",
            )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.journey.execute(
                    session,
                    account_id=self.account_a,
                    profile_id=self.profile_a,
                    browser_session_id="synthetic-browser-session-1",
                    step_up_token=other_step,
                    confirmed=True,
                    now=self.now + timedelta(seconds=3),
                )

    def test_stale_version_and_two_exact_jd_saves_serialize_without_deadlock(self):
        source = "- Build a test API\n- Query SQL data\n"
        paste = JDPastePresentationService(PASTE_SECRET)
        with Session(self.engine) as session:
            form = paste.present(
                session,
                account_id=self.account_a,
                browser_session_id="synthetic-browser-session-1",
                now=self.now,
            )
            first = prepare_jd_analysis(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                profile_version=1,
                source_text=source,
                analyzer=MockJDAnalyzer(),
            )
            self.assertEqual(len(first.requirements), 2)
        barrier = Barrier(2)

        def save_same():
            with Session(self.engine) as session:
                session.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=5)
                session.scalar(
                    select(Account).where(Account.id == self.account_a).with_for_update()
                )
                session.scalar(
                    select(CareerProfile)
                    .where(CareerProfile.id == self.profile_a)
                    .with_for_update()
                )
                proposal = prepare_jd_analysis(
                    session,
                    account_id=self.account_a,
                    profile_id=self.profile_a,
                    profile_version=1,
                    source_text=source,
                    analyzer=MockJDAnalyzer(),
                )
                self.assertEqual(proposal.source_hash, first.source_hash)
                jd = paste.submit(
                    session,
                    account_id=self.account_a,
                    browser_session_id="synthetic-browser-session-1",
                    paste_token=form.paste_token,
                    selected_text=source,
                    now=self.now + timedelta(seconds=1),
                )
                identifier = jd.id
                session.commit()
                return identifier

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save_same) for _ in range(2)]
            ids = [future.result(timeout=15) for future in futures]
        self.assertEqual(ids[0], ids[1])
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(JobDescription)
                    .where(JobDescription.account_id == self.account_a)
                ),
                1,
            )
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(JobDescription)
                    .where(JobDescription.account_id == self.account_b)
                ),
                0,
            )
            old = self.journey.preview(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                scope="ACCOUNT",
                now=self.now,
            )
            session.get(CareerProfile, self.profile_a).version = 2
            session.commit()
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.journey.reauthenticate(
                session,
                account_id=self.account_a,
                profile_id=self.profile_a,
                browser_session_id="synthetic-browser-session-1",
                preview_token=old.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )


if __name__ == "__main__":
    unittest.main()

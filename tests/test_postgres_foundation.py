"""Real PostgreSQL smoke test, skipped unless an explicitly local test DB is configured."""

from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.domain.claim_review_submission import (
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.jd_mapping import JDMappingRejected, link_jd_requirement_to_claim
from careerground.domain.profile_archive import read_profile_archive
from careerground.domain.profiling_protocol_workspace import record_question_delivery
from careerground.storage.graph_models import Claim, ClaimAssessment, ProfileArchive
from careerground.storage.jd_artifact_models import Artifact, JDRequirement
from careerground.storage.models import (
    Account,
    AuthIdentity,
    CareerProfile,
    OutboxEvent,
    ProfilingInput,
    ProfilingProtocolStep,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.outbox import due_events, enqueue_event
from careerground.workers.profiling_retention import (
    ExpiryBatchResult,
    delete_expired_profiling_batch,
)


class PostgreSQLFoundationTests(unittest.TestCase):
    def test_question_delivery_serializes_on_owned_workspace(self) -> None:
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
        suffix = uuid4().hex
        account_id = f"a-{suffix}"
        profile_id = f"p-{suffix}"
        work_id = f"w-{suffix}"
        now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        try:
            with Session(engine) as session:
                session.add(Account(id=account_id))
                session.add(CareerProfile(id=profile_id, account_id=account_id, version=0))
                session.flush()
                session.add(
                    ProfilingSession(
                        id=work_id,
                        account_id=account_id,
                        profile_id=profile_id,
                        status="ACTIVE",
                        base_profile_version=0,
                        created_at=now,
                        last_activity_at=now,
                        retention_expires_at=now + timedelta(days=90),
                    )
                )
                session.commit()
            with Session(engine) as first, Session(engine) as second:
                delivered = record_question_delivery(
                    first,
                    account_id=account_id,
                    profiling_session_id=work_id,
                    delivery_key="synthetic_delivery_0001",
                    now=now,
                )
                self.assertEqual(delivered.attempt, 1)
                second.execute(text("SET LOCAL lock_timeout = '200ms'"))
                with self.assertRaises(OperationalError):
                    record_question_delivery(
                        second,
                        account_id=account_id,
                        profiling_session_id=work_id,
                        delivery_key="synthetic_delivery_0002",
                        now=now,
                    )
                second.rollback()
                first.commit()
                delivered = record_question_delivery(
                    second,
                    account_id=account_id,
                    profiling_session_id=work_id,
                    delivery_key="synthetic_delivery_0002",
                    now=now,
                )
                self.assertEqual(delivered.attempt, 2)
                second.commit()
        finally:
            with engine.begin() as connection:
                connection.execute(delete(ProfilingSession).where(ProfilingSession.id == work_id))
                connection.execute(delete(CareerProfile).where(CareerProfile.id == profile_id))
                connection.execute(delete(Account).where(Account.id == account_id))
            engine.dispose()

    def test_expiry_skips_a_workspace_locked_by_another_worker(self) -> None:
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
        suffix = uuid4().hex
        account_id = f"a-{suffix}"
        profile_id = f"p-{suffix}"
        work_id = f"w-{suffix}"
        now = datetime(2026, 9, 27, tzinfo=UTC)
        try:
            with Session(engine) as session:
                session.add(Account(id=account_id, status="ACTIVE"))
                session.add(CareerProfile(id=profile_id, account_id=account_id, version=0))
                session.flush()
                session.add(
                    ProfilingSession(
                        id=work_id,
                        account_id=account_id,
                        profile_id=profile_id,
                        status="ACTIVE",
                        base_profile_version=0,
                        created_at=now - timedelta(days=90),
                        last_activity_at=now - timedelta(days=90),
                        retention_expires_at=now,
                    )
                )
                session.commit()
            with Session(engine) as worker_a, Session(engine) as worker_b:
                worker_a.scalar(
                    select(ProfilingSession).where(ProfilingSession.id == work_id).with_for_update()
                )
                delete_expired_profiling_batch(worker_b, now=now)
                self.assertIsNotNone(worker_b.get(ProfilingSession, work_id))
                worker_b.rollback()
                worker_a.rollback()
        finally:
            with engine.begin() as connection:
                connection.execute(delete(ProfilingSession).where(ProfilingSession.id == work_id))
                connection.execute(delete(CareerProfile).where(CareerProfile.id == profile_id))
                connection.execute(delete(Account).where(Account.id == account_id))
            engine.dispose()

    def test_two_outbox_workers_skip_a_locked_event(self) -> None:
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
        event_id = None
        try:
            now = datetime(2026, 9, 27, tzinfo=UTC)
            target_id = str(uuid4())
            with Session(engine) as session:
                event_row = enqueue_event(
                    session,
                    event_type="DELETION_WORK",
                    target_id=target_id,
                    handler_id=f"deletion:{target_id}",
                    now=now,
                )
                event_id = event_row.id
                session.commit()
            with Session(engine) as worker_a, Session(engine) as worker_b:
                claimed = due_events(worker_a, now=now, limit=100, event_type="DELETION_WORK")
                self.assertIn(event_id, {event.id for event in claimed})
                competing = due_events(worker_b, now=now, limit=100, event_type="DELETION_WORK")
                self.assertNotIn(event_id, {event.id for event in competing})
                worker_b.rollback()
                worker_a.rollback()
        finally:
            if event_id is not None:
                with engine.begin() as connection:
                    connection.execute(delete(OutboxEvent).where(OutboxEvent.id == event_id))
            engine.dispose()

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
                        "20261003_0020",
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
                        session.add(
                            ProfilingProtocolStep(
                                id="protocol-ci-expired",
                                account_id="acct-ci-a",
                                session_id="work-ci-expired",
                                state="CONTEXT_DISCOVERY",
                                asked_count=1,
                                first_delivery_key="synthetic_delivery_0001",
                                observation_status="SATISFIED",
                                source_input_id="input-work-ci-expired",
                                updated_at=now - timedelta(days=90),
                            )
                        )
                        session.flush()
                        draft = propose_verbatim_draft(
                            session,
                            account_id="acct-ci-a",
                            profiling_session_id="work-ci-current",
                            source_input_id="input-work-ci-current",
                            scope_key="ci-scope",
                            claim_type="CONTRIBUTION",
                            exact_text="synthetic private statement",
                            now=now,
                        )
                        session.flush()
                        preparation = ClaimReviewPreparation(
                            b"synthetic-review-signing-key-32-bytes"
                        )
                        batch = preparation.prepare(
                            session,
                            account_id="acct-ci-a",
                            profiling_session_id="work-ci-current",
                            draft_ids=(draft.id,),
                            now=now,
                        )
                        session.flush()
                        self.assertEqual(batch.base_profile_version, 0)
                        item = session.scalar(
                            select(ProfilingReviewItem).where(
                                ProfilingReviewItem.batch_id == batch.id
                            )
                        )
                        change = submit_synthetic_review(
                            session,
                            preparation=preparation,
                            approval=VerifiedReviewApproval(
                                account_id="acct-ci-a",
                                batch_id=batch.id,
                                review_digest=batch.review_digest,
                                decisions=((item.id, "ACCEPT"),),
                                expires_at=now + timedelta(minutes=2),
                            ),
                            now=now,
                        )
                        self.assertEqual(change.version_after, 1)
                        self.assertEqual(session.scalar(select(Claim)).account_id, "acct-ci-a")
                        self.assertEqual(len(list(session.scalars(select(ProfileArchive)))), 2)
                        self.assertEqual(
                            len(
                                read_profile_archive(
                                    session,
                                    account_id="acct-ci-a",
                                    profile_id="profile-ci-a",
                                    profile_version=1,
                                )["sections"]["claims"]
                            ),
                            1,
                        )
                        self.assertEqual(
                            session.scalar(select(ClaimAssessment)).usage_policy,
                            "REVIEW_REQUIRED",
                        )
                        jd = record_pasted_jd_analysis(
                            session,
                            account_id="acct-ci-a",
                            profile_id="profile-ci-a",
                            source_text="Python required",
                            excerpts=(JDExcerpt(0, 6),),
                            now=now,
                        )
                        session.add(
                            Artifact(
                                id="artifact-ci-a",
                                account_id="acct-ci-a",
                                profile_id="profile-ci-a",
                                artifact_type="RESUME_TEXT",
                                artifact_version=1,
                                profile_version=1,
                                jd_id=jd.id,
                                status="REVIEW_REQUIRED",
                                created_at=now,
                            )
                        )
                        session.flush()
                        self.assertEqual(session.scalar(select(JDRequirement)).exact_text, "Python")
                        with self.assertRaises(JDMappingRejected):
                            link_jd_requirement_to_claim(
                                session,
                                account_id="acct-ci-a",
                                jd_id=jd.id,
                                requirement_id=session.scalar(select(JDRequirement)).id,
                                claim_id=session.scalar(select(Claim)).id,
                                profile_version=1,
                                now=now,
                            )
                        self.assertEqual(
                            delete_expired_profiling_batch(session, now=now),
                            ExpiryBatchResult(sessions_deleted=1, inputs_deleted=1),
                        )
                        self.assertIsNone(session.get(ProfilingSession, "work-ci-expired"))
                        self.assertIsNone(
                            session.get(
                                ProfilingProtocolStep, "protocol-ci-expired", populate_existing=True
                            )
                        )
                        self.assertIsNotNone(session.get(ProfilingSession, "work-ci-current"))
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

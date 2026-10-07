"""Synthetic confirmation, immediate block, outbox and incomplete scope tests."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.deletion_execution import (
    apply_deletion_work,
    execute_synthetic_deletion,
)
from careerground.domain.deletion_preview import (
    DeletionConfirmationRejected,
    DeletionPreviewService,
    DeletionScope,
    DeletionTargetUnavailable,
    VerifiedDeletionApproval,
)
from careerground.domain.private_objects import (
    PrivateObjectUnavailable,
    list_private_versions,
    register_private_version,
    register_upload_original,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    ErasureLedger,
    OutboxEvent,
    PrivateObject,
    PrivateObjectVersion,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.deletion_runner import run_deletion_cycle
from careerground.workers.outbox import apply_event, due_events

SECRET = b"synthetic-deletion-key-32-bytes-minimum"


class DeletionExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, tzinfo=UTC)
        self.service = DeletionPreviewService(SECRET)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=1),
                    AuthIdentity(
                        id="identity-a", account_id="acct-a", issuer="synthetic", subject="a"
                    ),
                ]
            )
            session.flush()
            session.add(
                ProfilingSession(
                    id="session-a",
                    account_id="acct-a",
                    profile_id="profile-a",
                    status="ACTIVE",
                    base_profile_version=1,
                    created_at=self.now,
                    last_activity_at=self.now,
                    retention_expires_at=self.now + timedelta(days=90),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="acct-a",
                    session_id="session-a",
                    idempotency_key="synthetic_input_0001",
                    content_kind="USER_STATEMENT",
                    body="synthetic private career source",
                    created_at=self.now,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def confirm(self, session: Session, *, account: str = "acct-a", scope=DeletionScope.ACCOUNT):
        target = account if scope == DeletionScope.ACCOUNT else "profile-a"
        preview = self.service.preview(
            session, account_id=account, scope=scope, target_id=target, now=self.now
        )
        return execute_synthetic_deletion(
            session,
            preview_service=self.service,
            ledger_secret=SECRET,
            account_id=account,
            scope=scope,
            target_id=target,
            deletion_digest=preview.deletion_digest,
            acknowledged_impact=True,
            step_up=VerifiedDeletionApproval(
                account_id=account,
                scope=scope,
                target_id=target,
                expires_at=self.now + timedelta(minutes=3),
            ),
            now=self.now,
        )

    def test_account_confirmation_blocks_reads_and_stages_reference_only_work(self) -> None:
        with Session(self.engine) as session:
            request = self.confirm(session)
            session.commit()
            self.assertEqual(session.get(Account, "acct-a").status, "DELETING")
            with self.assertRaises(ResourceNotFound):
                get_owned_profile(session, account_id="acct-a", profile_id="profile-a")
            self.assertEqual(session.get(ProfilingSession, "session-a").status, "DELETING")
            self.assertEqual(request.status, "DELETING")
            self.assertIsNotNone(session.get(ErasureLedger, request.id))
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionWorkItem)), 6)
            self.assertEqual(session.scalar(select(func.count()).select_from(OutboxEvent)), 5)
            self.assertNotIn(
                "synthetic private career source", str(session.query(OutboxEvent).all())
            )
            self.assertNotIn(
                "synthetic private career source", str(session.query(DeletionWorkItem).all())
            )
            self.assertNotIn(
                "synthetic private career source", str(session.query(ErasureLedger).all())
            )
            with self.assertRaises(DeletionTargetUnavailable):
                self.confirm(session)

    def test_rollback_keeps_active_and_no_work_or_ledger(self) -> None:
        with Session(self.engine) as session:
            self.confirm(session)
            session.rollback()
        with Session(self.engine) as session:
            self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")
            for model in (DeletionRequest, DeletionWorkItem, ErasureLedger, OutboxEvent):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)

    def test_stale_digest_other_account_and_missing_step_up_fail_closed(self) -> None:
        with Session(self.engine) as session:
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            session.add(
                ProfilingInput(
                    id="later-input",
                    account_id="acct-a",
                    session_id="session-a",
                    idempotency_key="synthetic_input_0002",
                    content_kind="USER_STATEMENT",
                    body="synthetic later source",
                    created_at=self.now,
                )
            )
            session.flush()
            with self.assertRaises(DeletionConfirmationRejected):
                execute_synthetic_deletion(
                    session,
                    preview_service=self.service,
                    ledger_secret=SECRET,
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    deletion_digest=preview.deletion_digest,
                    acknowledged_impact=True,
                    step_up=VerifiedDeletionApproval(
                        "acct-a",
                        DeletionScope.PROFILE,
                        "profile-a",
                        self.now + timedelta(minutes=3),
                    ),
                    now=self.now,
                )
            with self.assertRaises(DeletionConfirmationRejected):
                execute_synthetic_deletion(
                    session,
                    preview_service=self.service,
                    ledger_secret=SECRET,
                    account_id="acct-b",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    deletion_digest=preview.deletion_digest,
                    acknowledged_impact=True,
                    step_up=None,
                    now=self.now,
                )
            with self.assertRaises(DeletionConfirmationRejected):
                execute_synthetic_deletion(
                    session,
                    preview_service=self.service,
                    ledger_secret=SECRET,
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    deletion_digest=preview.deletion_digest,
                    acknowledged_impact=True,
                    step_up=None,
                    now=self.now,
                )
            session.rollback()

    def test_work_replay_removes_known_rows_but_never_marks_request_erased(self) -> None:
        with Session(self.engine) as session:
            request = self.confirm(session)
            request_id = request.id
            session.commit()
        with Session(self.engine) as session:
            for event_row in due_events(session, now=self.now, limit=20):
                apply_event(
                    session,
                    event_row,
                    now=self.now,
                    handlers={"DELETION_WORK": apply_deletion_work},
                )
                session.commit()
        with Session(self.engine) as session:
            self.assertIsNone(session.get(ProfilingInput, "input-a"))
            self.assertIsNone(session.get(ProfilingSession, "session-a"))
            self.assertIsNone(session.get(AuthIdentity, "identity-a"))
            self.assertIsNotNone(session.get(CareerProfile, "profile-b"))
            self.assertEqual(session.get(DeletionRequest, request_id).status, "DELETING")
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(DeletionWorkItem)
                    .where(DeletionWorkItem.status == "PENDING")
                ),
                1,
            )

    def test_internal_runner_replays_known_work_without_completing_request(self) -> None:
        with Session(self.engine) as session:
            request_id = self.confirm(session).id
            session.commit()
        factory = lambda: Session(self.engine)
        self.assertEqual(run_deletion_cycle(factory, now=self.now), (5, 0))
        self.assertEqual(run_deletion_cycle(factory, now=self.now), (0, 0))
        with factory() as session:
            self.assertEqual(session.get(DeletionRequest, request_id).status, "DELETING")
            self.assertIsNone(session.get(ProfilingInput, "input-a"))

    def test_permanent_work_failure_stays_visible_and_read_blocked(self) -> None:
        with Session(self.engine) as session:
            request_id = self.confirm(session).id
            item = session.scalar(
                select(DeletionWorkItem).where(DeletionWorkItem.kind == "AUTH_IDENTITY")
            )
            item.kind = "UNKNOWN_KIND"
            event_row = session.scalar(select(OutboxEvent).where(OutboxEvent.target_id == item.id))
            event_id = event_row.id
            for other in session.scalars(select(OutboxEvent)):
                if other.id != event_id:
                    other.status = "DONE"
            item_id = item.id
            session.commit()
        factory = lambda: Session(self.engine)
        clock = self.now
        for attempt in range(1, 6):
            self.assertEqual(run_deletion_cycle(factory, now=clock), (0, 1))
            clock += timedelta(seconds=2**attempt * 10)
        with factory() as session:
            self.assertEqual(session.get(DeletionWorkItem, item_id).status, "FAILED")
            self.assertEqual(session.get(DeletionRequest, request_id).status, "FAILED")
            self.assertEqual(session.get(Account, "acct-a").status, "DELETING")
            self.assertEqual(session.get(OutboxEvent, event_id).status, "DEAD")

    def test_private_object_versions_change_digest_and_remain_unverified(self) -> None:
        with Session(self.engine) as session:
            before = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now,
                now=self.now,
            )
            session.flush()
            version = register_private_version(
                session,
                account_id="acct-a",
                object_id=obj.id,
                provider_version_id="synthetic-v1",
                now=self.now,
            )
            session.commit()
            with self.assertRaises(DeletionConfirmationRejected):
                execute_synthetic_deletion(
                    session,
                    preview_service=self.service,
                    ledger_secret=SECRET,
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    deletion_digest=before.deletion_digest,
                    acknowledged_impact=True,
                    step_up=VerifiedDeletionApproval(
                        "acct-a",
                        DeletionScope.PROFILE,
                        "profile-a",
                        self.now + timedelta(minutes=3),
                    ),
                    now=self.now,
                )
            request = self.confirm(session, scope=DeletionScope.PROFILE)
            session.commit()
            self.assertEqual(session.get(PrivateObject, obj.id).status, "DELETING")
            self.assertEqual(session.get(PrivateObjectVersion, version.id).status, "DELETE_PENDING")
            with self.assertRaises(PrivateObjectUnavailable):
                list_private_versions(session, account_id="acct-a", object_id=obj.id, now=self.now)
            pending = list(
                session.scalars(
                    select(DeletionWorkItem).where(DeletionWorkItem.request_id == request.id)
                )
            )
            self.assertIn(
                ("PRIVATE_OBJECT_VERSION", "VERIFY", "PENDING"),
                {(item.kind, item.action, item.status) for item in pending},
            )
            self.assertEqual(request.status, "DELETING")

    def test_draft_and_review_rows_are_deleted_with_account_workspace(self) -> None:
        with Session(self.engine) as session:
            draft = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                source_input_id="input-a",
                scope_key="feature-a",
                claim_type="CONTRIBUTION",
                exact_text="synthetic private career source",
                now=self.now,
            )
            session.flush()
            ClaimReviewPreparation(SECRET).prepare(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                draft_ids=(draft.id,),
                now=self.now,
            )
            session.flush()
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            self.assertIn("PROFILING_REVIEW_ITEM", {item.kind for item in preview.items})
            request_id = self.confirm(session).id
            session.commit()
        factory = lambda: Session(self.engine)
        done, failed = run_deletion_cycle(factory, now=self.now)
        self.assertGreater(done, 0)
        self.assertEqual(failed, 0)
        with factory() as session:
            for model in (ProfilingDraft, ProfilingReviewBatch, ProfilingReviewItem):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)
            self.assertEqual(session.get(DeletionRequest, request_id).status, "DELETING")


if __name__ == "__main__":
    unittest.main()

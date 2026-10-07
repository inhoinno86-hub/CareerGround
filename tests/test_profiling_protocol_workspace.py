"""Synthetic question-progress ownership, replay, and erasure checks."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_submission import (
    ReviewSubmissionRejected,
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewStale,
    ReviewUnavailable,
    propose_verbatim_draft,
)
from careerground.domain.deletion_execution import execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionConfirmationRejected,
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.domain.profiling_protocol_workspace import (
    get_protocol_question_plan,
    record_protocol_observation,
    record_question_delivery,
)
from careerground.domain.profiling_questions import (
    ObservationStatus,
    ProtocolObservation,
    ProtocolState,
)
from careerground.domain.profiling_workspace import (
    InputKind,
    ProfilingExpired,
    ProfilingPaused,
    ProfilingUnavailable,
    ProfilingValidationError,
    append_explicit_profiling_input,
    resume_profiling_session,
    start_profiling_session,
)
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingDraft,
    ProfilingProtocolStep,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.deletion_runner import run_deletion_cycle
from careerground.workers.profiling_retention import delete_expired_profiling_batch

SECRET = b"synthetic-protocol-delete-secret-32-bytes"


class ProfilingProtocolWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=1),
                ]
            )
            session.commit()
        self.service = DeletionPreviewService(SECRET)

    def tearDown(self) -> None:
        self.engine.dispose()

    def start(self, session: Session, account: str = "acct-a") -> str:
        work = start_profiling_session(
            session,
            account_id=account,
            profile_id=f"profile-{account[-1]}",
            base_profile_version=1,
            now=self.now,
        )
        session.flush()
        return work.id

    def deliver(self, session: Session, work_id: str, key: str, *, now: datetime | None = None):
        return record_question_delivery(
            session,
            account_id="acct-a",
            profiling_session_id=work_id,
            delivery_key=key,
            now=now or self.now,
        )

    def input(self, session: Session, work_id: str, *, account: str = "acct-a") -> str:
        item = append_explicit_profiling_input(
            session,
            account_id=account,
            profiling_session_id=work_id,
            base_profile_version=1,
            content="Synthetic answer about a bounded role",
            content_kind=InputKind.USER_STATEMENT,
            idempotency_key="synthetic_source_0001",
            now=self.now + timedelta(minutes=1),
        )
        session.flush()
        return item.id

    def test_delivery_replay_source_and_pause_resume(self) -> None:
        with Session(self.engine) as session:
            work_id = self.start(session)
            first = self.deliver(session, work_id, "synthetic_delivery_0001")
            self.assertEqual((first.state, first.attempt), (ProtocolState.CONTEXT_DISCOVERY, 1))
            self.assertFalse(first.replayed)
            self.assertTrue(self.deliver(session, work_id, "synthetic_delivery_0001").replayed)
            self.assertEqual(
                get_protocol_question_plan(
                    session, account_id="acct-a", profiling_session_id=work_id, now=self.now
                ).question_attempt,
                2,
            )
            source_id = self.input(session, work_id)
            next_plan = record_protocol_observation(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                observation=ProtocolObservation(
                    ProtocolState.CONTEXT_DISCOVERY, ObservationStatus.SATISFIED, source_id
                ),
                now=self.now + timedelta(minutes=2),
            )
            self.assertEqual(next_plan.state, ProtocolState.ROLE_DISCOVERY)
            self.assertEqual(
                self.deliver(
                    session,
                    work_id,
                    "synthetic_delivery_0002",
                    now=self.now + timedelta(minutes=2),
                ).state,
                ProtocolState.ROLE_DISCOVERY,
            )
            session.commit()
            work = session.get(ProfilingSession, work_id)
            self.assertEqual(
                work.last_activity_at.replace(tzinfo=UTC), self.now + timedelta(minutes=1)
            )
            with self.assertRaises(ProfilingPaused):
                self.deliver(
                    session,
                    work_id,
                    "synthetic_delivery_0003",
                    now=self.now + timedelta(minutes=31),
                )
            resume_profiling_session(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                base_profile_version=1,
                now=self.now + timedelta(minutes=32),
            )
            self.assertEqual(
                self.deliver(
                    session,
                    work_id,
                    "synthetic_delivery_0003",
                    now=self.now + timedelta(minutes=33),
                ).attempt,
                2,
            )
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)

    def test_unknown_budget_and_cross_session_source_are_enforced(self) -> None:
        with Session(self.engine) as session:
            work_a = self.start(session)
            work_b = self.start(session, "acct-b")
            other_source = self.input(session, work_b, account="acct-b")
            self.deliver(session, work_a, "synthetic_delivery_0001")
            unknown = ProtocolObservation(
                ProtocolState.CONTEXT_DISCOVERY,
                ObservationStatus.UNKNOWN,
                reason="Synthetic unanswered field",
            )
            with self.assertRaises(ProfilingValidationError):
                record_protocol_observation(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work_a,
                    observation=unknown,
                    now=self.now + timedelta(minutes=2),
                )
            with self.assertRaises(ProfilingValidationError):
                record_protocol_observation(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work_a,
                    observation=ProtocolObservation(
                        ProtocolState.CONTEXT_DISCOVERY,
                        ObservationStatus.SATISFIED,
                        other_source,
                    ),
                    now=self.now + timedelta(minutes=2),
                )
            self.deliver(session, work_a, "synthetic_delivery_0002")
            blocked = record_protocol_observation(
                session,
                account_id="acct-a",
                profiling_session_id=work_a,
                observation=unknown,
                now=self.now + timedelta(minutes=2),
            )
            self.assertTrue(blocked.blocked)
            self.assertEqual(blocked.state, ProtocolState.CONTEXT_DISCOVERY)
            with self.assertRaises(ProfilingUnavailable):
                get_protocol_question_plan(
                    session, account_id="acct-b", profiling_session_id=work_a, now=self.now
                )
            session.flush()
            row = session.scalar(
                select(ProfilingProtocolStep).where(ProfilingProtocolStep.session_id == work_a)
            )
            self.assertIsNone(row.source_input_id)
            self.assertEqual(row.asked_count, 2)

    def test_protocol_step_is_in_impact_and_erased_with_session(self) -> None:
        with Session(self.engine) as session:
            work_id = self.start(session)
            source_id = self.input(session, work_id)
            old = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.deliver(
                session,
                work_id,
                "synthetic_delivery_0001",
                now=self.now + timedelta(minutes=2),
            )
            record_protocol_observation(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                observation=ProtocolObservation(
                    ProtocolState.CONTEXT_DISCOVERY, ObservationStatus.SATISFIED, source_id
                ),
                now=self.now + timedelta(minutes=2),
            )
            session.flush()
            step_id = session.scalar(select(ProfilingProtocolStep.id))
            current = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertIn(
                ("PROFILING_PROTOCOL_STEP", step_id), {(i.kind, i.target_id) for i in current.items}
            )
            with self.assertRaises(DeletionConfirmationRejected):
                self.service.confirm_intent(
                    session,
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    deletion_digest=old.deletion_digest,
                    acknowledged_impact=True,
                    step_up=VerifiedDeletionApproval(
                        "acct-a",
                        DeletionScope.PROFILE,
                        "profile-a",
                        self.now + timedelta(minutes=3),
                    ),
                    now=self.now,
                )
            execute_synthetic_deletion(
                session,
                preview_service=self.service,
                ledger_secret=SECRET,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                deletion_digest=current.deletion_digest,
                acknowledged_impact=True,
                step_up=VerifiedDeletionApproval(
                    "acct-a", DeletionScope.PROFILE, "profile-a", self.now + timedelta(minutes=3)
                ),
                now=self.now,
            )
            session.commit()
        done, failed = run_deletion_cycle(lambda: Session(self.engine), now=self.now, limit=20)
        self.assertGreaterEqual(done, 1)
        self.assertEqual(failed, 0)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(ProfilingProtocolStep, step_id))
            self.assertIsNone(session.get(ProfilingSession, work_id))

    def test_expiry_cascades_and_denies_question_reads(self) -> None:
        with Session(self.engine) as session:
            work_id = self.start(session)
            self.deliver(session, work_id, "synthetic_delivery_0001")
            session.commit()
            expiry = self.now + timedelta(days=90)
            with self.assertRaises(ProfilingExpired):
                get_protocol_question_plan(
                    session, account_id="acct-a", profiling_session_id=work_id, now=expiry
                )
            deleted = delete_expired_profiling_batch(session, now=expiry)
            self.assertEqual(deleted.sessions_deleted, 1)
            session.commit()
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ProfilingProtocolStep)), 0
            )

    def test_correction_restarts_questions_and_invalidates_pending_review(self) -> None:
        with Session(self.engine) as session:
            work_id = self.start(session)
            self.deliver(session, work_id, "synthetic_delivery_0001")
            old_source = self.input(session, work_id)
            record_protocol_observation(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                observation=ProtocolObservation(
                    ProtocolState.CONTEXT_DISCOVERY, ObservationStatus.SATISFIED, old_source
                ),
                now=self.now + timedelta(minutes=2),
            )
            draft = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                source_input_id=old_source,
                scope_key="synthetic_scope",
                claim_type="CONTRIBUTION",
                exact_text="Synthetic answer about a bounded role",
                now=self.now + timedelta(minutes=2),
            )
            preparation = ClaimReviewPreparation(b"synthetic-review-key-32-bytes-long")
            batch = preparation.prepare(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                draft_ids=(draft.id,),
                now=self.now + timedelta(minutes=2),
            )
            session.flush()
            review_item = session.scalar(
                select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == batch.id)
            )
            corrected = append_explicit_profiling_input(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                base_profile_version=1,
                content="Corrected synthetic work boundary",
                content_kind=InputKind.CORRECTION,
                idempotency_key="synthetic_correction_0001",
                now=self.now + timedelta(minutes=3),
            )
            self.assertEqual(corrected.protocol_cycle, 1)
            self.assertEqual(session.get(ProfilingSession, work_id).protocol_cycle, 1)
            self.assertEqual(session.get(ProfilingReviewBatch, batch.id).status, "EXPIRED")
            self.assertEqual(session.get(ProfilingDraft, draft.id).status, "EDIT_REQUIRED")
            self.assertEqual(
                get_protocol_question_plan(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work_id,
                    now=self.now + timedelta(minutes=3),
                ).state,
                ProtocolState.CONTEXT_DISCOVERY,
            )
            with self.assertRaises(ProfilingValidationError):
                self.deliver(
                    session,
                    work_id,
                    "synthetic_delivery_0001",
                    now=self.now + timedelta(minutes=3),
                )
            self.assertEqual(
                self.deliver(
                    session,
                    work_id,
                    "synthetic_delivery_0002",
                    now=self.now + timedelta(minutes=3),
                ).attempt,
                1,
            )
            with self.assertRaises(ProfilingValidationError):
                record_protocol_observation(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work_id,
                    observation=ProtocolObservation(
                        ProtocolState.CONTEXT_DISCOVERY, ObservationStatus.SATISFIED, old_source
                    ),
                    now=self.now + timedelta(minutes=4),
                )
            next_plan = record_protocol_observation(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                observation=ProtocolObservation(
                    ProtocolState.CONTEXT_DISCOVERY, ObservationStatus.SATISFIED, corrected.id
                ),
                now=self.now + timedelta(minutes=4),
            )
            self.assertEqual(next_plan.state, ProtocolState.ROLE_DISCOVERY)
            retry = append_explicit_profiling_input(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                base_profile_version=1,
                content="Corrected synthetic work boundary",
                content_kind=InputKind.CORRECTION,
                idempotency_key="synthetic_correction_0001",
                now=self.now + timedelta(minutes=5),
            )
            self.assertEqual(retry.id, corrected.id)
            self.assertEqual(session.get(ProfilingSession, work_id).protocol_cycle, 1)
            with self.assertRaises(ReviewUnavailable):
                preparation.get(
                    session,
                    account_id="acct-a",
                    batch_id=batch.id,
                    now=self.now + timedelta(minutes=5),
                )
            with self.assertRaises((ReviewStale, ReviewSubmissionRejected)):
                submit_synthetic_review(
                    session,
                    preparation=preparation,
                    approval=VerifiedReviewApproval(
                        account_id="acct-a",
                        batch_id=batch.id,
                        review_digest=batch.review_digest,
                        decisions=((review_item.id, "ACCEPT"),),
                        expires_at=self.now + timedelta(minutes=10),
                    ),
                    now=self.now + timedelta(minutes=5),
                )
            with self.assertRaises(ReviewUnavailable):
                propose_verbatim_draft(
                    session,
                    account_id="acct-a",
                    profiling_session_id=work_id,
                    source_input_id=old_source,
                    scope_key="synthetic_scope",
                    claim_type="CONTRIBUTION",
                    exact_text="Synthetic answer about a bounded role",
                    now=self.now + timedelta(minutes=5),
                )
            new_draft = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                source_input_id=corrected.id,
                scope_key="synthetic_scope",
                claim_type="CONTRIBUTION",
                exact_text="Corrected synthetic work boundary",
                now=self.now + timedelta(minutes=5),
            )
            self.assertEqual(new_draft.status, "DRAFT")
            new_batch = preparation.prepare(
                session,
                account_id="acct-a",
                profiling_session_id=work_id,
                draft_ids=(new_draft.id,),
                now=self.now + timedelta(minutes=6),
            )
            self.assertEqual(new_batch.status, "PREPARED")
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
            session.flush()
            self.assertEqual(
                {step.protocol_cycle for step in session.scalars(select(ProfilingProtocolStep))},
                {0, 1},
            )
            session.commit()
            self.assertEqual(
                session.get(ProfilingSession, work_id, populate_existing=True).protocol_cycle, 1
            )
            self.assertEqual(
                session.get(ProfilingReviewBatch, batch.id, populate_existing=True).status,
                "EXPIRED",
            )
            expiry = self.now + timedelta(minutes=3) + timedelta(days=90)
            self.assertEqual(
                delete_expired_profiling_batch(session, now=expiry).sessions_deleted, 1
            )
            session.commit()
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ProfilingProtocolStep)), 0
            )

    def test_cross_cycle_source_foreign_key_rejects_direct_insert(self) -> None:
        with Session(self.engine) as session:
            work_id = self.start(session)
            old_source = self.input(session, work_id)
            session.add(
                ProfilingProtocolStep(
                    id="wrong-cycle-step",
                    account_id="acct-a",
                    session_id=work_id,
                    protocol_cycle=1,
                    state="CONTEXT_DISCOVERY",
                    asked_count=1,
                    first_delivery_key="synthetic_delivery_0001",
                    observation_status="SATISFIED",
                    source_input_id=old_source,
                    updated_at=self.now,
                )
            )
            with self.assertRaises(IntegrityError):
                session.flush()


if __name__ == "__main__":
    unittest.main()

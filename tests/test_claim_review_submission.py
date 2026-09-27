"""Exact synthetic review, canonical provenance, replay and lifecycle boundaries."""

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
    propose_verbatim_draft,
)
from careerground.domain.deletion_execution import (
    apply_deletion_work,
    execute_synthetic_deletion,
)
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimConstraint,
    ClaimReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
    ProfileChangeSet,
)
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    DeletionWorkItem,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.profiling_retention import delete_expired_profiling_batch

SECRET = b"synthetic-review-signing-key-at-least-32-bytes"


class ClaimReviewSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        self.preparation = ClaimReviewPreparation(SECRET)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=2),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                ]
            )
            session.flush()
            session.add(
                ProfilingSession(
                    id="session-a",
                    account_id="acct-a",
                    profile_id="profile-a",
                    status="ACTIVE",
                    base_profile_version=2,
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
                    body="I implemented speed logic, tested it in SIL, and did not own the architecture.",
                    created_at=self.now,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def _prepare(self, session: Session, texts: tuple[str, ...]):
        drafts = [
            propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                source_input_id="input-a",
                scope_key="speed-control",
                claim_type="CONTRIBUTION",
                exact_text=text,
                now=self.now,
            )
            for text in texts
        ]
        session.flush()
        batch = self.preparation.prepare(
            session,
            account_id="acct-a",
            profiling_session_id="session-a",
            draft_ids=tuple(draft.id for draft in drafts),
            now=self.now,
        )
        session.flush()
        items = tuple(
            session.scalars(
                select(ProfilingReviewItem)
                .where(ProfilingReviewItem.batch_id == batch.id)
                .order_by(ProfilingReviewItem.position)
            )
        )
        return batch, items

    def _approval(self, batch, items, decisions, *, account="acct-a"):
        return VerifiedReviewApproval(
            account_id=account,
            batch_id=batch.id,
            review_digest=batch.review_digest,
            decisions=tuple((item.id, decision) for item, decision in zip(items, decisions)),
            expires_at=self.now + timedelta(minutes=3),
        )

    def test_accepted_claim_preserves_source_and_survives_workspace_expiry(self) -> None:
        preview = DeletionPreviewService(SECRET)
        with Session(self.engine) as session:
            before = preview.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            batch, items = self._prepare(session, ("I implemented speed logic",))
            change = submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=self._approval(batch, items, ("ACCEPT",)),
                now=self.now,
            )
            self.assertEqual((change.version_before, change.version_after), (2, 3))
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 3)
            assessment = session.scalar(select(ClaimAssessment))
            self.assertEqual(assessment.knowledge_status, "USER_CONFIRMED")
            self.assertEqual(assessment.consistency_status, "NOT_EVALUATED")
            self.assertEqual(assessment.usage_policy, "REVIEW_REQUIRED")
            self.assertEqual(session.scalar(select(EvidenceItem)).content_text, items[0].exact_text)
            self.assertEqual(session.scalar(select(EvidenceSource)).source_ref, "input-a")
            self.assertEqual(session.scalar(select(EvidenceClaimLink)).relation_type, "SUPPORTS")
            self.assertEqual(session.scalar(select(ClaimReview)).review_digest, batch.review_digest)
            old = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=2
            )
            current = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=3
            )
            self.assertEqual(old["sections"]["claims"], [])
            self.assertEqual(len(current["sections"]["claims"]), 1)
            with self.assertRaises(ArchiveUnavailable):
                read_profile_archive(
                    session, account_id="acct-a", profile_id="profile-a", profile_version=1
                )
            after = preview.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertNotEqual(before.deletion_digest, after.deletion_digest)
            self.assertIn("CLAIM", {item.kind for item in after.items})
            session.commit()
        with Session(self.engine) as session:
            delete_expired_profiling_batch(session, now=self.now + timedelta(days=90))
            session.commit()
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 1)
            claim_id = session.scalar(select(Claim.id))
            view = get_claim_evidence(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=3,
                claim_id=claim_id,
            )
            self.assertEqual(view.evidence[0].exact_excerpt, "I implemented speed logic")
            self.assertEqual(view.evidence[0].source_availability, "SELECTED_EXCERPT_ONLY")
            self.assertTrue(view.reviewed)
            self.assertEqual(
                len(
                    get_career_profile(
                        session,
                        account_id="acct-a",
                        profile_id="profile-a",
                        profile_version=2,
                    ).claims
                ),
                0,
            )
            with self.assertRaises(GraphUnavailable):
                get_claim_evidence(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=2,
                    claim_id=claim_id,
                )
            with self.assertRaises(GraphUnavailable):
                get_claim_evidence(
                    session,
                    account_id="acct-b",
                    profile_id="profile-a",
                    profile_version=3,
                    claim_id=claim_id,
                )
            self.assertEqual(
                len(
                    read_profile_archive(
                        session, account_id="acct-a", profile_id="profile-a", profile_version=3
                    )["sections"]["evidence_items"]
                ),
                1,
            )

    def test_mixed_decisions_are_exact_and_replay_does_not_mutate(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(
                session,
                (
                    "I implemented speed logic",
                    "tested it in SIL",
                    "did not own the architecture",
                ),
            )
            approval = self._approval(batch, items, ("ACCEPT", "EDIT", "EXCLUDE_DO_NOT_USE"))
            change = submit_synthetic_review(
                session, preparation=self.preparation, approval=approval, now=self.now
            )
            session.commit()
            self.assertEqual(change.version_after, 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
            constraint = session.scalar(select(ClaimConstraint))
            self.assertEqual(
                (constraint.constraint_type, constraint.exact_text),
                ("DO_NOT_USE", "did not own the architecture"),
            )
            self.assertEqual(
                [session.get(ProfilingDraft, item.draft_id).status for item in items],
                ["PROMOTED", "EDIT_REQUIRED", "EXCLUDED"],
            )
            replay = submit_synthetic_review(
                session, preparation=self.preparation, approval=approval, now=self.now
            )
            self.assertEqual(replay.id, change.id)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileChangeSet)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileArchive)), 2)

    def test_archive_tampering_or_wrong_owner_fails_without_latest_fallback(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=self._approval(batch, items, ("ACCEPT",)),
                now=self.now,
            )
            session.commit()
        with Session(self.engine) as session:
            with self.assertRaises(ArchiveUnavailable):
                read_profile_archive(
                    session, account_id="acct-b", profile_id="profile-a", profile_version=3
                )
            archive = session.scalar(
                select(ProfileArchive).where(ProfileArchive.profile_version == 3)
            )
            archive.snapshot_json = archive.snapshot_json.replace(
                "I implemented speed logic", "I owned the architecture"
            )
            session.flush()
            with self.assertRaises(ArchiveUnavailable):
                read_profile_archive(
                    session, account_id="acct-a", profile_id="profile-a", profile_version=3
                )

    def test_second_promotion_preserves_earlier_exact_version(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=self._approval(batch, items, ("ACCEPT",)),
                now=self.now,
            )
            session.commit()
        with Session(self.engine) as session:
            second_at = self.now + timedelta(hours=1)
            session.add(
                ProfilingSession(
                    id="session-second",
                    account_id="acct-a",
                    profile_id="profile-a",
                    status="ACTIVE",
                    base_profile_version=3,
                    created_at=second_at,
                    last_activity_at=second_at,
                    retention_expires_at=second_at + timedelta(days=90),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-second",
                    account_id="acct-a",
                    session_id="session-second",
                    idempotency_key="synthetic_input_second",
                    content_kind="USER_STATEMENT",
                    body="I tested it in SIL.",
                    created_at=second_at,
                )
            )
            session.flush()
            draft = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="session-second",
                source_input_id="input-second",
                scope_key="speed-control",
                claim_type="VALIDATION",
                exact_text="I tested it in SIL",
                now=second_at,
            )
            session.flush()
            second_batch = self.preparation.prepare(
                session,
                account_id="acct-a",
                profiling_session_id="session-second",
                draft_ids=(draft.id,),
                now=second_at,
            )
            session.flush()
            second_item = session.scalar(
                select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == second_batch.id)
            )
            submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=VerifiedReviewApproval(
                    account_id="acct-a",
                    batch_id=second_batch.id,
                    review_digest=second_batch.review_digest,
                    decisions=((second_item.id, "ACCEPT"),),
                    expires_at=second_at + timedelta(minutes=3),
                ),
                now=second_at,
            )
            session.commit()
            old = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=3
            )
            new = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=4
            )
            self.assertEqual(len(old["sections"]["claims"]), 1)
            self.assertEqual(len(new["sections"]["claims"]), 2)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 4)

    def test_missing_wrong_owner_stale_and_changed_source_fail_closed(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic", "tested it in SIL"))
            with self.assertRaises(ReviewSubmissionRejected):
                submit_synthetic_review(
                    session,
                    preparation=self.preparation,
                    approval=self._approval(batch, items, ("ACCEPT",)),
                    now=self.now,
                )
            with self.assertRaises(ReviewSubmissionRejected):
                submit_synthetic_review(
                    session,
                    preparation=self.preparation,
                    approval=self._approval(batch, items, ("ACCEPT", "ACCEPT"), account="acct-b"),
                    now=self.now,
                )
            session.get(ProfilingInput, "input-a").body = "tampered source"
            session.flush()
            with self.assertRaises(ReviewStale):
                submit_synthetic_review(
                    session,
                    preparation=self.preparation,
                    approval=self._approval(batch, items, ("ACCEPT", "ACCEPT")),
                    now=self.now,
                )
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
            session.rollback()
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            session.get(CareerProfile, "profile-a").version = 3
            session.flush()
            with self.assertRaises(ReviewStale):
                submit_synthetic_review(
                    session,
                    preparation=self.preparation,
                    approval=self._approval(batch, items, ("ACCEPT",)),
                    now=self.now,
                )

    def test_edit_only_does_not_change_canonical_version(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            approval = self._approval(batch, items, ("EDIT",))
            change = submit_synthetic_review(
                session, preparation=self.preparation, approval=approval, now=self.now
            )
            self.assertIsNone(change)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(session.get(ProfilingReviewBatch, batch.id).status, "SUBMITTED")
            self.assertEqual(session.get(ProfilingDraft, items[0].draft_id).status, "EDIT_REQUIRED")
            session.commit()
            self.assertIsNone(
                submit_synthetic_review(
                    session, preparation=self.preparation, approval=approval, now=self.now
                )
            )

    def test_graph_relationship_cannot_point_across_accounts(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=self._approval(batch, items, ("ACCEPT",)),
                now=self.now,
            )
            claim_id = session.scalar(select(Claim.id))
            evidence_id = session.scalar(select(EvidenceItem.id))
            session.commit()
        with Session(self.engine) as session:
            session.add(
                EvidenceClaimLink(
                    id="bad-cross-owner-link",
                    account_id="acct-b",
                    profile_id="profile-b",
                    evidence_id=evidence_id,
                    claim_id=claim_id,
                    relation_type="SUPPORTS",
                    created_in_version=1,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_profile_deletion_clears_canonical_rows_but_keeps_request_pending(self) -> None:
        with Session(self.engine) as session:
            batch, items = self._prepare(session, ("I implemented speed logic",))
            submit_synthetic_review(
                session,
                preparation=self.preparation,
                approval=self._approval(batch, items, ("ACCEPT",)),
                now=self.now,
            )
            session.commit()
        with Session(self.engine) as session:
            service = DeletionPreviewService(SECRET)
            preview = service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            request = execute_synthetic_deletion(
                session,
                preview_service=service,
                ledger_secret=SECRET,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                deletion_digest=preview.deletion_digest,
                acknowledged_impact=True,
                step_up=VerifiedDeletionApproval(
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    expires_at=self.now + timedelta(minutes=3),
                ),
                now=self.now,
            )
            session.commit()
            graph_work = session.scalar(
                select(DeletionWorkItem).where(
                    DeletionWorkItem.request_id == request.id,
                    DeletionWorkItem.kind == "PROFILE_LOCAL_DATA",
                )
            )
            self.assertIsNotNone(graph_work)
            apply_deletion_work(session, graph_work.id)
            session.commit()
            for model in (
                Claim,
                EvidenceSource,
                EvidenceItem,
                EvidenceClaimLink,
                ClaimAssessment,
                ClaimReview,
                ProfileChangeSet,
                ProfileArchive,
            ):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)
            graph_items = list(
                session.scalars(
                    select(DeletionWorkItem).where(
                        DeletionWorkItem.request_id == request.id,
                        DeletionWorkItem.kind == "CLAIM",
                    )
                )
            )
            self.assertTrue(graph_items)
            self.assertTrue(all(item.status == "DONE" for item in graph_items))
            self.assertEqual(
                session.scalar(
                    select(DeletionWorkItem.status).where(
                        DeletionWorkItem.request_id == request.id,
                        DeletionWorkItem.kind == "UNVERIFIED_SCOPE",
                    )
                ),
                "PENDING",
            )
            self.assertEqual(session.get(CareerProfile, "profile-a").status, "DELETING")
            with self.assertRaises(GraphUnavailable):
                get_career_profile(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=1,
                )


if __name__ == "__main__":
    unittest.main()

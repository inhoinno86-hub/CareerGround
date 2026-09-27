"""Synthetic exact-review boundary changes and publication recheck."""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.boundary_review import (
    BoundaryReviewRejected,
    BoundaryReviewService,
    VerifiedBoundaryApproval,
)
from careerground.domain.conflict_review import (
    ConflictReviewRejected,
    ConflictReviewService,
    VerifiedConflictApproval,
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
from careerground.domain.graph_projection import get_claim_evidence
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    ClaimConstraint,
    ClaimReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
)
from careerground.storage.models import Account, Base, CareerProfile, DeletionWorkItem

SECRET = b"synthetic-boundary-review-signing-key-32-bytes"


class BoundaryReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 15, tzinfo=UTC)
        self.service = BoundaryReviewService(SECRET)
        self.conflicts = ConflictReviewService(SECRET)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id="claim-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        scope_key="project-a",
                        claim_type="CONTRIBUTION",
                        canonical_text="I implemented a feature",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    Claim(
                        id="claim-unaffected",
                        account_id="acct-a",
                        profile_id="profile-a",
                        scope_key="project-b",
                        claim_type="CONTRIBUTION",
                        canonical_text="I maintained documentation",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    EvidenceSource(
                        id="source-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_type="EXPLICIT_PROFILING_INPUT",
                        source_ref="synthetic-input",
                        content_hash="0" * 64,
                        created_in_version=1,
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    EvidenceItem(
                        id="support-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_id="source-a",
                        content_text="I implemented a feature",
                        content_hash=hashlib.sha256(b"I implemented a feature").hexdigest(),
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    EvidenceItem(
                        id="contradiction-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_id="source-a",
                        content_text="I did not lead this work",
                        content_hash=hashlib.sha256(b"I did not lead this work").hexdigest(),
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    EvidenceClaimLink(
                        id="support-link",
                        account_id="acct-a",
                        profile_id="profile-a",
                        evidence_id="support-a",
                        claim_id="claim-a",
                        relation_type="SUPPORTS",
                        created_in_version=1,
                    ),
                    EvidenceClaimLink(
                        id="contradiction-link",
                        account_id="acct-a",
                        profile_id="profile-a",
                        evidence_id="contradiction-a",
                        claim_id="claim-a",
                        relation_type="CONTRADICTS",
                        created_in_version=1,
                    ),
                    ClaimAssessment(
                        id="assessment-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        claim_id="claim-a",
                        knowledge_status="USER_CONFIRMED",
                        consistency_status="DISPUTED",
                        usage_policy="REVIEW_REQUIRED",
                        profile_version=1,
                        assessed_at=self.now,
                    ),
                    ClaimAssessment(
                        id="assessment-unaffected",
                        account_id="acct-a",
                        profile_id="profile-a",
                        claim_id="claim-unaffected",
                        knowledge_status="USER_CONFIRMED",
                        consistency_status="CONSISTENT",
                        usage_policy="ALLOWED",
                        profile_version=1,
                        assessed_at=self.now,
                    ),
                    ClaimReview(
                        id="review-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        claim_id="claim-a",
                        review_batch_id="synthetic-fact-batch",
                        review_item_id="synthetic-fact-item",
                        review_digest="3" * 64,
                        review_purpose="FACT_CONFIRMATION",
                        review_action="ACCEPT",
                        base_profile_version=0,
                        profile_version=1,
                        reviewed_at=self.now,
                    ),
                    ClaimConstraint(
                        id="old-boundary",
                        account_id="acct-a",
                        profile_id="profile-a",
                        scope_key="project-a",
                        constraint_type="DO_NOT_USE",
                        exact_text="Do not claim sole leadership",
                        status="ACTIVE",
                        review_batch_id="synthetic-boundary-batch",
                        review_item_id="synthetic-boundary-item",
                        review_digest="4" * 64,
                        created_in_version=0,
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            ensure_profile_archive(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=1,
                now=self.now,
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def _approval(self, view):
        return VerifiedBoundaryApproval(
            account_id="acct-a",
            review_id=view.review_id,
            action=view.action,
            review_digest=view.review_digest,
            expires_at=view.expires_at,
        )

    def _conflict_approval(self, view):
        return VerifiedConflictApproval(
            account_id="acct-a",
            review_id=view.review_id,
            resolution=view.resolution,
            review_digest=view.review_digest,
            expires_at=view.expires_at,
        )

    def test_conflict_review_preserves_opposing_evidence_and_never_auto_publishes(self) -> None:
        for resolution in (
            "KEEP_EXISTING",
            "ACCEPT_CORRECTION",
            "KEEP_BOTH_SCOPED",
            "REMAIN_UNCERTAIN",
        ):
            with self.subTest(resolution=resolution), Session(self.engine) as session:
                view = self.conflicts.prepare(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    claim_id="claim-a",
                    conflict_link_id="contradiction-link",
                    resolution=resolution,
                    explanation="Synthetic explicit decision; keep opposing source trace",
                    now=self.now,
                )
                self.assertEqual(view.opposing_evidence_text, "I did not lead this work")
                review = self.conflicts.submit(
                    session, view=view, approval=self._conflict_approval(view), now=self.now
                )
                self.assertEqual(
                    self.conflicts.submit(
                        session, view=view, approval=self._conflict_approval(view), now=self.now
                    ).id,
                    review.id,
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
                current = get_claim_evidence(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=2,
                    claim_id="claim-a",
                )
                self.assertIn("CONTRADICTS", {item.relation_type for item in current.evidence})
                self.assertNotEqual(current.claim.usage_policy, "ALLOWED")
                if resolution == "ACCEPT_CORRECTION":
                    self.assertEqual(current.claim.consistency_status, "CONTRADICTED")
                    self.assertEqual(current.claim.usage_policy, "DO_NOT_CLAIM")
                else:
                    self.assertEqual(current.claim.consistency_status, "DISPUTED")
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(ClaimAssessment)
                        .where(ClaimAssessment.claim_id == "claim-unaffected")
                    ),
                    1,
                )
                session.rollback()

    def test_conflict_review_rejects_wrong_owner_and_changed_explanation(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(ConflictReviewRejected):
                self.conflicts.prepare(
                    session,
                    account_id="acct-b",
                    profile_id="profile-a",
                    claim_id="claim-a",
                    conflict_link_id="contradiction-link",
                    resolution="REMAIN_UNCERTAIN",
                    explanation="Synthetic explanation",
                    now=self.now,
                )
            view = self.conflicts.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                conflict_link_id="contradiction-link",
                resolution="REMAIN_UNCERTAIN",
                explanation="Synthetic explanation",
                now=self.now,
            )
            with self.assertRaises(ConflictReviewRejected):
                self.conflicts.submit(
                    session,
                    view=replace(view, explanation="Changed explanation"),
                    approval=self._conflict_approval(view),
                    now=self.now,
                )
            with self.assertRaises(ConflictReviewRejected):
                self.conflicts.submit(
                    session,
                    view=view,
                    approval=self._conflict_approval(view),
                    now=self.now + timedelta(minutes=11),
                )
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimConflictReview)), 0
            )

    def test_add_boundary_changes_only_affected_scope_and_replays(self) -> None:
        with Session(self.engine) as session:
            view = self.service.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                evidence_id="contradiction-a",
                action="ADD",
                constraint_id=None,
                proposed_boundary_text="Do not claim final decision authority",
                allowed_wording="I implemented a feature",
                remaining_prohibited_expansion="No final decision claim",
                now=self.now,
            )
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
            review = self.service.submit(
                session, view=view, approval=self._approval(view), now=self.now
            )
            session.commit()
            self.assertEqual(review.action, "ADD")
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(
                self.service.submit(
                    session, view=view, approval=self._approval(view), now=self.now
                ).id,
                review.id,
            )
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(ClaimAssessment)
                    .where(ClaimAssessment.claim_id == "claim-unaffected")
                ),
                1,
            )
            latest = session.scalar(
                select(ClaimAssessment)
                .where(ClaimAssessment.claim_id == "claim-a")
                .order_by(ClaimAssessment.profile_version.desc())
            )
            self.assertEqual(latest.usage_policy, "REVIEW_REQUIRED")
            self.assertEqual(
                len(
                    get_claim_evidence(
                        session,
                        account_id="acct-a",
                        profile_id="profile-a",
                        profile_version=2,
                        claim_id="claim-a",
                    ).constraints
                ),
                2,
            )

    def test_revoke_boundary_keeps_old_snapshot_and_blocks_auto_publication(self) -> None:
        with Session(self.engine) as session:
            view = self.service.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                evidence_id="support-a",
                action="REVOKE",
                constraint_id="old-boundary",
                proposed_boundary_text=None,
                allowed_wording="I implemented a feature",
                remaining_prohibited_expansion="Do not claim sole leadership",
                now=self.now,
            )
            self.assertEqual(view.old_boundary_text, "Do not claim sole leadership")
            self.service.submit(session, view=view, approval=self._approval(view), now=self.now)
            session.commit()
            self.assertEqual(session.get(ClaimConstraint, "old-boundary").status, "REVOKED")
            self.assertEqual(
                len(
                    get_claim_evidence(
                        session,
                        account_id="acct-a",
                        profile_id="profile-a",
                        profile_version=1,
                        claim_id="claim-a",
                    ).constraints
                ),
                1,
            )
            current = get_claim_evidence(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=2,
                claim_id="claim-a",
            )
            self.assertEqual(current.constraints, ())
            self.assertEqual(current.claim.usage_policy, "REVIEW_REQUIRED")

    def test_preexisting_v1_archive_remains_valid_across_boundary_change(self) -> None:
        with Session(self.engine) as session:
            archive = session.scalar(select(ProfileArchive))
            legacy = json.loads(archive.snapshot_json)
            legacy["schema"] = "canonical-foundation-v1"
            legacy["sections"].pop("claim_boundary_reviews")
            legacy["sections"].pop("claim_conflict_reviews")
            for row in legacy["sections"]["claim_constraints"]:
                row.pop("status")
            archive.snapshot_json = json.dumps(
                legacy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            archive.content_hash = hashlib.sha256(archive.snapshot_json.encode()).hexdigest()
            session.commit()
        with Session(self.engine) as session:
            view = self.service.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                evidence_id="support-a",
                action="REVOKE",
                constraint_id="old-boundary",
                proposed_boundary_text=None,
                allowed_wording="I implemented a feature",
                remaining_prohibited_expansion="No sole leadership",
                now=self.now,
            )
            self.service.submit(session, view=view, approval=self._approval(view), now=self.now)
            session.commit()
            versions = tuple(
                session.scalars(select(ProfileArchive).order_by(ProfileArchive.profile_version))
            )
            self.assertEqual(
                [json.loads(row.snapshot_json)["schema"] for row in versions],
                [
                    "canonical-foundation-v1",
                    "canonical-foundation-v2",
                ],
            )

    def test_wrong_owner_tampering_and_stale_version_reject(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(BoundaryReviewRejected):
                self.service.prepare(
                    session,
                    account_id="acct-b",
                    profile_id="profile-a",
                    claim_id="claim-a",
                    evidence_id="support-a",
                    action="REVOKE",
                    constraint_id="old-boundary",
                    proposed_boundary_text=None,
                    allowed_wording="I implemented a feature",
                    remaining_prohibited_expansion="No sole leadership",
                    now=self.now,
                )
            view = self.service.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                evidence_id="support-a",
                action="REVOKE",
                constraint_id="old-boundary",
                proposed_boundary_text=None,
                allowed_wording="I implemented a feature",
                remaining_prohibited_expansion="No sole leadership",
                now=self.now,
            )
            with self.assertRaises(BoundaryReviewRejected):
                self.service.submit(
                    session,
                    view=replace(view, allowed_wording="I led the entire team"),
                    approval=self._approval(view),
                    now=self.now,
                )
            with self.assertRaises(BoundaryReviewRejected):
                self.service.submit(
                    session,
                    view=view,
                    approval=self._approval(view),
                    now=self.now + timedelta(minutes=11),
                )
            assessment = session.get(ClaimAssessment, "assessment-a")
            assessment.usage_policy = "ALLOWED"
            session.flush()
            with self.assertRaises(BoundaryReviewRejected):
                self.service.submit(session, view=view, approval=self._approval(view), now=self.now)
            assessment.usage_policy = "REVIEW_REQUIRED"
            session.get(CareerProfile, "profile-a").version = 2
            session.flush()
            with self.assertRaises(BoundaryReviewRejected):
                self.service.submit(session, view=view, approval=self._approval(view), now=self.now)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimBoundaryReview)), 0
            )

    def test_deletion_purges_boundary_journal_before_graph(self) -> None:
        with Session(self.engine) as session:
            view = self.service.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                evidence_id="support-a",
                action="REVOKE",
                constraint_id="old-boundary",
                proposed_boundary_text=None,
                allowed_wording="I implemented a feature",
                remaining_prohibited_expansion="No sole leadership",
                now=self.now,
            )
            self.service.submit(session, view=view, approval=self._approval(view), now=self.now)
            conflict_view = self.conflicts.prepare(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                claim_id="claim-a",
                conflict_link_id="contradiction-link",
                resolution="REMAIN_UNCERTAIN",
                explanation="Synthetic uncertainty",
                now=self.now,
            )
            self.conflicts.submit(
                session,
                view=conflict_view,
                approval=self._conflict_approval(conflict_view),
                now=self.now,
            )
            session.commit()
        with Session(self.engine) as session:
            preview_service = DeletionPreviewService(SECRET)
            preview = preview_service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertIn("CLAIM_BOUNDARY_REVIEW", {item.kind for item in preview.items})
            self.assertIn("CLAIM_CONFLICT_REVIEW", {item.kind for item in preview.items})
            request = execute_synthetic_deletion(
                session,
                preview_service=preview_service,
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
                    expires_at=self.now + timedelta(minutes=2),
                ),
                now=self.now,
            )
            session.commit()
            work = session.scalar(
                select(DeletionWorkItem).where(
                    DeletionWorkItem.request_id == request.id,
                    DeletionWorkItem.kind == "PROFILE_LOCAL_DATA",
                )
            )
            apply_deletion_work(session, work.id)
            session.commit()
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimBoundaryReview)), 0
            )
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimConflictReview)), 0
            )
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileArchive)), 0)


if __name__ == "__main__":
    unittest.main()

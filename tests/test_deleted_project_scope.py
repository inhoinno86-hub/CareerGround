"""A project tombstone blocks new temporary and canonical writes for its key."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_submission import (
    ReviewSubmissionRejected,
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewUnavailable,
    propose_verbatim_draft,
)
from careerground.domain.profiling_draft_extraction import propose_explicit_bullet_drafts_once
from careerground.storage.graph_models import Claim
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
    ProjectScope,
)


class DeletedProjectScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.now = datetime(2026, 10, 3, 12, tzinfo=UTC)
        self.preparation = ClaimReviewPreparation(b"synthetic-review-signing-key-at-least-32-bytes")
        with Session(self.engine) as session:
            session.add_all([Account(id="a"), Account(id="b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="pa", account_id="a", version=0),
                    CareerProfile(id="pb", account_id="b", version=0),
                ]
            )
            session.flush()
            session.add_all(
                [
                    ProfilingSession(
                        id="sa",
                        account_id="a",
                        profile_id="pa",
                        status="ACTIVE",
                        base_profile_version=0,
                        created_at=self.now,
                        last_activity_at=self.now,
                        retention_expires_at=self.now + timedelta(days=1),
                    ),
                    ProjectScope(
                        id="deleted-project",
                        account_id="a",
                        profile_id="pa",
                        scope_key="project-one",
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="a",
                    session_id="sa",
                    idempotency_key="synthetic_input_0001",
                    content_kind="USER_STATEMENT",
                    body="- I built an offline feature.",
                    created_at=self.now,
                )
            )
            session.commit()

    def _draft(self, session: Session, scope_key: str = "project-one") -> ProfilingDraft:
        draft = propose_verbatim_draft(
            session,
            account_id="a",
            profiling_session_id="sa",
            source_input_id="input-a",
            scope_key=scope_key,
            claim_type="CONTRIBUTION",
            exact_text="I built an offline feature.",
            now=self.now,
        )
        session.flush()
        return draft

    def _tombstone(self, session: Session) -> None:
        session.get(ProjectScope, "deleted-project").status = "DELETING"
        session.flush()

    def test_draft_and_prepare_reject_deleted_key_but_other_key_can_continue(self) -> None:
        with Session(self.engine) as session:
            old_draft = self._draft(session)
            old_draft_id = old_draft.id
            session.commit()
        with Session(self.engine) as session:
            self._tombstone(session)
            session.commit()
        with Session(self.engine) as session:
            with self.assertRaises(ReviewUnavailable):
                self._draft(session)
            with self.assertRaises(ReviewUnavailable):
                propose_explicit_bullet_drafts_once(
                    session,
                    account_id="a",
                    profiling_session_id="sa",
                    source_input_id="input-a",
                    scope_key="project-one",
                    now=self.now,
                )
            with self.assertRaises(ReviewUnavailable):
                self.preparation.prepare(
                    session,
                    account_id="a",
                    profiling_session_id="sa",
                    draft_ids=(old_draft_id,),
                    now=self.now,
                )
            with self.assertRaises(ReviewUnavailable):
                self.preparation.prepare_for_scope(
                    session,
                    account_id="a",
                    profiling_session_id="sa",
                    scope_key="project-one",
                    base_profile_version=0,
                    idempotency_key="synthetic-prep-key-0001",
                    now=self.now,
                )
            other = self._draft(session, "other-project")
            self.assertEqual(other.scope_key, "other-project")
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)

    def test_prepared_approval_cannot_promote_after_project_tombstone(self) -> None:
        with Session(self.engine) as session:
            draft = self._draft(session)
            batch = self.preparation.prepare(
                session,
                account_id="a",
                profiling_session_id="sa",
                draft_ids=(draft.id,),
                now=self.now,
            )
            session.flush()
            item = session.scalar(
                select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == batch.id)
            )
            approval = VerifiedReviewApproval(
                account_id="a",
                batch_id=batch.id,
                review_digest=batch.review_digest,
                decisions=((item.id, "ACCEPT"),),
                expires_at=self.now + timedelta(minutes=3),
            )
            batch_id = batch.id
            session.commit()
        with Session(self.engine) as session:
            self._tombstone(session)
            session.commit()
        with Session(self.engine) as session:
            with self.assertRaises(ReviewSubmissionRejected):
                submit_synthetic_review(
                    session,
                    preparation=self.preparation,
                    approval=approval,
                    now=self.now + timedelta(minutes=1),
                )
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
            self.assertEqual(session.get(CareerProfile, "pa").version, 0)
            self.assertEqual(session.get(ProfilingReviewBatch, batch_id).status, "PREPARED")


if __name__ == "__main__":
    unittest.main()

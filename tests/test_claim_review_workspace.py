"""Temporary review snapshots never promote a canonical Claim without submission."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewIdempotencyConflict,
    ReviewStale,
    ReviewUnavailable,
    propose_verbatim_draft,
)
from careerground.domain.deletion_preview import DeletionPreviewService, DeletionScope
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.profiling_retention import delete_expired_profiling_batch

SECRET = b"synthetic-review-signing-key-at-least-32-bytes"


class ClaimReviewWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        self.service = ClaimReviewPreparation(SECRET)
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
                    body="I implemented target-speed logic and tested it in SIL.",
                    created_at=self.now,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def draft(self, session: Session, text: str, *, scope: str = "feature-a") -> ProfilingDraft:
        return propose_verbatim_draft(
            session,
            account_id="acct-a",
            profiling_session_id="session-a",
            source_input_id="input-a",
            scope_key=scope,
            claim_type="CONTRIBUTION",
            exact_text=text,
            now=self.now,
        )

    def test_exact_snapshot_and_no_implicit_approval(self) -> None:
        with Session(self.engine) as session:
            first = self.draft(session, "I implemented target-speed logic")
            second = self.draft(session, "tested it in SIL")
            session.flush()
            batch = self.service.prepare(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                draft_ids=(first.id, second.id),
                now=self.now,
            )
            session.commit()
            stored, items = self.service.get(
                session, account_id="acct-a", batch_id=batch.id, now=self.now
            )
            self.assertEqual(stored.base_profile_version, 2)
            self.assertEqual(
                [item.exact_text for item in items], [first.exact_text, second.exact_text]
            )
            self.assertEqual([item.decision for item in items], [None, None])
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            with self.assertRaises(ReviewUnavailable):
                self.service.get(session, account_id="acct-b", batch_id=batch.id, now=self.now)
            with self.assertRaises(ReviewUnavailable):
                self.service.get(
                    session,
                    account_id="acct-a",
                    batch_id=batch.id,
                    now=self.now + timedelta(minutes=10),
                )

    def test_scope_preparation_replays_one_exact_batch_without_promotion(self) -> None:
        with Session(self.engine) as session:
            self.draft(session, "I implemented target-speed logic")
            self.draft(session, "tested it in SIL")
            session.flush()
            request = {
                "account_id": "acct-a",
                "profiling_session_id": "session-a",
                "scope_key": "feature-a",
                "base_profile_version": 2,
                "idempotency_key": "synthetic_prepare_0001",
            }
            first = self.service.prepare_for_scope(session, **request, now=self.now)
            session.commit()
            retry = self.service.prepare_for_scope(
                session, **request, now=self.now + timedelta(minutes=1)
            )
            self.assertEqual(retry.id, first.id)
            self.assertEqual(retry.review_digest, first.review_digest)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ProfilingReviewBatch)), 1
            )
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            with self.assertRaises(ReviewIdempotencyConflict):
                self.service.prepare_for_scope(
                    session,
                    **{**request, "scope_key": "feature-b"},
                    now=self.now + timedelta(minutes=1),
                )
            with self.assertRaises(ReviewUnavailable):
                self.service.prepare_for_scope(
                    session,
                    **{
                        **request,
                        "scope_key": "missing",
                        "idempotency_key": "synthetic_prepare_0002",
                    },
                    now=self.now + timedelta(minutes=1),
                )

    def test_mixed_scope_six_items_and_unsupported_inference_fail(self) -> None:
        with Session(self.engine) as session:
            first = self.draft(session, "I implemented target-speed logic")
            second = self.draft(session, "tested it in SIL", scope="feature-b")
            session.flush()
            with self.assertRaises(ValueError):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    draft_ids=(first.id, second.id),
                    now=self.now,
                )
            with self.assertRaises(ValueError):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    draft_ids=tuple(str(index) for index in range(6)),
                    now=self.now,
                )
            with self.assertRaises(ReviewUnavailable):
                self.draft(session, "I owned the full ACC architecture")
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ProfilingReviewBatch)), 0
            )
            for _ in range(5):
                self.draft(session, "I implemented target-speed logic")
            session.flush()
            with self.assertRaises(ValueError):
                self.service.prepare_for_scope(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    scope_key="feature-a",
                    base_profile_version=2,
                    idempotency_key="synthetic_prepare_limit_0001",
                    now=self.now,
                )

    def test_source_or_version_change_rejects_preparation(self) -> None:
        with Session(self.engine) as session:
            draft = self.draft(session, "I implemented target-speed logic")
            session.flush()
            session.get(ProfilingInput, "input-a").body = "I tested it in HIL."
            session.flush()
            with self.assertRaises(ReviewStale):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    draft_ids=(draft.id,),
                    now=self.now,
                )
            session.rollback()
        with Session(self.engine) as session:
            draft = self.draft(session, "I implemented target-speed logic")
            session.flush()
            session.get(CareerProfile, "profile-a").version = 3
            session.flush()
            with self.assertRaises(ReviewStale):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    draft_ids=(draft.id,),
                    now=self.now,
                )

    def test_tampered_snapshot_and_cross_account_fk_fail(self) -> None:
        with Session(self.engine) as session:
            draft = self.draft(session, "I implemented target-speed logic")
            session.flush()
            batch = self.service.prepare(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                draft_ids=(draft.id,),
                now=self.now,
            )
            session.commit()
            item = session.scalar(
                select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == batch.id)
            )
            item.exact_text = "I owned the full ACC architecture"
            session.flush()
            with self.assertRaises(ReviewStale):
                self.service.get(session, account_id="acct-a", batch_id=batch.id, now=self.now)
            session.rollback()
            session.add(
                ProfilingDraft(
                    id="bad-cross-account",
                    account_id="acct-b",
                    session_id="session-a",
                    source_input_id="input-a",
                    scope_key="feature-a",
                    claim_type="CONTRIBUTION",
                    exact_text="synthetic",
                    source_content_hash="0" * 64,
                    status="DRAFT",
                    created_at=self.now,
                    expires_at=self.now + timedelta(days=90),
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_review_rows_appear_in_deletion_impact_and_expire_with_workspace(self) -> None:
        preview_service = DeletionPreviewService(SECRET)
        with Session(self.engine) as session:
            before = preview_service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            draft = self.draft(session, "I implemented target-speed logic")
            session.flush()
            batch = self.service.prepare(
                session,
                account_id="acct-a",
                profiling_session_id="session-a",
                draft_ids=(draft.id,),
                now=self.now,
            )
            session.flush()
            after = preview_service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertNotEqual(before.deletion_digest, after.deletion_digest)
            self.assertIn(
                ("PROFILING_DRAFT", draft.id), {(i.kind, i.target_id) for i in after.items}
            )
            self.assertIn(
                ("PROFILING_REVIEW_BATCH", batch.id),
                {(i.kind, i.target_id) for i in after.items},
            )
            session.commit()
        with Session(self.engine) as session:
            result = delete_expired_profiling_batch(session, now=self.now + timedelta(days=90))
            self.assertEqual((result.sessions_deleted, result.inputs_deleted), (1, 1))
            session.commit()
            for model in (ProfilingDraft, ProfilingReviewBatch, ProfilingReviewItem):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)


if __name__ == "__main__":
    unittest.main()

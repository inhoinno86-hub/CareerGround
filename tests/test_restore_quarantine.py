"""Old synthetic snapshot remains closed until a signed erasure ledger is replayed."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.claim_review_submission import (
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.deletion_execution import execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import JobDescription
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    ErasureLedger,
    PrivateObject,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

SECRET = b"synthetic-restore-signing-key-32-bytes"


def engine_for(path: Path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


class RestoreQuarantineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.live_path = root / "live.sqlite"
        self.old_path = root / "old.sqlite"
        self.engine = engine_for(self.live_path)
        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=1),
                    AuthIdentity(id="identity-a", account_id="acct-a", issuer="test", subject="a"),
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
                    body="synthetic old career material",
                    created_at=self.now,
                )
            )
            session.commit()
        shutil.copyfile(self.live_path, self.old_path)
        with Session(self.engine) as session:
            service = DeletionPreviewService(SECRET)
            preview = service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            execute_synthetic_deletion(
                session,
                preview_service=service,
                ledger_secret=SECRET,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                deletion_digest=preview.deletion_digest,
                acknowledged_impact=True,
                step_up=VerifiedDeletionApproval(
                    "acct-a", DeletionScope.ACCOUNT, "acct-a", self.now + timedelta(minutes=3)
                ),
                now=self.now,
            )
            session.commit()
            self.ledger = list(session.scalars(select(ErasureLedger)))
            for row in self.ledger:
                session.expunge(row)
        self.manifest = signed_manifest(self.ledger, secret=SECRET)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp.cleanup()

    def test_old_snapshot_stays_closed_then_reconciles_without_fallback(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
                gate.reconcile(
                    session,
                    ledger_rows=self.ledger,
                    expected_manifest=self.manifest,
                    secret=SECRET,
                )
                gate.assert_ready()
                self.assertEqual(session.get(Account, "acct-a").status, "DELETING")
                self.assertIsNone(session.get(ProfilingInput, "input-a"))
                self.assertIsNone(session.get(ProfilingSession, "session-a"))
                self.assertIsNone(session.get(AuthIdentity, "identity-a"))
                with self.assertRaises(ResourceNotFound):
                    get_owned_profile(session, account_id="acct-a", profile_id="profile-a")
                self.assertIsNotNone(
                    get_owned_profile(session, account_id="acct-b", profile_id="profile-b")
                )
        finally:
            restored.dispose()

    def test_missing_or_tampered_ledger_keeps_snapshot_closed(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session, ledger_rows=[], expected_manifest=self.manifest, secret=SECRET
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
                self.ledger[0].target_id = "acct-b"
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session,
                        ledger_rows=self.ledger,
                        expected_manifest=self.manifest,
                        secret=SECRET,
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
                self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")
        finally:
            restored.dispose()

    def test_partial_replay_rolls_back_the_first_erasure(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        invalid = ErasureLedger(
            request_id="synthetic-invalid-ledger-record",
            account_id="acct-b",
            scope="ACCOUNT",
            target_id="acct-b",
            created_at=self.now,
            signature="0" * 64,
        )
        records = [*self.ledger, invalid]
        checkpoint = signed_manifest(records, secret=SECRET)
        try:
            with Session(restored) as session:
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session,
                        ledger_rows=records,
                        expected_manifest=checkpoint,
                        secret=SECRET,
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
                self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")
                self.assertIsNotNone(session.get(ProfilingInput, "input-a"))
        finally:
            restored.dispose()

    def test_unverified_private_object_keeps_restored_copy_closed(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                session.add(
                    PrivateObject(
                        id="synthetic-object",
                        account_id="acct-a",
                        profile_id="profile-a",
                        object_class="UPLOAD_ORIGINAL",
                        status="ACTIVE",
                        retention_anchor_at=self.now,
                        retention_expires_at=self.now + timedelta(days=30),
                        created_at=self.now,
                    )
                )
                session.commit()
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session,
                        ledger_rows=self.ledger,
                        expected_manifest=self.manifest,
                        secret=SECRET,
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
                self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")
        finally:
            restored.dispose()

    def test_old_canonical_graph_keeps_restored_copy_closed(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                draft = propose_verbatim_draft(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    source_input_id="input-a",
                    scope_key="feature-a",
                    claim_type="CONTRIBUTION",
                    exact_text="synthetic old career material",
                    now=self.now,
                )
                session.flush()
                preparation = ClaimReviewPreparation(SECRET)
                batch = preparation.prepare(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    draft_ids=(draft.id,),
                    now=self.now,
                )
                session.flush()
                item = session.scalar(
                    select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == batch.id)
                )
                submit_synthetic_review(
                    session,
                    preparation=preparation,
                    approval=VerifiedReviewApproval(
                        account_id="acct-a",
                        batch_id=batch.id,
                        review_digest=batch.review_digest,
                        decisions=((item.id, "ACCEPT"),),
                        expires_at=self.now + timedelta(minutes=3),
                    ),
                    now=self.now,
                )
                session.commit()
                self.assertIsNotNone(session.scalar(select(Claim)))
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session,
                        ledger_rows=self.ledger,
                        expected_manifest=self.manifest,
                        secret=SECRET,
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
        finally:
            restored.dispose()

    def test_old_jd_excerpt_keeps_restored_copy_closed(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                session.add(
                    JobDescription(
                        id="synthetic-jd",
                        account_id="acct-a",
                        profile_id="profile-a",
                        jd_version=1,
                        source_kind="PASTED_TEXT",
                        source_hash="0" * 64,
                        source_length=10,
                        company_name=None,
                        job_title=None,
                        status="ACTIVE",
                        created_at=self.now,
                    )
                )
                session.commit()
                with self.assertRaises(QuarantineRejected):
                    gate.reconcile(
                        session,
                        ledger_rows=self.ledger,
                        expected_manifest=self.manifest,
                        secret=SECRET,
                    )
                with self.assertRaises(QuarantineRejected):
                    gate.assert_ready()
        finally:
            restored.dispose()

    def test_replay_purges_temporary_review_snapshot_with_input(self) -> None:
        restored = engine_for(self.old_path)
        gate = RestoreQuarantine()
        try:
            with Session(restored) as session:
                draft = propose_verbatim_draft(
                    session,
                    account_id="acct-a",
                    profiling_session_id="session-a",
                    source_input_id="input-a",
                    scope_key="feature-a",
                    claim_type="CONTRIBUTION",
                    exact_text="synthetic old career material",
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
                session.commit()
                gate.reconcile(
                    session,
                    ledger_rows=self.ledger,
                    expected_manifest=self.manifest,
                    secret=SECRET,
                )
                gate.assert_ready()
                for model in (ProfilingDraft, ProfilingReviewBatch, ProfilingReviewItem):
                    self.assertEqual(len(list(session.scalars(select(model)))), 0)
        finally:
            restored.dispose()


if __name__ == "__main__":
    unittest.main()

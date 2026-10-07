"""Short internal status proof after synthetic explicit account deletion."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.authorization import (
    AuthenticationRequired,
    VerifiedIdentity,
    resolve_account_id,
)
from careerground.domain.deletion_execution import apply_deletion_work, execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.domain.deletion_status_capability import (
    DeletionStatusCapabilityRejected,
    DeletionStatusCapabilityService,
    TrustedDeletionStatusIssuer,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    ErasureLedger,
)

SECRET = b"synthetic-internal-status-capability-32-byte-secret"
LEDGER_SECRET = b"synthetic-deletion-ledger-32-byte-secret"


class DeletionStatusCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 10, 1, tzinfo=UTC)
        self.ready = [True]
        self.service = DeletionStatusCapabilityService(
            SECRET, restore_quarantine_ready=lambda: self.ready[0]
        )
        self.approval = VerifiedDeletionApproval(
            account_id="acct-a",
            scope=DeletionScope.ACCOUNT,
            target_id="acct-a",
            expires_at=self.now + timedelta(minutes=3),
        )
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=0),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                    AuthIdentity(
                        id="identity-a",
                        account_id="acct-a",
                        issuer="https://auth.synthetic.example/",
                        subject="user-a",
                    ),
                ]
            )
            session.commit()

    def sessions(self) -> Session:
        return Session(self.engine)

    def execute(self) -> tuple[str, str]:
        with self.sessions() as session:
            preview_service = DeletionPreviewService(LEDGER_SECRET)
            preview = preview_service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            request = execute_synthetic_deletion(
                session,
                preview_service=preview_service,
                ledger_secret=LEDGER_SECRET,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                deletion_digest=preview.deletion_digest,
                acknowledged_impact=True,
                step_up=self.approval,
                now=self.now,
            )
            request_id = request.id
            proof = self.service.issue(
                session,
                trusted_issuer=TrustedDeletionStatusIssuer(request_id, self.approval),
                now=self.now,
            )
            session.commit()
        return request_id, proof

    def test_status_remains_available_after_active_identity_is_erased(self) -> None:
        request_id, proof = self.execute()
        with self.sessions() as session:
            identity_item = session.scalar(
                select(DeletionWorkItem).where(
                    DeletionWorkItem.request_id == request_id,
                    DeletionWorkItem.kind == "AUTH_IDENTITY",
                )
            )
            apply_deletion_work(session, identity_item.id)
            session.commit()
        with self.sessions() as session:
            with self.assertRaises(AuthenticationRequired):
                resolve_account_id(
                    session, VerifiedIdentity("https://auth.synthetic.example/", "user-a")
                )
            snapshot = self.service.read(session, capability=proof, now=self.now)
            self.assertEqual(snapshot.erasure_request_id, request_id)
            self.assertEqual(snapshot.status, "DELETING")
            self.assertEqual(snapshot.known_local_done, 1)
            self.assertGreaterEqual(snapshot.pending_or_failed, 1)
            self.assertGreaterEqual(snapshot.unverified, 0)
            self.assertEqual(snapshot.coverage, "FOUNDATION_ONLY")
            self.assertFalse(snapshot.ready_to_execute)
            self.assertEqual(session.get(Account, "acct-a").status, "DELETING")

    def test_wrong_approval_absent_ledger_and_unready_restore_refuse_issuance(self) -> None:
        request_id, proof = self.execute()
        wrong = VerifiedDeletionApproval(
            account_id="acct-b",
            scope=DeletionScope.ACCOUNT,
            target_id="acct-b",
            expires_at=self.now + timedelta(minutes=3),
        )
        with self.sessions() as session:
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.issue(
                    session,
                    trusted_issuer=TrustedDeletionStatusIssuer(request_id, wrong),
                    now=self.now,
                )
            session.delete(session.get(ErasureLedger, request_id))
            session.flush()
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.issue(
                    session,
                    trusted_issuer=TrustedDeletionStatusIssuer(request_id, self.approval),
                    now=self.now,
                )
            session.rollback()

        self.ready[0] = False
        with self.sessions() as session:
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.issue(
                    session,
                    trusted_issuer=TrustedDeletionStatusIssuer(request_id, self.approval),
                    now=self.now,
                )
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.read(session, capability=proof, now=self.now)
        self.ready[0] = True
        with self.sessions() as session:
            self.assertEqual(
                self.service.read(session, capability=proof, now=self.now).status, "DELETING"
            )

    def test_proof_is_exact_signed_short_lived_and_metadata_only(self) -> None:
        request_id, proof = self.execute()
        self.assertNotIn("synthetic private source", proof)
        self.assertLessEqual(len(proof), 1024)
        tampered = ("A" if proof[0] != "A" else "B") + proof[1:]
        with self.sessions() as session:
            for candidate in (tampered, proof + "x", "", request_id):
                with (
                    self.subTest(candidate=candidate[:12]),
                    self.assertRaises(DeletionStatusCapabilityRejected),
                ):
                    self.service.read(session, capability=candidate, now=self.now)
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.read(session, capability=proof, now=self.now + timedelta(minutes=5))

            request = session.get(Account, "acct-a")
            request.status = "ACTIVE"
            session.flush()
            with self.assertRaises(DeletionStatusCapabilityRejected):
                self.service.read(session, capability=proof, now=self.now)
            session.rollback()

    def test_failure_state_is_local_only_and_does_not_certify_erasure(self) -> None:
        request_id, proof = self.execute()
        with self.sessions() as session:
            request = session.get(DeletionRequest, request_id)
            request.status = "FAILED"
            session.commit()
        with self.sessions() as session:
            self.assertEqual(
                self.service.read(session, capability=proof, now=self.now).status, "FAILED"
            )
            request = session.get(DeletionRequest, request_id)
            request.status = "ERASED"
            session.commit()
        with self.sessions() as session:
            self.assertEqual(
                self.service.read(session, capability=proof, now=self.now).status, "DELETING"
            )


if __name__ == "__main__":
    unittest.main()

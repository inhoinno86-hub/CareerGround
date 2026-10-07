"""Fresh-store, local mock deletion: exact consent, local erasure, and restore gate."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.synthetic_deletion_journey import (
    MockDeletionJourney,
    MockDeletionJourneyRejected,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import Account, AuthIdentity, Base, CareerProfile, ErasureLedger
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

PREVIEW_SECRET = b"synthetic-journey-preview-secret-32-byte"
LEDGER_SECRET = b"synthetic-journey-ledger-secret-32-byte"
STATUS_SECRET = b"synthetic-journey-status-secret-32-byte"


def engine_for(path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


class MockDeletionJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = engine_for(self.root / "live.sqlite")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 10, 1, 12, tzinfo=UTC)
        self.service = MockDeletionJourney(PREVIEW_SECRET, LEDGER_SECRET, STATUS_SECRET)
        with Session(self.engine) as session:
            session.add_all([Account(id="account-a"), Account(id="account-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="account-a", version=1),
                    CareerProfile(id="profile-b", account_id="account-b", version=1),
                    AuthIdentity(
                        id="identity-a", account_id="account-a", issuer="test", subject="a"
                    ),
                    AuthIdentity(
                        id="identity-b", account_id="account-b", issuer="test", subject="b"
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id="claim-a",
                        account_id="account-a",
                        profile_id="profile-a",
                        scope_key="a",
                        claim_type="CONTRIBUTION",
                        canonical_text="synthetic private career detail",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    Claim(
                        id="claim-b",
                        account_id="account-b",
                        profile_id="profile-b",
                        scope_key="b",
                        claim_type="CONTRIBUTION",
                        canonical_text="other account's detail",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.commit()

    def flow(self, scope="ACCOUNT", *, session_id="browser-session-a", time=None):
        time = time or self.now
        with Session(self.engine) as session:
            view = self.service.preview(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id=session_id,
                scope=scope,
                now=time,
            )
        with Session(self.engine) as session:
            token = self.service.reauthenticate(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id=session_id,
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=time + timedelta(seconds=1),
            )
        return view, token

    def execute(self, token, *, session_id="browser-session-a", time=None):
        with Session(self.engine) as session:
            result = self.service.execute(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id=session_id,
                step_up_token=token,
                confirmed=True,
                now=time or self.now + timedelta(seconds=2),
            )
            session.commit()
        return result

    def test_account_journey_erases_local_rows_keeps_other_owner_and_status(self):
        view, token = self.flow()
        self.assertEqual(view.scope, "ACCOUNT")
        self.assertIn(("CLAIM", 1), view.impact_counts)
        self.assertNotIn("synthetic private career detail", view.preview_token)
        result = self.execute(token)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Account, "account-a").status, "DELETING")
            self.assertEqual(session.get(CareerProfile, "profile-a").status, "DELETING")
            self.assertIsNone(session.get(AuthIdentity, "identity-a"))
            self.assertIsNone(session.get(Claim, "claim-a"))
            self.assertIsNotNone(session.get(AuthIdentity, "identity-b"))
            self.assertIsNotNone(session.get(Claim, "claim-b"))
            with self.assertRaises(ResourceNotFound):
                get_owned_profile(session, account_id="account-a", profile_id="profile-a")
            self.assertIsNotNone(
                get_owned_profile(session, account_id="account-b", profile_id="profile-b")
            )
            status = self.service.read_status(
                session, capability=result.status_capability, now=self.now + timedelta(seconds=3)
            )
            self.assertEqual(status.erasure_request_id, result.request_id)
            self.assertEqual(
                (status.status, status.coverage, status.ready_to_execute),
                ("DELETING", "FOUNDATION_ONLY", False),
            )
            self.assertGreaterEqual(status.unverified, 1)
        self.assertEqual(self.execute(token), result)

    def test_profile_scope_preserves_account_identity_and_rejects_foreign_session(self):
        view, token = self.flow("PROFILE")
        self.assertEqual(view.target_id, "profile-a")
        with Session(self.engine) as session:
            exact = self.service.describe_step(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="browser-session-a",
                step_up_token=token,
                now=self.now + timedelta(seconds=2),
            )
            self.assertEqual(exact.impact_counts, view.impact_counts)
            self.assertEqual(exact.preview_token, view.preview_token)
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.service.execute(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="different-browser",
                step_up_token=token,
                confirmed=True,
                now=self.now + timedelta(seconds=2),
            )
        result = self.execute(token)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Account, "account-a").status, "ACTIVE")
            self.assertIsNotNone(session.get(AuthIdentity, "identity-a"))
            self.assertIsNone(session.get(Claim, "claim-a"))
            self.assertEqual(
                self.service.read_status(
                    session,
                    capability=result.status_capability,
                    now=self.now + timedelta(seconds=3),
                ).status,
                "DELETING",
            )

    def test_missing_consent_tamper_stale_impact_and_version_fail_closed(self):
        with Session(self.engine) as session:
            view = self.service.preview(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="browser-session-a",
                scope="ACCOUNT",
                now=self.now,
            )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.reauthenticate(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    preview_token=view.preview_token,
                    acknowledged_impact=False,
                    mock_reauthenticated=True,
                    now=self.now,
                )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.reauthenticate(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    preview_token=view.preview_token,
                    acknowledged_impact=True,
                    mock_reauthenticated=False,
                    now=self.now,
                )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.reauthenticate(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    preview_token=view.preview_token + "x",
                    acknowledged_impact=True,
                    mock_reauthenticated=True,
                    now=self.now,
                )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.reauthenticate(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    preview_token=view.preview_token,
                    acknowledged_impact=True,
                    mock_reauthenticated=True,
                    now=self.now + timedelta(minutes=6),
                )
        with Session(self.engine) as session:
            session.add(
                Claim(
                    id="new-claim-a",
                    account_id="account-a",
                    profile_id="profile-a",
                    scope_key="new",
                    claim_type="CONTRIBUTION",
                    canonical_text="new private item",
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.commit()
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.service.reauthenticate(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="browser-session-a",
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )
            session.get(CareerProfile, "profile-a").version = 2
            session.commit()
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.service.reauthenticate(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="browser-session-a",
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )

    def test_signed_ledger_blocks_old_snapshot_with_predelete_graph(self):
        old_path = self.root / "old.sqlite"
        shutil.copyfile(self.root / "live.sqlite", old_path)
        _, token = self.flow()
        self.execute(token)
        with Session(self.engine) as session:
            ledger = list(session.scalars(select(ErasureLedger)))
            for row in ledger:
                session.expunge(row)
        restored = engine_for(old_path)
        self.addCleanup(restored.dispose)
        gate = RestoreQuarantine()
        with Session(restored) as session:
            with self.assertRaises(QuarantineRejected):
                gate.assert_ready()
            with self.assertRaises(QuarantineRejected):
                gate.reconcile(
                    session,
                    ledger_rows=ledger,
                    expected_manifest=signed_manifest(ledger, secret=LEDGER_SECRET),
                    secret=LEDGER_SECRET,
                )
            with self.assertRaises(QuarantineRejected):
                gate.assert_ready()
            self.assertEqual(session.get(Account, "account-a").status, "ACTIVE")
            self.assertIsNotNone(session.get(Claim, "claim-a"))
            self.assertIsNotNone(session.get(Claim, "claim-b"))

    def test_stale_after_step_and_rollback_retry(self):
        _, token = self.flow()
        with Session(self.engine) as session:
            session.add(
                Claim(
                    id="late-claim-a",
                    account_id="account-a",
                    profile_id="profile-a",
                    scope_key="late",
                    claim_type="CONTRIBUTION",
                    canonical_text="late private material",
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.commit()
        with Session(self.engine) as session:
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.describe_step(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    step_up_token=token,
                    now=self.now + timedelta(seconds=2),
                )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.service.execute(
                    session,
                    account_id="account-a",
                    profile_id="profile-a",
                    browser_session_id="browser-session-a",
                    step_up_token=token,
                    confirmed=True,
                    now=self.now + timedelta(seconds=2),
                )
        _, fresh = self.flow(time=self.now + timedelta(seconds=10))
        with Session(self.engine) as session:
            staged = self.service.execute(
                session,
                account_id="account-a",
                profile_id="profile-a",
                browser_session_id="browser-session-a",
                step_up_token=fresh,
                confirmed=True,
                now=self.now + timedelta(seconds=12),
            )
            session.rollback()
        committed = self.execute(fresh, time=self.now + timedelta(seconds=13))
        self.assertNotEqual(staged.request_id, committed.request_id)
        self.assertEqual(self.execute(fresh, time=self.now + timedelta(seconds=14)), committed)


if __name__ == "__main__":
    unittest.main()

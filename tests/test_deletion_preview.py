"""Synthetic deletion impact/confirmation checks; no erasure execution occurs."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.deletion_preview import (
    DeletionConfirmationRejected,
    DeletionPreviewService,
    DeletionScope,
    DeletionTargetUnavailable,
    VerifiedDeletionApproval,
)
from careerground.domain.profiling_workspace import (
    InputKind,
    append_explicit_profiling_input,
    start_profiling_session,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
)
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app


class DeletionPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all(
                [
                    Account(id="acct-a", status="ACTIVE"),
                    Account(id="acct-b", status="ACTIVE"),
                    AuthIdentity(
                        id="identity-a", account_id="acct-a", issuer="https://a/", subject="a"
                    ),
                    AuthIdentity(
                        id="identity-b", account_id="acct-b", issuer="https://a/", subject="b"
                    ),
                    CareerProfile(id="profile-a", account_id="acct-a", version=2),
                    CareerProfile(id="profile-b", account_id="acct-b", version=4),
                ]
            )
            session.commit()
        self.service = DeletionPreviewService(b"synthetic-only-secret-32-bytes-long!!")
        self.now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)

    def tearDown(self) -> None:
        self.engine.dispose()

    def approval(
        self, scope: DeletionScope = DeletionScope.ACCOUNT, target_id: str = "acct-a"
    ) -> VerifiedDeletionApproval:
        return VerifiedDeletionApproval(
            account_id="acct-a",
            scope=scope,
            target_id=target_id,
            expires_at=self.now + timedelta(minutes=2),
        )

    def confirm(self, session: Session, digest: str, **changes: object):
        arguments = {
            "account_id": "acct-a",
            "scope": DeletionScope.ACCOUNT,
            "target_id": "acct-a",
            "deletion_digest": digest,
            "acknowledged_impact": True,
            "step_up": self.approval(),
            "now": self.now + timedelta(seconds=10),
        }
        arguments.update(changes)
        return self.service.confirm_intent(session, **arguments)

    def test_account_preview_is_non_mutating_and_confirmable(self) -> None:
        with Session(self.engine) as session:
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            self.assertEqual(preview.coverage, "FOUNDATION_ONLY")
            self.assertFalse(preview.ready_to_execute)
            self.assertEqual(
                {(item.kind, item.target_id) for item in preview.items},
                {
                    ("ACCOUNT", "acct-a"),
                    ("AUTH_IDENTITY", "identity-a"),
                    ("CAREER_PROFILE", "profile-a"),
                },
            )
            self.assertNotIn("https://a/", preview.deletion_digest)
            self.assertLessEqual(len(preview.deletion_digest), 96)
            confirmed = self.confirm(session, preview.deletion_digest)
            self.assertEqual(confirmed, preview)
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionWorkItem)), 0)
            self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")

    def test_isolated_browser_preview_is_explicitly_incomplete_and_read_only(self) -> None:
        app = build_synthetic_review_app(
            session_factory=sessionmaker(bind=self.engine),
            authenticate_browser=lambda request, _response: (
                TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a")
                if request.cookies.get("cg_session") == "opaque-a"
                else TrustedBrowserIdentity("acct-b", "synthetic-browser-session-b")
                if request.cookies.get("cg_session") == "opaque-b"
                else None
            ),
            review_signing_secret=b"synthetic-review-secret-32-bytes-long",
            presentation_signing_secret=b"synthetic-preview-secret-32-bytes-long",
        )
        with TestClient(app) as client:
            self.assertEqual(client.get("/deletion/preview/account").status_code, 401)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get("/deletion/preview/profile/profile-a").status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            account = client.get("/deletion/preview/account")
            self.assertEqual(account.status_code, 200)
            self.assertEqual(account.headers["cache-control"], "no-store")
            self.assertIn("일부만 집계", account.text)
            self.assertIn("적용 가능: 아니오", account.text)
            self.assertIn("AUTH_IDENTITY: 1", account.text)
            self.assertNotIn("https://a/", account.text)
            self.assertNotIn("name='deletion_digest'", account.text)
            profile = client.get("/deletion/preview/profile/profile-a")
            self.assertEqual(profile.status_code, 200)
            self.assertIn("CAREER_PROFILE: 1", profile.text)
            self.assertNotIn("AUTH_IDENTITY", profile.text)
            self.assertEqual(client.post("/deletion/preview/account").status_code, 405)
            with Session(self.engine) as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(DeletionRequest)), 0
                )
                self.assertEqual(session.get(Account, "acct-a").status, "ACTIVE")

    def test_changed_impact_or_expired_digest_cannot_be_confirmed(self) -> None:
        with Session(self.engine) as session:
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            session.get(CareerProfile, "profile-a").version += 1
            session.commit()
            with self.assertRaises(DeletionConfirmationRejected):
                self.confirm(session, preview.deletion_digest)

            fresh = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            session.add(
                AuthIdentity(
                    id="identity-a-extra",
                    account_id="acct-a",
                    issuer="https://other/",
                    subject="a",
                )
            )
            session.commit()
            with self.assertRaises(DeletionConfirmationRejected):
                self.confirm(session, fresh.deletion_digest)
            with self.assertRaises(DeletionConfirmationRejected):
                self.confirm(
                    session,
                    fresh.deletion_digest,
                    now=self.now + timedelta(minutes=5),
                )

    def test_confirmation_requires_exact_target_ack_and_trusted_step_up(self) -> None:
        with Session(self.engine) as session:
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.ACCOUNT,
                target_id="acct-a",
                now=self.now,
            )
            for changes in (
                {"acknowledged_impact": False},
                {"acknowledged_impact": "yes"},
                {"step_up": None},
                {"step_up": self.approval(target_id="acct-b")},
                {
                    "deletion_digest": preview.deletion_digest[:-1]
                    + ("0" if preview.deletion_digest[-1] != "0" else "1")
                },
                {"target_id": "acct-b"},
            ):
                with self.subTest(changes=changes), self.assertRaises(DeletionConfirmationRejected):
                    self.confirm(session, preview.deletion_digest, **changes)

    def test_profile_scope_excludes_other_accounts_and_deleting_profiles(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(DeletionTargetUnavailable):
                self.service.preview(
                    session,
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-b",
                    now=self.now,
                )
            preview = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertEqual(len(preview.items), 1)
            confirmed = self.confirm(
                session,
                preview.deletion_digest,
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                step_up=self.approval(DeletionScope.PROFILE, "profile-a"),
            )
            self.assertEqual(confirmed, preview)
            session.get(CareerProfile, "profile-a").status = "DELETING"
            session.commit()
            with self.assertRaises(ResourceNotFound):
                get_owned_profile(session, account_id="acct-a", profile_id="profile-a")
            with self.assertRaises(DeletionConfirmationRejected):
                self.confirm(
                    session,
                    preview.deletion_digest,
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    step_up=self.approval(DeletionScope.PROFILE, "profile-a"),
                )

    def test_workspace_inputs_change_exact_deletion_impact_without_leaking_body(self) -> None:
        with Session(self.engine) as session:
            work = start_profiling_session(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                base_profile_version=2,
                now=self.now,
            )
            session.flush()
            before = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertIn(
                ("PROFILING_SESSION", work.id), {(i.kind, i.target_id) for i in before.items}
            )
            private_text = "synthetic private source text"
            item = append_explicit_profiling_input(
                session,
                account_id="acct-a",
                profiling_session_id=work.id,
                base_profile_version=2,
                content=private_text,
                content_kind=InputKind.USER_STATEMENT,
                idempotency_key="synthetic_input_0001",
                now=self.now + timedelta(seconds=5),
            )
            session.flush()
            after = self.service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertIn(
                ("PROFILING_INPUT", item.id), {(i.kind, i.target_id) for i in after.items}
            )
            self.assertNotIn(private_text, str(after))
            with self.assertRaises(DeletionConfirmationRejected):
                self.confirm(
                    session,
                    before.deletion_digest,
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    step_up=self.approval(DeletionScope.PROFILE, "profile-a"),
                )

    def test_schema_rejects_invalid_deletion_state(self) -> None:
        with Session(self.engine) as session:
            session.add(
                DeletionRequest(
                    id="request-bad",
                    account_id="acct-a",
                    scope="EVIDENCE",
                    target_id="profile-a",
                    status="DELETING",
                    impact_digest="0" * 64,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                DeletionRequest(
                    id="request-a",
                    account_id="acct-a",
                    scope="ACCOUNT",
                    target_id="acct-a",
                    status="DELETING",
                    impact_digest="v1.1780000000." + "0" * 64,
                )
            )
            session.add(
                DeletionWorkItem(
                    id="item-a",
                    request_id="request-a",
                    kind="CAREER_PROFILE",
                    target_id="profile-a",
                    action="ERASE",
                    status="PENDING",
                )
            )
            session.commit()
            self.assertEqual(session.get(DeletionWorkItem, "item-a").status, "PENDING")
            session.add(
                DeletionWorkItem(
                    id="item-duplicate",
                    request_id="request-a",
                    kind="CAREER_PROFILE",
                    target_id="profile-a",
                    action="ERASE",
                    status="PENDING",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()

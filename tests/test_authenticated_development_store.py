"""Private persistent auth data, key/config stability and DB-only rollback denial."""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from careerground.development_runtime import DevelopmentRuntime
from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import AuthenticationRequired, VerifiedIdentity
from careerground.domain.deletion_execution import ledger_signature
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.storage.authenticated_development_store import AuthenticatedDevelopmentStore
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.storage.graph_models import Claim, EvidenceItem
from careerground.storage.models import (
    Account,
    AuthIdentity,
    CareerProfile,
    ErasureLedger,
    ProfilingInput,
    ProfilingSession,
)
from careerground.web.authenticated_management import AuthenticatedManagement
from careerground.web.verified_browser_sessions import COOKIE
from careerground.workers.retention_runner import run_retention_cycle
from tests import test_authenticated_management as fixtures
from tests.test_authenticated_management import ISSUER, ORIGIN, RESOURCE


class AuthenticatedStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "authenticated"
        fixtures.AuthenticatedManagementTests.setUpClass()
        self.fixture = fixtures.AuthenticatedManagementTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client_settings = self.fixture.login.settings

    def open(self, **kwargs):
        store = AuthenticatedDevelopmentStore(self.path, self.client_settings, RESOURCE, **kwargs)
        self.addCleanup(store.close)
        return store

    def app(self, store):
        fixture = self.fixture
        app = AuthenticatedManagement(
            login=fixture.login,
            origin=ORIGIN,
            session_factory=store.sessions,
            account_admission=store.admit,
            review_secret=store.review_secret,
            presentation_secret=store.presentation_secret,
            mcp_settings=McpOAuthSettings(ISSUER, RESOURCE),
            signing_key=lambda _: fixture.key.public_key(),
        )
        fixture.app, fixture.sessions = app, store.sessions
        return app

    def test_restart_preserves_profile_and_keys_but_not_browser_session(self):
        store = self.open()
        self.app(store)
        # Exercise the existing HTTP/MCP fact-review journey against the actual
        # persistent store before checking restart, including its source evidence.
        self.fixture.test_actual_management_confirmation_is_owner_bound_and_consumed_by_mcp()
        with TestClient(self.app(store), base_url=ORIGIN, follow_redirects=False) as browser:
            self.fixture.begin(browser)
            profile_id = self.fixture.rpc(browser, "get_my_profile")["data"]["profile_id"]
            cookie = browser.cookies.get(COOKIE)
            args = {"profile_id": profile_id, "profile_version": 1}
            before = self.fixture.rpc(browser, "get_career_profile", args)
            self.assertEqual(len(before["data"]["claims"]), 1)
            with store.sessions() as session:
                evidence = session.scalar(select(EvidenceItem))
                self.assertEqual(evidence.content_text, "합성 기능의 테스트를 작성했습니다.")
                evidence_before = (evidence.id, evidence.content_text, evidence.content_hash)
            key = store.admission_secret
        store.close()
        reopened = self.open()
        self.assertEqual(reopened.admission_secret, key)
        with TestClient(self.app(reopened), base_url=ORIGIN, follow_redirects=False) as browser:
            browser.cookies.set(COOKIE, cookie)
            self.assertEqual(browser.get("/account").status_code, 401)
            browser.cookies.clear()
            self.fixture.begin(browser)
            self.assertIn(f"/profile/{profile_id}/1", browser.get("/account").text)
            self.assertEqual(
                self.fixture.rpc(browser, "get_my_profile")["data"]["profile_id"], profile_id
            )
            self.assertEqual(self.fixture.rpc(browser, "get_career_profile", args), before)
            with reopened.sessions() as session:
                evidence = session.get(EvidenceItem, evidence_before[0])
                self.assertEqual(
                    (evidence.id, evidence.content_text, evidence.content_hash), evidence_before
                )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.path.iterdir()))

    def test_physical_retention_removes_expired_workspace_and_keeps_approved_facts_on_restart(self):
        store = self.open()
        self.app(store)
        self.fixture.test_actual_management_confirmation_is_owner_bound_and_consumed_by_mcp()
        with store.sessions() as session:
            workspace = session.scalar(select(ProfilingSession))
            workspace.created_at = datetime(1999, 10, 3, tzinfo=UTC)
            workspace.last_activity_at = datetime(1999, 10, 3, tzinfo=UTC)
            workspace.retention_expires_at = datetime(2000, 1, 1, tzinfo=UTC)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 1)
            session.commit()

        async def sweep():
            stopping = asyncio.Event()
            loop = asyncio.get_running_loop()

            def bounded_cycle(*args, **kwargs):
                result = run_retention_cycle(*args, **kwargs)
                self.assertEqual(result, (1, 0))
                loop.call_soon_threadsafe(stopping.set)
                return result

            with patch("careerground.auth0_development_runtime.run_retention_cycle", bounded_cycle):
                await asyncio.wait_for(_retention_loop(store, stopping), timeout=5)

        asyncio.run(sweep())
        store.close()
        reopened = self.open()
        with reopened.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingInput)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 1)

    def test_unsafe_development_flags_fail_before_provider_discovery(self):
        with patch("careerground.auth0_development_runtime.discover") as discover:
            for flags in ({"allow_retention": True}, {"require_deletion_mfa": True}):
                with self.subTest(flags=flags), self.assertRaises(ValueError):
                    Auth0DevelopmentRuntime(None, None, **flags)
            discover.assert_not_called()

    def test_account_tombstone_still_denies_reenrollment_after_restart(self):
        store = self.open()
        identity = VerifiedIdentity(ISSUER, "user-a")
        account_id = store.admit(identity)
        with store.sessions() as session:
            profile = initialize_account_profile(
                session, identity=identity, enrollment_account_id=account_id
            )
            session.get(Account, profile.account_id).status = "ERASED"
            session.execute(delete(AuthIdentity))
            session.commit()
        store.close()
        reopened = self.open()
        self.assertEqual(reopened.admit(identity), account_id)
        with reopened.sessions() as session:
            with self.assertRaises(AuthenticationRequired):
                initialize_account_profile(
                    session, identity=identity, enrollment_account_id=reopened.admit(identity)
                )
            self.assertEqual(len(session.scalars(select(Account)).all()), 1)

    def test_lock_binding_permissions_symlink_and_synthetic_store_are_rejected(self):
        store = self.open()
        with self.assertRaises((DevelopmentStoreRejected, BlockingIOError)):
            self.open()
        store.close()
        for settings in (
            replace(self.client_settings, client_id="different-client"),
            replace(self.client_settings, issuer="https://different.synthetic.example/"),
        ):
            with self.assertRaises(DevelopmentStoreRejected):
                AuthenticatedDevelopmentStore(self.path, settings, RESOURCE)
        with self.assertRaises(DevelopmentStoreRejected):
            AuthenticatedDevelopmentStore(
                self.path, self.client_settings, "https://other.synthetic.example/mcp"
            )
        self.path.chmod(0o755)
        with self.assertRaises(DevelopmentStoreRejected):
            self.open()
        self.path.chmod(0o700)
        alias = self.path.parent / "alias"
        alias.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(DevelopmentStoreRejected):
            AuthenticatedDevelopmentStore(alias, self.client_settings, RESOURCE)
        demo_path = self.path.parent / "synthetic"
        demo = DevelopmentRuntime(8091, demo_path)
        demo.close()
        before = (demo_path / "synthetic.sqlite").read_bytes()
        with self.assertRaises(DevelopmentStoreRejected):
            AuthenticatedDevelopmentStore(demo_path, self.client_settings, RESOURCE)
        self.assertEqual((demo_path / "synthetic.sqlite").read_bytes(), before)

    def test_unsigned_checkpoint_and_corrupt_schema_fail_closed(self):
        store = self.open()
        store.close()
        ledger = self.path / "ledger.json"
        ledger.write_text("[{}]\n")
        with self.assertRaises(DevelopmentStoreRejected):
            self.open()
        ledger.write_text("[]\n")
        with sqlite3.connect(self.path / "authenticated.sqlite") as db:
            db.execute("CREATE TABLE unexpected_private_copy (payload TEXT)")
        with self.assertRaises(DevelopmentStoreRejected):
            self.open()

    def test_key_replacement_after_identity_erasure_is_rejected(self):
        store = self.open()
        store.close()
        (self.path / "admission.key").write_bytes(b"X" * 32)
        with self.assertRaises(DevelopmentStoreRejected):
            self.open()

    def test_db_only_restore_cannot_resurrect_erased_identity(self):
        store = self.open()
        identity = VerifiedIdentity(ISSUER, "user-a")
        with store.sessions() as session:
            profile = initialize_account_profile(
                session, identity=identity, enrollment_account_id=store.admit(identity)
            )
            account_id, profile_id = profile.account_id, profile.id
            session.commit()
        backup = self.path.parent / "before-deletion.sqlite"
        store.engine.dispose()
        shutil.copyfile(store.database_path, backup)
        now = datetime.now(UTC)
        request_id = "00000000-0000-0000-0000-000000000099"
        with store.sessions() as session:
            session.add(
                ErasureLedger(
                    request_id=request_id,
                    account_id=account_id,
                    scope="ACCOUNT",
                    target_id=account_id,
                    created_at=now,
                    signature=ledger_signature(
                        store.ledger_secret,
                        request_id=request_id,
                        account_id=account_id,
                        scope="ACCOUNT",
                        target_id=account_id,
                        created_at=now,
                    ),
                )
            )
            session.flush()
            store.before_deletion_commit(session)
            session.get(Account, account_id).status = "ERASED"
            session.get(CareerProfile, profile_id).status = "ERASED"
            session.execute(delete(AuthIdentity))
            session.commit()
        store.close()
        shutil.copyfile(backup, self.path / "authenticated.sqlite")
        # A backup containing archived profile content stays quarantined;
        # reconciliation must not silently serve or erase that old copy.
        with self.assertRaises(DevelopmentStoreRejected):
            self.open()


from careerground.auth0_development_runtime import Auth0DevelopmentRuntime, _retention_loop

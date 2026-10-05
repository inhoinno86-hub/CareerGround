"""Fresh signed provider authentication -> separate local PROFILE erasure consent."""

import json
import re
import shutil
import tempfile
import unittest
from html import unescape
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
from fastapi import Response
from sqlalchemy import func, select

from careerground.domain.authorization import VerifiedIdentity
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.providers.oidc_identity import MFA_AUTHENTICATION_CONTEXT
from careerground.storage.authenticated_development_store import AuthenticatedDevelopmentStore
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.storage.graph_models import Claim, EvidenceItem
from careerground.storage.models import CareerProfile, DeletionRequest, ErasureLedger
from careerground.web.authenticated_management import AuthenticatedManagement
from careerground.web.verified_browser_sessions import VerifiedBrowserSessions
from tests import test_authenticated_management as foundation


class AuthenticatedDeletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.AuthenticatedManagementTests.setUpClass()

    def setUp(self):
        self.fx = foundation.AuthenticatedManagementTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.folder = tempfile.TemporaryDirectory(prefix="cg-authenticated-deletion-")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "state"
        self.store = AuthenticatedDevelopmentStore(
            self.path, self.fx.login.settings, foundation.RESOURCE
        )
        self.addCleanup(self.store.close)
        self.fx.sessions = self.store.sessions
        self.fx.admit = self.store.admit
        self.original_exchange = self.fx.login._exchange
        self.auth_time = lambda: int(self.fx.now)
        self.methods = ["pwd"]

        def exchange(body):
            response = self.original_exchange(body)
            claims = jwt.decode(response["id_token"], options={"verify_signature": False})
            if self.auth_time is not None:
                claims["auth_time"] = self.auth_time()
            if self.methods is not None:
                claims["amr"] = self.methods
            return {
                "id_token": jwt.encode(
                    claims, self.fx.key, algorithm="RS256", headers={"kid": "synthetic"}
                )
            }

        self.fx.login._exchange = exchange
        self.fx.app = AuthenticatedManagement(
            login=self.fx.login,
            origin=foundation.ORIGIN,
            session_factory=self.store.sessions,
            account_admission=self.store.admit,
            review_secret=self.store.review_secret,
            presentation_secret=self.store.presentation_secret,
            mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
            signing_key=lambda _: self.fx.key.public_key(),
            deletion_store=self.store,
            clock=lambda: self.fx.now,
        )

    def profile(self, subject="user-a"):
        with self.store.sessions() as session:
            return session.scalar(
                select(CareerProfile).where(
                    CareerProfile.account_id
                    == self.store.admit(VerifiedIdentity(foundation.ISSUER, subject))
                )
            )

    def fields(self, page, confirm):
        return {
            "request_id": self.fx.form_token(page, "request_id"),
            "token": self.fx.form_token(page),
            "confirm": confirm,
        }

    def start(self, browser):
        profile = self.profile()
        page = browser.get("/deletion/development/profile/" + profile.id)
        fields = self.fields(page, "reviewed_impact")
        response = browser.post(
            "/deletion/development/reauth", data=fields, headers={"origin": foundation.ORIGIN}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("Max-Age=600", response.headers["set-cookie"])
        link = unescape(
            re.search(r"<a href='([^']+)'>인증 제공자에서 계속", response.text).group(1)
        )
        query = parse_qs(urlsplit(link).query)
        self.assertEqual(query["max_age"], ["0"])
        if self.fx.app.require_deletion_mfa:
            self.assertEqual(query["acr_values"], [MFA_AUTHENTICATION_CONTEXT])
        else:
            self.assertNotIn("acr_values", query)
        self.fx.nonce = query["nonce"][0]
        return fields, {"state": query["state"][0], "code": "user-a"}

    def ready(self, browser):
        _, callback = self.start(browser)
        result = browser.get("/auth/callback", params=callback)
        self.assertEqual(result.status_code, 303, result.text)
        page = browser.get(result.headers["location"])
        return self.fields(page, "erase_local_profile")

    def counts(self):
        with self.store.sessions() as session:
            return tuple(
                session.scalar(select(func.count()).select_from(model))
                for model in (DeletionRequest, ErasureLedger)
            )

    def test_mfa_policy_rejects_password_only_and_does_not_delete_on_callback(self):
        self.fx.app.require_deletion_mfa = True
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            for methods in (["pwd"], ["otp"], ["federated"], [], None):
                with self.subTest(methods=methods):
                    self.methods = methods
                    _, callback = self.start(browser)
                    rejected = browser.get("/auth/callback", params=callback)
                    self.assertEqual(rejected.status_code, 409)
                    self.assertIn("삭제에 필요한 추가 인증", rejected.text)
                    self.assertEqual(self.counts(), (0, 0))
            self.methods = ["mfa"]
            fields = self.ready(browser)
            self.assertEqual(self.counts(), (0, 0))
            result = browser.post(
                "/deletion/development/execute", data=fields, headers={"origin": foundation.ORIGIN}
            )
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(self.counts(), (1, 1))

    def test_fresh_authentication_requires_separate_final_approval_and_checkpoint(self):
        # Existing fixture uses real synthetic HTTP/MCP source review and receipt
        # consumption. This leaves one canonical fact/source, not an empty DB.
        self.fx.test_actual_management_confirmation_is_owner_bound_and_consumed_by_mcp()
        with self.fx.other_browser() as browser:
            self.fx.begin(browser)
            profile = self.profile()
            backup = self.path.parent / "before-deletion.sqlite"
            self.store.engine.dispose()
            shutil.copyfile(self.store.database_path, backup)
            with self.store.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
                self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 1)
            fields = self.ready(browser)
            self.assertEqual(self.counts(), (0, 0))
            result = browser.post(
                "/deletion/development/execute", data=fields, headers={"origin": foundation.ORIGIN}
            )
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIn("FOUNDATION_ONLY", result.text)
            self.assertEqual(self.counts(), (1, 1))
            self.assertEqual(browser.get("/account").status_code, 401)
            with self.store.sessions() as session:
                self.assertEqual(session.get(CareerProfile, profile.id).status, "DELETING")
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 0)
            self.assertEqual(len(json.loads((self.path / "ledger.json").read_text())), 1)
            self.store.close()
            reopened = AuthenticatedDevelopmentStore(
                self.path, self.fx.login.settings, foundation.RESOURCE
            )
            self.addCleanup(reopened.close)
            with reopened.sessions() as session:
                self.assertEqual(session.get(CareerProfile, profile.id).status, "DELETING")
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 0)
            reopened.close()
            shutil.copyfile(backup, self.path / "authenticated.sqlite")
            with self.assertRaises(DevelopmentStoreRejected):
                AuthenticatedDevelopmentStore(
                    self.path, self.fx.login.settings, foundation.RESOURCE
                )

    def test_checkpoint_failure_blocks_both_web_and_mcp_until_verified_restart(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            fields = self.ready(browser)
            checkpoint = self.store.before_deletion_commit

            def fail(session):
                checkpoint(session)
                raise RuntimeError("synthetic-private-checkpoint-failure")

            self.store.before_deletion_commit = fail
            result = browser.post(
                "/deletion/development/execute",
                data=fields,
                headers={"origin": foundation.ORIGIN},
            )
            self.assertEqual(result.status_code, 409)
            self.assertNotIn("synthetic-private", result.text)
            self.assertEqual(self.counts(), (0, 0))
            self.assertEqual(browser.get("/account").status_code, 503)
            self.assertEqual(self.fx.rpc_response(browser, "get_my_profile").status_code, 503)
            self.assertEqual(browser.get("/health/live").status_code, 503)

    def test_session_revoked_while_form_is_read_cannot_execute_approved_deletion(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            fields = self.ready(browser)
            authenticate = VerifiedBrowserSessions.__call__
            calls = 0

            async def revoke_before_recheck(sessions, request, response):
                nonlocal calls
                calls += 1
                if calls == 2:
                    sessions.revoke(request, Response())
                return await authenticate(sessions, request, response)

            with patch.object(VerifiedBrowserSessions, "__call__", revoke_before_recheck):
                result = browser.post(
                    "/deletion/development/execute",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                )
            self.assertEqual(result.status_code, 401)
            self.assertEqual(self.counts(), (0, 0))

    def test_interrupted_reauthentication_does_not_block_a_fresh_normal_login(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            _, stale_callback = self.start(browser)
            self.fx.begin(browser)
            self.assertEqual(browser.get("/account").status_code, 200)
            self.assertNotEqual(
                browser.get("/auth/callback", params=stale_callback).status_code, 303
            )
            self.assertEqual(self.counts(), (0, 0))

    def test_four_minute_provider_login_retains_binding_but_final_approval_expires(self):
        with self.fx.client() as browser:
            self.fx.now -= 240
            self.fx.enroll(browser)
            _, callback = self.start(browser)
            self.fx.now += 240
            result = browser.get("/auth/callback", params=callback)
            self.assertEqual(result.status_code, 303, result.text)
            final_url = result.headers["location"]
            fields = self.fields(browser.get(final_url), "erase_local_profile")
            self.assertEqual(self.counts(), (0, 0))
            self.fx.now += 181
            self.assertEqual(browser.get(final_url).status_code, 409)
            self.assertEqual(
                browser.post(
                    "/deletion/development/execute",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            self.assertEqual(self.counts(), (0, 0))

    def test_fresh_social_exchange_without_signed_password_or_mfa_method_cannot_delete(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            for methods in (None, [], ["federated"], ["otp"], "pwd"):
                with self.subTest(methods=methods):
                    self.methods = methods
                    _, callback = self.start(browser)
                    result = browser.get("/auth/callback", params=callback)
                    self.assertEqual(result.status_code, 409)
                    if methods != "pwd":
                        self.assertIn("최근 로그인과 동일 계정은 확인했습니다", result.text)
                        self.assertIn("현재 방식의 로그인을 반복할 필요는 없습니다", result.text)
                        self.assertIn("href='/account'", result.text)
                        self.assertNotIn("관리 화면에서 새 검토를 시작하세요", result.text)
                    else:
                        # A malformed signed method list fails before freshness
                        # is verified; it must not claim successful authentication.
                        self.assertNotIn("최근 로그인과 동일 계정은 확인했습니다", result.text)
                    self.assertEqual(self.counts(), (0, 0))
                    self.assertIsNotNone(self.profile())

    def test_signed_but_missing_stale_or_different_account_authentication_cannot_delete(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            for bad in ("absent", "old", "other_account", "future"):
                with self.subTest(bad=bad):
                    fields, callback = self.start(browser)
                    if bad == "absent":
                        self.auth_time = None
                    elif bad == "old":
                        self.auth_time = lambda: int(self.fx.now) - 60
                    elif bad == "future":
                        self.auth_time = lambda: int(self.fx.now) + 60
                    else:
                        self.auth_time = lambda: int(self.fx.now)
                        callback["code"] = "user-b"
                    result = browser.get("/auth/callback", params=callback)
                    self.assertEqual(result.status_code, 409)
                    self.assertEqual(
                        browser.post(
                            "/deletion/development/execute",
                            data={**fields, "confirm": "erase_local_profile"},
                            headers={"origin": foundation.ORIGIN},
                        ).status_code,
                        409,
                    )
                    self.assertEqual(self.counts(), (0, 0))
                    self.assertIsNotNone(self.profile())
                    self.auth_time = lambda: int(self.fx.now)

    def test_other_browser_duplicate_callback_and_direct_execution_are_refused(self):
        with self.fx.client() as browser, self.fx.other_browser() as other:
            self.fx.enroll(browser)
            self.fx.begin(other)
            fields, callback = self.start(browser)
            self.assertEqual(
                other.post(
                    "/deletion/development/reauth",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            self.assertEqual(
                browser.post(
                    "/deletion/development/execute",
                    data={**fields, "confirm": "erase_local_profile"},
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            done = browser.get("/auth/callback", params=callback)
            self.assertEqual(done.status_code, 303)
            final_fields = self.fields(browser.get(done.headers["location"]), "erase_local_profile")
            self.assertEqual(
                other.post(
                    "/deletion/development/execute",
                    data=final_fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            self.assertNotEqual(browser.get("/auth/callback", params=callback).status_code, 303)
            self.assertEqual(self.counts(), (0, 0))

    def test_version_change_expiry_origin_and_missing_consent_are_refused(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            fields = self.ready(browser)
            endpoint = "/deletion/development/execute"
            self.assertEqual(
                browser.post(
                    endpoint, data=fields, headers={"origin": "https://evil.synthetic.example"}
                ).status_code,
                403,
            )
            self.assertEqual(
                browser.post(
                    endpoint,
                    data={**fields, "confirm": "no"},
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                400,
            )
            with self.store.sessions() as session:
                session.get(CareerProfile, self.profile().id).version += 1
                session.commit()
            self.assertEqual(
                browser.post(
                    endpoint, data=fields, headers={"origin": foundation.ORIGIN}
                ).status_code,
                409,
            )
            fields = self.ready(browser)
            self.fx.now += 181
            self.assertEqual(
                browser.post(
                    endpoint, data=fields, headers={"origin": foundation.ORIGIN}
                ).status_code,
                409,
            )
            self.assertEqual(self.counts(), (0, 0))

    def test_other_account_preview_hidden_form_tamper_and_logout_during_authentication(self):
        with self.fx.client() as browser, self.fx.other_browser() as other:
            self.fx.enroll(browser)
            self.fx.enroll(other, "user-b")
            self.assertEqual(
                other.get("/deletion/development/profile/" + self.profile().id).status_code, 404
            )
            fields, callback = self.start(browser)
            self.assertEqual(
                browser.post(
                    "/deletion/development/reauth",
                    data={**fields, "token": "forged"},
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            token = self.fx.form_token(browser.get("/account"))
            browser.post(
                "/auth/logout", data={"token": token}, headers={"origin": foundation.ORIGIN}
            )
            # Logout clears the deletion cookie; the stale deletion state cannot
            # be consumed as a normal login transaction either.
            self.assertEqual(browser.get("/auth/callback", params=callback).status_code, 400)
            self.assertEqual(self.counts(), (0, 0))

    def test_opt_in_missing_checkpoint_store_cannot_be_mixed_with_other_database(self):
        with self.assertRaises(ValueError):
            AuthenticatedManagement(
                login=self.fx.login,
                origin=foundation.ORIGIN,
                session_factory=lambda: None,
                account_admission=self.store.admit,
                review_secret=self.store.review_secret,
                presentation_secret=self.store.presentation_secret,
                mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
                deletion_store=self.store,
            )

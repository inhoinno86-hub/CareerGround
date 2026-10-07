"""Verified connection denial survives restart and blocks reissued credentials."""

import json
import tempfile
import unittest
from pathlib import Path

from careerground.domain.authorization import VerifiedIdentity
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.web.authenticated_management import AuthenticatedManagement
from tests import test_authenticated_management as foundation


class DevelopmentConnectionRevocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.AuthenticatedManagementTests.setUpClass()

    def setUp(self):
        self.fx = foundation.AuthenticatedManagementTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        folder = tempfile.TemporaryDirectory(prefix="cg-local-revocation-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "revocations"
        self.registry = DevelopmentConnectionRevocations(
            self.path, issuer=foundation.ISSUER, initialize=True
        )
        self.addCleanup(lambda: self.registry.close())
        self.fx.app = AuthenticatedManagement(
            login=self.fx.login,
            origin=foundation.ORIGIN,
            session_factory=self.fx.sessions,
            account_admission=self.fx.admit,
            review_secret=foundation.SECRET,
            presentation_secret=foundation.SECRET,
            mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
            signing_key=lambda _: self.fx.key.public_key(),
            connection_is_revoked=lambda access: self.registry.is_revoked(access),
            clock=lambda: self.fx.now,
        )

    def test_owner_client_denial_survives_restart_and_new_token_web_and_other_user_unaffected(self):
        with self.fx.client() as browser, self.fx.other_browser() as other:
            self.fx.enroll(browser)
            self.fx.enroll(other, "user-b")
            self.assertEqual(self.fx.rpc_response(browser, "get_my_profile").status_code, 200)
            identity = VerifiedIdentity(foundation.ISSUER, "user-a")
            self.registry.block(identity, "synthetic-mcp-client")
            self.registry.block(identity, "synthetic-mcp-client")
            self.assertEqual(self.fx.rpc_response(browser, "get_my_profile").status_code, 401)
            self.assertEqual(
                self.fx.rpc_response(browser, "get_my_profile", jti="new-token").status_code, 401
            )
            self.assertEqual(browser.get("/account").status_code, 200)
            self.assertEqual(
                self.fx.rpc_response(browser, "get_my_profile", subject="user-b").status_code, 200
            )
            self.assertEqual(
                self.fx.rpc_response(browser, "get_my_profile", azp="other-client").status_code, 200
            )
            self.registry.close()
            self.registry = DevelopmentConnectionRevocations(self.path, issuer=foundation.ISSUER)
            self.assertEqual(self.fx.rpc_response(browser, "get_my_profile").status_code, 401)
            serialized = (self.path / "denials.json").read_text()
            self.assertNotIn("user-a", serialized)
            self.assertNotIn("synthetic-mcp-client", serialized)
            self.assertNotIn(self.fx.bearer(), serialized)
            self.assertEqual(len(json.loads(serialized)["payload"]["denials"]), 1)

    def test_tamper_missing_and_unavailable_gate_fail_closed(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            (self.path / "denials.json").write_text("{}")
            self.assertEqual(self.fx.rpc_response(browser, "get_my_profile").status_code, 401)
            self.assertEqual(browser.get("/account").status_code, 200)
            self.registry.close()
            with self.assertRaises(DevelopmentStoreRejected):
                DevelopmentConnectionRevocations(self.path, issuer=foundation.ISSUER)
            with self.assertRaises(DevelopmentStoreRejected):
                DevelopmentConnectionRevocations(
                    self.path.parent / "missing", issuer=foundation.ISSUER
                )

    def test_unverified_token_never_reaches_the_connection_gate(self):
        with self.fx.client() as browser:
            self.fx.enroll(browser)
            self.registry.is_revoked = lambda _: self.fail("Invalid token reached revocation gate")
            response = browser.post(
                "/mcp",
                headers={"authorization": "Bearer invalid"},
                json={"jsonrpc": "2.0", "id": 1},
            )
            self.assertEqual(response.status_code, 401)

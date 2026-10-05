"""Owner Web consent denies shared-client MCP requests, without erasing data."""

import tempfile
import unittest
from pathlib import Path

from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations
from careerground.web.authenticated_management import AuthenticatedManagement
from tests import test_authenticated_management as foundation


class DevelopmentConnectionControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.AuthenticatedManagementTests.setUpClass()

    def setUp(self):
        self.fx = foundation.AuthenticatedManagementTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        folder = tempfile.TemporaryDirectory(prefix="cg-connection-controls-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "denials"
        self.registry = DevelopmentConnectionRevocations(
            self.path, issuer=foundation.ISSUER, initialize=True
        )
        self.addCleanup(lambda: self.registry.close())
        self.app()

    def app(self):
        self.fx.app = AuthenticatedManagement(
            login=self.fx.login,
            origin=foundation.ORIGIN,
            session_factory=self.fx.sessions,
            account_admission=self.fx.admit,
            review_secret=foundation.SECRET,
            presentation_secret=foundation.SECRET,
            mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
            signing_key=lambda _: self.fx.key.public_key(),
            connection_registry=self.registry,
            connection_client_id="synthetic-mcp-client",
            clock=lambda: self.fx.now,
        )

    def test_csrf_owner_target_and_signed_requests_after_block_and_restart(self):
        with self.fx.client() as a, self.fx.other_browser() as b:
            self.fx.enroll(a)
            self.fx.enroll(b, "user-b")
            page = a.get("/connections/development")
            self.assertIn("두 연결", page.text)
            fields = {"token": self.fx.form_token(page), "confirm": "block_shared_client"}
            endpoint = "/connections/development/block"
            self.assertEqual(
                b.post(endpoint, data=fields, headers={"origin": foundation.ORIGIN}).status_code,
                409,
            )
            self.assertEqual(
                a.post(
                    endpoint, data=fields, headers={"origin": "https://evil.example"}
                ).status_code,
                403,
            )
            self.assertEqual(
                a.post(
                    endpoint,
                    data={**fields, "client_id": "other-client"},
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                400,
            )
            self.assertEqual(self.fx.rpc_response(a, "get_my_profile").status_code, 200)
            result = a.post(endpoint, data=fields, headers={"origin": foundation.ORIGIN})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(a.get("/account").status_code, 200)
            self.assertEqual(self.fx.rpc_response(a, "get_my_profile").status_code, 401)
            self.assertEqual(
                self.fx.rpc_response(a, "get_my_profile", subject="user-b").status_code, 200
            )
            self.assertEqual(
                self.fx.rpc_response(a, "get_my_profile", azp="other-client").status_code,
                200,
            )
        self.registry.close()
        self.registry = DevelopmentConnectionRevocations(self.path, issuer=foundation.ISSUER)
        self.app()
        with self.fx.client() as a:
            self.fx.begin(a)
            self.assertEqual(a.get("/account").status_code, 200)
            self.assertEqual(
                self.fx.rpc_response(a, "get_my_profile", jti="synthetic-reissued").status_code,
                401,
            )

    def test_tampered_registry_denies_mcp_and_preserves_web_login(self):
        with self.fx.client() as a:
            self.fx.enroll(a)
            (self.path / "denials.json").write_text("{}")
            self.assertEqual(self.fx.rpc_response(a, "get_my_profile").status_code, 401)
            self.assertEqual(a.get("/account").status_code, 200)

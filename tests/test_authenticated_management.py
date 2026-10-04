"""Signed synthetic OAuth -> explicit Web enrollment -> shared MCP account."""

from __future__ import annotations

import logging
import re
import time
import unittest
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.providers.oidc_identity import (
    IdentityClientSettings,
    IdentityOnlyLogin,
    StableAccountAdmission,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import Account, AuthIdentity, Base, CareerProfile
from careerground.web.authenticated_management import POLICY, AuthenticatedManagement
from careerground.web.verified_browser_sessions import COOKIE

ISSUER = "https://auth.management.synthetic.example/"
RESOURCE = "https://mcp.management.synthetic.example/mcp"
ORIGIN = "https://localhost:5000"
CLIENT_ID = "synthetic-web-client"
SECRET = b"synthetic-management-key-at-least-32-bytes"
SCOPES = "career.profile.read career.profile.write career.artifact.read career.artifact.write career.export career.delete"


class AuthenticatedManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        logging.getLogger("httpx").setLevel(logging.WARNING)

    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            hide_parameters=True,
        )
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def configure(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.now = time.time()
        previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, previous_logging)
        self.nonce = ""
        self.exchanges = 0

        def exchange(body):
            self.exchanges += 1
            subject = body["code"]
            return {
                "id_token": jwt.encode(
                    {
                        "iss": ISSUER,
                        "sub": subject,
                        "aud": CLIENT_ID,
                        "iat": int(time.time()),
                        "exp": int(time.time()) + 300,
                        "nonce": self.nonce,
                        "email": "unused@synthetic.example",
                    },
                    self.key,
                    algorithm="RS256",
                    headers={"kid": "synthetic"},
                )
            }

        self.login = IdentityOnlyLogin(
            IdentityClientSettings(
                ISSUER,
                CLIENT_ID,
                ISSUER + "authorize",
                ISSUER + "oauth/token",
                ORIGIN + "/auth/callback",
            ),
            exchange_code=exchange,
            signing_key=lambda _: self.key.public_key(),
            clock=lambda: self.now,
        )
        self.admit = StableAccountAdmission(
            issuer=ISSUER,
            secret=SECRET,
            admitted_subjects=frozenset({"user-a", "user-b"}),
        )
        self.app = AuthenticatedManagement(
            login=self.login,
            origin=ORIGIN,
            session_factory=self.sessions,
            account_admission=self.admit,
            review_secret=SECRET,
            presentation_secret=SECRET,
            mcp_settings=McpOAuthSettings(ISSUER, RESOURCE),
            signing_key=lambda _: self.key.public_key(),
            clock=lambda: self.now,
        )

    def client(self):
        return TestClient(self.app, base_url=ORIGIN, follow_redirects=False)

    def other_browser(self):
        # The one composite client owns MCP lifespan. A second browser uses
        # the same Web app/session store without starting MCP a second time.
        return TestClient(self.app.web, base_url=ORIGIN, follow_redirects=False)

    def begin(self, client, subject="user-a"):
        result = client.get("/auth/login")
        self.assertEqual(result.status_code, 303)
        query = parse_qs(urlsplit(result.headers["location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["scope"], ["openid profile email"])
        self.assertNotIn("audience", query)
        self.nonce = query["nonce"][0]
        callback = {"code": subject, "state": query["state"][0]}
        result = client.get("/auth/callback", params=callback)
        self.assertEqual(result.status_code, 303, result.text)
        return callback

    def form_token(self, response, name="token"):
        self.assertEqual(response.status_code, 200, response.text)
        return re.search(f"name='{name}' value='([^']+)'", response.text).group(1)

    def setup_form(self, client):
        return {
            "token": self.form_token(client.get("/account/setup")),
            "policy_version": POLICY,
            "confirm": "reviewed",
        }

    def enroll(self, client, subject="user-a"):
        self.begin(client, subject)
        result = client.post(
            "/account/setup", data=self.setup_form(client), headers={"origin": ORIGIN}
        )
        self.assertEqual(result.status_code, 303, result.text)
        result = client.get("/account")
        self.assertEqual(result.status_code, 200)
        return re.search(r"href='/profile/([^/']+)/(\d+)'", result.text).group(1)

    def bearer(self, subject="user-a", scope=SCOPES, **overrides):
        return jwt.encode(
            {
                "iss": ISSUER,
                "sub": subject,
                "aud": RESOURCE,
                "azp": "synthetic-mcp-client",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "scope": scope,
                **overrides,
            },
            self.key,
            algorithm="RS256",
            headers={"kid": "synthetic"},
        )

    def rpc_response(self, client, name, args=None, subject="user-a", **claims):
        return client.post(
            "/mcp",
            headers={"authorization": "Bearer " + self.bearer(subject, **claims)},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": args or {}},
            },
        )

    def rpc(self, client, name, args=None, subject="user-a", **claims):
        response = self.rpc_response(client, name, args, subject, **claims)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]["structuredContent"]

    def count(self, model):
        with self.sessions() as session:
            return session.scalar(select(func.count()).select_from(model))

    def test_no_automatic_enrollment_and_setup_has_consent_csrf_and_one_use(self):
        with self.client() as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/account").status_code, 401)
            self.begin(client)
            self.assertEqual(self.count(Account), 0)
            form = self.setup_form(client)
            for values, origin, expected in [
                ({**form, "account_id": "forged"}, ORIGIN, 400),
                (form, "https://foreign.synthetic.example", 403),
                ({**form, "token": "bad"}, ORIGIN, 409),
                ({**form, "confirm": ""}, ORIGIN, 400),
            ]:
                response = client.post("/account/setup", data=values, headers={"origin": origin})
                self.assertEqual(response.status_code, expected)
                self.assertEqual(self.count(Account), 0)
            self.assertEqual(client.post("/account/setup", data=form).status_code, 403)
            response = client.post("/account/setup", data=form, headers={"origin": ORIGIN})
            self.assertEqual(response.status_code, 303)
            self.assertEqual(
                client.post("/account/setup", data=form, headers={"origin": ORIGIN}).status_code,
                401,
            )
            self.assertEqual(
                [self.count(m) for m in (Account, AuthIdentity, CareerProfile)], [1, 1, 1]
            )
            self.assertNotIn("unused@synthetic", client.get("/account").text)
            self.assertIn("HttpOnly", response.headers["set-cookie"])
            self.assertIn("Secure", response.headers["set-cookie"])

    def test_same_web_mcp_profile_and_two_accounts_cannot_cross(self):
        with self.client() as a, self.other_browser() as b:
            profile_a = self.enroll(a)
            profile_b = self.enroll(b, "user-b")
            self.assertNotEqual(profile_a, profile_b)
            self.assertEqual(self.rpc(a, "get_my_profile")["data"]["profile_id"], profile_a)
            self.assertEqual(
                self.rpc(a, "get_my_profile", subject="user-b")["data"]["profile_id"], profile_b
            )
            self.assertEqual(a.get(f"/profile/{profile_a}/0").status_code, 200)
            self.assertEqual(b.get(f"/profile/{profile_a}/0").status_code, 404)
            result = self.rpc(
                a,
                "get_career_profile",
                {"profile_id": profile_a, "profile_version": 0},
                subject="user-b",
            )
            self.assertEqual(result["error"]["code"], "NOT_FOUND")
            self.assertEqual(self.rpc_response(a, "get_my_profile", aud=CLIENT_ID).status_code, 401)
            self.assertEqual(
                self.rpc_response(a, "get_my_profile", scope="careerground:probe").status_code, 401
            )
            self.assertEqual(
                self.rpc_response(a, "get_my_profile", subject="unknown").status_code, 401
            )

    def test_setup_cookie_and_form_are_bound_to_verified_user_and_expire(self):
        with self.client() as a, self.other_browser() as b:
            self.begin(a)
            form_a = self.setup_form(a)
            self.begin(b, "user-b")
            self.assertEqual(
                b.post("/account/setup", data=form_a, headers={"origin": ORIGIN}).status_code, 409
            )
            self.assertEqual(self.count(Account), 0)
            self.now += 181
            self.assertEqual(
                a.post("/account/setup", data=form_a, headers={"origin": ORIGIN}).status_code, 401
            )
            self.assertEqual(self.count(Account), 0)

    def test_callback_is_one_use_and_errors_have_no_provider_payload(self):
        with self.client() as client:
            callback = self.begin(client)
            self.assertEqual(client.get("/auth/callback", params=callback).status_code, 400)
            self.assertEqual(self.exchanges, 1)
            response = client.get(
                "/auth/callback", params={"error": "secret-token-payload", "state": "forged"}
            )
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("secret-token-payload", response.text)
            self.assertEqual(self.count(Account), 0)

    def test_logout_revokes_saved_browser_cookie_but_is_not_mcp_disconnect(self):
        with self.client() as client:
            profile_id = self.enroll(client)
            old_cookie = client.cookies.get(COOKIE)
            form = {"token": self.form_token(client.get("/account"))}
            self.assertEqual(client.get("/auth/logout").status_code, 405)
            self.assertEqual(
                client.post(
                    "/auth/logout", data=form, headers={"origin": "https://foreign.example"}
                ).status_code,
                403,
            )
            self.assertEqual(client.get("/account").status_code, 200)
            response = client.post("/auth/logout", data=form, headers={"origin": ORIGIN})
            self.assertEqual(response.status_code, 303)
            self.assertTrue(response.headers["location"].startswith(ISSUER + "v2/logout?"))
            client.cookies.clear()
            client.cookies.set(COOKIE, old_cookie)
            self.assertEqual(client.get("/account").status_code, 401)
            self.assertEqual(client.get(f"/profile/{profile_id}/0").status_code, 401)
            self.assertEqual(self.rpc(client, "get_my_profile")["data"]["profile_id"], profile_id)
            client.cookies.clear()
            self.begin(client)
            self.assertEqual(client.get("/account").status_code, 200)
            self.assertEqual(self.count(Account), 1)

    def test_blocked_erased_accounts_deny_web_mcp_and_reenrollment(self):
        with self.client() as client:
            profile_id = self.enroll(client)
            with self.sessions() as session:
                profile = session.get(CareerProfile, profile_id)
                session.get(Account, profile.account_id).status = "ERASED"
                session.execute(delete(AuthIdentity))
                session.commit()
            self.assertEqual(client.get("/account").status_code, 401)
            self.assertEqual(self.rpc_response(client, "get_my_profile").status_code, 401)
            self.begin(client)
            response = client.post(
                "/account/setup", data=self.setup_form(client), headers={"origin": ORIGIN}
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(self.count(Account), 1)
            self.assertEqual(self.count(AuthIdentity), 0)

    def test_actual_management_confirmation_is_owner_bound_and_consumed_by_mcp(self):
        with self.client() as a, self.other_browser() as b:
            profile_id = self.enroll(a)
            self.enroll(b, "user-b")
            work = self.rpc(
                a,
                "start_profiling",
                {
                    "profile_id": profile_id,
                    "goal": "ADD_EXPERIENCE",
                    "policy_version": POLICY,
                    "idempotency_key": "auth_management_start_0001",
                },
            )["data"]["profiling_session_id"]
            text = "합성 기능의 테스트를 작성했습니다."
            source = self.rpc(
                a,
                "add_profiling_input",
                {
                    "profiling_session_id": work,
                    "base_profile_version": 0,
                    "content": text,
                    "content_kind": "USER_STATEMENT",
                    "idempotency_key": "auth_management_input_0001",
                },
            )["data"]["input_id"]
            self.rpc(
                a,
                "propose_profiling_drafts",
                {
                    "profiling_session_id": work,
                    "source_input_id": source,
                    "base_profile_version": 0,
                    "experience_scope_id": "synthetic-auth-project",
                    "spans": [{"start": 0, "end": len(text)}],
                },
            )
            review = self.rpc(
                a,
                "prepare_claim_review",
                {
                    "profiling_session_id": work,
                    "experience_scope_id": "synthetic-auth-project",
                    "base_profile_version": 0,
                    "idempotency_key": "auth_management_review_0001",
                },
            )["data"]
            confirmation = self.rpc(
                a,
                "request_user_confirmation",
                {
                    "action": "FACT_REVIEW",
                    "target_id": review["review_batch_id"],
                    "profile_version": 0,
                    "format": "NONE",
                    "idempotency_key": "auth_management_confirm_0001",
                },
            )["data"]
            path = confirmation["confirmation_path"]
            self.assertEqual(confirmation["confirmation_url"], ORIGIN + path)
            self.assertEqual(b.get(path).status_code, 404)
            form = {
                "confirmation_token": self.form_token(a.get(path), "confirmation_token"),
                "confirm": "reviewed",
                "allow_connection": "yes",
                "decision_" + review["items"][0]["review_item_id"]: "ACCEPT",
            }
            self.assertEqual(b.post(path, data=form, headers={"origin": ORIGIN}).status_code, 409)
            self.assertEqual(self.count(Claim), 0)
            self.assertEqual(a.post(path, data=form, headers={"origin": ORIGIN}).status_code, 200)
            status = self.rpc(
                a, "get_confirmation_status", {"request_id": confirmation["request_id"]}
            )["data"]
            self.assertEqual(status["status"], "DONE")
            self.assertEqual(self.count(Claim), 1)
            result = self.rpc(
                a,
                "submit_claim_review",
                {
                    "review_batch_id": review["review_batch_id"],
                    "approval_receipt": status["approval_receipt"],
                },
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(self.count(Claim), 1)
            status = self.rpc(
                a, "get_confirmation_status", {"request_id": confirmation["request_id"]}
            )["data"]
            self.assertEqual(status["status"], "CONSUMED")


if __name__ == "__main__":
    unittest.main()

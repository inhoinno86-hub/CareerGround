"""Synthetic HTTP checks for the isolated, account-guarded product foundation."""

from __future__ import annotations

import time
import unittest
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import PROFILE_READ_SCOPE, build_product_foundation_app
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)

ISSUER = "https://product-auth.synthetic.example/"
RESOURCE = "https://product-mcp.synthetic.example/mcp"


class ProductFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            session.add_all(
                [
                    Account(id="acct-a", status="ACTIVE"),
                    Account(id="acct-b", status="ACTIVE"),
                    AuthIdentity(
                        id="identity-a", account_id="acct-a", issuer=ISSUER, subject="user-a"
                    ),
                    AuthIdentity(
                        id="identity-b", account_id="acct-b", issuer=ISSUER, subject="user-b"
                    ),
                    CareerProfile(id="profile-a", account_id="acct-a", version=3),
                    CareerProfile(id="profile-b", account_id="acct-b", version=8),
                ]
            )
            session.commit()
        self.app = build_product_foundation_app(
            McpOAuthSettings(issuer=ISSUER, resource_url=RESOURCE),
            session_factory=self.sessions,
            signing_key=lambda _token: self.private_key.public_key(),
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def token(
        self, *, sub: str = "user-a", scope: str = PROFILE_READ_SCOPE, **claims: object
    ) -> str:
        now = int(time.time())
        payload: dict[str, object] = {
            "iss": ISSUER,
            "sub": sub,
            "aud": RESOURCE,
            "azp": "synthetic-client",
            "scope": scope,
            "iat": now,
            "exp": now + 300,
        }
        payload.update(claims)
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": "test"})

    def call(self, client: TestClient, *, token: str, name: str, arguments: dict) -> object:
        return client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )

    def test_read_only_tools_require_product_scope_and_own_account(self) -> None:
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            listing = client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {self.token()}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            self.assertEqual(listing.status_code, 200)
            tools = listing.json()["result"]["tools"]
            self.assertEqual(
                {tool["name"] for tool in tools},
                {"get_account_profile", "get_owned_profile_metadata", "get_profiling_session"},
            )
            for tool in tools:
                self.assertEqual(
                    tool["securitySchemes"],
                    [{"type": "oauth2", "scopes": [PROFILE_READ_SCOPE]}],
                )
                self.assertTrue(tool["annotations"]["readOnlyHint"])
            account_tool = next(tool for tool in tools if tool["name"] == "get_account_profile")
            self.assertTrue(account_tool["_meta"]["openai/profile"])

            identity = self.call(
                client, token=self.token(), name="get_account_profile", arguments={}
            )
            self.assertEqual(identity.status_code, 200)
            self.assertEqual(identity.json()["result"]["structuredContent"], {"id": "acct-a"})
            owned = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "profile-a"},
            )
            self.assertEqual(owned.status_code, 200)
            self.assertEqual(
                owned.json()["result"]["structuredContent"],
                {"found": True, "profile_id": "profile-a", "version": 3},
            )
            foreign = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "profile-b"},
            )
            missing = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "not-a-profile"},
            )
            self.assertEqual(foreign.json()["result"], missing.json()["result"])
            self.assertEqual(
                foreign.json()["result"]["structuredContent"],
                {"found": False, "profile_id": None, "version": None},
            )

    def test_session_metadata_is_owner_scoped_and_never_returns_input_text(self) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.add_all(
                [
                    ProfilingSession(
                        id="work-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        status="ACTIVE",
                        base_profile_version=3,
                        created_at=now - timedelta(minutes=31),
                        last_activity_at=now - timedelta(minutes=31),
                        retention_expires_at=now + timedelta(days=89),
                    ),
                    ProfilingSession(
                        id="work-b",
                        account_id="acct-b",
                        profile_id="profile-b",
                        status="ACTIVE",
                        base_profile_version=8,
                        created_at=now,
                        last_activity_at=now,
                        retention_expires_at=now + timedelta(days=90),
                    ),
                ]
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="acct-a",
                    session_id="work-a",
                    idempotency_key="synthetic_input_0001",
                    content_kind="USER_STATEMENT",
                    body="synthetic private text must not leave storage",
                    created_at=now - timedelta(minutes=30),
                )
            )
            session.commit()

        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            owned = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "work-a"},
            )
            self.assertEqual(owned.status_code, 200)
            data = owned.json()["result"]["structuredContent"]
            self.assertTrue(data["found"])
            self.assertEqual(data["status"], "PAUSED")
            self.assertEqual(data["base_profile_version"], 3)
            self.assertEqual(data["current_profile_version"], 3)
            self.assertNotIn("synthetic private text", str(data))
            foreign = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "work-b"},
            )
            missing = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "missing"},
            )
            self.assertEqual(foreign.json()["result"], missing.json()["result"])
            self.assertFalse(foreign.json()["result"]["structuredContent"]["found"])

    def test_reused_token_is_denied_after_account_disable(self) -> None:
        token = self.token()
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                200,
            )
            with self.sessions() as session:
                session.get(Account, "acct-a").status = "DISABLED"
                session.commit()
            denied = self.call(client, token=token, name="get_account_profile", arguments={})
            self.assertEqual(denied.status_code, 401)
            self.assertIn("resource_metadata=", denied.headers["www-authenticate"])
            other = self.call(
                client, token=self.token(sub="user-b"), name="get_account_profile", arguments={}
            )
            self.assertEqual(other.status_code, 200)
            self.assertEqual(other.json()["result"]["structuredContent"], {"id": "acct-b"})

    def test_deleting_profile_is_hidden_from_read_tool(self) -> None:
        token = self.token()
        arguments = {"profile_id": "profile-a"}
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            before = self.call(
                client, token=token, name="get_owned_profile_metadata", arguments=arguments
            )
            self.assertTrue(before.json()["result"]["structuredContent"]["found"])
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").status = "DELETING"
                session.commit()
            after = self.call(
                client, token=token, name="get_owned_profile_metadata", arguments=arguments
            )
            self.assertEqual(after.status_code, 200)
            self.assertFalse(after.json()["result"]["structuredContent"]["found"])

    def test_wrong_scope_audience_or_unknown_identity_are_rejected(self) -> None:
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            no_token = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            self.assertEqual(no_token.status_code, 401)
            for token in (
                self.token(scope="careerground:probe"),
                self.token(aud="https://wrong.synthetic.example/mcp"),
                self.token(iss="https://wrong.synthetic.example/"),
                self.token(exp=int(time.time()) - 120),
                self.token(sub="unknown-user"),
            ):
                with self.subTest(token=token[:12]):
                    response = self.call(
                        client, token=token, name="get_account_profile", arguments={}
                    )
                    self.assertEqual(response.status_code, 401)

    def test_database_lookup_failure_fails_closed(self) -> None:
        token = self.token()
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                200,
            )
            # A disposed in-memory DB loses its schema, forcing a lookup error.
            self.engine.dispose()
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                401,
            )


if __name__ == "__main__":
    unittest.main()

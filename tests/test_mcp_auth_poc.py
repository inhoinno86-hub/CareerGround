"""Synthetic HTTP and JWT checks for the isolated OAuth MCP probe."""

from __future__ import annotations

import asyncio
import json
import os
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.mcp.poc_server import (
    PROBE_SCOPE,
    JwtTokenVerifier,
    PocSettings,
    build_account_guarded_probe_app,
    build_app,
)
from careerground.storage.models import Account, AuthIdentity, Base

ISSUER = "https://auth.synthetic.example/"
RESOURCE = "https://poc.synthetic.example/mcp"
TUNNEL_RESOURCE = (
    "https://tunnel-service.synthetic.example/v1/mcp/tunnel_0123456789abcdef0123456789abcdef"
)


class PocServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.settings = PocSettings(issuer=ISSUER, resource_url=RESOURCE)

    def make_token(self, **changes: object) -> str:
        now = int(time.time())
        claims: dict[str, object] = {
            "iss": ISSUER,
            "sub": "synthetic-user-a",
            "aud": RESOURCE,
            "azp": "synthetic-client",
            "scope": PROBE_SCOPE,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(changes)
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"})

    def verifier(self) -> JwtTokenVerifier:
        return JwtTokenVerifier(
            self.settings,
            signing_key=lambda _token: self.private_key.public_key(),
        )

    def test_configuration_is_explicit_and_https_only(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            PocSettings.from_environment()
        for issuer, resource in (
            ("http://auth.synthetic.example/", RESOURCE),
            (ISSUER, "http://poc.synthetic.example/mcp"),
            (ISSUER, "https://poc.synthetic.example/other"),
            (ISSUER, "https://tunnel-service.synthetic.example/v1/mcp/tunnel_short"),
            (ISSUER, TUNNEL_RESOURCE + "/"),
            ("https://auth.synthetic.example", RESOURCE),
            (ISSUER, "https://user:secret@poc.synthetic.example/mcp"),
        ):
            with self.subTest(issuer=issuer, resource=resource), self.assertRaises(ValueError):
                PocSettings(issuer=issuer, resource_url=resource)
        self.assertEqual(self.settings.jwks_url, ISSUER + ".well-known/jwks.json")
        self.assertEqual(
            PocSettings(issuer=ISSUER, resource_url=TUNNEL_RESOURCE).resource_url, TUNNEL_RESOURCE
        )

    def test_signed_token_requires_exact_issuer_audience_scope_and_time(self) -> None:
        verifier = self.verifier()
        valid = asyncio.run(verifier.verify_token(self.make_token()))
        self.assertIsNotNone(valid)
        self.assertEqual(valid.subject, "synthetic-user-a")
        self.assertEqual(valid.resource, RESOURCE)
        now = int(time.time())
        for changes in (
            {"iss": "https://other.synthetic.example/"},
            {"aud": "https://other.synthetic.example/mcp"},
            {"scope": "other:read"},
            {"exp": now - 120},
            {"iat": now + 120},
            {"azp": ""},
            {"sub": ""},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(asyncio.run(verifier.verify_token(self.make_token(**changes))))

    def test_wrong_signature_and_missing_kid_are_rejected(self) -> None:
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = self.make_token()
        now = int(time.time())
        no_kid = jwt.encode(
            {
                "iss": ISSUER,
                "sub": "synthetic-user-a",
                "aud": RESOURCE,
                "azp": "synthetic-client",
                "scope": PROBE_SCOPE,
                "iat": now,
                "exp": now + 300,
            },
            self.private_key,
            algorithm="RS256",
        )
        verifier = JwtTokenVerifier(
            self.settings, signing_key=lambda _token: other_key.public_key()
        )
        self.assertIsNone(asyncio.run(verifier.verify_token(token)))
        self.assertIsNone(asyncio.run(self.verifier().verify_token(no_kid)))

    def test_http_discovery_and_authentication_fail_closed(self) -> None:
        app = build_app(self.settings, signing_key=lambda _token: self.private_key.public_key())
        with TestClient(app, base_url="https://poc.synthetic.example") as client:
            metadata = client.get("/.well-known/oauth-protected-resource/mcp")
            self.assertEqual(metadata.status_code, 200)
            self.assertEqual(metadata.json()["resource"], RESOURCE)
            self.assertEqual(metadata.json()["authorization_servers"], [ISSUER])
            self.assertEqual(metadata.json()["scopes_supported"], [PROBE_SCOPE])
            unauthenticated = client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            self.assertEqual(unauthenticated.status_code, 401)
            self.assertIn("resource_metadata=", unauthenticated.headers["www-authenticate"])
            self.assertNotIn("synthetic-user", unauthenticated.text)
            invalid_scope = client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {self.make_token(scope='other:read')}"},
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            self.assertEqual(invalid_scope.status_code, 401)

    def test_tunnel_resource_keeps_local_metadata_discovery(self) -> None:
        settings = PocSettings(issuer=ISSUER, resource_url=TUNNEL_RESOURCE)
        app = build_app(settings, signing_key=lambda _token: self.private_key.public_key())
        with TestClient(app, base_url="http://127.0.0.1") as client:
            metadata = client.get("/.well-known/oauth-protected-resource/mcp")
            self.assertEqual(metadata.status_code, 200)
            self.assertEqual(metadata.json()["resource"], TUNNEL_RESOURCE)
            self.assertEqual(metadata.json()["authorization_servers"], [ISSUER])
            unauthenticated = client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            self.assertEqual(unauthenticated.status_code, 401)
            self.assertIn("resource_metadata=", unauthenticated.headers["www-authenticate"])

    def test_http_tool_is_read_only_and_returns_only_stable_pseudonym(self) -> None:
        app = build_app(self.settings, signing_key=lambda _token: self.private_key.public_key())
        headers = {
            "Authorization": f"Bearer {self.make_token()}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        with TestClient(app, base_url="https://poc.synthetic.example") as client:
            initialize = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "synthetic-test", "version": "1"},
                    },
                },
            )
            self.assertEqual(initialize.status_code, 200, initialize.text)
            listing = client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            self.assertEqual(listing.status_code, 200, listing.text)
            tool = listing.json()["result"]["tools"][0]
            self.assertEqual(tool["name"], "get_poc_identity")
            self.assertEqual(tool["securitySchemes"], [{"type": "oauth2", "scopes": [PROBE_SCOPE]}])
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertEqual(tool["outputSchema"]["required"], ["id"])
            self.assertFalse(tool["outputSchema"]["additionalProperties"])
            self.assertTrue(tool["_meta"]["openai/profile"])
            result = client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "get_poc_identity", "arguments": {}},
                },
            )
            self.assertEqual(result.status_code, 200, result.text)
            profile = result.json()["result"]["structuredContent"]
            self.assertTrue(profile["id"].startswith("poc_"))
            self.assertEqual(list(profile), ["id"])
            self.assertEqual(json.loads(result.json()["result"]["content"][0]["text"]), profile)
            self.assertNotIn("synthetic-user-a", result.text)
            self.assertNotIn("@", result.text)
            other_headers = {
                **headers,
                "Authorization": f"Bearer {self.make_token(sub='synthetic-user-b')}",
            }
            other_result = client.post(
                "/mcp",
                headers=other_headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "get_poc_identity", "arguments": {}},
                },
            )
            self.assertEqual(other_result.status_code, 200)
            self.assertNotEqual(
                other_result.json()["result"]["structuredContent"]["id"], profile["id"]
            )

    def test_account_gate_rechecks_same_token_on_every_http_request(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as session:
            session.add(Account(id="acct-synthetic-a", status="ACTIVE"))
            session.add(
                AuthIdentity(
                    id="identity-synthetic-a",
                    account_id="acct-synthetic-a",
                    issuer=ISSUER,
                    subject="synthetic-user-a",
                )
            )
            session.commit()

        app = build_account_guarded_probe_app(
            self.settings,
            session_factory=sessions,
            signing_key=lambda _token: self.private_key.public_key(),
        )
        token = self.make_token()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        with TestClient(app, base_url="https://poc.synthetic.example") as client:

            def call(bearer: str) -> int:
                return client.post(
                    "/mcp", headers={"Authorization": f"Bearer {bearer}"}, json=request
                ).status_code

            self.assertEqual(call(token), 200)
            self.assertEqual(call(self.make_token(sub="unknown-user")), 401)
            with sessions() as session:
                session.get(Account, "acct-synthetic-a").status = "DISABLED"
                session.commit()
            self.assertEqual(call(token), 401)
            with sessions() as session:
                session.get(Account, "acct-synthetic-a").status = "ACTIVE"
                session.commit()
            self.assertEqual(call(token), 200)
            with sessions() as session:
                session.query(AuthIdentity).filter_by(id="identity-synthetic-a").delete()
                session.commit()
            self.assertEqual(call(token), 401)
        engine.dispose()

    def test_account_gate_denies_when_account_database_is_unavailable(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # No tables: account lookup raises an SQL error and must fail closed.
        app = build_account_guarded_probe_app(
            self.settings,
            session_factory=sessionmaker(bind=engine),
            signing_key=lambda _token: self.private_key.public_key(),
        )
        with TestClient(app, base_url="https://poc.synthetic.example") as client:
            response = client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {self.make_token()}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            self.assertEqual(response.status_code, 401)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()

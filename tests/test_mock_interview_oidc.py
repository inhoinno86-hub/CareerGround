"""Offline cryptographic policy tests, NOT a provider/login execution."""

import base64
import copy
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/mock-interview/runtime"))
from cg_mock.api import create_app
from cg_mock.oidc import AccessTokenPolicy
from cg_mock.provider import ProviderVerifier
from cg_mock.session import Rejected, Sessions


class OfflineOidcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        row = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwks = {"keys": [{**row, "kid": "synthetic-key", "use": "sig", "alg": "RS256"}]}

    def setUp(self):
        self.policy = AccessTokenPolicy(
            issuer="https://synthetic-issuer.invalid/",
            audience="synthetic-api",
            client_id="synthetic-native-client",
            jwks=self.jwks,
        )

    def token(self, changes=None, headers=None, key=None, omitted=()):
        now = int(time.time())
        claims = {
            "iss": "https://synthetic-issuer.invalid/",
            "aud": "synthetic-api",
            "sub": "synthetic-user-a",
            "exp": now + 300,
            "iat": now - 1,
            "scope": "openid use:interview",
            "azp": "synthetic-native-client",
        }
        claims.update(changes or {})
        for name in omitted:
            claims.pop(name, None)
        return jwt.encode(
            claims,
            key or self.key,
            algorithm="RS256",
            headers={"kid": "synthetic-key", **(headers or {})},
        )

    def test_valid_signature_produces_stable_opaque_owner_without_network(self):
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            first = self.policy.verify(self.token())
            second = self.policy.verify(self.token({"exp": int(time.time()) + 600}))
        self.assertEqual(first.owner_binding, second.owner_binding)
        self.assertRegex(first.owner_binding, r"^oidc-[0-9a-f]{64}$")
        self.assertNotIn("synthetic-user-a", first.owner_binding)
        other = self.policy.verify(self.token({"sub": "synthetic-user-b"}))
        self.assertNotEqual(first.owner_binding, other.owner_binding)

    def test_expired_future_missing_and_wrong_claims_are_rejected(self):
        now = int(time.time())
        for changes in [
            {"exp": now - 1},
            {"iat": now + 60},
            {"nbf": now + 60},
            {"iss": "https://other.invalid/"},
            {"aud": "other-api"},
            {"scope": "openid"},
            {"scope": ["use:interview"]},
            {"azp": "other-client"},
            {"client_id": "other-client"},
            {"sub": ""},
            {"sub": ["user"]},
            {"exp": True},
            {"iat": True},
            {"iat": float("inf")},
            {"exp": float("inf")},
            {"nbf": float("inf")},
            {"sub": "\ud800"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.policy.verify(self.token(changes))
        for missing in ("iss", "aud", "sub", "exp", "iat", "azp"):
            with self.subTest(missing=missing), self.assertRaises(Rejected):
                self.policy.verify(self.token(omitted=[missing]))

    def test_audience_array_and_rfc_access_token_client_are_supported(self):
        principal = self.policy.verify(
            self.token(
                {
                    "aud": ["synthetic-api", "https://synthetic-issuer.invalid/userinfo"],
                    "client_id": "synthetic-native-client",
                },
                omitted=["azp"],
            )
        )
        self.assertTrue(principal.owner_binding.startswith("oidc-"))

    def test_forged_signature_and_algorithm_confusion_are_rejected(self):
        bad_signature = self.token(key=self.other_key)
        encoded_payload = jwt.decode(self.token(), options={"verify_signature": False})
        unsigned = jwt.encode(
            encoded_payload, key=None, algorithm="none", headers={"kid": "synthetic-key"}
        )
        symmetric = jwt.encode(
            encoded_payload, key=b"x" * 64, algorithm="HS256", headers={"kid": "synthetic-key"}
        )
        for token in (bad_signature, unsigned, symmetric):
            with self.subTest(size=len(token)), self.assertRaises(Rejected):
                self.policy.verify(token)

    def test_token_urls_unknown_keys_and_critical_headers_are_not_used(self):
        for headers in [
            {"kid": "unknown"},
            {"kid": []},
            {"typ": ["JWT"]},
            {"jku": "https://invalid.example/keys"},
            {"x5u": "https://invalid.example/cert"},
            {"crit": ["custom"]},
        ]:
            # PyJWT rejects non-string kid during encoding; construct that header explicitly.
            if isinstance(headers.get("kid"), list):
                token = self.token()
                parts = token.split(".")
                data = json.dumps({"alg": "RS256", "kid": []}).encode()
                parts[0] = base64.urlsafe_b64encode(data).decode().rstrip("=")
                token = ".".join(parts)
            else:
                token = self.token(headers=headers)
            with self.subTest(headers=headers), self.assertRaises(Rejected):
                self.policy.verify(token)

    def test_bad_config_duplicate_private_and_weak_keys_are_rejected(self):
        weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        weak_row = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(weak.public_key()))
        private_row = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key))
        for jwks in [
            {},
            {"keys": []},
            {"keys": self.jwks["keys"] * 2},
            {"keys": [{**self.jwks["keys"][0], "alg": "HS256"}]},
            {"keys": [{**weak_row, "kid": "weak"}]},
            {"keys": [{**private_row, "kid": "private"}]},
        ]:
            with self.subTest(keys=len(jwks.get("keys", []))), self.assertRaises(ValueError):
                AccessTokenPolicy(
                    issuer="https://synthetic.invalid/",
                    audience="api",
                    client_id="native",
                    jwks=jwks,
                )
        with self.assertRaises(ValueError):
            AccessTokenPolicy(
                issuer="http://synthetic.invalid/",
                audience="api",
                client_id="native",
                jwks=self.jwks,
            )

    def test_verified_other_user_cannot_access_fixed_session(self):
        first = self.policy.verify(self.token())
        other = self.policy.verify(self.token({"sub": "synthetic-user-b"}))
        store = Sessions()
        view = store.create(
            first.owner_binding, (ROOT / "fixtures/portable/handoff-v1.json").read_bytes(), {}
        )
        with self.assertRaises(Rejected):
            store.export(view["session_id"], other.owner_binding)
        self.assertEqual(
            store.view(view["session_id"], first.owner_binding)["state"], "REVIEW_REQUIRED"
        )

    def test_tokens_are_bounded_and_invalid_forms_are_rejected(self):
        for token in (None, "", "x" * 16385, "not.a.token", []):
            with self.subTest(kind=type(token).__name__), self.assertRaises(Rejected):
                self.policy.verify(token)
        before = copy.deepcopy(self.jwks)
        self.policy.verify(self.token())
        self.assertEqual(self.jwks, before)


class OidcRuntimeTests(unittest.TestCase):
    """Signed synthetic tokens through real handlers; not an Auth0 login."""

    @classmethod
    def setUpClass(cls):
        OfflineOidcTests.setUpClass.__func__(cls)

    token = OfflineOidcTests.token

    def setUp(self):
        self.config = {
            "issuer": "https://synthetic-issuer.invalid/",
            "audience": "synthetic-api",
            "client_id": "synthetic-native-client",
        }
        self.policy = AccessTokenPolicy(**self.config, jwks=self.jwks)

    def test_real_handlers_reject_bad_claims_and_synthetic_credentials(self):
        with TestClient(create_app(oidc_verifier=self.policy)) as client:
            for token in [
                "synthetic-join-code",
                self.token({"aud": "wrong"}),
                self.token({"iss": "https://wrong.invalid/"}),
                self.token({"azp": "wrong"}),
                self.token({"scope": "openid"}),
                self.token({"exp": int(time.time()) - 1}),
                self.token(key=self.other_key),
            ]:
                with self.subTest(kind=len(token)):
                    response = client.get(
                        "/v1/status", headers={"Authorization": "Bearer " + token}
                    )
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
            valid = client.get("/v1/status", headers={"Authorization": "Bearer " + self.token()})
            self.assertEqual(valid.json()["auth_mode"], "oidc")
            self.assertNotIn("synthetic-user-a", valid.text)

    def test_owner_restore_and_logout_revoke_boundaries(self):
        first = {"Authorization": "Bearer " + self.token()}
        second = {"Authorization": "Bearer " + self.token({"sub": "synthetic-user-b"})}
        with TestClient(create_app(oidc_verifier=self.policy)) as client:
            created = client.post(
                "/v1/import",
                headers=first,
                json={
                    "handoff_base64": base64.b64encode(
                        (ROOT / "fixtures/portable/handoff-v1.json").read_bytes()
                    ).decode(),
                    "attachments": {},
                },
            )
            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["auth_mode"], "oidc")
            sid = created.json()["session_id"]
            exported = client.get(f"/v1/sessions/{sid}/export", headers=first)
            self.assertEqual(exported.json()["auth_mode"], "oidc")
            denied = client.get(f"/v1/sessions/{sid}/export", headers=second)
            self.assertIn(denied.status_code, (403, 404))
            payload = {
                "session_base64": base64.b64encode(exported.content).decode(),
                "attachments": {},
            }
            self.assertEqual(
                client.post("/v1/restore", headers=second, json=payload).status_code, 403
            )
            self.assertEqual(
                client.post("/v1/restore", headers=first, json=payload).status_code, 200
            )
            wrong_mode = exported.json()
            wrong_mode["auth_mode"] = "synthetic_dev"
            invalid = {
                "session_base64": base64.b64encode(json.dumps(wrong_mode).encode()).decode(),
                "attachments": {},
            }
            refused = client.post("/v1/restore", headers=first, json=invalid)
            self.assertEqual(refused.status_code, 403)
            self.assertEqual(refused.json()["errors"], ["AUTH_MODE_CONFLICT"])
            self.assertEqual(client.post("/v1/logout", headers=first).status_code, 204)
            self.assertEqual(client.get("/v1/status", headers=first).status_code, 401)
            self.assertEqual(client.get("/v1/status", headers=second).status_code, 200)

    def test_exactly_one_mode_is_required(self):
        for kwargs in (
            {},
            {"credentials": {}},
            {"credentials": {"x": "a"}, "oidc_verifier": self.policy},
        ):
            with self.assertRaises(ValueError):
                create_app(**kwargs)
        with self.assertRaises(ValueError):
            create_app(oidc_verifier=self.policy, sessions=Sessions())
        with self.assertRaises(ValueError):
            Sessions(auth_mode="unsupported")

    def provider(self, handler, clock=None):
        return ProviderVerifier(
            self.config,
            transport=httpx.MockTransport(handler),
            **({"clock": clock} if clock else {}),
        )

    def metadata(self):
        issuer = self.config["issuer"]
        return {
            "issuer": issuer,
            "authorization_endpoint": issuer + "authorize",
            "token_endpoint": issuer + "oauth/token",
            "jwks_uri": issuer + ".well-known/jwks.json",
            "code_challenge_methods_supported": ["S256"],
        }

    def test_fixed_urls_cache_rotation_and_refresh_throttle(self):
        calls, clock = [], [0]
        keys = copy.deepcopy(self.jwks)

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(
                200, json=self.metadata() if request.url.path.endswith("configuration") else keys
            )

        provider = self.provider(handler, lambda: clock[0])
        provider.verify(self.token())
        self.assertEqual(len(calls), 2)
        for tick in [0, 31, 32]:
            clock[0] = tick
            with self.assertRaises(Rejected):
                provider.verify(self.token(headers={"kid": "rotated"}))
        self.assertEqual(len(calls), 3)
        keys["keys"][0]["kid"] = "rotated"
        clock[0] = 62
        provider.verify(self.token(headers={"kid": "rotated"}))
        self.assertTrue(
            all(url.startswith(self.config["issuer"] + ".well-known/") for url in calls)
        )

    def test_expired_keys_network_failure_is_closed_and_throttled(self):
        clock, calls = [0], []

        def handler(request):
            calls.append(str(request.url))
            if clock[0] >= 300:
                raise httpx.ConnectError("synthetic outage")
            return httpx.Response(
                200,
                json=self.metadata() if request.url.path.endswith("configuration") else self.jwks,
            )

        provider = self.provider(handler, lambda: clock[0])
        clock[0] = 301
        for _ in range(2):
            with self.assertRaises(Rejected) as caught:
                provider.verify(self.token())
            self.assertEqual(caught.exception.status, 503)
        self.assertEqual(len(calls), 3)

    def test_metadata_redirect_oversize_duplicate_and_endpoint_mismatch(self):
        bad = {**self.metadata(), "jwks_uri": "https://unreviewed.invalid/keys"}
        for response in [
            httpx.Response(302, headers={"Location": "https://unreviewed.invalid/"}),
            httpx.Response(200, content=b"x" * 65537),
            httpx.Response(200, content=b'{"issuer":1,"issuer":2}'),
            httpx.Response(200, json=bad),
        ]:
            with (
                self.subTest(status=response.status_code),
                self.assertRaises((Rejected, ValueError)),
            ):
                self.provider(lambda request, reply=response: reply)


if __name__ == "__main__":
    unittest.main()

"""Real CBOR/ECDSA WebAuthn proofs; fresh OIDC -> device -> separate consent."""

import copy
import hashlib
import json
import re
import secrets
import unittest
from html import unescape
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url as b64
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse

from careerground.auth0_development_runtime import Auth0DevelopmentRuntime
from careerground.config import Auth0Settings
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.storage.development_deletion_passkeys import DevelopmentDeletionPasskeys
from careerground.storage.development_files import DevelopmentStoreRejected
from careerground.web.authenticated_management import AuthenticatedManagement
from tests import test_authenticated_deletion as deletion
from tests import test_authenticated_management as foundation


class Device:
    """Synthetic authenticator; this does not prove a human used a real device."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.id = secrets.token_bytes(32)

    def response(
        self,
        challenge,
        *,
        register=False,
        origin=foundation.ORIGIN,
        rp="localhost",
        flags=None,
        count=1,
    ):
        client = json.dumps(
            {
                "type": "webauthn.create" if register else "webauthn.get",
                "challenge": b64(challenge),
                "origin": origin,
                "crossOrigin": False,
            }
        ).encode()
        data = (
            hashlib.sha256(rp.encode()).digest()
            + bytes([flags if flags is not None else (0x45 if register else 0x05)])
            + count.to_bytes(4, "big")
        )
        if register:
            public = self.key.public_key().public_numbers()
            cose = {
                1: 2,
                3: -7,
                -1: 1,
                -2: public.x.to_bytes(32, "big"),
                -3: public.y.to_bytes(32, "big"),
            }
            data += bytes(16) + len(self.id).to_bytes(2, "big") + self.id + cbor2.dumps(cose)
            response = {
                "attestationObject": b64(
                    cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data})
                ),
                "clientDataJSON": b64(client),
            }
        else:
            response = {
                "authenticatorData": b64(data),
                "clientDataJSON": b64(client),
                "signature": b64(
                    self.key.sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
                ),
                "userHandle": None,
            }
        return {
            "id": b64(self.id),
            "rawId": b64(self.id),
            "type": "public-key",
            "response": response,
            "clientExtensionResults": {},
        }


class DevelopmentDeletionPasskeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        deletion.AuthenticatedDeletionTests.setUpClass()

    def setUp(self):
        self.fx = deletion.AuthenticatedDeletionTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.base = self.fx.fx
        self.binding = hashlib.sha256(
            self.fx.store.admission_secret + self.fx.store.binding_digest.encode()
        ).hexdigest()
        self.path = self.fx.path.parent / "passkeys"
        self.registry = DevelopmentDeletionPasskeys(
            self.path, origin=foundation.ORIGIN, store_binding=self.binding, initialize=True
        )
        self.addCleanup(lambda: self.registry.close())
        self.base.app = AuthenticatedManagement(
            login=self.base.login,
            origin=foundation.ORIGIN,
            session_factory=self.fx.store.sessions,
            account_admission=self.fx.store.admit,
            review_secret=self.fx.store.review_secret,
            presentation_secret=self.fx.store.presentation_secret,
            mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
            signing_key=lambda _: self.base.key.public_key(),
            deletion_store=self.fx.store,
            deletion_passkeys=self.registry,
            allow_passkey_enrollment=True,
            clock=lambda: self.base.now,
        )
        self.fx.methods = ["federated"]
        self.device = Device()

    def options(self, page):
        return json.loads(unescape(re.search("data-options='([^']+)'", page.text).group(1)))

    def fields(self, page, confirm):
        return self.fx.fields(page, confirm)

    def register_browser(self, browser):
        page = browser.get("/security/development/passkey")
        response = browser.post(
            "/security/development/passkey/reauth",
            data={"token": self.base.form_token(page), "confirm": "reviewed_enrollment"},
            headers={"origin": foundation.ORIGIN},
        )
        self.assertEqual(response.status_code, 200, response.text)
        link = unescape(re.search("href='([^']+)'>인증 제공자에서 계속", response.text).group(1))
        query = parse_qs(urlsplit(link).query)
        self.assertNotIn("acr_values", query)
        self.base.nonce = query["nonce"][0]
        page = browser.get("/auth/callback", params={"state": query["state"][0], "code": "user-a"})
        self.assertEqual(page.status_code, 200, page.text)
        challenge = self.base.app.passkeys.pending[
            self.base.form_token(page, "request_id")
        ].challenge
        fields = {
            **self.fields(page, "register_device"),
            "credential": json.dumps(self.device.response(challenge, register=True, count=0)),
        }
        result = browser.post(
            "/security/development/passkey/register",
            data=fields,
            headers={"origin": foundation.ORIGIN},
        )
        self.assertEqual(result.status_code, 303, result.text)
        self.assertEqual(
            browser.post(
                "/security/development/passkey/register",
                data=fields,
                headers={"origin": foundation.ORIGIN},
            ).status_code,
            409,
        )
        self.assertEqual(self.fx.counts(), (0, 0))

    def deletion_page(self, browser):
        _, callback = self.fx.start(browser)
        page = browser.get("/auth/callback", params=callback)
        self.assertEqual(page.status_code, 200, page.text)
        fields = self.fields(page, "verified_device")
        challenge = self.base.app.deletion.pending[fields["request_id"]].passkey_challenge
        fields["credential"] = json.dumps(self.device.response(challenge))
        return fields

    def test_social_owner_enrollment_and_device_proof_require_separate_final_approval(self):
        with self.base.client() as browser:
            self.base.enroll(browser)
            self.register_browser(browser)
            fields = self.deletion_page(browser)
            premature = browser.post(
                "/deletion/development/execute",
                data={
                    k: v
                    for k, v in {**fields, "confirm": "erase_local_profile"}.items()
                    if k != "credential"
                },
                headers={"origin": foundation.ORIGIN},
            )
            self.assertEqual(premature.status_code, 409)
            verified = browser.post(
                "/deletion/development/passkey", data=fields, headers={"origin": foundation.ORIGIN}
            )
            self.assertEqual(verified.status_code, 303, verified.text)
            self.assertEqual(self.fx.counts(), (0, 0))
            self.assertEqual(
                browser.post(
                    "/deletion/development/passkey",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            final = self.fields(browser.get(verified.headers["location"]), "erase_local_profile")
            result = browser.post(
                "/deletion/development/execute", data=final, headers={"origin": foundation.ORIGIN}
            )
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(self.fx.counts(), (1, 1))

    def test_cryptographic_binding_uv_counter_and_restart(self):
        challenge = secrets.token_bytes(32)
        self.registry.register(
            "owner-a", challenge, self.device.response(challenge, register=True, count=0)
        )
        for kind in ("challenge", "origin", "rp", "uv", "up", "signature", "id", "handle", "owner"):
            with self.subTest(kind=kind):
                response = self.device.response(
                    challenge,
                    origin="https://evil.example" if kind == "origin" else foundation.ORIGIN,
                    rp="evil.example" if kind == "rp" else "localhost",
                    flags={"uv": 0x01, "up": 0x04}.get(kind),
                )
                if kind == "signature":
                    response["response"]["signature"] = b64(bytes(64))
                if kind == "id":
                    response["id"] = response["rawId"] = b64(bytes(32))
                if kind == "handle":
                    response["response"]["userHandle"] = b64(bytes(32))
                with self.assertRaises(
                    (InvalidAuthenticationResponse, DevelopmentStoreRejected, KeyError)
                ):
                    self.registry.verify(
                        "owner-b" if kind == "owner" else "owner-a",
                        b"wrong" if kind == "challenge" else challenge,
                        response,
                    )
        proof = self.device.response(challenge)
        self.registry.verify("owner-a", challenge, proof)
        with self.assertRaises((InvalidAuthenticationResponse, DevelopmentStoreRejected, KeyError)):
            self.registry.verify("owner-a", challenge, proof)
        self.registry.close()
        self.registry = DevelopmentDeletionPasskeys(
            self.path, origin=foundation.ORIGIN, store_binding=self.binding
        )
        self.assertTrue(self.registry.has_credential("owner-a"))
        self.registry.verify("owner-a", challenge, self.device.response(challenge, count=2))
        self.assertNotIn("owner-a", (self.path / "keys.json").read_text())
        with self.assertRaises(DevelopmentStoreRejected):
            self.registry.register(
                "owner-a", challenge, self.device.response(challenge, register=True)
            )

    def test_registration_rejects_missing_uv_and_other_owner_reuse(self):
        challenge = secrets.token_bytes(32)
        with self.assertRaises(InvalidRegistrationResponse):
            self.registry.register(
                "a", challenge, self.device.response(challenge, register=True, flags=0x41)
            )
        self.registry.register("a", challenge, self.device.response(challenge, register=True))
        with self.assertRaises(DevelopmentStoreRejected):
            self.registry.register("b", challenge, self.device.response(challenge, register=True))

    def test_tampering_missing_registry_wrong_binding_and_concurrent_open_fail_closed(self):
        with self.assertRaises(BlockingIOError):
            DevelopmentDeletionPasskeys(
                self.path, origin=foundation.ORIGIN, store_binding=self.binding
            )
        self.registry.close()
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentDeletionPasskeys(self.path, origin=foundation.ORIGIN, store_binding="0" * 64)
        self.registry = DevelopmentDeletionPasskeys(
            self.path, origin=foundation.ORIGIN, store_binding=self.binding
        )
        envelope = json.loads((self.path / "keys.json").read_text())
        envelope["payload"]["credentials"]["0" * 64] = {"id": "fake"}
        (self.path / "keys.json").write_text(json.dumps(envelope))
        with self.assertRaises(DevelopmentStoreRejected):
            self.registry.has_credential("a")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentDeletionPasskeys(
                self.path.parent / "missing", origin=foundation.ORIGIN, store_binding=self.binding
            )

    def test_other_session_bad_signature_and_expired_ceremony_cannot_delete(self):
        with self.base.client() as browser, self.base.other_browser() as other:
            self.base.enroll(browser)
            self.base.begin(other)
            self.register_browser(browser)
            fields = self.deletion_page(browser)
            self.assertEqual(
                other.post(
                    "/deletion/development/passkey",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            broken = copy.deepcopy(json.loads(fields["credential"]))
            broken["response"]["signature"] = b64(bytes(64))
            self.assertEqual(
                browser.post(
                    "/deletion/development/passkey",
                    data={**fields, "credential": json.dumps(broken)},
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            self.assertEqual(
                browser.post(
                    "/deletion/development/passkey",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            fields = self.deletion_page(browser)
            self.base.now += 181
            self.assertEqual(
                browser.post(
                    "/deletion/development/passkey",
                    data=fields,
                    headers={"origin": foundation.ORIGIN},
                ).status_code,
                409,
            )
            self.assertEqual(self.fx.counts(), (0, 0))

    def test_registration_disabled_and_non_owner_provider_callback_are_refused(self):
        with self.base.client() as browser:
            self.base.enroll(browser)
            self.base.app.passkeys.allow_enrollment = False
            self.assertEqual(browser.get("/security/development/passkey").status_code, 403)
            self.base.app.passkeys.allow_enrollment = True
            page = browser.get("/security/development/passkey")
            result = browser.post(
                "/security/development/passkey/reauth",
                data={"token": self.base.form_token(page), "confirm": "reviewed_enrollment"},
                headers={"origin": foundation.ORIGIN},
            )
            query = parse_qs(
                urlsplit(
                    unescape(re.search("href='([^']+)'>인증 제공자에서 계속", result.text).group(1))
                ).query
            )
            self.base.nonce = query["nonce"][0]
            self.assertEqual(
                browser.get(
                    "/auth/callback", params={"state": query["state"][0], "code": "user-b"}
                ).status_code,
                409,
            )
            self.assertEqual(self.fx.counts(), (0, 0))

    def test_missing_registered_device_blocks_before_another_provider_login(self):
        with self.base.client() as browser:
            self.base.enroll(browser)
            page = browser.get("/deletion/development/profile/" + self.fx.profile().id)
            exchanges = self.base.exchanges
            result = browser.post(
                "/deletion/development/reauth",
                data=self.fields(page, "reviewed_impact"),
                headers={"origin": foundation.ORIGIN},
            )
            self.assertEqual(result.status_code, 409)
            self.assertIn("패스키 등록이 필요", result.text)
            self.assertEqual(self.base.exchanges, exchanges)
            self.assertEqual(self.fx.counts(), (0, 0))

    def test_expired_registration_review_has_safe_restart_and_fresh_review_succeeds(self):
        with self.base.client() as browser:
            self.base.enroll(browser)
            self.base.now -= 181
            page = browser.get("/security/development/passkey")
            fields = {"token": self.base.form_token(page), "confirm": "reviewed_enrollment"}
            self.base.now += 181
            exchanges = self.base.exchanges
            result = browser.post(
                "/security/development/passkey/reauth",
                data=fields,
                headers={"origin": foundation.ORIGIN},
            )
            self.assertEqual(result.status_code, 409)
            self.assertIn("새 등록 검토 열기", result.text)
            self.assertEqual(self.base.exchanges, exchanges)
            self.assertFalse(self.registry.has_credential(self.fx.profile().account_id))
            self.assertEqual(self.fx.counts(), (0, 0))
            self.register_browser(browser)
            self.assertTrue(self.registry.has_credential(self.fx.profile().account_id))

    def test_invalid_runtime_opt_ins_fail_before_provider_discovery(self):
        settings = Auth0Settings(
            "unused.example", "synthetic", "synthetic", "synthetic", "http://localhost:5000"
        )
        mcp = McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE)
        for flags in (
            {"initialize_passkeys": True},
            {"allow_passkey_enrollment": True},
            {"passkey_dir": self.path},
            {"connection_denials_dir": self.path},
            {"connection_client_id": "synthetic"},
            {"initialize_connection_denials": True},
        ):
            with (
                self.subTest(flags=tuple(flags)),
                patch("careerground.auth0_development_runtime.discover") as discover,
            ):
                with self.assertRaises(ValueError):
                    Auth0DevelopmentRuntime(settings, mcp, **flags)
                discover.assert_not_called()

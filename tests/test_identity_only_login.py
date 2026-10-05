"""Signed synthetic identity tokens, one-use callbacks, and local account isolation."""

import asyncio
import base64
import hashlib
import time
import unittest
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request, Response
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import AuthenticationRequired, VerifiedIdentity
from careerground.providers.oidc_identity import (
    MFA_AUTHENTICATION_CONTEXT,
    IdentityClientSettings,
    IdentityLoginRejected,
    IdentityOnlyLogin,
    StableAccountAdmission,
)
from careerground.storage.models import Account, AuthIdentity, CareerProfile
from careerground.web.review_foundation import build_synthetic_review_app
from careerground.web.verified_browser_sessions import COOKIE, VerifiedBrowserSessions
from tests import test_mcp_product_foundation as foundation

ISSUER = "https://identity.synthetic.example/"
CLIENT = "synthetic-registered-client"
BINDING = "synthetic-browser-transaction-binding-0001"
SECRET = b"synthetic-persistent-admission-key-0001"


class IdentityLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.now = time.time()
        self.settings = IdentityClientSettings(
            ISSUER,
            CLIENT,
            ISSUER + "authorize",
            ISSUER + "token",
            "https://manage.synthetic.example/callback",
        )
        self.exchanges = []
        self.overrides = {}
        self.signing_key = self.key
        self.login = IdentityOnlyLogin(
            self.settings,
            exchange_code=self.exchange,
            signing_key=lambda _token: self.key.public_key(),
            clock=lambda: self.now,
        )

    def exchange(self, body):
        self.exchanges.append(body)
        claims = {
            "iss": ISSUER,
            "sub": "synthetic-a",
            "aud": CLIENT,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "nonce": self.query["nonce"][0],
            "email": "untrusted@synthetic.example",
            **self.overrides,
        }
        return {
            "id_token": jwt.encode(
                claims, self.signing_key, algorithm="RS256", headers={"kid": "synthetic"}
            )
        }

    def start(self):
        self.query = parse_qs(urlsplit(self.login.begin(BINDING)).query)
        return {
            "state": self.query["state"][0],
            "code": "synthetic-code",
            "browser_binding": BINDING,
        }

    def test_identity_only_scope_s256_nonce_and_single_use(self):
        args = self.start()
        self.assertEqual(self.query["scope"], ["openid profile email"])
        self.assertNotIn("resource", self.query)
        self.assertEqual(self.query["code_challenge_method"], ["S256"])
        self.assertEqual(self.login.finish(**args), VerifiedIdentity(ISSUER, "synthetic-a"))
        body = self.exchanges[0]
        digest = (
            base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"].encode()).digest())
            .decode()
            .rstrip("=")
        )
        self.assertEqual(digest, self.query["code_challenge"][0])
        self.assertEqual(body["redirect_uri"], self.settings.redirect_uri)
        with self.assertRaises(IdentityLoginRejected):
            self.login.finish(**args)
        self.assertEqual(len(self.exchanges), 1)

    def test_unknown_expired_and_wrong_browser_state_do_not_exchange(self):
        for failure in ["unknown", "expired", "browser"]:
            args = self.start()
            if failure == "unknown":
                args["state"] = "unknown"
            if failure == "expired":
                self.now += 181
            if failure == "browser":
                args["browser_binding"] = BINDING + "other"
            with self.subTest(failure=failure), self.assertRaises(IdentityLoginRejected):
                self.login.finish(**args)
        self.assertEqual(self.exchanges, [])

    def test_bad_claims_and_signature_fail_without_provider_payload(self):
        for changes in [
            {"iss": "https://other.synthetic.example/"},
            {"aud": "other-client"},
            {"exp": 1},
            {"iat": int(time.time()) + 600},
            {"nonce": "wrong"},
            {"sub": ""},
            {"sub": "synthetic\x00other"},
            {"exp": str(int(time.time()) + 300)},
            {"iat": True},
            {"azp": "other-client"},
            {"aud": [CLIENT, "other-client"]},
        ]:
            self.overrides = changes
            with self.subTest(changes=changes), self.assertRaises(IdentityLoginRejected) as error:
                self.login.finish(**self.start())
            self.assertEqual(str(error.exception), "")
        self.overrides = {}
        self.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(IdentityLoginRejected):
            self.login.finish(**self.start())

    def test_exchange_failure_is_sanitized_and_consumes_transaction(self):
        def fail(_body):
            raise RuntimeError("synthetic-private-provider-response")

        self.login._exchange = fail
        args = self.start()
        for _ in range(2):
            with self.assertRaises(IdentityLoginRejected) as error:
                self.login.finish(**args)
            self.assertEqual(str(error.exception), "")

    def start_reauthentication(self):
        self.query = parse_qs(urlsplit(self.login.begin_reauthentication(BINDING)).query)
        return {
            "state": self.query["state"][0],
            "code": "synthetic-code",
            "browser_binding": BINDING,
        }

    def test_reauthentication_requires_signed_fresh_auth_time(self):
        self.overrides = {"auth_time": int(self.now)}
        result = self.login.finish_reauthentication(**self.start_reauthentication())
        self.assertEqual(self.query["max_age"], ["0"])
        self.assertEqual(self.query["prompt"], ["login"])
        self.assertEqual(result.identity, VerifiedIdentity(ISSUER, "synthetic-a"))
        self.assertEqual(result.authenticated_at, int(self.now))

    def test_mfa_request_is_opt_in_and_normal_login_does_not_request_it(self):
        for begin in (self.login.begin, self.login.begin_reauthentication):
            query = parse_qs(urlsplit(begin(BINDING)).query)
            self.assertNotIn("acr_values", query)
        query = parse_qs(
            urlsplit(self.login.begin_reauthentication(BINDING, require_mfa=True)).query
        )
        self.assertEqual(query["acr_values"], [MFA_AUTHENTICATION_CONTEXT])
        self.assertEqual(query["max_age"], ["0"])
        self.assertEqual(query["prompt"], ["login"])
        self.assertEqual(query["scope"], ["openid profile email"])
        with self.assertRaises(IdentityLoginRejected):
            self.login.begin_reauthentication(BINDING, require_mfa="true")

    def test_reauthentication_rejects_absent_old_future_and_wrong_type_auth_time(self):
        for value in (None, int(self.now) - 1, int(self.now) + 10, True, str(int(self.now))):
            self.overrides = {} if value is None else {"auth_time": value}
            with self.subTest(value=value), self.assertRaises(IdentityLoginRejected):
                self.login.finish_reauthentication(**self.start_reauthentication())

    def test_slow_interactive_reauthentication_needs_a_fresh_result_and_bounded_transaction(self):
        for delay, stale in ((240, False), (240, True), (601, False)):
            with self.subTest(delay=delay, stale=stale):
                self.now = time.time() - delay
                args = self.start_reauthentication()
                requested_at = int(self.now)
                self.now += delay
                self.overrides = {"auth_time": requested_at if stale else int(self.now)}
                if stale or delay > 600:
                    with self.assertRaises(IdentityLoginRejected):
                        self.login.finish_reauthentication(**args)
                else:
                    self.assertEqual(
                        self.login.finish_reauthentication(**args).authenticated_at, int(self.now)
                    )

    def test_normal_login_and_reauthentication_transactions_cannot_be_interchanged(self):
        self.overrides = {"auth_time": int(self.now)}
        for start, finish in (
            (self.start, self.login.finish_reauthentication),
            (self.start_reauthentication, self.login.finish),
        ):
            args = start()
            with self.assertRaises(IdentityLoginRejected):
                finish(**args)
            with self.assertRaises(IdentityLoginRejected):
                finish(**args)
        self.assertEqual(self.exchanges, [])

    def test_transactions_are_bounded_expire_and_fail_after_restart(self):
        args = self.start()
        for _ in range(127):
            self.login.begin(BINDING)
        with self.assertRaises(IdentityLoginRejected):
            self.login.begin(BINDING)
        self.now += 181
        self.login.begin(BINDING)
        self.assertEqual(len(self.login._transactions), 1)
        fresh = IdentityOnlyLogin(
            self.settings, exchange_code=self.exchange, signing_key=lambda _t: self.key.public_key()
        )
        with self.assertRaises(IdentityLoginRejected):
            fresh.finish(**args)

    def test_settings_reject_remote_plaintext_credentials_queries_and_bad_ports(self):
        for value in [
            "http://remote.example/callback",
            "https://u:p@host.example/callback",
            "https://host.example/callback?next=other",
            "https://host.example:99999/callback",
            "https://host.example\\other",
            "https://host.example\n",
            None,
            "https://host.example/" + "a" * 2048,
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                IdentityClientSettings(
                    ISSUER, CLIENT, ISSUER + "authorize", ISSUER + "token", value
                )


class AdmissionSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.ProductFoundationTests.setUpClass()

    def setUp(self):
        self.fixture = foundation.ProductFoundationTests()
        self.fixture.setUp()
        self.sessions = self.fixture.sessions
        self.now = time.time()
        self.admission = StableAccountAdmission(
            issuer=ISSUER,
            secret=SECRET,
            admitted_subjects=frozenset({"synthetic-a", "synthetic-b"}),
        )
        self.identities = [
            VerifiedIdentity(ISSUER, "synthetic-a"),
            VerifiedIdentity(ISSUER, "synthetic-b"),
        ]
        with self.sessions() as session:
            for identity in self.identities:
                initialize_account_profile(
                    session, identity=identity, enrollment_account_id=self.admission(identity)
                )
            session.commit()
        self.browser = VerifiedBrowserSessions(self.sessions, clock=lambda: self.now)

    def tearDown(self):
        self.fixture.tearDown()

    def cookie(self, identity):
        response = Response()
        self.browser.issue(identity, response)
        header = response.headers["set-cookie"]
        self.assertIn("HttpOnly", header)
        self.assertIn("Secure", header)
        self.assertIn("SameSite=lax", header)
        return header.split(";", 1)[0]

    def request(self, cookie):
        return Request({"type": "http", "headers": [(b"cookie", cookie.encode())]})

    def read(self, cookie):
        return asyncio.run(self.browser(self.request(cookie), Response()))

    def test_stable_admission_survives_restart_and_erased_mapping_cannot_reenroll(self):
        identity = self.identities[0]
        restarted = StableAccountAdmission(
            issuer=ISSUER, secret=SECRET, admitted_subjects=frozenset({identity.subject})
        )
        self.assertEqual(self.admission(identity), restarted(identity))
        self.assertNotEqual(self.admission(identity), self.admission(self.identities[1]))
        self.assertIsNone(self.admission(VerifiedIdentity(ISSUER, "unknown")))
        self.assertIsNone(
            self.admission(VerifiedIdentity("https://other.example/", identity.subject))
        )
        with self.sessions() as session:
            session.get(Account, self.admission(identity)).status = "ERASED"
            session.execute(
                delete(AuthIdentity).where(AuthIdentity.account_id == self.admission(identity))
            )
            session.commit()
        with self.sessions() as session, self.assertRaises(AuthenticationRequired):
            initialize_account_profile(
                session, identity=identity, enrollment_account_id=restarted(identity)
            )

    def test_two_accounts_separate_sessions_cookie_swap_expiry_and_revoke(self):
        a, b = (self.cookie(identity) for identity in self.identities)
        first, second = self.read(a), self.read(b)
        self.assertEqual(first.account_id, self.admission(self.identities[0]))
        self.assertEqual(second.account_id, self.admission(self.identities[1]))
        self.assertNotEqual(first.session_id, second.session_id)
        self.assertIsNone(self.read(a + "; " + b))
        response = Response()
        self.browser.revoke(self.request(a), response)
        self.assertIsNone(self.read(a))
        self.assertIsNotNone(self.read(b))
        self.now += 3601
        self.assertIsNone(self.read(b))

    def test_account_disable_or_mapping_removal_blocks_existing_cookie_next_request(self):
        identity = self.identities[0]
        cookie = self.cookie(identity)
        with self.sessions() as session:
            session.get(Account, self.admission(identity)).status = "DISABLED"
            session.commit()
        self.assertIsNone(self.read(cookie))
        with self.sessions() as session:
            session.get(Account, self.admission(identity)).status = "ACTIVE"
            session.commit()
        self.assertIsNone(self.read(cookie))
        cookie = self.cookie(identity)
        with self.sessions() as session:
            session.execute(
                delete(AuthIdentity).where(AuthIdentity.account_id == self.admission(identity))
            )
            session.commit()
        self.assertIsNone(self.read(cookie))

    def test_session_restart_denies_old_cookie_and_unknown_identity_never_provisions(self):
        cookie = self.cookie(self.identities[0])
        fresh = VerifiedBrowserSessions(self.sessions)
        self.assertIsNone(asyncio.run(fresh(self.request(cookie), Response())))
        with self.assertRaises(AuthenticationRequired):
            fresh.issue(VerifiedIdentity(ISSUER, "unknown"), Response())

    def test_review_factory_uses_same_account_and_denies_other_profile_and_revoked_session(self):
        app = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=self.browser,
            review_signing_secret=foundation.REVIEW_SECRET,
            presentation_signing_secret=foundation.REVIEW_SECRET,
        )
        with self.sessions() as session:
            profiles = [
                session.scalar(
                    select(CareerProfile.id).where(
                        CareerProfile.account_id == self.admission(identity)
                    )
                )
                for identity in self.identities
            ]
        cookies = [self.cookie(identity).split("=", 1)[1] for identity in self.identities]
        with TestClient(app, base_url="https://manage.synthetic.example") as client:
            client.cookies.set(COOKIE, cookies[0])
            self.assertEqual(client.get("/profiling/start").status_code, 200)
            self.assertEqual(client.get(f"/profile/{profiles[0]}/export/0").status_code, 200)
            denied = client.get(f"/profile/{profiles[1]}/export/0")
            self.assertEqual(denied.status_code, 404)
            self.assertNotIn(profiles[1], denied.text)
            self.browser.revoke(self.request(COOKIE + "=" + cookies[0]), Response())
            self.assertEqual(client.get("/profiling/start").status_code, 401)
            client.cookies.set(COOKIE, cookies[1])
            self.assertEqual(client.get(f"/profile/{profiles[1]}/export/0").status_code, 200)

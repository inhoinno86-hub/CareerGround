"""Shared quotas, exception privacy and wire contracts on isolated synthetic adapters."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.config import Settings
from careerground.domain.request_limits import (
    AccountRequestLimiter,
    RequestLimitExceeded,
    RequestLimitPolicy,
    RequestLimitStoreUnavailable,
)
from careerground.domain.safe_events import security_metrics_snapshot
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.storage.database import make_engine
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    DeletionRequest,
    ProfilingSession,
    RequestLimitBucket,
)
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app

SECRET = b"synthetic-adapter-security-secret-at-least-32-bytes"
ISSUER = "https://auth.security.synthetic.example/"
RESOURCE = "https://mcp.security.synthetic.example/mcp"


class AdapterSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            for suffix in ("a", "b"):
                session.add(
                    AuthIdentity(
                        id=f"identity-{suffix}",
                        account_id=f"acct-{suffix}",
                        issuer=ISSUER,
                        subject=f"user-{suffix}",
                    )
                )
                session.add(
                    CareerProfile(id=f"profile-{suffix}", account_id=f"acct-{suffix}", version=0)
                )
            session.commit()

    def apps(self, limits=None):
        limits = limits or RequestLimitPolicy(2, 2, 60)
        web = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=lambda request, _response: TrustedBrowserIdentity(
                "acct-b" if request.cookies.get("account") == "b" else "acct-a",
                "synthetic-browser-session-" + request.cookies.get("account", "a"),
            ),
            review_signing_secret=SECRET,
            presentation_signing_secret=SECRET,
            request_limits=limits,
        )
        mcp = build_product_foundation_app(
            McpOAuthSettings(ISSUER, RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=SECRET,
            signing_key=lambda _token: self.key.public_key(),
            request_limits=limits,
        )
        return web, mcp

    def token(self, *, scope="career.profile.read", subject="user-a"):
        now = int(time.time())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": RESOURCE,
                "sub": subject,
                "azp": "synthetic-client",
                "scope": scope,
                "iat": now,
                "exp": now + 300,
            },
            self.key,
            algorithm="RS256",
            headers={"kid": "synthetic-key"},
        )

    def call(self, client, name, args, *, scope="career.profile.read", subject="user-a"):
        return client.post(
            "/mcp",
            headers={"Authorization": "Bearer " + self.token(scope=scope, subject=subject)},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": args},
            },
        )

    def test_read_quota_is_shared_across_factories_and_account_sessions(self):
        web, mcp = self.apps()
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            self.assertEqual(browser.get("/profiling/start").status_code, 200)
            self.assertEqual(
                self.call(client, "get_account_profile", {}).json()["result"]["structuredContent"][
                    "status"
                ],
                "ok",
            )
            limited = browser.get("/profiling/start")
            self.assertEqual(limited.status_code, 429)
            self.assertGreater(int(limited.headers["retry-after"]), 0)
            limited_mcp = self.call(client, "get_account_profile", {})
            self.assertEqual(limited_mcp.status_code, 429)
            error = limited_mcp.json()["result"]["structuredContent"]["error"]
            self.assertEqual(error["code"], "RATE_LIMITED")
            self.assertEqual(int(limited_mcp.headers["retry-after"]), error["retry_after_seconds"])
            browser.cookies.set("account", "b")
            self.assertEqual(browser.get("/profiling/start").status_code, 200)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 0)
            rows = tuple(session.scalars(select(RequestLimitBucket)))
            self.assertEqual(sorted(row.requests for row in rows), [1, 2])
            self.assertFalse(
                any("acct" in row.bucket_key or "user" in row.bucket_key for row in rows)
            )

    def test_write_quota_rejects_before_domain_mutation_and_wrong_scope(self):
        web, mcp = self.apps()
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            start = browser.get("/profiling/start")
            token = re.search(r"name='start_token' value='([^']+)'", start.text).group(1)
            form = {"start_token": token, "confirm": "start"}
            args = {
                "profile_id": "profile-a",
                "goal": "ADD_EXPERIENCE",
                "policy_version": "product-policy-v0.1",
                "idempotency_key": "synthetic_security_start",
            }
            denied = self.call(client, "start_profiling", args)
            self.assertEqual(
                denied.json()["result"]["structuredContent"]["error"]["code"], "FORBIDDEN"
            )
            self.assertEqual(
                browser.post("/profiling/start", data=form, follow_redirects=False).status_code, 303
            )
            created = self.call(client, "start_profiling", args, scope="career.profile.write")
            self.assertEqual(created.json()["result"]["structuredContent"]["status"], "ok")
            self.assertEqual(browser.post("/profiling/start", data=form).status_code, 429)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 2)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)

    def test_unscoped_confirmation_requests_do_not_charge_write_quota(self):
        web, mcp = self.apps()
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            start = browser.get("/profiling/start")
            token = re.search(r"name='start_token' value='([^']+)'", start.text).group(1)
            for _ in range(3):
                denied = self.call(
                    client,
                    "request_user_confirmation",
                    {
                        "action": "PROFILE_EXPORT",
                        "target_id": "profile-a",
                        "profile_version": 0,
                        "format": "JSON",
                        "idempotency_key": "synthetic_wrong_scope_0001",
                    },
                )
                self.assertEqual(
                    denied.json()["result"]["structuredContent"]["error"]["code"], "FORBIDDEN"
                )
            self.assertEqual(
                browser.post(
                    "/profiling/start",
                    data={"start_token": token, "confirm": "start"},
                    follow_redirects=False,
                ).status_code,
                303,
            )
        with self.sessions() as session:
            self.assertEqual(sorted(session.scalars(select(RequestLimitBucket.requests))), [1, 1])

    def test_mcp_ingress_rejects_oversized_private_body_before_auth_or_database(self):
        calls = []

        def forbidden_session():
            calls.append(True)
            raise AssertionError("MCP ingress reached the database")

        app = build_product_foundation_app(
            McpOAuthSettings(ISSUER, RESOURCE),
            session_factory=forbidden_session,
            review_signing_secret=SECRET,
            signing_key=lambda _token: self.key.public_key(),
        )
        sentinel = "synthetic-private-ingress-source-and-token"
        body = ("{" + sentinel + "}").encode() + b"x" * (128 * 1024)
        with TestClient(app, base_url="https://mcp.security.synthetic.example") as client:
            response = client.post(
                "/mcp",
                content=body,
                headers={"Authorization": "Bearer " + sentinel, "Content-Type": "application/json"},
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn(sentinel, response.text)
        self.assertEqual(calls, [])

    def test_malformed_protocol_requests_do_not_echo_private_source_or_credentials(self):
        _, mcp = self.apps()
        sentinel = "synthetic-private-malformed-protocol-source"
        bodies = (
            sentinel,
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": 123, "params": {"private": sentinel}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": [sentinel], "arguments": {}},
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_account_profile", "arguments": sentinel},
                }
            ),
        )
        with (
            self.assertLogs(level="INFO") as logs,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            token = self.token()
            for body in bodies:
                with self.subTest(kind=bodies.index(body)):
                    response = client.post(
                        "/mcp",
                        content=body,
                        headers={
                            "Authorization": "Bearer " + token,
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                        },
                    )
                    self.assertIn(response.status_code, {200, 400})
                    self.assertNotIn(sentinel, response.text)
                    self.assertNotIn(token, response.text)
        self.assertNotIn(sentinel, "\n".join(logs.output))
        self.assertNotIn(token, "\n".join(logs.output))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfilingSession)), 0)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)

    def test_authenticated_invalid_tool_calls_share_read_budget_before_error(self):
        web, mcp = self.apps(RequestLimitPolicy(4, 2, 60))
        sentinel = "synthetic-private-malformed-field"
        attempts = (
            ("get_account_profile", {"surplus": sentinel}),
            ("unknown_synthetic_tool", {}),
            ("get_career_profile", {"profile_id": "profile-a", "profile_version": True}),
            (
                "request_user_confirmation",
                {
                    "action": "BOGUS",
                    "target_id": "profile-a",
                    "profile_version": 0,
                    "format": "NONE",
                    "idempotency_key": "synthetic_invalid_action_0001",
                },
            ),
        )
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
            self.assertLogs("careerground", level="INFO") as logs,
        ):
            for name, arguments in attempts:
                response = self.call(client, name, arguments)
                self.assertEqual(response.status_code, 200, (name, response.text))
                self.assertEqual(
                    response.json()["result"]["structuredContent"]["error"]["code"],
                    "VALIDATION_FAILED",
                )
                self.assertNotIn(sentinel, response.text)
            denied = self.call(client, "get_account_profile", {})
            self.assertEqual(denied.status_code, 429)
            self.assertEqual(
                denied.json()["result"]["structuredContent"]["error"]["code"],
                "RATE_LIMITED",
            )
            self.assertEqual(browser.get("/profiling/start").status_code, 429)
            browser.cookies.set("account", "b")
            self.assertEqual(browser.get("/profiling/start").status_code, 200)
        self.assertNotIn(sentinel, "\n".join(logs.output))
        with self.sessions() as session:
            read_key = hmac.new(SECRET, b"request-quota-v1:read:acct-a", hashlib.sha256).hexdigest()
            self.assertEqual(
                session.scalar(
                    select(RequestLimitBucket.requests).where(
                        RequestLimitBucket.bucket_key == read_key
                    )
                ),
                4,
            )
            write_key = hmac.new(
                SECRET, b"request-quota-v1:write:acct-a", hashlib.sha256
            ).hexdigest()
            self.assertIsNone(
                session.scalar(
                    select(RequestLimitBucket.requests).where(
                        RequestLimitBucket.bucket_key == write_key
                    )
                )
            )

    def test_unexpected_errors_and_validation_never_log_or_return_private_values(self):
        web, mcp = self.apps(RequestLimitPolicy(20, 20, 60))
        sentinel = "synthetic-private-body-token-or-sql-parameter"
        crash = IntegrityError("SELECT private_value", {"value": sentinel}, RuntimeError(sentinel))
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            with self.assertLogs("careerground", level="INFO") as logs:
                with patch(
                    "careerground.domain.profiling_start_presentation.ProfilingStartService.present",
                    side_effect=crash,
                ):
                    failed_web = browser.get("/profiling/start")
                self.assertEqual(failed_web.status_code, 500)
                self.assertNotIn(sentinel, failed_web.text)
                self.assertNotIn("저장되지 않았습니다", failed_web.text)
                with patch("careerground.mcp.product_server.get_career_profile", side_effect=crash):
                    failed_mcp = self.call(
                        client,
                        "get_career_profile",
                        {"profile_id": "profile-a", "profile_version": 0},
                    )
                self.assertEqual(
                    failed_mcp.json()["result"]["structuredContent"]["error"]["code"],
                    "INTERNAL_ERROR",
                )
                self.assertNotIn(sentinel, failed_mcp.text)
                invalid = browser.get("/profile/profile-a/" + sentinel)
                self.assertEqual(invalid.status_code, 400)
                self.assertNotIn(sentinel, invalid.text)
            self.assertNotIn(sentinel, "\n".join(logs.output))
            self.assertNotIn("Traceback", "\n".join(logs.output))
        self.engine.dispose()
        with TestClient(web) as browser:
            self.assertEqual(browser.get("/profiling/start").status_code, 503)

    def test_foundation_deletion_preview_matches_web_counts_without_execution(self):
        web, mcp = self.apps(RequestLimitPolicy(20, 20, 60))
        with (
            TestClient(web) as browser,
            TestClient(mcp, base_url="https://mcp.security.synthetic.example") as client,
        ):
            page = browser.get("/deletion/preview/account")
            result = self.call(
                client,
                "preview_data_deletion",
                {"scope": "ACCOUNT", "target_ids": ["acct-a"]},
                scope="career.delete",
            )
            data = result.json()["result"]["structuredContent"]["data"]
            self.assertEqual(data["coverage"], "FOUNDATION_ONLY")
            self.assertIs(data["ready_to_execute"], False)
            self.assertNotIn("deletion_digest", data)
            self.assertIn("완전한 삭제 영향이나 삭제 완료를 뜻하지 않습니다", page.text)
            for kind, count in data["counts"].items():
                self.assertIn(f"{kind}: {count}", page.text)
            for scope, target in (("PROFILE", "profile-b"), ("ACCOUNT", "acct-b")):
                denied = self.call(
                    client,
                    "preview_data_deletion",
                    {"scope": scope, "target_ids": [target]},
                    scope="career.delete",
                )
                self.assertEqual(
                    denied.json()["result"]["structuredContent"]["error"]["code"], "NOT_FOUND"
                )
            malformed = self.call(
                client,
                "preview_data_deletion",
                {"scope": "INVALID", "target_ids": ["anything"]},
                scope="career.delete",
            )
            self.assertEqual(
                malformed.json()["result"]["structuredContent"]["error"]["code"],
                "VALIDATION_FAILED",
            )
            unscoped = self.call(
                client, "preview_data_deletion", {"scope": "ACCOUNT", "target_ids": ["acct-a"]}
            )
            self.assertEqual(
                unscoped.json()["result"]["structuredContent"]["error"]["code"], "FORBIDDEN"
            )
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 0)

    def test_web_metrics_count_success_and_error_once(self):
        web, _ = self.apps()
        before = security_metrics_snapshot()["requests"]["web"]
        with TestClient(web) as browser:
            self.assertEqual(browser.get("/profiling/start").status_code, 200)
            self.assertEqual(
                browser.post("/profiling/start", data={"confirm": "wrong"}).status_code, 400
            )
        after = security_metrics_snapshot()["requests"]["web"]
        self.assertEqual(after["OK"], before["OK"] + 1)
        self.assertEqual(after["VALIDATION_FAILED"], before["VALIDATION_FAILED"] + 1)

    def test_engine_hides_sql_parameters_in_database_errors(self):
        engine = make_engine(Settings("sqlite+pysqlite:///:memory:"))
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE sample (value TEXT UNIQUE)"))
            connection.execute(
                text("INSERT INTO sample VALUES (:value)"), {"value": "synthetic-private-bind"}
            )
            with self.assertRaises(IntegrityError) as caught:
                connection.execute(
                    text("INSERT INTO sample VALUES (:value)"), {"value": "synthetic-private-bind"}
                )
        self.assertNotIn("synthetic-private-bind", str(caught.exception))

    def test_all_tool_schemas_describe_the_actual_common_envelope(self):
        _, app = self.apps(RequestLimitPolicy(120, 60, 60))
        with TestClient(app, base_url="https://mcp.security.synthetic.example") as client:

            def listing():
                response = client.post(
                    "/mcp",
                    headers={"Authorization": "Bearer " + self.token()},
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                self.assertEqual(response.status_code, 200)
                return response.json()["result"]["tools"]

            tools = listing()
            self.assertEqual(tools, listing(), "listing must not repeatedly nest envelopes")
            self.assertEqual(len(tools), 30)
            for tool in tools:
                with self.subTest(tool=tool["name"]):
                    self.assertIs(tool["inputSchema"]["additionalProperties"], False)
                    schema = tool["outputSchema"]
                    Draft202012Validator.check_schema(schema)
                    invalid = self.call(client, tool["name"], {"surplus": "synthetic-private"})
                    result = invalid.json()["result"]
                    Draft202012Validator(schema).validate(result["structuredContent"])
                    self.assertTrue(result["isError"])
                    self.assertEqual(
                        json.loads(result["content"][0]["text"]), result["structuredContent"]
                    )
                    self.assertNotIn("synthetic-private", invalid.text)
            for name, args, scope in (
                ("get_account_profile", {}, "career.profile.read"),
                (
                    "get_owned_profile_metadata",
                    {"profile_id": "profile-a"},
                    "career.profile.read",
                ),
                (
                    "preview_data_deletion",
                    {"scope": "ACCOUNT", "target_ids": ["acct-a"]},
                    "career.delete",
                ),
                (
                    "start_profiling",
                    {
                        "profile_id": "profile-a",
                        "goal": "ADD_EXPERIENCE",
                        "policy_version": "product-policy-v0.1",
                        "idempotency_key": "synthetic_schema_start",
                    },
                    "career.profile.write",
                ),
            ):
                result = self.call(client, name, args, scope=scope).json()["result"]
                self.assertEqual(result["structuredContent"]["status"], "ok", (name, result))
                schema = next(tool["outputSchema"] for tool in tools if tool["name"] == name)
                Draft202012Validator(schema).validate(result["structuredContent"])


class RequestLimitConcurrencyTests(unittest.TestCase):
    def test_concurrent_reservations_are_bounded_and_expired_rows_are_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine("sqlite+pysqlite:///" + str(Path(directory) / "quota.sqlite"))
            try:
                Base.metadata.create_all(engine)
                sessions = sessionmaker(bind=engine)
                now = [120.0]
                limiter = AccountRequestLimiter(
                    sessions, SECRET, policy=RequestLimitPolicy(5, 5, 60), clock=lambda: now[0]
                )

                def reserve(_):
                    try:
                        limiter.consume("synthetic-race-account", "write")
                        return True
                    except RequestLimitExceeded:
                        return False

                with ThreadPoolExecutor(max_workers=8) as workers:
                    self.assertEqual(sum(workers.map(reserve, range(24))), 5)
                now[0] = 180.0
                limiter.consume("synthetic-race-account", "write")
                with sessions() as session:
                    rows = tuple(session.scalars(select(RequestLimitBucket)))
                    self.assertEqual([(row.window_start, row.requests) for row in rows], [(180, 1)])
                engine.dispose()
                with self.assertRaises(RequestLimitStoreUnavailable):
                    AccountRequestLimiter(
                        lambda: (_ for _ in ()).throw(
                            IntegrityError("private", {}, Exception("private"))
                        ),
                        SECRET,
                    ).consume("synthetic", "read")
            finally:
                engine.dispose()

    def test_postgres_concurrent_reservations_share_one_counter(self):
        raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw_url:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("CI requires an explicit local PostgreSQL test URL")
            self.skipTest("local test PostgreSQL URL is not configured")
        url = make_url(raw_url)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing to run outside a local *_test PostgreSQL database")
        engine = create_engine(url, hide_parameters=True)
        sessions = sessionmaker(bind=engine)
        account = "synthetic-race-" + uuid4().hex
        limiter = AccountRequestLimiter(
            sessions, SECRET, policy=RequestLimitPolicy(5, 5, 60), clock=lambda: 120.0
        )

        def reserve(_):
            try:
                limiter.consume(account, "write")
                return True
            except RequestLimitExceeded:
                return False

        try:
            with ThreadPoolExecutor(max_workers=8) as workers:
                self.assertEqual(sum(workers.map(reserve, range(24))), 5)
        finally:
            key = hmac.new(
                SECRET, f"request-quota-v1:write:{account}".encode(), hashlib.sha256
            ).hexdigest()
            with engine.begin() as connection:
                connection.execute(
                    delete(RequestLimitBucket).where(RequestLimitBucket.bucket_key == key)
                )
            engine.dispose()

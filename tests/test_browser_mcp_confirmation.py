"""Actual HTTP browser confirmation, MCP receipt and private export integration."""

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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from careerground.domain.browser_operations import BrowserOperationService, prune_browser_operations
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.storage.graph_models import Claim, ClaimAssessment, ProfileChangeSet
from careerground.storage.jd_artifact_models import ArtifactWordingReview
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    BrowserOperation,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    RequestLimitBucket,
)
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app
from careerground.workers.local_security_maintenance import run_local_security_maintenance

SECRET = b"synthetic-confirmation-integration-secret-32-bytes"
PRESENTATION = b"separate-synthetic-browser-presentation-secret-32-bytes"
ISSUER = "https://auth.confirmation.synthetic.example/"
RESOURCE = "https://mcp.confirmation.synthetic.example/mcp"
SCOPES = "career.profile.read career.profile.write career.artifact.read career.artifact.write career.export career.delete"
PHRASE = "합성 기능의 테스트를 작성했다."


class BrowserMCPConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def prepare_database(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.engine = create_engine(
            "sqlite+pysqlite:///" + str(Path(self.folder.name) / "synthetic.sqlite"),
            hide_parameters=True,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

    def setUp(self):
        self.tokens = {}
        self.schemas = {}
        self.prepare_database()
        with self.sessions() as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            for suffix in ("a", "b"):
                session.add(
                    AuthIdentity(
                        id="auth-" + suffix,
                        account_id="acct-" + suffix,
                        issuer=ISSUER,
                        subject="user-" + suffix,
                    )
                )
                session.add(
                    CareerProfile(id="profile-" + suffix, account_id="acct-" + suffix, version=0)
                )
            session.commit()
        identities = {
            "owner": TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a"),
            "other-session": TrustedBrowserIdentity("acct-a", "synthetic-browser-session-b"),
            "foreign": TrustedBrowserIdentity("acct-b", "synthetic-browser-session-c"),
        }
        self.web = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=lambda request, _response: identities.get(
                request.cookies.get("cg_session", "owner")
            ),
            review_signing_secret=SECRET,
            presentation_signing_secret=PRESENTATION,
        )
        self.mcp = build_product_foundation_app(
            McpOAuthSettings(ISSUER, RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=SECRET,
            presentation_signing_secret=PRESENTATION,
            signing_key=lambda _token: self.key.public_key(),
        )
        self.service = BrowserOperationService(SECRET, PRESENTATION)

    def token(self, client_id="client-a", subject="user-a", scopes=SCOPES):
        identity = (client_id, subject, scopes)
        if identity in self.tokens:
            return self.tokens[identity]
        now = int(time.time())
        token = jwt.encode(
            {
                "iss": ISSUER,
                "aud": RESOURCE,
                "sub": subject,
                "azp": client_id,
                "scope": scopes,
                "iat": now,
                "exp": now + 300,
            },
            self.key,
            algorithm="RS256",
            headers={"kid": "synthetic-key"},
        )
        self.tokens[identity] = token
        return token

    def rpc(self, client, method, params, **identity):
        return client.post(
            "/mcp",
            headers={"Authorization": "Bearer " + self.token(**identity)},
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )

    def call(self, client, name, args, **identity):
        if not self.schemas:
            tools = self.rpc(client, "tools/list", {}).json()["result"]["tools"]
            self.schemas = {tool["name"]: tool["outputSchema"] for tool in tools}
        result = self.rpc(
            client, "tools/call", {"name": name, "arguments": args}, **identity
        ).json()["result"]["structuredContent"]
        Draft202012Validator(self.schemas[name]).validate(result)
        return result

    def request(
        self,
        client,
        action,
        target,
        version,
        format="NONE",
        key="synthetic_confirm_request_0001",
        **identity,
    ):
        result = self.call(
            client,
            "request_user_confirmation",
            {
                "action": action,
                "target_id": target,
                "profile_version": version,
                "format": format,
                "idempotency_key": key,
            },
            **identity,
        )
        self.assertEqual(result["status"], "ok", result)
        return result["data"]

    def hidden(self, html, name):
        value = re.search(rf"name='{name}' value='([^']+)'", html)
        self.assertIsNotNone(value, name)
        return value.group(1)

    def post(self, client, path, token_name, confirm, **extra):
        page = client.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        response = client.post(
            path,
            data={token_name: self.hidden(page.text, token_name), "confirm": confirm, **extra},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        return response.headers["location"]

    def review_batch(self, browser):
        work = self.post(browser, "/profiling/start", "start_token", "start")
        inputs = work + "/input"
        bullet = self.post(browser, inputs, "input_token", "submit", content="- " + PHRASE)
        drafts = self.post(browser, bullet, "bullet_token", "draft", scope_key="synthetic-feature")
        prepare = re.search(r"href='([^']+/prepare)'", browser.get(drafts).text).group(1)
        review = self.post(browser, prepare, "prepare_token", "prepare")
        return review.split("/")[-1]

    def form(self, browser, path):
        page = browser.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        confirms = re.findall(r"name='confirm' value='([^']+)'", page.text)
        data = {
            "confirmation_token": self.hidden(page.text, "confirmation_token"),
            "confirm": confirms[0],
            "allow_connection": "yes",
        }
        for name in re.findall(r"<select[^>]*name='([^']+)'", page.text):
            data[name] = "ACCEPT"
        return data

    def confirm(self, browser, path, data=None):
        result = browser.post(path, data=data or self.form(browser, path))
        self.assertEqual(result.status_code, 200, result.text)
        receipt = re.search(r"id='approval-receipt'>([^<]+)</code>", result.text)
        self.assertIsNotNone(receipt, result.text)
        return receipt.group(1)

    def fact(self, browser, client):
        batch = self.review_batch(browser)
        requested = self.request(client, "FACT_REVIEW", batch, 0)
        receipt = self.confirm(browser, requested["confirmation_path"])
        result = self.call(
            client, "submit_claim_review", {"review_batch_id": batch, "approval_receipt": receipt}
        )
        self.assertEqual(result["status"], "ok", result)
        return batch, receipt

    def artifact(self, browser, client):
        self.fact(browser, client)
        return self.artifact_after_fact(browser)

    def artifact_after_fact(self, browser):
        with self.sessions() as session:
            claim = session.scalar(select(Claim))
            claim_id = claim.id
        use = f"/profile/profile-a/1/claim/{claim_id}/use-review"
        page = browser.get(use)
        response = browser.post(
            use,
            data={
                "approval_token": self.hidden(page.text, "approval_token"),
                "confirm_consistency": "yes",
                "confirm_use": "yes",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303, response.text)
        jd = self.post(
            browser, "/jd/new", "paste_token", "store_excerpts", selected_text="- 테스트 작성 경험"
        )
        mapping = re.search(r"href='([^']+/mapping/2)'", browser.get(jd).text).group(1)
        link = re.search(r"href='([^']+/link/[^']+)'", browser.get(mapping).text).group(1)
        self.post(browser, link, "link_token", "link_potential")
        draft = re.search(r"href='([^']+/draft/2)'", browser.get(mapping).text).group(1)
        trace = self.post(browser, draft, "draft_token", "create_r1", claim_id=claim_id)
        return trace.split("/")[2]

    def test_fact_requires_actual_browser_and_same_connection_exact_retry(self):
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            batch = self.review_batch(browser)
            requested = self.request(client, "FACT_REVIEW", batch, 0)
            self.assertEqual(requested, self.request(client, "FACT_REVIEW", batch, 0))
            data = self.form(browser, requested["confirmation_path"])
            with self.sessions() as session:
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
            fake = self.call(
                client,
                "submit_claim_review",
                {
                    "review_batch_id": batch,
                    "approval_receipt": requested["request_id"] + "." + "0" * 64,
                },
            )
            self.assertEqual(fake["error"]["code"], "REVIEW_REQUIRED")
            self.assertEqual(
                browser.post(
                    requested["confirmation_path"],
                    data={k: v for k, v in data.items() if k != "allow_connection"},
                ).status_code,
                400,
            )
            browser.cookies.set("cg_session", "other-session")
            self.assertEqual(
                browser.post(requested["confirmation_path"], data=data).status_code, 409
            )
            browser.cookies.set("cg_session", "foreign")
            self.assertEqual(browser.get(requested["confirmation_path"]).status_code, 404)
            browser.cookies.set("cg_session", "owner")
            self.assertEqual(
                browser.post(
                    requested["confirmation_path"],
                    data=data,
                    headers={"Origin": "https://foreign.synthetic.example"},
                ).status_code,
                400,
            )
            self.assertEqual(
                browser.post(
                    requested["confirmation_path"], data=data, headers={"Origin": "null"}
                ).status_code,
                400,
            )
            receipt = self.confirm(browser, requested["confirmation_path"], data)
            changed = {
                **data,
                next(key for key in data if key.startswith("decision_")): "NEEDS_FOLLOWUP",
            }
            self.assertEqual(
                browser.post(requested["confirmation_path"], data=changed).status_code, 409
            )
            self.assertEqual(self.confirm(browser, requested["confirmation_path"], data), receipt)
            args = {"review_batch_id": batch, "approval_receipt": receipt}
            for identity in ({"client_id": "other-client"}, {"subject": "user-b"}):
                self.assertEqual(
                    self.call(client, "submit_claim_review", args, **identity)["status"], "error"
                )
            result = self.call(client, "submit_claim_review", args)
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual(result, self.call(client, "submit_claim_review", args))
        with self.sessions() as session:
            assessment = session.scalar(select(ClaimAssessment))
            self.assertEqual(
                (assessment.knowledge_status, assessment.usage_policy),
                ("USER_CONFIRMED", "REVIEW_REQUIRED"),
            )
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileChangeSet)), 1)
            row = session.scalar(select(BrowserOperation))
            self.assertEqual(row.status, "CONSUMED")
            self.assertNotIn(PHRASE, row.result_json)
            self.assertNotIn(receipt, row.result_json)

    def test_wording_and_export_resource_recheck_owner_connection_expiry_and_erasure(self):
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            artifact = self.artifact(browser, client)
            wording = self.request(
                client, "WORDING_REVIEW", artifact, 2, key="synthetic_confirm_wording_0001"
            )
            receipt = self.confirm(browser, wording["confirmation_path"])
            result = self.call(
                client,
                "submit_resume_wording_review",
                {"artifact_id": artifact, "approval_receipt": receipt},
            )
            self.assertEqual(result["status"], "ok", result)
            request = self.request(
                client,
                "RESUME_EXPORT",
                artifact,
                2,
                "MARKDOWN",
                key="synthetic_confirm_export_0001",
            )
            consent = self.confirm(browser, request["confirmation_path"])
            args = {"artifact_id": artifact, "format": "MARKDOWN", "approval_receipt": consent}
            self.assertEqual(
                self.call(client, "export_resume", {**args, "format": "JSON"})["status"], "error"
            )
            exported = self.call(client, "export_resume", args)
            self.assertEqual(exported["status"], "ok", exported)
            uri = exported["data"]["resource_uri"]
            self.assertEqual(exported["data"]["content_delivery"], "INLINE")
            listed = self.rpc(client, "resources/list", {}).json()["result"]["resources"]
            self.assertEqual([resource["uri"] for resource in listed], [uri])
            self.assertNotIn(PHRASE, str(listed))
            resource = self.rpc(client, "resources/read", {"uri": uri})
            self.assertEqual(resource.status_code, 200)
            self.assertEqual(
                exported["data"]["content"], resource.json()["result"]["contents"][0]["text"]
            )
            self.assertEqual(
                re.sub(r"\\(.)", r"\1", resource.json()["result"]["contents"][0]["text"]),
                "- " + PHRASE + "\n",
            )
            for identity in (
                {"client_id": "other-client"},
                {"subject": "user-b"},
                {"scopes": "career.profile.read"},
            ):
                denied = self.rpc(client, "resources/read", {"uri": uri}, **identity)
                self.assertIn("error", denied.json())
                self.assertNotIn(PHRASE, denied.text)
                listed = self.rpc(client, "resources/list", {}, **identity).json()
                self.assertEqual(listed["result"]["resources"], [])
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").status = "DELETING"
                session.commit()
            self.assertIn("error", self.rpc(client, "resources/read", {"uri": uri}).json())
            self.assertEqual(
                self.rpc(client, "resources/list", {}).json()["result"]["resources"], []
            )
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").status = "ACTIVE"
                row = session.get(BrowserOperation, request["request_id"])
                row.created_at = datetime.now(UTC) - timedelta(minutes=10)
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                session.commit()
            self.assertIn("error", self.rpc(client, "resources/read", {"uri": uri}).json())
            self.assertEqual(
                self.rpc(client, "resources/list", {}).json()["result"]["resources"], []
            )
            self.assertEqual(self.call(client, "export_resume", args)["status"], "error")
        with self.sessions() as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ArtifactWordingReview)), 1
            )

    def test_profile_export_is_explicit_canonical_only_and_private(self):
        with self.sessions() as session:
            ensure_profile_archive(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=0,
                now=datetime.now(UTC),
            )
            session.commit()
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            request = self.request(client, "PROFILE_EXPORT", "profile-a", 0, "JSON")
            uri = "careerground://exports/" + request["request_id"]
            self.assertIn("error", self.rpc(client, "resources/read", {"uri": uri}).json())
            self.assertEqual(
                self.rpc(client, "resources/list", {}).json()["result"]["resources"], []
            )
            consent = self.confirm(browser, request["confirmation_path"])
            self.assertEqual(
                self.rpc(client, "resources/list", {}).json()["result"]["resources"], []
            )
            exported = self.call(
                client,
                "export_profile_data",
                {
                    "profile_id": "profile-a",
                    "profile_version": 0,
                    "format": "JSON",
                    "approval_receipt": consent,
                },
            )
            self.assertEqual(exported["status"], "ok", exported)
            listed = self.rpc(client, "resources/list", {}).json()["result"]["resources"]
            self.assertEqual([resource["uri"] for resource in listed], [uri])
            body = self.rpc(client, "resources/read", {"uri": uri}).json()["result"]["contents"][0][
                "text"
            ]
            self.assertIsInstance(json.loads(body), dict)
            self.assertEqual(exported["data"]["content_delivery"], "INLINE")
            self.assertEqual(exported["data"]["content"], body)
            self.assertNotIn("approval_receipt", body)
            with patch("careerground.mcp.confirmation_tools.MAX_INLINE_EXPORT_BYTES", 1):
                resource_only = self.call(
                    client,
                    "export_profile_data",
                    {
                        "profile_id": "profile-a",
                        "profile_version": 0,
                        "format": "JSON",
                        "approval_receipt": consent,
                    },
                )["data"]
            self.assertEqual(resource_only["content_delivery"], "RESOURCE_ONLY")
            self.assertIsNone(resource_only["content"])
            self.assertEqual(resource_only["content_hash"], exported["data"]["content_hash"])
            self.assertEqual(
                self.call(
                    client,
                    "export_profile_data",
                    {
                        "profile_id": "profile-a",
                        "profile_version": 1,
                        "format": "JSON",
                        "approval_receipt": consent,
                    },
                )["status"],
                "error",
            )
            identity = ("client-a", "user-a", SCOPES)
            original = self.tokens[identity]
            renewed = jwt.decode(original, options={"verify_signature": False})
            renewed["jti"] = "another-access-token-for-the-same-client"
            self.tokens[identity] = jwt.encode(
                renewed, self.key, algorithm="RS256", headers={"kid": "synthetic-key"}
            )
            self.assertIn("error", self.rpc(client, "resources/read", {"uri": uri}).json())
            self.assertEqual(
                self.rpc(client, "resources/list", {}).json()["result"]["resources"], []
            )
            self.tokens[identity] = original

    def test_deletion_status_counts_without_internal_secrets_and_no_false_completion(self):
        with self.sessions() as session:
            session.add(
                DeletionRequest(
                    id="synthetic-erasure",
                    account_id="acct-a",
                    scope="PROFILE",
                    target_id="profile-a",
                    status="ERASED",
                    impact_digest="synthetic-private-digest",
                )
            )
            session.flush()
            session.add_all(
                [
                    DeletionWorkItem(
                        id="local-done",
                        request_id="synthetic-erasure",
                        kind="CAREER_PROFILE",
                        target_id="synthetic-private-target",
                        action="ERASE",
                        status="DONE",
                    ),
                    DeletionWorkItem(
                        id="external-pending",
                        request_id="synthetic-erasure",
                        kind="UNVERIFIED_SCOPE",
                        target_id="synthetic-private-target",
                        action="VERIFY",
                        status="PENDING",
                    ),
                ]
            )
            session.commit()
        with TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client:
            args = {"erasure_request_id": "synthetic-erasure"}
            result = self.call(client, "get_deletion_status", args)
            self.assertEqual(result["data"]["status"], "DELETING")
            self.assertEqual(result["data"]["unverified"], 1)
            self.assertNotIn("synthetic-private", json.dumps(result))
            self.assertEqual(
                self.call(client, "get_deletion_status", args, subject="user-b")["error"]["code"],
                "NOT_FOUND",
            )
            self.assertEqual(
                self.call(client, "get_deletion_status", args, scopes="career.profile.read")[
                    "error"
                ]["code"],
                "FORBIDDEN",
            )

    def test_inactive_account_cannot_poll_or_create_confirmations(self):
        with self.sessions() as session:
            session.get(Account, "acct-a").status = "DELETING"
            session.commit()
        with TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client:
            result = self.rpc(
                client,
                "tools/call",
                {
                    "name": "get_deletion_status",
                    "arguments": {"erasure_request_id": "synthetic-erasure"},
                },
            )
            self.assertEqual(result.status_code, 401)

    def test_concurrent_browser_approval_and_receipt_expiry_cleanup(self):
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            batch = self.review_batch(browser)
            request = self.request(client, "FACT_REVIEW", batch, 0)
            data = self.form(browser, request["confirmation_path"])

        def approve(_):
            with self.sessions() as session:
                row = self.service.confirm(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    operation_id=request["request_id"],
                    confirmation_token=data["confirmation_token"],
                    confirm_value="reviewed",
                    decisions=tuple(
                        (key.removeprefix("decision_"), value)
                        for key, value in data.items()
                        if key.startswith("decision_")
                    ),
                    now=datetime.now(UTC),
                )
                receipt = self.service.receipt(row)
                session.commit()
                return receipt

        with ThreadPoolExecutor(max_workers=4) as workers:
            receipts = tuple(workers.map(approve, range(4)))
        self.assertEqual(len(set(receipts)), 1)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileChangeSet)), 1)
            self.assertEqual(prune_browser_operations(session, now=datetime.now(UTC)), 0)
            self.assertEqual(
                prune_browser_operations(session, now=datetime.now(UTC) + timedelta(minutes=10)), 1
            )
            session.commit()

    def test_stale_tampered_and_expired_confirmation_changes_no_canonical_data(self):
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            batch = self.review_batch(browser)
            request = self.request(client, "FACT_REVIEW", batch, 0)
            data = self.form(browser, request["confirmation_path"])
            self.assertEqual(
                browser.post(
                    request["confirmation_path"],
                    data={**data, "confirmation_token": data["confirmation_token"] + "x"},
                ).status_code,
                409,
            )
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 1
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=data).status_code, 409)
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 0
                row = session.get(BrowserOperation, request["request_id"])
                row.created_at = datetime.now(UTC) - timedelta(minutes=10)
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=data).status_code, 409)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)

    def test_idle_schedule_expires_confirmation_and_quota_without_api_requests(self):
        with (
            TestClient(self.web) as browser,
            TestClient(self.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            batch = self.review_batch(browser)
            request = self.request(client, "FACT_REVIEW", batch, 0)
        waits = []
        results = run_local_security_maintenance(
            self.sessions,
            cycles=2,
            interval_seconds=1,
            clock=lambda: time.time() + 600,
            sleep=waits.append,
        )
        self.assertEqual(waits, [1])
        self.assertEqual(results[0]["deleted_operations"], 1)
        self.assertGreater(results[0]["deleted_buckets"], 0)
        self.assertEqual(results[1], {"deleted_buckets": 0, "deleted_operations": 0})
        with self.sessions() as session:
            self.assertIsNone(session.get(BrowserOperation, request["request_id"]))
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)


class PostgreSQLBrowserConfirmationTests(BrowserMCPConfirmationTests):
    def prepare_database(self):
        raw = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("required local PostgreSQL URL is absent")
            self.skipTest("local test PostgreSQL URL is not configured")
        url = make_url(raw)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"localhost", "127.0.0.1"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing a non-local or non-test database")
        self.engine = create_engine(url, hide_parameters=True)
        self.addCleanup(self.engine.dispose)
        # The concurrency case needs independent connections; only these known
        # synthetic fixture accounts are created and cleaned in this empty DB.
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            if session.scalar(select(Account.id).where(Account.id.in_(["acct-a", "acct-b"]))):
                self.fail(
                    "synthetic fixture IDs already exist; refusing to overwrite or clean them"
                )
        self.addCleanup(self.clean_synthetic_rows)

    def clean_synthetic_rows(self):
        with self.engine.begin() as connection:
            for account in ("acct-a", "acct-b"):
                for lane in ("read", "write"):
                    key = hmac.new(
                        SECRET, f"request-quota-v1:{lane}:{account}".encode(), hashlib.sha256
                    ).hexdigest()
                    connection.execute(
                        RequestLimitBucket.__table__.delete().where(
                            RequestLimitBucket.bucket_key == key
                        )
                    )
            connection.execute(
                DeletionWorkItem.__table__.delete().where(
                    DeletionWorkItem.request_id.in_(
                        select(DeletionRequest.id).where(
                            DeletionRequest.account_id.in_(["acct-a", "acct-b"])
                        )
                    )
                )
            )
            for table in reversed(Base.metadata.sorted_tables):
                if "account_id" in table.c:
                    connection.execute(
                        table.delete().where(table.c.account_id.in_(["acct-a", "acct-b"]))
                    )
            connection.execute(
                Account.__table__.delete().where(Account.id.in_(["acct-a", "acct-b"]))
            )


if __name__ == "__main__":
    unittest.main()

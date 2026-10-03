"""Synthetic first-use, source-bound MCP, and browser handoff security checks."""

from __future__ import annotations

import logging
import re
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import AuthenticationRequired, VerifiedIdentity
from careerground.mcp.management_navigation import validate_management_origin
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.storage.graph_models import Claim
from careerground.storage.models import (
    Account,
    AuthIdentity,
    CareerProfile,
    ProfilingDraft,
    ProfilingSession,
)
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app
from tests import test_mcp_product_foundation as foundation


class ChatGPTJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        foundation.ProductFoundationTests.setUpClass()

    def setUp(self):
        self.fixture = foundation.ProductFoundationTests()
        self.fixture.setUp()
        self.sessions = self.fixture.sessions
        self.admission_id = str(uuid4())
        self.admissions = {"new-user": self.admission_id}
        self.scope = "career.profile.read career.profile.write career.export"
        self.tokens = {}
        self.app = build_product_foundation_app(
            McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=foundation.REVIEW_SECRET,
            signing_key=lambda _token: self.fixture.private_key.public_key(),
            enrollment_account_id=lambda identity: self.admissions.get(identity.subject),
            management_origin="https://manage.synthetic.example/",
        )

    def tearDown(self):
        self.fixture.tearDown()

    def call(self, client, name, arguments, *, sub="user-a", scope=None, token=None):
        cache_key = (sub, scope or self.scope)
        if cache_key not in self.tokens:
            self.tokens[cache_key] = self.fixture.token(sub=sub, scope=cache_key[1])
        response = self.fixture.call(
            client,
            token=token or self.tokens[cache_key],
            name=name,
            arguments=arguments,
        )
        if response.status_code != 200:
            return {"http_status": response.status_code}
        return response.json()["result"]["structuredContent"]

    def client(self, app=None):
        return TestClient(app or self.app, base_url="https://product-mcp.synthetic.example")

    def seed_input(
        self,
        client,
        *,
        text="합성 API를 구현했습니다.\n합성 테스트를 작성했습니다.",
        kind="USER_STATEMENT",
        work=None,
    ):
        if work is None:
            result = self.call(
                client,
                "start_profiling",
                {
                    "profile_id": "profile-a",
                    "goal": "ADD_EXPERIENCE",
                    "policy_version": "product-policy-v0.1",
                    "idempotency_key": "hybrid_start_key_0001",
                },
            )
            work = result["data"]["profiling_session_id"]
        result = self.call(
            client,
            "add_profiling_input",
            {
                "profiling_session_id": work,
                "base_profile_version": 3,
                "content": text,
                "content_kind": kind,
                "idempotency_key": "hybrid_input_" + str(uuid4()),
            },
        )
        return {
            "profiling_session_id": work,
            "source_input_id": result["data"]["input_id"],
            "base_profile_version": 3,
            "experience_scope_id": "hybrid-project",
            "spans": [{"start": 0, "end": len(text.splitlines()[0])}],
        }

    def count(self, model):
        with self.sessions() as session:
            return session.scalar(select(func.count()).select_from(model))

    def test_discover_profile_without_user_supplied_identifiers(self):
        with self.client() as client:
            result = self.call(client, "get_my_profile", {})
            self.assertEqual(
                result["data"],
                {
                    "found": True,
                    "profile_id": "profile-a",
                    "version": 3,
                    "pending_profiling_sessions": [],
                },
            )
            self.assertEqual(
                self.call(client, "get_my_profile", {"profile_id": "profile-b"})["error"]["code"],
                "VALIDATION_FAILED",
            )

    def test_discovery_recovers_only_owned_current_live_pending_work(self):
        with self.client() as client:
            args = self.seed_input(client)
            self.assertEqual(self.call(client, "propose_profiling_drafts", args)["status"], "ok")
            found = self.call(client, "get_my_profile", {})["data"]
            self.assertEqual(
                found["pending_profiling_sessions"],
                [
                    {
                        "profiling_session_id": args["profiling_session_id"],
                        "base_profile_version": 3,
                        "experience_scope_ids": ["hybrid-project"],
                    }
                ],
            )
            self.assertNotIn("합성 API", str(found))
            self.assertEqual(
                self.call(client, "get_my_profile", {}, sub="user-b")["data"][
                    "pending_profiling_sessions"
                ],
                [],
            )
            with self.sessions() as session:
                work = session.get(ProfilingSession, args["profiling_session_id"])
                work.status = "PAUSED"
                session.commit()
            self.assertEqual(
                self.call(client, "get_my_profile", {})["data"]["pending_profiling_sessions"], []
            )
            with self.sessions() as session:
                work = session.get(ProfilingSession, args["profiling_session_id"])
                work.status = "ACTIVE"
                work.last_activity_at = datetime.now(UTC) - timedelta(days=2)
                work.retention_expires_at = datetime.now(UTC) - timedelta(days=1)
                session.commit()
            self.assertEqual(
                self.call(client, "get_my_profile", {})["data"]["pending_profiling_sessions"], []
            )

    def test_first_use_is_explicit_admitted_and_replay_safe(self):
        before = self.count(Account)
        with self.client() as client:
            self.assertEqual(
                self.call(client, "get_my_profile", {}, sub="new-user")["error"]["code"],
                "NOT_FOUND",
            )
            self.assertEqual(self.count(Account), before)
            args = {"policy_version": "product-policy-v0.1"}
            first = self.call(client, "initialize_career_profile", args, sub="new-user")
            second = self.call(client, "initialize_career_profile", args, sub="new-user")
            self.assertEqual(first, second)
            self.assertEqual(first["data"]["version"], 0)
            discovered = self.call(client, "get_my_profile", {}, sub="new-user")
            self.assertEqual(discovered["data"]["profile_id"], first["data"]["profile_id"])
            empty = self.call(
                client,
                "get_career_profile",
                {"profile_id": first["data"]["profile_id"], "profile_version": "CURRENT"},
                sub="new-user",
            )
            self.assertEqual(empty["status"], "ok")
            self.assertEqual(empty["data"]["claims"], [])
        self.assertEqual(self.count(Account), before + 1)
        self.assertEqual(self.count(AuthIdentity), 3)
        self.assertEqual(self.count(Claim), 0)

    def test_unknown_and_missing_scope_do_not_provision(self):
        with self.client() as client:
            for sub, scope in [
                ("unadmitted-user", self.scope),
                ("new-user", "career.profile.read"),
            ]:
                self.assertEqual(
                    self.call(
                        client,
                        "initialize_career_profile",
                        {"policy_version": "product-policy-v0.1"},
                        sub=sub,
                        scope=scope,
                    )["http_status"],
                    401,
                )
        self.assertEqual(self.count(Account), 2)

    def test_policy_and_identity_injection_rejected_without_writes(self):
        with self.client() as client:
            for args in [
                {"policy_version": "other"},
                {"policy_version": "product-policy-v0.1", "subject": "user-b"},
            ]:
                result = self.call(client, "initialize_career_profile", args, sub="new-user")
                self.assertEqual(result["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(self.count(Account), 2)

    def test_erased_admission_with_removed_identity_cannot_reenroll(self):
        with self.client() as client:
            self.call(
                client,
                "initialize_career_profile",
                {"policy_version": "product-policy-v0.1"},
                sub="new-user",
            )
            with self.sessions() as session:
                session.get(Account, self.admission_id).status = "ERASED"
                session.execute(
                    delete(AuthIdentity).where(AuthIdentity.account_id == self.admission_id)
                )
                session.commit()
            result = self.call(
                client,
                "initialize_career_profile",
                {"policy_version": "product-policy-v0.1"},
                sub="new-user",
            )
            self.assertEqual(result["http_status"], 401)
        self.assertEqual(self.count(Account), 3)
        self.assertEqual(self.count(AuthIdentity), 2)

    def test_existing_blocked_account_or_profile_is_not_repaired(self):
        for model, target in [(Account, "acct-a"), (CareerProfile, "profile-a")]:
            with self.subTest(model=model):
                with self.sessions() as session:
                    row = session.get(model, target)
                    row.status = "DELETING"
                    session.commit()
                with self.sessions() as session, self.assertRaises(AuthenticationRequired):
                    initialize_account_profile(
                        session,
                        identity=VerifiedIdentity(foundation.ISSUER, "user-a"),
                        enrollment_account_id=str(uuid4()),
                    )
                with self.sessions() as session:
                    session.get(model, target).status = "ACTIVE"
                    session.commit()
        self.assertEqual(self.count(Account), 2)

    def test_exact_unicode_drafts_replay_and_no_canonical_approval(self):
        with self.client() as client:
            text = "합성 🚀 API를 구현했습니다.\n합성 테스트를 작성했습니다."
            args = self.seed_input(client, text=text)
            first_end = len(text.splitlines()[0])
            args["spans"].append({"start": first_end + 1, "end": len(text)})
            first = self.call(client, "propose_profiling_drafts", args)
            second = self.call(client, "propose_profiling_drafts", args)
            self.assertEqual(first, second)
            self.assertEqual([d["exact_text"] for d in first["data"]["drafts"]], text.splitlines())
            self.assertFalse(first["data"]["canonical_saved"])
            self.assertTrue(first["data"]["review_required"])
            self.assertEqual(first["data"]["atomicity"], "UNVERIFIED")
        self.assertEqual(self.count(ProfilingDraft), 2)
        self.assertEqual(self.count(Claim), 0)

    def test_invalid_span_shapes_and_authority_injection_are_atomic(self):
        with self.client() as client:
            base = self.seed_input(client)
            for spans in [
                [],
                [{"start": True, "end": 3}],
                [{"start": "0", "end": 3}],
                [{"start": 0, "end": 3, "approved": True}],
                [{"start": 0, "end": 999}],
                [{"start": 0, "end": 10}, {"start": 5, "end": 12}],
                [{"start": 0, "end": -1}],
                [{"start": 0, "end": 3}] * 6,
                [{"start": 0, "end": 30}],
            ]:
                with self.subTest(spans=spans):
                    result = self.call(client, "propose_profiling_drafts", {**base, "spans": spans})
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(self.count(ProfilingDraft), 0)
            self.assertEqual(
                self.call(client, "propose_profiling_drafts", {**base, "claim_type": "OUTCOME"})[
                    "error"
                ]["code"],
                "VALIDATION_FAILED",
            )

    def test_owner_scope_version_and_changed_proposal_rejected(self):
        with self.client() as client:
            args = self.seed_input(client)
            self.assertEqual(
                self.call(client, "propose_profiling_drafts", args, sub="user-b")["error"]["code"],
                "NOT_FOUND",
            )
            self.assertEqual(
                self.call(client, "propose_profiling_drafts", {**args, "base_profile_version": 2})[
                    "error"
                ]["code"],
                "VERSION_CONFLICT",
            )
            self.assertEqual(
                self.call(client, "propose_profiling_drafts", args, scope="career.profile.read")[
                    "error"
                ]["code"],
                "FORBIDDEN",
            )
            self.call(client, "propose_profiling_drafts", args)
            self.assertEqual(
                self.call(
                    client, "propose_profiling_drafts", {**args, "spans": [{"start": 0, "end": 3}]}
                )["error"]["code"],
                "VALIDATION_FAILED",
            )
        self.assertEqual(self.count(ProfilingDraft), 1)

    def test_correction_invalidates_old_source_and_uses_new_verbatim_input(self):
        with self.client() as client:
            old = self.seed_input(client)
            self.call(client, "propose_profiling_drafts", old)
            new = self.seed_input(
                client,
                text="합성 팀과 함께 API를 구현했습니다.",
                kind="CORRECTION",
                work=old["profiling_session_id"],
            )
            self.assertEqual(self.call(client, "propose_profiling_drafts", old)["status"], "error")
            result = self.call(client, "propose_profiling_drafts", new)
            self.assertEqual(
                result["data"]["drafts"][0]["exact_text"], "합성 팀과 함께 API를 구현했습니다."
            )
        self.assertEqual(self.count(Claim), 0)

    def test_browser_approval_status_and_exact_originating_connection(self):
        with self.client() as client:
            args = self.seed_input(client)
            self.call(client, "propose_profiling_drafts", args)
            review = self.call(
                client,
                "prepare_claim_review",
                {
                    "profiling_session_id": args["profiling_session_id"],
                    "experience_scope_id": "hybrid-project",
                    "base_profile_version": 3,
                    "idempotency_key": "hybrid_review_key_0001",
                },
            )["data"]
            request = self.call(
                client,
                "request_user_confirmation",
                {
                    "action": "FACT_REVIEW",
                    "target_id": review["review_batch_id"],
                    "profile_version": 3,
                    "format": "NONE",
                    "idempotency_key": "hybrid_confirm_key_0001",
                },
            )["data"]
            self.assertEqual(
                request["confirmation_url"],
                "https://manage.synthetic.example" + request["confirmation_path"],
            )
            status_args = {"request_id": request["request_id"]}
            waiting = self.call(client, "get_confirmation_status", status_args)["data"]
            self.assertEqual(waiting["status"], "WAITING")
            self.assertIsNone(waiting["approval_receipt"])
            for sub, token in [
                ("user-b", None),
                ("user-a", self.fixture.token(scope=self.scope, azp="other-connection")),
            ]:
                result = self.call(
                    client, "get_confirmation_status", status_args, sub=sub, token=token
                )
                self.assertEqual(result["status"], "error")
            web = build_synthetic_review_app(
                session_factory=self.sessions,
                authenticate_browser=lambda _req, _res: TrustedBrowserIdentity(
                    "acct-a", "hybrid-browser-session-0001"
                ),
                review_signing_secret=foundation.REVIEW_SECRET,
                presentation_signing_secret=foundation.REVIEW_SECRET,
            )
            with TestClient(web) as browser:
                page = browser.get(request["confirmation_path"])
                self.assertEqual(page.status_code, 200)
                token = re.search("name='confirmation_token' value='([^']+)'", page.text).group(1)
                item = review["items"][0]["review_item_id"]
                response = browser.post(
                    request["confirmation_path"],
                    data={
                        "confirmation_token": token,
                        "confirm": "reviewed",
                        "allow_connection": "yes",
                        "decision_" + item: "ACCEPT",
                    },
                    headers={"origin": "http://testserver"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn("직접 복사할 필요", response.text)
            done = self.call(client, "get_confirmation_status", status_args)["data"]
            self.assertTrue(done["completed_in_browser"])
            receipt = done["approval_receipt"]
            self.assertIsNotNone(receipt)
            self.assertEqual(
                self.call(
                    client, "get_confirmation_status", status_args, scope="career.profile.read"
                )["error"]["code"],
                "NOT_FOUND",
            )
            submitted = self.call(
                client,
                "submit_claim_review",
                {"review_batch_id": review["review_batch_id"], "approval_receipt": receipt},
            )
            self.assertEqual(submitted["status"], "ok")
            self.assertEqual(
                self.call(client, "get_confirmation_status", status_args)["data"]["status"],
                "CONSUMED",
            )
        self.assertEqual(self.count(Claim), 1)


class ManagementOriginTests(unittest.TestCase):
    def test_only_configured_https_or_loopback_origins_are_accepted(self):
        for value in [
            "https://manage.synthetic.example/",
            "http://127.0.0.1:8008",
            "http://[::1]:8008",
        ]:
            self.assertEqual(validate_management_origin(value), value.rstrip("/"))
        for value in [
            "http://remote.example",
            "https://u:p@host.example",
            "https://host.example/path",
            "https://host.example?next=elsewhere",
            "https://host.example#other",
            "//host.example",
            "https://host.example:99999",
            "https://host.example\\other",
            "https://host.example\n",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_management_origin(value)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main()

"""Exact local HTTP/MCP CURRENT, export options and separate R2 approvals."""

import json
import re
import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from careerground.domain.profile_archive import ensure_profile_archive
from careerground.storage.jd_artifact_models import Artifact
from careerground.storage.models import CareerProfile, ProfilingDraft, ProjectScope
from tests import test_browser_mcp_confirmation as fixtures

RESOURCE = fixtures.RESOURCE


class ContractCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.BrowserMCPConfirmationTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.BrowserMCPConfirmationTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_current_freezes_options_same_connection_and_exact_retry(self):
        f = self.fixture
        choices = {
            "claims": False,
            "evidence": False,
            "boundaries": False,
            "drafts": False,
            "unavailable_references": False,
        }
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            f.fact(browser, client)
            args = {
                "action": "PROFILE_EXPORT",
                "target_id": "profile-a",
                "profile_version": "CURRENT",
                "format": "JSON",
                "idempotency_key": "current_export_options_0001",
                "inclusion": choices,
            }
            requested = f.call(client, "request_user_confirmation", args)
            self.assertEqual(requested["status"], "ok", requested)
            request = requested["data"]
            page = browser.get(request["confirmation_path"])
            self.assertEqual(page.status_code, 200, page.text)
            self.assertIn("버전 1", page.text)
            receipt = f.confirm(browser, request["confirmation_path"])
            export_args = {
                "profile_id": "profile-a",
                "profile_version": "CURRENT",
                "format": "JSON",
                "approval_receipt": receipt,
                "inclusion": choices,
            }
            wrong = f.call(
                client,
                "export_profile_data",
                {**export_args, "inclusion": {**choices, "claims": True}},
            )
            self.assertNotEqual(wrong["status"], "ok", wrong)
            foreign = f.call(client, "export_profile_data", export_args, client_id="client-b")
            self.assertNotEqual(foreign["status"], "ok", foreign)
            exported = f.call(client, "export_profile_data", export_args)
            self.assertEqual(exported["status"], "ok", exported)
            self.assertEqual(exported["data"]["profile_version"], 1)
            self.assertEqual(exported["data"]["inclusion"], choices)
            resource = f.rpc(
                client, "resources/read", {"uri": exported["data"]["resource_uri"]}
            ).json()
            body = json.loads(resource["result"]["contents"][0]["text"])
            self.assertEqual(body["claims"], [])
            self.assertEqual(body["active_boundaries"], [])
            self.assertEqual(body["inclusion"], choices)
            with f.sessions() as session:
                profile = session.get(CareerProfile, "profile-a")
                profile.version = 2
                session.flush()
                ensure_profile_archive(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=2,
                    now=datetime.now(UTC),
                )
                session.commit()
            retry = f.call(client, "request_user_confirmation", args)
            self.assertEqual(retry["data"]["request_id"], requested["data"]["request_id"])
            self.assertEqual(retry["data"]["status"], "CONSUMED")
            self.assertEqual(f.call(client, "export_profile_data", export_args), exported)
            changed = f.call(
                client,
                "request_user_confirmation",
                {**args, "inclusion": {**choices, "claims": True}},
            )
            self.assertNotEqual(changed["status"], "ok", changed)
            current = f.call(
                client,
                "get_career_profile",
                {"profile_id": "profile-a", "profile_version": "CURRENT"},
            )
            self.assertEqual(current["data"]["profile_version"], 2)

    def test_live_drafts_are_unapproved_and_expiry_invalidates_exact_export(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            f.fact(browser, client)
            f.review_batch(browser)
            choices = {
                "claims": True,
                "evidence": True,
                "boundaries": True,
                "drafts": True,
                "unavailable_references": True,
            }
            args = {
                "action": "PROFILE_EXPORT",
                "target_id": "profile-a",
                "profile_version": "CURRENT",
                "format": "JSON",
                "idempotency_key": "live_draft_export_0001",
                "inclusion": choices,
            }
            requested = f.call(client, "request_user_confirmation", args)
            self.assertEqual(requested["status"], "ok", requested)
            receipt = f.confirm(browser, requested["data"]["confirmation_path"])
            exported = f.call(
                client,
                "export_profile_data",
                {
                    "profile_id": "profile-a",
                    "profile_version": "CURRENT",
                    "format": "JSON",
                    "approval_receipt": receipt,
                    "inclusion": choices,
                },
            )
            self.assertEqual(exported["status"], "ok", exported)
            uri = exported["data"]["resource_uri"]
            resource = f.rpc(client, "resources/read", {"uri": uri}).json()
            body = json.loads(resource["result"]["contents"][0]["text"])
            self.assertTrue(body["temporary_drafts"])
            self.assertTrue(
                all(row["fact_review"] == "UNAPPROVED" for row in body["temporary_drafts"])
            )
            with f.sessions() as session:
                for draft in session.scalars(
                    select(ProfilingDraft).where(ProfilingDraft.status == "IN_REVIEW")
                ):
                    draft.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                session.commit()
            denied = f.rpc(client, "resources/read", {"uri": uri}).json()
            self.assertIn("error", denied)

    def test_current_changed_before_confirmation_rejects(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            f.fact(browser, client)
            request = f.request(
                client,
                "PROFILE_EXPORT",
                "profile-a",
                "CURRENT",
                format="JSON",
                key="current_before_change_0001",
            )
            data = f.form(browser, request["confirmation_path"])
            with f.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 2
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=data).status_code, 409)

    def test_browser_r2_exact_new_artifact_and_r3_does_not_write(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            artifact = f.artifact(browser, client)
            path = f"/resume/{artifact}/r2"
            page = browser.get(path)
            self.assertEqual(page.status_code, 200, page.text)
            fields = dict(re.findall(r"name='([^']+)' value='([^']*)'", page.text))
            fields.update(
                proposed_text_0="합성 기능의 테스트를 작성했습니다.", fact_review_0="NO_NEW_FACTS"
            )
            exact = browser.post(path + "/prepare", data=fields)
            self.assertEqual(exact.status_code, 200, exact.text)
            with f.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 1)
            approve = {
                "approval_token": f.hidden(exact.text, "approval_token"),
                "confirm": "approve_r2",
            }
            browser.cookies.set("cg_session", "other-session")
            self.assertEqual(browser.post(path + "/approve", data=approve).status_code, 409)
            browser.cookies.set("cg_session", "owner")
            response = browser.post(path + "/approve", data=approve, follow_redirects=False)
            self.assertEqual(response.status_code, 303, response.text)
            r2 = response.headers["location"].split("/")[2]
            self.assertNotEqual(r2, artifact)
            export = browser.get(f"/resume/{r2}/export/JSON")
            self.assertEqual(export.status_code, 200, export.text)
            downloaded = browser.post(
                f"/resume/{r2}/export/JSON",
                data={"export_token": f.hidden(export.text, "export_token"), "confirm": "download"},
            )
            self.assertEqual(downloaded.status_code, 200, downloaded.text)
            body = json.loads(downloaded.content)
            self.assertIn("작성했습니다", json.dumps(body, ensure_ascii=False))
            page = browser.get(path)
            fields = dict(re.findall(r"name='([^']+)' value='([^']*)'", page.text))
            fields.update(
                proposed_text_0="새 프로젝트에서 팀 전체를 이끌었다.",
                fact_review_0="R3_NEEDS_FACT_REVIEW",
            )
            rejected = browser.post(path + "/prepare", data=fields)
            self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertIn("/profiling/start", rejected.text)
            with f.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 2)
                self.assertEqual(session.get(Artifact, r2).source_artifact_id, artifact)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)

    def test_project_registration_requires_owned_known_scope(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            f.fact(browser, client)
            path = "/profile/profile-a/projects"
            page = browser.get(path)
            self.assertEqual(page.status_code, 200, page.text)
            token = f.hidden(page.text, "registration_token")
            bad = browser.post(
                path,
                data={
                    "registration_token": token,
                    "scope_key": "unknown",
                    "confirm": "register_project",
                },
            )
            self.assertIn(bad.status_code, (400, 409))
            good = browser.post(
                path,
                data={
                    "registration_token": token,
                    "scope_key": "synthetic-feature",
                    "confirm": "register_project",
                },
                follow_redirects=False,
            )
            self.assertEqual(good.status_code, 303, good.text)
            with f.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(ProjectScope)), 1)
            browser.cookies.set("cg_session", "foreign")
            self.assertEqual(browser.get(path).status_code, 404)

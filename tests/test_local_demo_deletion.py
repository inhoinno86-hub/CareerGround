"""Local deletion needs separate impact, mock reauthentication and final consent."""

import unittest

from sqlalchemy import func, select

import tests.test_local_demo as fixture
from careerground.local_demo import ACCOUNTS, COOKIE
from careerground.storage.jd_artifact_models import JobDescription
from careerground.storage.models import Account, AuthIdentity, CareerProfile, DeletionRequest


class LocalDemoDeletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.LocalDemoTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.choose()
        self.client = self.fixture.client
        self.demo = self.fixture.demo

    def preview(self, scope="ACCOUNT"):
        page = self.client.get("/demo/deletion")
        result = self.client.post(
            "/demo/deletion/preview",
            data={"form_token": self.fixture.hidden(page.text, "form_token"), "scope": scope},
        )
        self.assertEqual(result.status_code, 200, result.text)
        return self.fixture.hidden(result.text, "preview_token")

    def reauth(self, token):
        return self.client.post(
            "/demo/deletion/reauth",
            data={
                "preview_token": token,
                "acknowledged_impact": "yes",
                "mock_reauthenticated": "yes",
                "mock_phrase": "합성 계정 A",
            },
        )

    def execute(self, token):
        return self.client.post(
            "/demo/deletion/execute",
            data={"step_up_token": token, "confirm": "erase_local"},
            follow_redirects=False,
        )

    def test_account_erasure_idempotent_status_private_and_other_account_preserved(self):
        self.fixture.post_form(
            "/jd/new", "paste_token", "store_excerpts", selected_text="- 삭제할 합성 요구"
        )
        self.fixture.call("get_account_profile", {})
        preview = self.preview()
        with self.demo.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 0)
        page = self.reauth(preview)
        self.assertEqual(page.status_code, 200, page.text)
        token = self.fixture.hidden(page.text, "step_up_token")
        for _ in range(2):
            result = self.execute(token)
            self.assertEqual(result.status_code, 303, result.text)
            self.assertEqual(result.headers["location"], "/demo/deletion/status")
        status = self.client.get("/demo/deletion/status")
        self.assertEqual(status.status_code, 200, status.text)
        self.assertIn("FOUNDATION_ONLY", status.text)
        self.assertIn("DELETING", status.text)
        self.assertNotIn("ERASED", status.text)
        state = self.demo.browsers[self.client.cookies.get(COOKIE)]
        self.assertNotIn(state["deletion_capability"], status.text)
        self.assertNotIn("삭제할 합성 요구", status.text)
        self.assertEqual(self.client.get("/profiling/start").status_code, 401)
        with self.demo.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(JobDescription)), 0)
            self.assertIsNone(
                session.scalar(
                    select(AuthIdentity).where(AuthIdentity.account_id == ACCOUNTS["a"][0])
                )
            )
            self.assertEqual(session.get(Account, ACCOUNTS["b"][0]).status, "ACTIVE")
        # Even a previously minted MCP token cannot regain account access.
        status_code, _ = self.client.portal.call(
            self.demo.rpc, state, "tools/call", {"name": "get_account_profile", "arguments": {}}
        )
        self.assertEqual(status_code, 401)
        self.fixture.choose("b")
        self.assertEqual(self.client.get("/demo/deletion/status").status_code, 404)
        self.assertEqual(self.client.get("/profiling/start").status_code, 200)

    def test_profile_erasure_keeps_account_active_but_profile_unavailable(self):
        page = self.reauth(self.preview("PROFILE"))
        result = self.execute(self.fixture.hidden(page.text, "step_up_token"))
        self.assertEqual(result.status_code, 303, result.text)
        self.assertEqual(self.client.get("/demo/deletion/status").status_code, 200)
        with self.demo.sessions() as session:
            self.assertEqual(session.get(Account, ACCOUNTS["a"][0]).status, "ACTIVE")
            self.assertEqual(session.get(CareerProfile, ACCOUNTS["a"][1]).status, "DELETING")
        self.assertEqual(self.client.get("/jd/new").status_code, 404)

    def test_body_markers_missing_stepup_tampering_or_new_session_cannot_delete(self):
        preview = self.preview()
        self.assertEqual(self.execute(preview).status_code, 409)
        fields = {
            "preview_token": preview,
            "acknowledged_impact": "yes",
            "mock_reauthenticated": "yes",
            "mock_phrase": "합성 계정 A",
        }
        for changed in (
            {"mock_phrase": "actual-password-never-echo"},
            {"mock_reauthenticated": "no"},
            {"acknowledged_impact": "no"},
            {"VerifiedDeletionApproval": "true"},
        ):
            result = self.client.post("/demo/deletion/reauth", data=fields | changed)
            self.assertIn(result.status_code, (400, 409))
            self.assertNotIn("actual-password-never-echo", result.text)
        page = self.reauth(preview)
        token = self.fixture.hidden(page.text, "step_up_token")
        self.assertEqual(self.execute(token + "tampered").status_code, 409)
        self.fixture.choose("a")
        self.assertEqual(self.execute(token).status_code, 409)
        with self.demo.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 0)

    def test_new_data_after_preview_prevents_execution_without_erasing_it(self):
        page = self.reauth(self.preview())
        token = self.fixture.hidden(page.text, "step_up_token")
        self.fixture.post_form(
            "/jd/new", "paste_token", "store_excerpts", selected_text="- 후속 합성 요구"
        )
        self.assertEqual(self.execute(token).status_code, 409)
        with self.demo.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(DeletionRequest)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(JobDescription)), 1)

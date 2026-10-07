"""Actual local Web/MCP composite and disposable auth/data lifecycle."""

from __future__ import annotations

import json
import re
import unittest
from html import unescape
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from careerground.local_demo import ACCOUNTS, COOKIE, LocalDemo
from careerground.storage.graph_models import Claim
from careerground.storage.models import CareerProfile


class LocalDemoTests(unittest.TestCase):
    def setUp(self):
        self.demo = LocalDemo()
        self.addCleanup(self.demo.close)
        self.client = TestClient(self.demo, base_url=self.demo.origin, client=("127.0.0.1", 40000))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def hidden(self, text, name):
        match = re.search(rf"name='{name}' value='([^']*)'", text)
        self.assertIsNotNone(match, name)
        return unescape(match.group(1))

    def choose(self, label="a"):
        page = self.client.get("/demo")
        result = self.client.post(
            "/demo/account",
            data={"form_token": self.hidden(page.text, "form_token"), "account": label},
        )
        self.assertEqual(result.status_code, 200, result.text)

    def post_form(self, path, token, confirm, **fields):
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        result = self.client.post(
            path,
            data={token: self.hidden(page.text, token), "confirm": confirm, **fields},
            follow_redirects=False,
        )
        self.assertEqual(result.status_code, 303, result.text)
        return result.headers["location"]

    def call(self, tool, arguments):
        page = self.client.get("/demo/mcp")
        result = self.client.post(
            "/demo/mcp",
            data={
                "form_token": self.hidden(page.text, "form_token"),
                "tool": tool,
                "arguments": json.dumps(arguments),
            },
        )
        self.assertEqual(result.status_code, 200, result.text)
        match = re.search(r"<pre id='mcp-result'>(.*?)</pre>", result.text, re.DOTALL)
        self.assertIsNotNone(match)
        return json.loads(unescape(match.group(1)))

    def test_isolated_accounts_require_selection_and_runtime_environment_is_not_used(self):
        self.assertEqual(self.client.get("/profiling/start").status_code, 401)
        self.assertEqual(self.client.post("/mcp", json={}).status_code, 401)
        with (
            patch.dict(
                "os.environ",
                {
                    "CAREERGROUND_DATABASE_URL": "postgresql+psycopg://invalid-production.example/live",
                    "AUTH0_DOMAIN": "real-provider.example",
                },
            ),
            LocalDemo(8009) as isolated,
        ):
            self.assertTrue(isolated.database_path.is_file())
            self.assertNotEqual(isolated.database_path, self.demo.database_path)
        self.choose()
        first = self.client.cookies.get(COOKIE)
        result = self.call("get_account_profile", {})
        self.assertEqual(result["result"]["structuredContent"]["data"]["id"], ACCOUNTS["a"][0])
        self.choose("b")
        self.assertNotIn(first, self.demo.browsers)
        result = self.call("get_owned_profile_metadata", {"profile_id": ACCOUNTS["a"][1]})
        self.assertEqual(result["result"]["structuredContent"]["error"]["code"], "NOT_FOUND")
        self.assertEqual(Path(self.demo.folder.name).stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.demo.database_path.stat().st_mode & 0o777, 0o600)

    def test_loopback_host_origin_and_extra_field_boundaries(self):
        for headers in (
            {"Host": "attacker.example"},
            {"Origin": "https://attacker.example"},
            {"Origin": "null"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            self.assertEqual(self.client.get("/demo", headers=headers).status_code, 403)
        foreign = TestClient(self.demo, base_url=self.demo.origin, client=("192.0.2.1", 123))
        try:
            self.assertEqual(foreign.get("/demo").status_code, 403)
        finally:
            foreign.close()
        self.assertEqual(
            self.client.get(
                "/demo", headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/demo", headers={"Origin": "null", "Sec-Fetch-Site": "cross-site"}
            ).status_code,
            403,
        )
        page = self.client.get("/demo")
        token = self.hidden(page.text, "form_token")
        self.assertEqual(
            self.client.post(
                "/demo/account", data={"form_token": token, "account": "a", "user_id": "other"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/demo/account", data={"form_token": token + "tampered", "account": "a"}
            ).status_code,
            409,
        )

    def test_empty_profile_through_local_mcp_browser_fact_jd_and_reviewed_r1(self):
        self.choose()
        phrase = "합성 기능의 테스트를 작성했다."
        work = self.post_form("/profiling/start", "start_token", "start")
        bullets = self.post_form(work + "/input", "input_token", "submit", content="- " + phrase)
        draft = self.post_form(bullets, "bullet_token", "draft", scope_key="local-feature")
        prepare = re.search(r"href='([^']+/prepare)'", self.client.get(draft).text).group(1)
        review = self.post_form(prepare, "prepare_token", "prepare")
        request = self.call(
            "request_user_confirmation",
            {
                "action": "FACT_REVIEW",
                "target_id": review.split("/")[-1],
                "profile_version": 0,
                "format": "NONE",
                "idempotency_key": "local_demo_fact_request_0001",
            },
        )["result"]["structuredContent"]["data"]
        path = request["confirmation_path"]
        page = self.client.get(path)
        decisions = {
            name: "ACCEPT" for name in re.findall(r"<select[^>]*name='([^']+)'", page.text)
        }
        result = self.client.post(
            path,
            data={
                "confirmation_token": self.hidden(page.text, "confirmation_token"),
                "confirm": "reviewed",
                "allow_connection": "yes",
                **decisions,
            },
        )
        self.assertEqual(result.status_code, 200, result.text)
        receipt = re.search(r"id='approval-receipt'>([^<]+)", result.text).group(1)
        self.assertEqual(
            self.call(
                "submit_claim_review",
                {"review_batch_id": review.split("/")[-1], "approval_receipt": receipt},
            )["result"]["structuredContent"]["status"],
            "ok",
        )
        with self.demo.sessions() as session:
            claim = session.scalar(select(Claim.id))
        use = f"/profile/{ACCOUNTS['a'][1]}/1/claim/{claim}/use-review"
        page = self.client.get(use)
        self.assertEqual(
            self.client.post(
                use,
                data={
                    "approval_token": self.hidden(page.text, "approval_token"),
                    "confirm_consistency": "yes",
                    "confirm_use": "yes",
                },
                follow_redirects=False,
            ).status_code,
            303,
        )
        jd = self.post_form(
            "/jd/new",
            "paste_token",
            "store_excerpts",
            selected_text="- 합성 테스트 경험",
        )
        mapping = re.search(r"href='([^']+/mapping/2)'", self.client.get(jd).text).group(1)
        link = re.search(r"href='([^']+/link/[^']+)'", self.client.get(mapping).text).group(1)
        self.post_form(link, "link_token", "link_potential")
        draft = re.search(r"href='([^']+/draft/2)'", self.client.get(mapping).text).group(1)
        trace = self.post_form(draft, "draft_token", "create_r1", claim_id=claim)
        artifact = trace.split("/")[2]
        wording = f"/resume/{artifact}/wording"
        self.post_form(wording, "approval_token", "accept_r1")
        export = f"/resume/{artifact}/export/MARKDOWN"
        page = self.client.get(export)
        result = self.client.post(
            export,
            data={"export_token": self.hidden(page.text, "export_token"), "confirm": "download"},
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(re.sub(r"\\(.)", r"\1", result.text), "- " + phrase + "\n")
        with self.demo.sessions() as session:
            self.assertEqual(session.get(CareerProfile, ACCOUNTS["a"][1]).version, 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)

    def test_runtime_database_and_in_memory_credentials_are_removed_on_close(self):
        with LocalDemo(8010) as demo:
            path = demo.database_path
            parent = path.parent
            demo.browsers["dummy"] = {"access_token": "synthetic-only"}
        self.assertFalse(path.exists())
        self.assertFalse(parent.exists())
        self.assertIsNone(demo.key)
        self.assertEqual(demo.browsers, {})


if __name__ == "__main__":
    unittest.main()

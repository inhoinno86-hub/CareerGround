"""Private trial transport remains loopback-only and has a synthetic identity."""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

from careerground.chatgpt_synthetic_trial import SyntheticChatGPTTrial
from careerground.local_demo import COOKIE
from careerground.storage.models import CareerProfile


class SyntheticTrialTests(unittest.TestCase):
    def setUp(self):
        self.trial = SyntheticChatGPTTrial(8044)
        self.client = TestClient(self.trial, base_url=self.trial.origin, client=("127.0.0.1", 1))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.trial.close()

    def rpc(self, method, params=None, id=7):
        return self.client.post(
            "/chatgpt/mcp",
            json={"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}},
        )

    def test_metadata_auth_describes_only_the_synthetic_outer_transport(self):
        response = self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "synthetic-trial-test", "version": "1"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 7)
        self.assertIn("not your real identity", response.json()["result"]["instructions"])
        tools = self.rpc("tools/list").json()["result"]["tools"]
        self.assertEqual(len(tools), 30)
        self.assertTrue(all(t["securitySchemes"] == [{"type": "noauth"}] for t in tools))
        self.assertTrue(all(t["description"].startswith("SYNTHETIC PRIVATE TRIAL") for t in tools))

    def test_enrollment_and_browser_have_separate_connection_credentials(self):
        response = self.rpc(
            "tools/call",
            {
                "name": "initialize_career_profile",
                "arguments": {"policy_version": "product-policy-v0.1"},
            },
        )
        self.assertEqual(response.json()["result"]["structuredContent"]["status"], "ok")
        with self.trial.sessions() as session:
            self.assertIsNotNone(
                session.scalar(
                    select(CareerProfile).where(
                        CareerProfile.account_id == self.trial.trial_account_id
                    )
                )
            )
        page = self.client.get("/chatgpt")
        import re

        token = re.search("name='form_token' value='([^']+)'", page.text).group(1)
        self.assertEqual(
            self.client.post("/chatgpt/account", data={"form_token": token}).status_code, 200
        )
        state = self.trial.browsers[self.client.cookies.get(COOKIE)]
        self.assertNotEqual(state["session_id"], self.trial.trial_state["session_id"])
        self.assertNotIn("access_token", state)
        self.assertNotEqual(
            self.trial._access_token(state), self.trial._access_token(self.trial.trial_state)
        )

    def test_foreign_host_origin_and_unbounded_inputs_are_denied(self):
        for headers in [{"host": "remote.example"}, {"origin": "https://remote.example"}]:
            self.assertEqual(
                self.client.post("/chatgpt/mcp", json={}, headers=headers).status_code, 403
            )
        self.assertEqual(
            self.client.post(
                "/chatgpt/mcp", content=b"x" * 131073, headers={"content-type": "application/json"}
            ).status_code,
            413,
        )
        self.assertEqual(self.rpc("tools/call", id=True).status_code, 400)
        self.assertEqual(self.rpc("unsupported").json()["error"]["code"], -32601)
        # A model cannot inject a new outer identity or authorization.
        response = self.client.post(
            "/chatgpt/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "subject": "someone-else"},
        )
        self.assertEqual(response.status_code, 400)

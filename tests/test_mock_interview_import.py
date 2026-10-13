"""STEP 02 synthetic runtime checks. Does not build Android or call any AI."""

import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/mock-interview/runtime"))
from cg_mock.api import create_app
from cg_mock.session import (
    MAX_ATTACHMENT,
    MAX_ATTACHMENTS_TOTAL,
    MAX_ENVELOPE,
    MAX_JSON,
    Rejected,
    Sessions,
    decode,
    exchange,
    parse,
    sha,
)


def raw_fixture():
    return (ROOT / "fixtures/portable/handoff-v1.json").read_bytes()


def encode(data):
    return json.dumps(data, ensure_ascii=False).encode()


def b64(raw):
    return base64.b64encode(raw).decode()


def with_attachment():
    handoff = parse(raw_fixture())
    evidence = b"synthetic evidence"
    handoff["workspace"]["attachments"] = [
        {
            "id": "attachment-1",
            "path": "evidence.txt",
            "sha256": sha(evidence),
        }
    ]
    handoff["workspace"]["artifacts"][0]["payload"]["sources"][0]["attachment_id"] = "attachment-1"
    handoff["selection"]["attachment_ids"] = ["attachment-1"]
    return handoff, evidence


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.store = Sessions()
        self.raw = raw_fixture()
        self.owner = "synthetic-a"

    def create(self, raw=None, attachments=None):
        return self.store.create(self.owner, self.raw if raw is None else raw, attachments or {})

    def test_pins_original_and_returns_defensive_copies(self):
        before = hashlib.sha256(self.raw).hexdigest()
        view = self.create()
        sid = view["session_id"]
        self.assertEqual(view["canonical_digest"], exchange.digest(parse(self.raw)))
        self.assertEqual(view["raw_sha256"], before)
        self.assertNotEqual(view["raw_sha256"], view["canonical_digest"])
        view["handoff"]["goals"].append("mutated UI copy")
        again = self.store.view(sid, self.owner)
        self.assertNotIn("mutated UI copy", again["handoff"]["goals"])
        self.assertEqual(
            base64.b64decode(parse(self.store.export(sid, self.owner))["handoff_base64"]), self.raw
        )
        self.assertEqual(hashlib.sha256(raw_fixture()).hexdigest(), before)

    def test_review_is_required_before_start_and_bound_to_digest(self):
        view = self.create()
        sid, digest = view["session_id"], view["canonical_digest"]
        with self.assertRaisesRegex(Rejected, "STATE_CONFLICT"):
            self.store.transition(sid, self.owner, "start")
        for wrong_digest, record, mode in [
            ("0" * 64, "review", "coaching"),
            (digest, " ", "coaching"),
            (digest, "review", []),
        ]:
            with self.subTest(record=record, mode=mode), self.assertRaises(Rejected):
                self.store.review(sid, self.owner, wrong_digest, record, mode)
        self.assertEqual(
            self.store.review(sid, self.owner, digest, "scope reviewed", "simulation")["state"],
            "READY",
        )
        for action, state in [
            ("start", "IN_PROGRESS"),
            ("pause", "PAUSED"),
            ("continue", "IN_PROGRESS"),
            ("abort", "ABORTED"),
        ]:
            self.assertEqual(self.store.transition(sid, self.owner, action)["state"], state)
        with self.assertRaises(Rejected):
            self.store.transition(sid, self.owner, "start")

    def test_wrong_kind_version_duplicates_and_invalid_utf8(self):
        cases = [
            self.raw.replace(b'"kind": "career-handoff"', b'"kind": "career-result"', 1),
            self.raw.replace(b'"schema_version": "1.0"', b'"schema_version": "0.9"', 1),
            b'{"kind":"career-handoff","kind":"career-handoff"}',
            b"\xff",
            b"{}{}",
            b'{"x":NaN}',
            b"[" * 2000,
            b"x" * (MAX_JSON + 1),
        ]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(Rejected):
                self.create(raw)
        self.assertFalse(self.store._items)

    def test_semantic_invalid_inputs_are_not_sessions(self):
        handoff = parse(self.raw)
        variants = []

        def changed(change):
            data = copy.deepcopy(handoff)
            change(data)
            variants.append(data)

        changed(lambda d: d["profile_ref"].update(version=9))
        changed(lambda d: d["workspace"]["artifacts"][0]["payload"]["sources"].clear())
        changed(lambda d: d["selection"]["fact_ids"].append("fact-1"))
        changed(
            lambda d: d["workspace"]["artifacts"].append(
                copy.deepcopy(d["workspace"]["artifacts"][0])
            )
        )
        changed(
            lambda d: d["workspace"]["artifacts"][0]["payload"]["facts"][0]["confirmation"].update(
                status="pending", record=""
            )
        )
        changed(
            lambda d: d["workspace"]["artifacts"][0]["payload"]["facts"][0]["permission"].update(
                status="denied", scope=[]
            )
        )
        changed(
            lambda d: d["workspace"]["artifacts"][0]["payload"]["constraints"][0].update(
                rule="do_not_use"
            )
        )
        changed(
            lambda d: d["workspace"]["artifacts"][2]["payload"]["sentences"][0].update(
                review="pending"
            )
        )
        changed(lambda d: d["selection"]["source_ids"].clear())
        changed(lambda d: d["selected_history"][0].update(confirmation="pending", record=""))
        for index, data in enumerate(variants):
            with self.subTest(variant=index), self.assertRaises(Rejected):
                self.create(encode(data))
        self.assertFalse(self.store._items)

    def test_attachment_missing_tampered_extra_path_size_and_cleanup(self):
        handoff, evidence = with_attachment()
        raw = encode(handoff)
        for selected in [
            {},
            {"evidence.txt": b"changed"},
            {"evidence.txt": evidence, "extra.txt": b"extra"},
            {"evidence.txt": b"x" * (MAX_ATTACHMENT + 1)},
        ]:
            with self.subTest(names=list(selected)), self.assertRaises(Rejected):
                self.create(raw, selected)
        real_temp = tempfile.TemporaryDirectory
        paths = []

        def capture(*args, **kwargs):
            temp = real_temp(*args, **kwargs)
            paths.append(Path(temp.name))
            return temp

        with patch("cg_mock.session.tempfile.TemporaryDirectory", side_effect=capture):
            view = self.create(raw, {"evidence.txt": evidence})
            self.assertEqual(view["state"], "REVIEW_REQUIRED")
            with self.assertRaises(Rejected):
                self.create(raw, {"evidence.txt": b"tampered"})
        self.assertTrue(paths)
        self.assertTrue(all(not p.exists() for p in paths))
        handoff["workspace"]["attachments"][0]["path"] = "../secret"
        with self.assertRaises(Rejected):
            self.create(encode(handoff), {"../secret": evidence})

    def test_attachment_total_is_bounded(self):
        handoff, _ = with_attachment()
        rows = [
            {"id": f"attachment-{i}", "path": f"evidence{i}.txt", "sha256": "0" * 64}
            for i in range(3)
        ]
        handoff["workspace"]["attachments"] = rows
        handoff["selection"]["attachment_ids"] = [a["id"] for a in rows]
        handoff["workspace"]["artifacts"][0]["payload"]["sources"][0]["attachment_id"] = rows[0][
            "id"
        ]
        blobs = {a["path"]: b"x" * (MAX_ATTACHMENTS_TOTAL // 3 + 1) for a in rows}
        with self.assertRaisesRegex(Rejected, "ATTACHMENT_TOTAL_LIMIT"):
            self.create(encode(handoff), blobs)

    def test_restore_checks_hash_owner_schema_and_requires_new_review(self):
        view = self.create()
        sid = view["session_id"]
        self.store.review(sid, self.owner, view["canonical_digest"], "reviewed", "coaching")
        self.store.transition(sid, self.owner, "start")
        exported = self.store.export(sid, self.owner)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manual-session.json"
            path.write_bytes(exported)
            resumed = self.store.restore(self.owner, path.read_bytes(), {})
        self.assertNotEqual(resumed["session_id"], sid)
        self.assertEqual(resumed["state"], "REVIEW_REQUIRED")
        self.assertIsNone(resumed["review"])
        with self.assertRaisesRegex(Rejected, "OWNER_CONFLICT"):
            self.store.restore("synthetic-b", exported, {})
        for field, value in [
            ("raw_sha256", "0" * 64),
            ("handoff_ref", {"id": "wrong", "sha256": "0" * 64}),
            ("schema_version", "0.2"),
            ("access_token", "not-exportable"),
        ]:
            data = parse(exported)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(Rejected):
                self.store.restore(self.owner, encode(data), {})

    def test_resume_rechecks_attachments_and_terminal_state(self):
        data, evidence = with_attachment()
        v = self.create(encode(data), {"evidence.txt": evidence})
        exported = self.store.export(v["session_id"], self.owner)
        with self.assertRaises(Rejected):
            self.store.restore(self.owner, exported, {})
        terminal = parse(exported)
        terminal["state"] = "ABORTED"
        resumed = self.store.restore(self.owner, encode(terminal), {"evidence.txt": evidence})
        with self.assertRaises(Rejected):
            self.store.review(
                resumed["session_id"], self.owner, resumed["canonical_digest"], "review", "coaching"
            )

    def test_owner_logout_delete_ttl_capacity_and_restart(self):
        clock = [0]
        self.store = Sessions(clock=lambda: clock[0], ttl=10, capacity=1)
        v = self.create()
        sid = v["session_id"]
        for method in [
            lambda: self.store.view(sid, "other"),
            lambda: self.store.export(sid, "other"),
            lambda: self.store.delete(sid, "other"),
        ]:
            with self.assertRaisesRegex(Rejected, "SESSION_UNAVAILABLE"):
                method()
        with self.assertRaisesRegex(Rejected, "SESSION_CAPACITY"):
            self.create()
        clock[0] = 11
        with self.assertRaisesRegex(Rejected, "SESSION_UNAVAILABLE"):
            self.store.view(sid, self.owner)
        v = self.create()
        self.store.clear_owner("other")
        self.assertEqual(len(self.store._items), 1)
        self.store.clear_owner(self.owner)
        self.assertFalse(self.store._items)
        with self.assertRaises(Rejected):
            Sessions().view(v["session_id"], self.owner)

    def test_untrusted_commands_and_urls_remain_inert(self):
        handoff = parse(self.raw)
        handoff["goals"] = ["$(touch /tmp/cg-injected) https://invalid.example/steal"]
        with (
            patch("subprocess.run", side_effect=AssertionError("shell access")),
            patch("urllib.request.urlopen", side_effect=AssertionError("URL access")),
        ):
            view = self.create(encode(handoff))
            self.assertEqual(view["handoff"]["goals"], handoff["goals"])

    def test_base64_and_nonfinite_are_rejected(self):
        for data in ["invalid!", ["not string"], "eA==\n"]:
            with self.subTest(data=data), self.assertRaises(Rejected):
                decode(data, 1)
        self.assertEqual(decode("eA==", 1), b"x")
        with self.assertRaises(Rejected):
            parse(b'{"nested":{"x":Infinity}}')


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = Sessions()
        self.client = TestClient(
            create_app(
                credentials={"dev-a": "synthetic-a", "dev-b": "synthetic-b"}, sessions=self.store
            )
        )
        self.headers = {"Authorization": "Bearer dev-a"}
        self.payload = {"handoff_base64": b64(raw_fixture()), "attachments": {}}

    def post(self, path, data):
        return self.client.post(path, json=data, headers=self.headers)

    def test_import_review_state_export_file_restore_http_flow(self):
        status = self.client.get("/v1/status", headers=self.headers)
        self.assertEqual(status.json()["ai_status"], "NOT_IMPLEMENTED")
        view = self.post("/v1/import", self.payload).json()
        sid = view["session_id"]
        self.assertEqual(
            self.post(f"/v1/sessions/{sid}/transition", {"action": "start"}).status_code, 409
        )
        self.assertEqual(
            self.post(
                f"/v1/sessions/{sid}/review",
                {
                    "canonical_digest": view["canonical_digest"],
                    "record": "synthetic review",
                    "mode": "coaching",
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(f"/v1/sessions/{sid}/transition", {"action": "start"}).json()["state"],
            "IN_PROGRESS",
        )
        response = self.client.get(f"/v1/sessions/{sid}/export", headers=self.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            path.write_bytes(response.content)
            self.assertNotIn("dev-a", path.read_text())
            restored = self.post(
                "/v1/restore", {"session_base64": b64(path.read_bytes()), "attachments": {}}
            )
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["state"], "REVIEW_REQUIRED")
        self.assertEqual(restored.json()["canonical_digest"], view["canonical_digest"])
        self.assertEqual(self.client.post("/v1/logout", headers=self.headers).status_code, 204)
        self.assertFalse(self.store._items)

    def test_auth_origin_host_and_owner_boundaries(self):
        self.assertEqual(
            self.client.get("/v1/status", headers=[(b"authorization", b"Bearer \xff")]).status_code,
            401,
        )
        self.assertEqual(self.client.post("/v1/import", json=self.payload).status_code, 401)
        self.assertEqual(
            self.client.get("/v1/status", headers={"Authorization": "Bearer bad"}).status_code, 401
        )
        self.assertEqual(
            self.client.get(
                "/v1/status", headers={**self.headers, "Origin": "https://invalid.example"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/v1/status", headers={**self.headers, "Host": "invalid.example"}
            ).status_code,
            400,
        )
        sid = self.post("/v1/import", self.payload).json()["session_id"]
        self.assertEqual(
            self.client.get(
                f"/v1/sessions/{sid}", headers={"Authorization": "Bearer dev-b"}
            ).status_code,
            404,
        )

    def test_request_duplicates_content_type_bounds_and_schema(self):
        self.assertEqual(
            self.client.post("/v1/import", content=b"{}", headers=self.headers).status_code, 415
        )
        result = self.client.post(
            "/v1/import",
            content=b'{"attachments":{},"attachments":{}}',
            headers={**self.headers, "Content-Type": "application/json"},
        )
        self.assertEqual(result.json()["errors"], ["DUPLICATE_JSON_KEY"])
        for value in [
            [],
            {**self.payload, "unexpected": True},
            {**self.payload, "attachments": []},
        ]:
            self.assertEqual(self.post("/v1/import", value).status_code, 400)
        with patch("cg_mock.api.MAX_ENVELOPE", 100):
            self.assertEqual(self.post("/v1/import", self.payload).status_code, 413)
        self.assertLess(MAX_JSON, MAX_ENVELOPE)

    def test_malformed_action_and_mode_are_rejected_without_server_error(self):
        view = self.post("/v1/import", self.payload).json()
        sid = view["session_id"]
        for action in [[], {}, None, 1]:
            with self.subTest(action=action):
                self.assertEqual(
                    self.post(f"/v1/sessions/{sid}/transition", {"action": action}).status_code, 400
                )
        result = self.post(
            f"/v1/sessions/{sid}/review",
            {
                "canonical_digest": view["canonical_digest"],
                "record": "synthetic review",
                "mode": [],
            },
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(
            self.client.post(f"/v1/sessions/{sid}/questions", headers=self.headers).status_code, 404
        )

    def test_malformed_numbers_and_escaped_unicode_fail_before_state_changes(self):
        headers = {**self.headers, "Content-Type": "application/json"}
        for body in [b'{"x":' + b"9" * 5000 + b"}", b'{"x":1e999}', b'{"\\ud800":1}']:
            with self.subTest(body_size=len(body)):
                response = self.client.post("/v1/import", content=body, headers=headers)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["errors"], ["INVALID_JSON"])
        view = self.post("/v1/import", self.payload).json()
        sid = view["session_id"]
        payload = {
            "canonical_digest": view["canonical_digest"],
            "mode": "coaching",
            "record": "review \ud800",
        }
        response = self.client.post(
            f"/v1/sessions/{sid}/review", content=json.dumps(payload).encode(), headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.view(sid, "synthetic-a")["state"], "REVIEW_REQUIRED")
        payload["record"] = "합성 검토 \U0001f44d"
        self.assertEqual(self.post(f"/v1/sessions/{sid}/review", payload).status_code, 200)


if __name__ == "__main__":
    unittest.main()

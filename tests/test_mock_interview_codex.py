"""Offline failure/budget tests; these never invoke an AI provider."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/mock-interview/runtime"))
from cg_mock.codex_local import HOST_DISABLED, CallBudget, CliResponse, CodexRejected, IsolatedCodex

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"const": True}},
    "required": ["ok"],
    "additionalProperties": False,
}


class CodexBoundaryTests(unittest.TestCase):
    def send(self, response, event):
        response.event(json.dumps(event))

    def test_wire_subset_keeps_full_local_uniqueness_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}
            },
            "required": ["ids"],
            "additionalProperties": False,
        }
        self.assertNotIn("uniqueItems", IsolatedCodex.wire_schema(schema)["properties"]["ids"])
        self.assertTrue(schema["properties"]["ids"]["uniqueItems"])
        response = CliResponse()
        for event in [
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"ids":["a","a"]}'},
            },
            {"type": "turn.completed"},
        ]:
            self.send(response, event)
        with self.assertRaisesRegex(CodexRejected, "CODEX_RESPONSE_SCHEMA"):
            response.finish(schema)

    def test_expected_disabled_host_diagnostic_and_structured_result(self):
        response = CliResponse()
        for event in [
            {"type": "thread.started", "thread_id": "synthetic"},
            {"type": "item.completed", "item": {"type": "error", "message": HOST_DISABLED}},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": '{"ok":true}'}},
            {"type": "turn.completed", "usage": {"input_tokens": 4}},
        ]:
            self.send(response, event)
        self.assertEqual(response.finish(SCHEMA), {"ok": True})
        self.assertEqual(response.diagnostics, 1)
        self.assertEqual(response.usage, {"input_tokens": 4})

    def test_tool_or_unexpected_error_event_is_rejected(self):
        for item in [
            {"type": "command_execution", "command": "synthetic command"},
            {"type": "mcp_tool_call"},
            {"type": "web_search"},
            {"type": "error", "message": "some other startup failure"},
        ]:
            with self.subTest(item=item), self.assertRaises(CodexRejected):
                self.send(CliResponse(), {"type": "item.started", "item": item})
        response = CliResponse()
        self.send(response, {"type": "turn.started"})
        with self.assertRaises(CodexRejected):
            self.send(
                response,
                {"type": "item.completed", "item": {"type": "error", "message": HOST_DISABLED}},
            )

    def test_incomplete_invalid_and_multiple_messages_are_rejected(self):
        for messages, completed in [
            ([], False),
            (["{}"], True),
            (["not json"], True),
            (['{"ok":true}'] * 2, True),
        ]:
            response = CliResponse()
            self.send(response, {"type": "turn.started"})
            for message in messages:
                self.send(
                    response,
                    {"type": "item.completed", "item": {"type": "agent_message", "text": message}},
                )
            if completed:
                self.send(response, {"type": "turn.completed"})
            with self.subTest(messages=messages), self.assertRaises(CodexRejected):
                response.finish(SCHEMA)

    def test_budget_counts_failed_calls_persists_and_locks_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "counts.json"
            budget = CallBudget(ledger, limit=2)
            with (
                self.assertRaisesRegex(RuntimeError, "synthetic failure"),
                budget.reserve() as attempt,
            ):
                self.assertEqual(attempt, 1)
                with (
                    self.assertRaisesRegex(CodexRejected, "CODEX_BUSY"),
                    CallBudget(ledger, limit=2).reserve(),
                ):
                    self.fail("concurrent call permitted")
                raise RuntimeError("synthetic failure")
            with CallBudget(ledger, limit=2).reserve() as attempt:
                self.assertEqual(attempt, 2)
            with self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_EXHAUSTED"), budget.reserve():
                self.fail("over-budget call permitted")
            self.assertEqual(json.loads(ledger.read_text())["attempts"], 2)

    def test_explicit_extension_preserves_prior_count_and_stops_at_new_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "counts.json"
            ledger.write_text(json.dumps({"attempts": 11, "limit": 12}))
            ledger.chmod(0o600)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_INVALID"),
                CallBudget(ledger, limit=15).reserve(),
            ):
                self.fail("unmigrated ledger accepted")
            self.assertEqual(json.loads(ledger.read_text())["attempts"], 11)
            ledger.write_text(json.dumps({"attempts": 11, "limit": 15}))
            for expected in range(12, 16):
                with CallBudget(ledger, limit=15).reserve() as attempt:
                    self.assertEqual(attempt, expected)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_EXHAUSTED"),
                CallBudget(ledger, limit=15).reserve(),
            ):
                self.fail("approved cumulative limit exceeded")
            self.assertEqual(json.loads(ledger.read_text())["attempts"], 15)

    def test_explicit_limit_rejects_wrong_types_and_unapproved_upper_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "counts.json"
            for limit in [True, 0, 19, "18", 18.0]:
                with (
                    self.subTest(limit=limit),
                    self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_LOCATION"),
                ):
                    CallBudget(ledger, limit=limit)
            ledger.write_text(json.dumps({"attempts": 0, "limit": True}))
            ledger.chmod(0o600)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_INVALID"),
                CallBudget(ledger, limit=1).reserve(),
            ):
                self.fail("boolean ledger limit accepted as integer")

    def test_pace_extension_preserves_fourteen_calls_and_stops_at_eighteen(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "counts.json"
            ledger.write_text(json.dumps({"attempts": 14, "limit": 15}))
            ledger.chmod(0o600)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_INVALID"),
                CallBudget(ledger, limit=18).reserve(),
            ):
                self.fail("extension without ledger approval accepted")
            self.assertEqual(json.loads(ledger.read_text()), {"attempts": 14, "limit": 15})
            ledger.write_text(json.dumps({"attempts": 14, "limit": 18}))
            for expected in range(15, 19):
                with CallBudget(ledger, limit=18).reserve() as attempt:
                    self.assertEqual(attempt, expected)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_EXHAUSTED"),
                CallBudget(ledger, limit=18).reserve(),
            ):
                self.fail("approved cumulative limit exceeded")
            self.assertEqual(json.loads(ledger.read_text())["attempts"], 18)

    def test_budget_rejects_untrusted_location_symlink_and_corrupt_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            ledger = parent / "counts.json"
            ledger.write_text('{"attempts": true, "limit": 12}')
            ledger.chmod(0o600)
            with (
                self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_INVALID"),
                CallBudget(ledger).reserve(),
            ):
                self.fail("bad count permitted")
            link = parent / "link.json"
            link.symlink_to(ledger)
            with self.assertRaises(OSError), CallBudget(link).reserve():
                self.fail("symlink permitted")
            parent.chmod(0o755)
            with self.assertRaisesRegex(CodexRejected, "CODEX_BUDGET_LOCATION"):
                CallBudget(ledger)


if __name__ == "__main__":
    unittest.main()

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "plugins/careerground-portable/references"
sys.path.insert(0, str(REFERENCES))
SPEC = importlib.util.spec_from_file_location("exchange", REFERENCES / "exchange.py")
exchange = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exchange)
sys.path.pop(0)


def fixture(name):
    return json.loads((ROOT / "fixtures/portable" / name).read_text())


def export(workspace, **overrides):
    kwargs = {
        "resume_ref": {"id": "resume-jd-synthetic", "version": 1},
        "fact_ids": ["fact-1"],
        "source_ids": ["source-1"],
        "operation_ids": ["operation-tailor"],
        "attachment_ids": [],
        "handoff_id": "handoff-test",
        "created_at": "2026-10-09T12:00:00Z",
        "goals": ["공동 기여 설명"],
        "review_record": "합성 사용자 포함 범위 확인",
    }
    kwargs.update(overrides)
    return exchange.make_handoff(workspace, **kwargs)


class PortableExchangeTests(unittest.TestCase):
    def test_only_selected_content_exported_without_mutating_workspace(self):
        workspace = fixture("tailored-resume-v1.json")
        before = copy.deepcopy(workspace)
        handoff = export(workspace)
        self.assertEqual(workspace, before)
        self.assertEqual(exchange.validate_handoff(handoff), [])
        serialized = json.dumps(handoff, ensure_ascii=False)
        self.assertNotIn("fact-private", serialized)
        self.assertNotIn("source-private", serialized)
        self.assertEqual(len(handoff["workspace"]["artifacts"]), 3)
        self.assertEqual(handoff["omitted_refs"], [{"id": "resume-base", "version": 1}])
        self.assertEqual([op["id"] for op in handoff["selected_history"]], ["operation-tailor"])

    def test_export_rejects_forbidden_missing_selection_and_unreviewed_resume(self):
        for overrides in [
            {"fact_ids": ["fact-1", "fact-private"], "source_ids": ["source-1", "source-private"]},
            {"source_ids": []},
            {"operation_ids": ["missing"]},
            {"attachment_ids": ["missing"]},
        ]:
            with self.subTest(overrides=overrides), self.assertRaises(exchange.InvalidFile):
                export(fixture("tailored-resume-v1.json"), **overrides)
        workspace = fixture("tailored-resume-v1.json")
        resume = next(a for a in workspace["artifacts"] if a["id"] == "resume-jd-synthetic")
        resume["payload"]["sentences"][0]["review"] = "pending"
        with self.assertRaisesRegex(exchange.InvalidFile, "RESUME_UNREVIEWED"):
            export(workspace)

    def test_missing_conflicting_wrong_type_and_unsupported_files(self):
        self.assertIn(
            "MISSING_REFERENCE", exchange.validate_handoff(fixture("handoff-missing-source.json"))
        )
        handoff = fixture("handoff-v1.json")
        handoff["profile_ref"]["version"] = 9
        self.assertTrue(exchange.validate_handoff(handoff))
        handoff = fixture("handoff-v1.json")
        handoff["schema_version"] = "0.9"
        self.assertEqual(exchange.validate_handoff(handoff), ["UNSUPPORTED_VERSION"])
        self.assertTrue(exchange.validate_handoff(fixture("result-v1.json")))

    def test_attachments_hash_presence_and_path_are_checked(self):
        handoff = fixture("handoff-v1.json")
        attachment = {
            "id": "attachment-1",
            "path": "evidence.txt",
            "sha256": hashlib.sha256(b"synthetic evidence").hexdigest(),
        }
        handoff["workspace"]["attachments"] = [attachment]
        handoff["workspace"]["artifacts"][0]["payload"]["sources"][0]["attachment_id"] = (
            "attachment-1"
        )
        handoff["selection"]["attachment_ids"] = ["attachment-1"]
        self.assertIn("ATTACHMENT_NOT_CHECKED", exchange.validate_handoff(handoff))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIn(
                "MISSING_ATTACHMENT", exchange.validate_handoff(handoff, attachment_root=root)
            )
            (root / "evidence.txt").write_bytes(b"synthetic evidence")
            self.assertEqual(exchange.validate_handoff(handoff, attachment_root=root), [])
            (root / "evidence.txt").write_bytes(b"tampered")
            self.assertIn(
                "ATTACHMENT_HASH_MISMATCH", exchange.validate_handoff(handoff, attachment_root=root)
            )
            (root / "target.txt").write_bytes(b"synthetic evidence")
            (root / "evidence.txt").unlink()
            (root / "evidence.txt").symlink_to(root / "target.txt")
            self.assertIn(
                "MISSING_ATTACHMENT", exchange.validate_handoff(handoff, attachment_root=root)
            )
        attachment["path"] = "../secret"
        self.assertEqual(exchange.validate_handoff(handoff), ["SCHEMA"])

    def test_results_return_candidates_and_never_promote_or_mutate(self):
        handoff = fixture("handoff-v1.json")
        result = fixture("result-v1.json")
        originals = copy.deepcopy((handoff, result))
        imported = exchange.import_result(result, handoff)
        self.assertEqual((handoff, result), originals)
        self.assertEqual(imported["candidates"][0]["status"], "pending")
        imported["candidates"][0]["text"] = "edited locally"
        self.assertNotEqual(imported, result)
        result["candidates"][0]["status"] = "accepted"
        self.assertEqual(exchange.validate_result(result, handoff), ["SCHEMA"])

    def test_result_binds_exact_handoff_and_answer_references(self):
        handoff = fixture("handoff-v1.json")
        result = fixture("result-conflict.json")
        self.assertEqual(exchange.validate_result(result, handoff), ["HANDOFF_CONFLICT"])
        result = fixture("result-v1.json")
        result["candidates"][0]["answer_id"] = "lost"
        self.assertIn("MISSING_REFERENCE", exchange.validate_result(result, handoff))
        result = fixture("result-v1.json")
        handoff["goals"].append("changed")
        self.assertEqual(exchange.validate_result(result, handoff), ["HANDOFF_CONFLICT"])

    def test_data_commands_are_inert(self):
        handoff = fixture("handoff-v1.json")
        handoff["goals"] = ["$(touch /tmp/do-not-execute) https://invalid.example/steal"]
        self.assertEqual(exchange.validate_handoff(handoff), [])
        # The reader preserves text; no evaluation, shell, URL access or file writes.
        result = fixture("result-v1.json")
        result["handoff_ref"]["sha256"] = exchange.digest(handoff)
        self.assertEqual(exchange.import_result(result, handoff), result)

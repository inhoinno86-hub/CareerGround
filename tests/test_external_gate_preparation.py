"""Preparation evidence must not imply vendor quality, approval or release readiness."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest

from scripts.check_external_gate_preparation import (
    CORPUS,
    MANIFEST,
    ROOT,
    PreparationInvalid,
    load_json,
    reject_duplicate_keys,
    validate_bundle,
    validate_corpus,
)


class ExternalGatePreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_json(ROOT / MANIFEST)
        self.corpus = load_json(ROOT / CORPUS)

    def test_preparation_pass_keeps_external_execution_and_quality_unverified(self) -> None:
        report = validate_bundle(ROOT, self.manifest, self.corpus)
        self.assertEqual(report["preparation_status"], "PASS")
        self.assertIs(report["external_execution_ready"], False)
        self.assertEqual(report["semantic_model_cases_executed"], 0)
        self.assertEqual(report["thresholds_status"], "PROPOSED_NOT_APPROVED")
        self.assertEqual(set(report["gates"].values()), {"WAITING_EXTERNAL_APPROVAL"})

    def test_changed_approval_cost_requests_and_boolean_numbers_are_rejected(self) -> None:
        for key, values in {
            "external_execution_approved": [True, 0],
            "approved_requests": [1, False, 0.0],
            "approved_ai_cost": [1, False, 0.0],
            "approved_cloud_cost": [1, False, 0.0],
            "currency": ["USD"],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    changed = copy.deepcopy(self.manifest)
                    changed["policy"][key] = value
                    with self.assertRaises(PreparationInvalid):
                        validate_bundle(ROOT, changed, self.corpus)

    def test_fabricated_gate_pass_or_external_evidence_is_rejected(self) -> None:
        for gate in self.manifest["gates"]:
            for key, value in (("status", "PASS"), ("external_evidence", ["passed"])):
                with self.subTest(gate=gate, key=key):
                    changed = copy.deepcopy(self.manifest)
                    changed["gates"][gate][key] = value
                    with self.assertRaises(PreparationInvalid):
                        validate_bundle(ROOT, changed, self.corpus)

    def test_incomplete_cases_duplicate_ids_and_wrong_task_are_rejected(self) -> None:
        for mutation in ("missing", "duplicate", "task", "action", "followup", "authority"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.corpus)
                case = changed["cases"][0]
                if mutation == "missing":
                    changed["cases"].pop()
                elif mutation == "duplicate":
                    changed["cases"][1]["id"] = case["id"]
                elif mutation == "task":
                    case["task"] = "r3"
                elif mutation == "action":
                    case["expected_action"] = "AUTO_APPROVE"
                elif mutation == "followup":
                    case["expected_action"] = "FOLLOW_UP"
                    case["followup"] = ""
                else:
                    case["owner_id"] = "untrusted"
                with self.assertRaises(PreparationInvalid):
                    validate_corpus(changed)

    def test_changed_hash_or_document_path_is_rejected(self) -> None:
        for target, field, value in (
            ("corpus", "sha256", "0" * 64),
            ("G-I", "sha256", "0" * 64),
            ("G-I", "path", "../credentials.env"),
        ):
            with self.subTest(target=target, field=field):
                changed = copy.deepcopy(self.manifest)
                entry = changed["corpus"] if target == "corpus" else changed["documents"][target]
                entry[field] = value
                with self.assertRaises(PreparationInvalid):
                    validate_bundle(ROOT, changed, self.corpus)

    def test_duplicate_json_keys_are_rejected_instead_of_last_value_winning(self) -> None:
        with self.assertRaises(PreparationInvalid):
            json.loads(
                '{"approved_requests":1,"approved_requests":0}',
                object_pairs_hook=reject_duplicate_keys,
            )

    def test_release_requirement_exits_blocked_with_no_input_text_in_report(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_external_gate_preparation.py"),
                "--require-ready",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["preparation_status"], "PASS")
        self.assertIs(report["external_execution_ready"], False)
        self.assertNotIn("input_text", result.stdout)
        self.assertNotIn(self.corpus["cases"][0]["input_text"], result.stdout)


if __name__ == "__main__":
    unittest.main()

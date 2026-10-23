"""Synthetic offline contracts, not installed-host conversation evaluation."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "portable", ROOT / "plugins/careerground-portable/references/portable.py"
)
portable = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portable)


def fixture(name="profile-v1.json"):
    return json.loads((ROOT / "fixtures/portable" / name).read_text())


class PortableFileTests(unittest.TestCase):
    def test_in_memory_objects_obey_file_size_limit(self):
        data = fixture()
        sources = data["artifacts"][0]["payload"]["sources"]
        for index in range(110):
            sources.append(
                {
                    "id": f"large-{index}",
                    "kind": "user_statement",
                    "text": "x" * 20000,
                    "locator": "synthetic",
                    "attachment_id": None,
                }
            )
        self.assertEqual(portable.validate_workspace(data), ["SIZE_LIMIT"])

    def test_mapping_cannot_use_forbidden_fact_and_manual_jd_is_not_live_verified(self):
        data = fixture("tailored-resume-v1.json")
        tailored = next(a for a in data["artifacts"] if a["id"] == "resume-jd-synthetic")
        tailored["payload"]["mappings"][0]["fact_ids"] = ["fact-private"]
        self.assertIn("USE_FORBIDDEN", portable.validate_workspace(data))
        data = fixture("tailored-resume-v1.json")
        jd = next(a for a in data["artifacts"] if a["kind"] == "jd")
        jd["payload"]["status"] = "open_verified"
        self.assertIn("JD_UNCERTAINTY", portable.validate_workspace(data))

    def test_external_verification_requires_linked_external_source(self):
        data = fixture()
        profile = data["artifacts"][0]["payload"]
        profile["sources"].append(
            {
                "id": "external-1",
                "kind": "external_excerpt",
                "text": "다른 사실의 합성 문서",
                "locator": "문서 p1",
                "attachment_id": None,
            }
        )
        profile["facts"][0]["confirmation"] = {
            "status": "externally_verified",
            "record": "검토 기록",
            "source_id": "external-1",
        }
        self.assertIn("INVALID_VERIFICATION", portable.validate_workspace(data))
        profile["facts"][0]["source_ids"].append("external-1")
        self.assertEqual(portable.validate_workspace(data), [])

    def test_tailoring_preserves_base_and_records_all_jd_gaps(self):
        data = fixture("tailored-resume-v1.json")
        self.assertEqual(portable.validate_workspace(data), [])
        base = next(a for a in data["artifacts"] if a["id"] == "resume-base")
        prior = next(
            a for a in fixture("base-resume-v1.json")["artifacts"] if a["id"] == "resume-base"
        )
        self.assertEqual(base, prior)
        jd = next(a for a in data["artifacts"] if a["kind"] == "jd")["payload"]
        self.assertEqual(jd["status"], "unknown")
        self.assertEqual(jd["access"], "manual")
        tailored = next(a for a in data["artifacts"] if a["id"] == "resume-jd-synthetic")
        self.assertEqual(tailored["payload"]["mappings"][1]["assessment"], "gap")
        self.assertEqual(tailored["payload"]["mappings"][1]["fact_ids"], [])
        self.assertNotIn("비공개", tailored["payload"]["sentences"][0]["text"])
        tailored["payload"]["mappings"].pop()
        self.assertIn("MAPPING_INCOMPLETE", portable.validate_workspace(data))

    def test_empty_to_base_resume_has_no_jd_and_preserves_boundaries(self):
        data = fixture("base-resume-v1.json")
        self.assertEqual(portable.validate_workspace(data), [])
        profiles = [a for a in data["artifacts"] if a["kind"] == "profile"]
        self.assertEqual([p["version"] for p in profiles], [1, 2, 3])
        self.assertEqual(profiles[0]["payload"]["facts"], [])
        self.assertEqual(profiles[1]["payload"]["facts"][0]["confirmation"]["status"], "pending")
        resume = next(a for a in data["artifacts"] if a["kind"] == "resume")["payload"]
        self.assertIsNone(resume["jd_ref"])
        sentence = resume["sentences"][0]
        self.assertEqual(sentence["source_ids"], ["source-1"])
        self.assertIn("배포 실행은 동료", sentence["text"])
        self.assertIn("측정하지 않았다", sentence["text"])
        self.assertNotIn("fact-private", sentence["fact_ids"])
        self.assertEqual(
            portable.check_review(
                data, (ROOT / "fixtures/portable/base-resume-v1.review.md").read_text()
            ),
            [],
        )

    def test_resume_rejects_unconfirmed_forbidden_and_summary_evidence(self):
        for mutation, expected in [
            ("pending", "FACT_UNREVIEWED"),
            ("forbidden", "USE_FORBIDDEN"),
            ("model_summary", "SUMMARY_AS_EVIDENCE"),
        ]:
            data = fixture("base-resume-v1.json")
            profile = data["artifacts"][2]["payload"]
            if mutation == "pending":
                profile["facts"][0]["confirmation"]["status"] = "pending"
            elif mutation == "forbidden":
                profile["facts"][0]["permission"]["status"] = "forbidden"
                profile["facts"][0]["permission"]["scope"] = []
            else:
                profile["sources"][0]["kind"] = "model_summary"
            with self.subTest(mutation=mutation):
                self.assertIn(expected, portable.validate_workspace(data))

    def test_valid_empty_and_profile(self):
        for name in ["empty-v1.json", "profile-v1.json"]:
            self.assertEqual(portable.validate_workspace(fixture(name)), [])

    def test_error_categories_are_distinct(self):
        cases = []
        data = fixture()
        data["schema_version"] = "0.9"
        cases.append((data, "UNSUPPORTED_VERSION"))
        data = fixture()
        data["artifacts"].append(copy.deepcopy(data["artifacts"][0]))
        cases.append((data, "DUPLICATE_ID"))
        data = fixture()
        data["selected_profile"]["id"] = "missing"
        cases.append((data, "MISSING_REFERENCE"))
        data = fixture()
        newer = copy.deepcopy(data["artifacts"][0])
        newer["version"] = 2
        data["artifacts"].append(newer)
        cases.append((data, "STALE_VERSION"))
        data = fixture()
        data["artifacts"][0]["payload"]["sources"][0]["kind"] = "model_summary"
        cases.append((data, "SUMMARY_AS_EVIDENCE"))
        data = fixture()
        data["artifacts"][0]["payload"]["sources"][0]["attachment_id"] = "lost"
        cases.append((data, "MISSING_ATTACHMENT"))
        data = fixture()
        data["artifacts"][0]["payload"]["facts"][1]["permission"]["scope"] = ["interview"]
        cases.append((data, "USE_FORBIDDEN"))
        for data, code in cases:
            with self.subTest(code=code):
                self.assertIn(code, portable.validate_workspace(data))

    def test_review_and_baseline_conflicts(self):
        data = fixture()
        self.assertEqual(portable.check_review(data, portable.render_workspace(data)), [])
        self.assertEqual(portable.check_review(data, "edited"), ["REVIEW_CONFLICT"])
        other = copy.deepcopy(data)
        other["workspace_id"] = "other-profile"
        with self.assertRaisesRegex(portable.InvalidFile, "MULTIPLE_BASELINES"):
            portable.select_workspace([data, other])
        self.assertIs(
            portable.select_workspace(
                [data, other], ("workspace-synthetic", "profile-synthetic", 1)
            ),
            data,
        )
        conflicting = copy.deepcopy(data)
        conflicting["artifacts"][0]["payload"]["facts"][0]["period"] = "different period"
        with self.assertRaisesRegex(portable.InvalidFile, "BASELINE_CONFLICT"):
            portable.select_workspace(
                [data, conflicting], ("workspace-synthetic", "profile-synthetic", 1)
            )

    def test_confirmation_is_separate_from_permission(self):
        data = fixture()
        fact = data["artifacts"][0]["payload"]["facts"][0]
        fact["permission"] = {"status": "review_required", "scope": [], "record": ""}
        self.assertEqual(portable.validate_workspace(data), [])
        self.assertEqual(fact["confirmation"]["status"], "user_confirmed")

    def test_rejects_duplicate_json_keys_symlinks_and_oversize(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text('{"schema_version":"1.0","schema_version":"0.9"}')
            with self.assertRaisesRegex(portable.InvalidFile, "DUPLICATE_JSON_KEY"):
                portable.load_json(path)
            link = Path(folder) / "link.json"
            link.symlink_to(path)
            with self.assertRaisesRegex(portable.InvalidFile, "INVALID_FILE"):
                portable.load_json(link)
            path.write_bytes(b" " * (portable.MAX_JSON_BYTES + 1))
            with self.assertRaisesRegex(portable.InvalidFile, "SIZE_LIMIT"):
                portable.load_json(path)

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "portable_workflow", ROOT / "plugins/careerground-portable/references/workflow.py"
)
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class OnboardingTests(unittest.TestCase):
    def test_all_project_states_allow_explicitly_selected_work(self):
        for status in ["outside", "unknown", "ready", "declined", "unsupported", "move_failed"]:
            for count, action in [(0, "start_empty"), (2, "resume_selected")]:
                with self.subTest(status=status, count=count):
                    d = workflow.onboarding(status, baseline_count=count, selected=True)
                    self.assertEqual(d["action"], action)
                    self.assertTrue(d["collect_career"])
                    self.assertTrue(d["project_optional"])
                    self.assertFalse(d["ask_ready"])
                    self.assertFalse(d["project_verified"])
                    self.assertIsNone(d["reply"])

    def test_project_readiness_never_replaces_baseline_choice(self):
        for status in ["ready", "declined", "unsupported"]:
            for count, action in [(0, "choose_empty_start"), (2, "choose_baseline")]:
                d = workflow.onboarding(status, baseline_count=count)
                self.assertEqual(d["action"], action)
                self.assertFalse(d["collect_career"])

    def test_location_change_does_not_cancel_data_selection(self):
        for status in ["ready", "outside", "declined", "move_failed"]:
            d = workflow.onboarding(status, baseline_count=1, selected=True)
            self.assertEqual(d["action"], "resume_selected")
            self.assertTrue(d["collect_career"])

    def test_declined_or_unsupported_projects_are_not_repeatedly_requested(self):
        for status in ["declined", "unsupported", "move_failed", "ready"]:
            self.assertFalse(workflow.onboarding(status)["recommend_project"])
        self.assertTrue(workflow.onboarding("unknown")["recommend_project"])
        self.assertFalse(
            workflow.onboarding("unknown", project_advice_seen=True)["recommend_project"]
        )

    def test_explicit_stop_is_separate_from_project_refusal(self):
        d = workflow.onboarding("declined", selected=True, general_chat_requested=True)
        self.assertEqual(d["action"], "end_careerground")
        self.assertFalse(d["collect_career"])
        self.assertTrue(workflow.onboarding("declined", selected=True)["collect_career"])

    def test_invalid_state_and_count_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_PROJECT_STATE"):
            workflow.onboarding("invented", selected=True)
        with self.assertRaisesRegex(ValueError, "INVALID_BASELINE_COUNT"):
            workflow.onboarding("ready", baseline_count=-1)

    def test_final_reply_respects_data_selection_independent_of_project(self):
        question = "직접 수행한 업무를 알려주세요."
        d = workflow.onboarding("declined")
        self.assertEqual(workflow.final_reply(d, question), d["reply"])
        d = workflow.onboarding("declined", selected=True)
        self.assertEqual(workflow.final_reply(d, question), question)
        with self.assertRaisesRegex(ValueError, "INVALID_PROPOSED_REPLY"):
            workflow.final_reply(d, "가" * 10000)

    def test_cli_respects_nonproject_selection_and_does_not_read_unselected_draft(self):
        script = ROOT / "plugins/careerground-portable/references/workflow.py"
        result = subprocess.run(
            [sys.executable, str(script), "declined", "--selected"],
            capture_output=True,
            text=True,
            check=True,
        )
        d = json.loads(result.stdout)
        self.assertTrue(d["collect_career"])
        self.assertFalse(d["project_verified"])
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "ready",
                "--reply-only",
                "--proposed-reply",
                "/nonexistent-unselected-draft.txt",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), workflow.selection_reply("choose_empty_start"))


class JDWorkflowTests(unittest.TestCase):
    def test_only_reviewed_public_fields_reach_query(self):
        self.assertEqual(
            workflow.public_search_query(
                {"role": "운영 문서화", "region": "서울"}, user_approved=True
            ),
            "서울 운영 문서화 채용",
        )
        for data in [
            {"profile": "기밀 경력"},
            {"role": "name@example.com"},
            {"role": "연락처 01012345678"},
            {"role": "비공개\n성과"},
        ]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                workflow.public_search_query(data, user_approved=True)
        with self.assertRaises(ValueError):
            workflow.public_search_query({"role": "개발자"})

    def test_access_and_status_limits_have_explicit_fallbacks(self):
        for access in ["search_unavailable", "unavailable", "login_required"]:
            self.assertEqual(workflow.discovery_fallback(access), "manual_jd_with_uncertainty")
        self.assertEqual(
            workflow.discovery_fallback("read", "closed"), "exclude_closed_or_use_as_reference"
        )
        self.assertEqual(workflow.discovery_fallback("read"), "show_status_unknown")

    def test_new_fact_is_reviewed_separately(self):
        self.assertEqual(workflow.change_route(changes_facts=True), "fact_candidate_review")
        self.assertEqual(workflow.change_route(changes_facts=False), "wording_review")

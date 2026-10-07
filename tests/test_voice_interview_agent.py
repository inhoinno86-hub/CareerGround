import copy
import json
import os
import unittest

from voice_interview_reference import (
    VoiceContractError,
    allow_automatic_followup,
    apply_event,
    confirm_transcript,
    create_evidence_candidate,
    invalidate_derived_outputs,
    new_session,
    retention_deadlines,
    run_scenario,
    validate_assessment,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class VoiceInterviewAgentContractTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "fixtures", "voice_interview", "session_scenarios.json"), encoding="utf-8") as handle:
            self.scenarios = json.load(handle)

    def assertVoiceError(self, code, function, *args, **kwargs):
        with self.assertRaises(VoiceContractError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_declared_state_scenarios(self):
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario["name"]):
                session, error = run_scenario(scenario)
                self.assertEqual(session["state"], scenario["expected_state"])
                self.assertEqual(error, scenario.get("expected_error"))
                self.assertEqual(session.get("notice"), scenario.get("expected_notice"))

    def test_preflight_requires_notices_and_input_or_text_fallback(self):
        session = apply_event(new_session(), {"event": "BEGIN_PREFLIGHT"})
        self.assertVoiceError("PREFLIGHT_INCOMPLETE", apply_event, session, {"event": "ACCEPT_PREFLIGHT", "input_ready": True})
        self.assertVoiceError("MICROPHONE_UNAVAILABLE", apply_event, session, {"event": "ACCEPT_PREFLIGHT", "notices_accepted": True, "input_ready": False})

    def test_recording_defaults_off(self):
        self.assertFalse(new_session()["recording_enabled"])
        self.assertVoiceError("RECORDING_CONSENT_REQUIRED", new_session, recording_enabled=True)
        self.assertTrue(new_session(recording_enabled=True, recording_selected_by_user=True)["recording_enabled"])

    def test_start_requires_valid_single_use_matching_package(self):
        ready = new_session()
        ready["state"] = "READY"
        valid = {"event": "START", "package_valid": True, "subject_matches": True, "package_status": "ISSUED", "existing_session": False}
        self.assertTrue(apply_event(ready, valid)["package_consumed"])
        for changed in (
            {"package_valid": False}, {"subject_matches": False}, {"package_status": "REVOKED"}
        ):
            event = dict(valid); event.update(changed)
            with self.subTest(changed=changed):
                self.assertVoiceError("INTERVIEW_PACKAGE_INVALID", apply_event, ready, event)
        event = dict(valid); event["existing_session"] = True
        self.assertVoiceError("INTERVIEW_ALREADY_STARTED", apply_event, ready, event)

    def test_followup_cap_is_two_unless_user_requests_more(self):
        self.assertTrue(allow_automatic_followup(0))
        self.assertTrue(allow_automatic_followup(1))
        self.assertFalse(allow_automatic_followup(2))
        self.assertTrue(allow_automatic_followup(2, user_requested=True))

    def test_only_final_user_transcript_can_be_confirmed(self):
        base = {"speaker": "USER", "status": "FINAL_CANDIDATE", "text": "초안", "version": 0}
        confirmed = confirm_transcript(base, "수정된 확정 답변")
        self.assertEqual((confirmed["status"], confirmed["version"], confirmed["text"]), ("CONFIRMED", 1, "수정된 확정 답변"))
        partial = dict(base, status="PARTIAL")
        self.assertVoiceError("TRANSCRIPT_NOT_FINAL", confirm_transcript, partial)
        agent = dict(base, speaker="AGENT")
        self.assertVoiceError("TRANSCRIPT_SOURCE_INVALID", confirm_transcript, agent)

    def test_transcript_edit_invalidates_old_assessment_and_candidate(self):
        outputs = [
            {"type": "assessment", "transcript_version": 1},
            {"type": "candidate", "transcript_version": 2},
        ]
        invalidated = invalidate_derived_outputs(outputs, 2)
        self.assertTrue(invalidated[0]["stale"])
        self.assertNotIn("stale", invalidated[1])

    def test_candidate_requires_confirmed_user_source_and_atomic_text(self):
        turn = {"speaker": "USER", "status": "CONFIRMED", "session_id": "S-1", "turn_id": "T-1", "version": 2}
        candidate = create_evidence_candidate(turn, "SIL 자동화 스크립트를 작성했다.")
        self.assertEqual(candidate["status"], "PENDING")
        followup = create_evidence_candidate(turn, "새 수치 성과", duplicate_or_conflict="POSSIBLE_CONFLICT")
        self.assertEqual(followup["status"], "NEEDS_FOLLOWUP")
        self.assertVoiceError("CANDIDATE_NOT_ATOMIC", create_evidence_candidate, turn, "A와 B를 하고 C를 검증했다.", atomic=False)
        partial = dict(turn, status="PARTIAL")
        self.assertVoiceError("CANDIDATE_SOURCE_INVALID", create_evidence_candidate, partial, "사실")

    def test_agent_or_generated_text_cannot_be_candidate_source(self):
        agent_turn = {"speaker": "AGENT", "status": "CONFIRMED", "session_id": "S-1", "turn_id": "T-2", "version": 1}
        self.assertVoiceError("CANDIDATE_SOURCE_INVALID", create_evidence_candidate, agent_turn, "AI가 만든 요약")

    def test_assessment_allows_only_approved_traceable_dimensions(self):
        valid = {"dimension": "OWNERSHIP_ACCURACY", "turn_id": "T-1", "transcript_version": 1, "result": "ALIGNED"}
        self.assertTrue(validate_assessment(valid))
        for dimension in ("ACCENT", "EMOTION", "PERSONALITY", "AGE"):
            with self.subTest(dimension=dimension):
                invalid = dict(valid, dimension=dimension)
                self.assertVoiceError("ASSESSMENT_DIMENSION_PROHIBITED", validate_assessment, invalid)

    def test_hiring_probability_result_is_prohibited(self):
        assessment = {"dimension": "QUESTION_RELEVANCE", "turn_id": "T-1", "transcript_version": 1, "result": "PASS_PROBABILITY"}
        self.assertVoiceError("ASSESSMENT_RESULT_PROHIBITED", validate_assessment, assessment)

    def test_retention_is_90_days_and_optional_recording_is_30_days(self):
        without_recording = retention_deadlines("2026-09-23T00:00:00Z", False)
        self.assertEqual(without_recording["transcript_retention_until"], "2026-12-22T00:00:00+00:00")
        self.assertIsNone(without_recording["recording_retention_until"])
        with_recording = retention_deadlines("2026-09-23T00:00:00Z", True)
        self.assertEqual(with_recording["recording_retention_until"], "2026-10-23T00:00:00+00:00")

    def test_input_objects_are_not_mutated(self):
        session = new_session(); original = copy.deepcopy(session)
        apply_event(session, {"event": "BEGIN_PREFLIGHT"})
        self.assertEqual(session, original)


if __name__ == "__main__":
    unittest.main()

"""Dependency-free behavioral reference for Voice Interview Agent v1 tests.

This models approved state and policy guards only.  It is not a realtime audio,
storage, authentication, or production agent implementation.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta


TERMINAL_STATES = {"COMPLETED", "ABORTED", "FAILED", "DATA_REVOKED"}
COMPLETION_REASONS = {"PLAN_COMPLETED", "USER_ENDED_EARLY", "RESUME_WINDOW_EXPIRED", "TIME_BUDGET_REACHED"}
ALLOWED_ASSESSMENT_DIMENSIONS = {
    "QUESTION_RELEVANCE", "SPECIFICITY", "STRUCTURE",
    "EVIDENCE_ALIGNMENT", "OWNERSHIP_ACCURACY", "JD_CONNECTION",
}
PROHIBITED_ASSESSMENT_DIMENSIONS = {
    "ACCENT", "DIALECT", "VOICE_TONE", "EMOTION", "PERSONALITY",
    "DISABILITY", "GENDER", "AGE", "RACE", "RELIGION", "APPEARANCE",
}


class VoiceContractError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _fail(code, detail=""):
    raise VoiceContractError(code, detail)


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def new_session(recording_enabled=False, recording_selected_by_user=False):
    if recording_enabled and not recording_selected_by_user:
        _fail("RECORDING_CONSENT_REQUIRED")
    return {
        "state": "CREATED",
        "recording_enabled": bool(recording_enabled),
        "paused_at": None,
        "resume_until": None,
        "completion_reason": None,
        "notice": None,
        "package_consumed": False,
    }


def apply_event(session, event):
    result = deepcopy(session)
    state = result["state"]
    name = event["event"]
    if state in TERMINAL_STATES:
        _fail("INVALID_SESSION_TRANSITION", "terminal state is immutable")

    if state == "CREATED" and name == "BEGIN_PREFLIGHT":
        result["state"] = "PREFLIGHT"
    elif state == "PREFLIGHT" and name == "ACCEPT_PREFLIGHT":
        if not event.get("notices_accepted"):
            _fail("PREFLIGHT_INCOMPLETE", "required notices are not accepted")
        if not event.get("input_ready"):
            _fail("MICROPHONE_UNAVAILABLE", "neither microphone nor text fallback is ready")
        result["state"] = "READY"
    elif state == "PREFLIGHT" and name == "CANCEL":
        result["state"] = "ABORTED"
    elif state == "READY" and name == "START":
        if not event.get("package_valid") or not event.get("subject_matches") or event.get("package_status") != "ISSUED":
            _fail("INTERVIEW_PACKAGE_INVALID")
        if event.get("existing_session"):
            _fail("INTERVIEW_ALREADY_STARTED")
        result["package_consumed"] = True
        result["state"] = "IN_PROGRESS"
    elif state == "READY" and name == "PACKAGE_REVOKED":
        result["state"] = "DATA_REVOKED"
    elif state == "READY" and name == "CANCEL":
        result["state"] = "ABORTED"
    elif state == "IN_PROGRESS" and name == "PAUSE":
        paused_at = _time(event.get("at", "2026-09-23T00:00:00Z"))
        result.update({"state": "PAUSED", "paused_at": paused_at.isoformat(), "resume_until": (paused_at + timedelta(hours=24)).isoformat()})
    elif state == "IN_PROGRESS" and name == "FINISH":
        if event.get("confirmed_answer_count", 0) < 1:
            _fail("INVALID_SESSION_TRANSITION", "no confirmed answer to complete")
        reason = event.get("completion_reason")
        if reason not in COMPLETION_REASONS:
            _fail("INVALID_COMPLETION_REASON")
        result.update({"state": "COMPLETING", "completion_reason": reason})
    elif state == "IN_PROGRESS" and name == "DATA_WITHDRAWN":
        result["state"] = "DATA_REVOKED"
    elif state == "IN_PROGRESS" and name == "UNRECOVERABLE_FAILURE":
        result["state"] = "FAILED"
    elif state == "PAUSED" and name == "RESUME":
        now = _time(event["at"])
        if now > _time(result["resume_until"]):
            result.update({"state": "COMPLETING", "completion_reason": "RESUME_WINDOW_EXPIRED", "notice": "SESSION_RESUME_EXPIRED"})
        elif not event.get("subject_matches") or event.get("package_status") != "ISSUED":
            result["state"] = "DATA_REVOKED"
        else:
            result["state"] = "IN_PROGRESS"
    elif state == "PAUSED" and name == "FINISH":
        reason = event.get("completion_reason", "USER_ENDED_EARLY")
        if reason not in COMPLETION_REASONS:
            _fail("INVALID_COMPLETION_REASON")
        result.update({"state": "COMPLETING", "completion_reason": reason})
    elif state == "PAUSED" and name == "DATA_WITHDRAWN":
        result["state"] = "DATA_REVOKED"
    elif state == "COMPLETING" and name == "COMMIT_RESULTS":
        result["state"] = "COMPLETED"
    elif state == "COMPLETING" and name == "PERSISTENCE_RETRY":
        result["state"] = "COMPLETING"
    elif state == "COMPLETING" and name == "UNRECOVERABLE_FAILURE":
        result["state"] = "FAILED"
    else:
        _fail("INVALID_SESSION_TRANSITION", f"{state} + {name}")
    return result


def run_scenario(scenario):
    session = new_session()
    error = None
    for event in scenario["events"]:
        try:
            session = apply_event(session, event)
        except VoiceContractError as exc:
            error = exc.code
            break
    return session, error


def allow_automatic_followup(consecutive_count, user_requested=False):
    if consecutive_count < 0:
        _fail("INVALID_FOLLOWUP_COUNT")
    return consecutive_count < 2 or bool(user_requested)


def confirm_transcript(turn, corrected_text=None):
    if turn.get("speaker") != "USER":
        _fail("TRANSCRIPT_SOURCE_INVALID")
    if turn.get("status") not in {"FINAL_CANDIDATE", "AWAITING_CORRECTION"}:
        _fail("TRANSCRIPT_NOT_FINAL")
    result = deepcopy(turn)
    if corrected_text is not None:
        if not corrected_text.strip(): _fail("TRANSCRIPT_EMPTY")
        result["text"] = corrected_text
    result["status"] = "CONFIRMED"
    result["version"] = int(turn.get("version", 0)) + 1
    return result


def invalidate_derived_outputs(outputs, current_transcript_version):
    result = deepcopy(outputs)
    for item in result:
        if item.get("transcript_version") != current_transcript_version:
            item["stale"] = True
    return result


def create_evidence_candidate(turn, candidate_text, atomic=True, duplicate_or_conflict=None):
    if turn.get("speaker") != "USER" or turn.get("status") != "CONFIRMED":
        _fail("CANDIDATE_SOURCE_INVALID")
    if not atomic or not candidate_text.strip():
        _fail("CANDIDATE_NOT_ATOMIC")
    return {
        "candidate_text": candidate_text,
        "session_id": turn["session_id"],
        "turn_id": turn["turn_id"],
        "transcript_version": turn["version"],
        "status": "NEEDS_FOLLOWUP" if duplicate_or_conflict else "PENDING",
        "duplicate_or_conflict": duplicate_or_conflict,
    }


def validate_assessment(assessment):
    dimension = assessment.get("dimension")
    if dimension in PROHIBITED_ASSESSMENT_DIMENSIONS or dimension not in ALLOWED_ASSESSMENT_DIMENSIONS:
        _fail("ASSESSMENT_DIMENSION_PROHIBITED")
    if not assessment.get("turn_id") or not isinstance(assessment.get("transcript_version"), int):
        _fail("ASSESSMENT_TRACE_INVALID")
    if assessment.get("result") == "PASS_PROBABILITY":
        _fail("ASSESSMENT_RESULT_PROHIBITED")
    return True


def retention_deadlines(completed_at, recording_enabled):
    completed = _time(completed_at)
    return {
        "transcript_retention_until": (completed + timedelta(days=90)).isoformat(),
        "recording_retention_until": (completed + timedelta(days=30)).isoformat() if recording_enabled else None,
    }

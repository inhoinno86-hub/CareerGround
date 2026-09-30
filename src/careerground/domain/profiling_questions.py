"""Deterministic, read-only question planner for Profiling Protocol v1.

This planner consumes structured observations supplied by a future trusted
workspace adapter. It never interprets raw text, stores an answer, confirms a
Claim, or changes a profile version.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ProtocolState(StrEnum):
    CONTEXT_DISCOVERY = "CONTEXT_DISCOVERY"
    ROLE_DISCOVERY = "ROLE_DISCOVERY"
    PROJECT_DISCOVERY = "PROJECT_DISCOVERY"
    RESPONSIBILITY_DISCOVERY = "RESPONSIBILITY_DISCOVERY"
    CONTRIBUTION_DISCOVERY = "CONTRIBUTION_DISCOVERY"
    OWNERSHIP_PROBING = "OWNERSHIP_PROBING"
    TECHNICAL_DEPTH_PROBING = "TECHNICAL_DEPTH_PROBING"
    VALIDATION_PROBING = "VALIDATION_PROBING"
    OUTCOME_PROBING = "OUTCOME_PROBING"
    EVIDENCE_CAPTURE = "EVIDENCE_CAPTURE"
    CLAIM_DRAFTING = "CLAIM_DRAFTING"
    CLAIM_CONFIRMATION = "CLAIM_CONFIRMATION"
    BOUNDARY_CHECK = "BOUNDARY_CHECK"
    COMPLETE = "COMPLETE"


class ObservationStatus(StrEnum):
    SATISFIED = "SATISFIED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


_ORDER = tuple(state for state in ProtocolState if state is not ProtocolState.COMPLETE)
_OPTIONAL_UNKNOWN = frozenset(
    {
        ProtocolState.RESPONSIBILITY_DISCOVERY,
        ProtocolState.VALIDATION_PROBING,
        ProtocolState.OUTCOME_PROBING,
    }
)
_QUESTIONS: dict[ProtocolState, tuple[str, str]] = {
    ProtocolState.CONTEXT_DISCOVERY: (
        "어느 조직이나 활동에서 한 경험인가요? 비공개 별칭도 괜찮습니다.",
        "다른 경험과 구별할 수 있도록 조직 또는 활동 맥락을 한 가지 알려주세요.",
    ),
    ProtocolState.ROLE_DISCOVERY: (
        "당시 맡은 역할은 무엇이었나요?",
        "그 경험에서 본인의 역할이나 직무를 한 가지로 특정해 주세요.",
    ),
    ProtocolState.PROJECT_DISCOVERY: (
        "어느 프로젝트의 어떤 기능에 관한 경험인가요?",
        "프로젝트 전체와 본인이 맡은 기능 범위를 구분해 주세요.",
    ),
    ProtocolState.RESPONSIBILITY_DISCOVERY: (
        "공식적으로 맡은 책임은 무엇이었나요?",
        "공식 책임을 확인하기 어렵다면 그 이유를 알려주세요.",
    ),
    ProtocolState.CONTRIBUTION_DISCOVERY: (
        "본인이 직접 수행한 작업은 무엇이었나요?",
        "팀 결과와 구분해 본인이 직접 한 작업 한 가지를 알려주세요.",
    ),
    ProtocolState.OWNERSHIP_PROBING: (
        "그 작업의 담당 범위와 최종 결정자는 누구였나요?",
        "본인의 실행·검증 책임과 최종 결정권을 각각 구분해 주세요.",
    ),
    ProtocolState.TECHNICAL_DEPTH_PROBING: (
        "직접 설계하거나 구현한 부분은 정확히 어디까지인가요?",
        "선정 전후를 구분해 직접 설계·구현한 범위를 한 가지로 좁혀 주세요.",
    ),
    ProtocolState.VALIDATION_PROBING: (
        "어떤 검증을 직접 수행했고 승인자는 누구였나요?",
        "검증 방법과 본인의 수행·승인 책임을 나눠 알려주세요.",
    ),
    ProtocolState.OUTCOME_PROBING: (
        "결과가 있었나요? 수치라면 근거가 있나요?",
        "확인되지 않은 수치는 빼고 알려진 결과나 근거를 알려주세요.",
    ),
    ProtocolState.EVIDENCE_CAPTURE: (
        "이 작업을 뒷받침하는 발화나 자료의 출처는 무엇인가요?",
        "AI 초안 외에 사용자가 제공한 발화·자료의 출처를 한 가지 지정해 주세요.",
    ),
    ProtocolState.CLAIM_DRAFTING: (
        "확인할 사실을 한 문장씩 나눠 제시해 주세요.",
        "설계·구현·검증을 각각 독립적으로 확인할 수 있게 나눠 주세요.",
    ),
    ProtocolState.CLAIM_CONFIRMATION: (
        "각 문장과 담당 범위가 정확한지 항목별로 확인해 주세요.",
        "아직 확인하지 않은 문장은 승인하지 않고 별도로 표시해 주세요.",
    ),
    ProtocolState.BOUNDARY_CHECK: (
        "본인이 했다고 말하면 안 되는 부분이나 타인의 담당은 무엇인가요?",
        "최종 결정·전체 소유·성과로 확대하면 안 되는 범위를 확인해 주세요.",
    ),
}


@dataclass(frozen=True)
class ProtocolObservation:
    state: ProtocolState
    status: ObservationStatus
    source_input_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not ProtocolState or self.state is ProtocolState.COMPLETE:
            raise ValueError("invalid observed protocol state")
        if type(self.status) is not ObservationStatus:
            raise ValueError("invalid observation status")
        if self.source_input_id is not None and (
            not isinstance(self.source_input_id, str)
            or not self.source_input_id.strip()
            or len(self.source_input_id) > 128
        ):
            raise ValueError("invalid observation source")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 1000
        ):
            raise ValueError("invalid observation reason")
        if self.status in {ObservationStatus.SATISFIED, ObservationStatus.CONFLICT} and (
            self.source_input_id is None
        ):
            raise ValueError("sourced observation required")
        if self.status in {ObservationStatus.UNKNOWN, ObservationStatus.CONFLICT} and (
            self.reason is None
        ):
            raise ValueError("unknown or conflicting observation needs a reason")


@dataclass(frozen=True)
class QuestionPlan:
    state: ProtocolState
    question: str | None
    question_attempt: int
    blocked: bool
    unknown_fields: tuple[ProtocolState, ...]

    @property
    def complete(self) -> bool:
        return self.state is ProtocolState.COMPLETE


def plan_next_question(
    observations: Mapping[ProtocolState, ProtocolObservation],
    asked_counts: Mapping[ProtocolState, int],
) -> QuestionPlan:
    """Ask at most twice per state; never turn silence into a satisfied guard.

    `SATISFIED` means a future adapter has linked an explicit source input to
    that guard. This planner cannot verify the meaning of that input. It also
    cannot issue a factual approval or authorize canonical promotion.
    """

    for state, observation in observations.items():
        if type(state) is not ProtocolState or state is ProtocolState.COMPLETE:
            raise ValueError("invalid observation key")
        if type(observation) is not ProtocolObservation or observation.state is not state:
            raise ValueError("observation state mismatch")
    for state, count in asked_counts.items():
        if type(state) is not ProtocolState or state is ProtocolState.COMPLETE:
            raise ValueError("invalid question count key")
        if type(count) is not int or not 0 <= count <= 2:
            raise ValueError("question count must be between zero and two")

    unknown_fields: list[ProtocolState] = []
    for state in _ORDER:
        observation = observations.get(state)
        count = asked_counts.get(state, 0)
        if observation is not None and observation.status is ObservationStatus.SATISFIED:
            continue
        if observation is not None and observation.status is ObservationStatus.UNKNOWN:
            if state in _OPTIONAL_UNKNOWN:
                unknown_fields.append(state)
                continue
            return QuestionPlan(state, None, count, True, tuple(unknown_fields))
        if count >= 2:
            return QuestionPlan(state, None, count, True, tuple(unknown_fields))
        return QuestionPlan(
            state, _QUESTIONS[state][count], count + 1, False, tuple(unknown_fields)
        )
    # Protocol v1's COMPLETE also requires the separate §7 review checklist.
    # A question planner has no authority to certify those exact reviews.
    return QuestionPlan(
        ProtocolState.BOUNDARY_CHECK,
        None,
        asked_counts.get(ProtocolState.BOUNDARY_CHECK, 0),
        True,
        tuple(unknown_fields),
    )


def question_for(state: ProtocolState, attempt: int) -> str:
    """Reconstruct an already recorded delivery without consuming another attempt."""

    if type(state) is not ProtocolState or state is ProtocolState.COMPLETE:
        raise ValueError("invalid question state")
    if type(attempt) is not int or attempt not in (1, 2):
        raise ValueError("invalid question attempt")
    return _QUESTIONS[state][attempt - 1]

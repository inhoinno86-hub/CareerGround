"""Temporary owner-scoped question progress; no text interpretation or Claim approval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from careerground.domain.profiling_questions import (
    ObservationStatus,
    ProtocolObservation,
    ProtocolState,
    QuestionPlan,
    plan_next_question,
    question_for,
)
from careerground.domain.profiling_workspace import (
    AUTO_PAUSE_AFTER,
    ProfilingPaused,
    ProfilingValidationError,
    ProfilingVersionConflict,
    _as_utc,
    _ensure_available,
    _owned_work,
    _require_utc,
)
from careerground.storage.models import ProfilingInput, ProfilingProtocolStep

_DELIVERY_KEY = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")


@dataclass(frozen=True)
class QuestionDelivery:
    state: ProtocolState
    attempt: int
    question: str
    replayed: bool


@dataclass(frozen=True)
class ProtocolProgressStep:
    state: ProtocolState
    asked_count: int
    observation_status: ObservationStatus | None


@dataclass(frozen=True)
class ProtocolProgress:
    current_state: ProtocolState
    blocked: bool
    steps: tuple[ProtocolProgressStep, ...]


def get_protocol_progress(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> ProtocolProgress:
    """Read current-cycle state/count metadata without delivering a question or source text."""

    work, _now = _workspace(session, account_id, profiling_session_id, now, write=False)
    rows = _steps(session, account_id, profiling_session_id, work.protocol_cycle)
    by_state = {row.state: row for row in rows}
    plan = _plan(rows)
    return ProtocolProgress(
        current_state=plan.state,
        blocked=plan.blocked,
        steps=tuple(
            ProtocolProgressStep(
                state=state,
                asked_count=by_state[state.value].asked_count if state.value in by_state else 0,
                observation_status=(
                    ObservationStatus(by_state[state.value].observation_status)
                    if state.value in by_state
                    and by_state[state.value].observation_status is not None
                    else None
                ),
            )
            for state in ProtocolState
            if state is not ProtocolState.COMPLETE
        ),
    )


def _workspace(session: Session, account_id: str, work_id: str, now: datetime, *, write: bool):
    now = _require_utc(now)
    work, profile = _owned_work(session, account_id, work_id, for_update=write)
    _ensure_available(work, now)
    if work.base_profile_version != profile.version:
        raise ProfilingVersionConflict
    return work, now


def _steps(
    session: Session, account_id: str, work_id: str, protocol_cycle: int
) -> list[ProfilingProtocolStep]:
    return list(
        session.scalars(
            select(ProfilingProtocolStep).where(
                ProfilingProtocolStep.account_id == account_id,
                ProfilingProtocolStep.session_id == work_id,
                ProfilingProtocolStep.protocol_cycle == protocol_cycle,
            )
        )
    )


def _plan(rows: list[ProfilingProtocolStep]) -> QuestionPlan:
    observations = {}
    counts = {}
    for row in rows:
        state = ProtocolState(row.state)
        counts[state] = row.asked_count
        if row.observation_status is not None:
            observations[state] = ProtocolObservation(
                state=state,
                status=ObservationStatus(row.observation_status),
                source_input_id=row.source_input_id,
                reason=row.reason,
            )
    return plan_next_question(observations, counts)


def get_protocol_question_plan(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> QuestionPlan:
    """Read current question without counting a delivery or refreshing retention."""

    work, _now = _workspace(session, account_id, profiling_session_id, now, write=False)
    return _plan(_steps(session, account_id, profiling_session_id, work.protocol_cycle))


def record_question_delivery(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    delivery_key: str,
    now: datetime,
) -> QuestionDelivery:
    """Count a question only when a trusted caller delivers it to the user."""

    if not isinstance(delivery_key, str) or not _DELIVERY_KEY.fullmatch(delivery_key):
        raise ProfilingValidationError("invalid question delivery key")
    work, now = _workspace(session, account_id, profiling_session_id, now, write=True)
    matching = list(
        session.scalars(
            select(ProfilingProtocolStep).where(
                ProfilingProtocolStep.account_id == account_id,
                ProfilingProtocolStep.session_id == profiling_session_id,
                or_(
                    ProfilingProtocolStep.first_delivery_key == delivery_key,
                    ProfilingProtocolStep.second_delivery_key == delivery_key,
                ),
            )
        )
    )
    if len(matching) > 1:
        raise ProfilingValidationError("ambiguous question delivery key")
    if matching:
        row = matching[0]
        if row.protocol_cycle != work.protocol_cycle:
            raise ProfilingValidationError("question delivery key belongs to an earlier cycle")
        attempt = 1 if row.first_delivery_key == delivery_key else 2
        state = ProtocolState(row.state)
        return QuestionDelivery(state, attempt, question_for(state, attempt), True)
    if work.status != "ACTIVE" or now - _as_utc(work.last_activity_at) >= AUTO_PAUSE_AFTER:
        raise ProfilingPaused
    rows = _steps(session, account_id, profiling_session_id, work.protocol_cycle)
    plan = _plan(rows)
    if plan.question is None:
        raise ProfilingValidationError("question flow is blocked or complete")
    row = next((item for item in rows if item.state == plan.state.value), None)
    if row is None:
        row = ProfilingProtocolStep(
            id=str(uuid4()),
            account_id=account_id,
            session_id=profiling_session_id,
            protocol_cycle=work.protocol_cycle,
            state=plan.state.value,
            asked_count=0,
            updated_at=now,
        )
        session.add(row)
    row.asked_count = plan.question_attempt
    if plan.question_attempt == 1:
        row.first_delivery_key = delivery_key
    else:
        row.second_delivery_key = delivery_key
    row.updated_at = now
    return QuestionDelivery(plan.state, plan.question_attempt, plan.question, False)


def record_protocol_observation(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    observation: ProtocolObservation,
    now: datetime,
) -> QuestionPlan:
    """Record a structured observation from a trusted caller, never infer from raw text."""

    if type(observation) is not ProtocolObservation:
        raise ProfilingValidationError("invalid protocol observation")
    work, now = _workspace(session, account_id, profiling_session_id, now, write=True)
    if work.status != "ACTIVE" or now - _as_utc(work.last_activity_at) >= AUTO_PAUSE_AFTER:
        raise ProfilingPaused
    rows = _steps(session, account_id, profiling_session_id, work.protocol_cycle)
    plan = _plan(rows)
    if plan.state is not observation.state:
        raise ProfilingValidationError("observation is not for the current question")
    row = next((item for item in rows if item.state == observation.state.value), None)
    if row is None or row.asked_count == 0:
        raise ProfilingValidationError("question must be delivered before observation")
    if observation.status is ObservationStatus.UNKNOWN and row.asked_count < 2:
        raise ProfilingValidationError("unknown requires both question attempts")
    if observation.source_input_id is not None and (
        len(observation.source_input_id) > 36
        or session.scalar(
            select(ProfilingInput.id).where(
                ProfilingInput.id == observation.source_input_id,
                ProfilingInput.account_id == account_id,
                ProfilingInput.session_id == profiling_session_id,
                ProfilingInput.protocol_cycle == work.protocol_cycle,
            )
        )
        is None
    ):
        raise ProfilingValidationError("observation source must belong to this workspace")
    row.observation_status = observation.status.value
    row.source_input_id = observation.source_input_id
    row.reason = observation.reason
    row.updated_at = now
    return _plan(rows)

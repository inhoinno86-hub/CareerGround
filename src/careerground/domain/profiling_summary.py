"""Owner-scoped, read-only status for a temporary profiling workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careerground.domain.profiling_protocol_workspace import get_protocol_question_plan
from careerground.domain.profiling_workspace import (
    ProfilingSessionView,
    ProfilingVersionConflict,
    _as_utc,
    get_profiling_session,
)
from careerground.storage.models import ProfilingDraft, ProfilingReviewBatch


@dataclass(frozen=True)
class PendingReviewSummary:
    batch_id: str
    scope_key: str
    expires_at: datetime


@dataclass(frozen=True)
class ProfilingWorkspaceSummary:
    session: ProfilingSessionView
    protocol_state: str | None
    protocol_blocked: bool | None
    draft_counts: tuple[tuple[str, int], ...]
    pending_reviews: tuple[PendingReviewSummary, ...]


@dataclass(frozen=True)
class ProfilingDraftListItem:
    draft_id: str
    scope_key: str
    claim_type: str
    exact_text: str
    status: str


@dataclass(frozen=True)
class ProfilingDraftList:
    session: ProfilingSessionView
    items: tuple[ProfilingDraftListItem, ...]
    more_items: bool


def list_profiling_drafts_for_review(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> ProfilingDraftList:
    """Show bounded, unexpired proposed wording; never grant approval or refresh retention."""

    view = get_profiling_session(
        session, account_id=account_id, profiling_session_id=profiling_session_id, now=now
    )
    rows = tuple(
        session.scalars(
            select(ProfilingDraft)
            .where(
                ProfilingDraft.account_id == account_id,
                ProfilingDraft.session_id == profiling_session_id,
                ProfilingDraft.expires_at > now.astimezone(UTC),
            )
            .order_by(ProfilingDraft.created_at, ProfilingDraft.id)
            .limit(51)
        )
    )
    return ProfilingDraftList(
        session=view,
        items=tuple(
            ProfilingDraftListItem(
                item.id, item.scope_key, item.claim_type, item.exact_text, item.status
            )
            for item in rows[:50]
        ),
        more_items=len(rows) > 50,
    )


def get_profiling_workspace_summary(
    session: Session, *, account_id: str, profiling_session_id: str, now: datetime
) -> ProfilingWorkspaceSummary:
    """Read only metadata after validating the active owner and session lifetime."""

    view = get_profiling_session(
        session, account_id=account_id, profiling_session_id=profiling_session_id, now=now
    )
    try:
        plan = get_protocol_question_plan(
            session, account_id=account_id, profiling_session_id=profiling_session_id, now=now
        )
        protocol_state, protocol_blocked = plan.state.value, plan.blocked
    except ProfilingVersionConflict:
        protocol_state, protocol_blocked = None, True
    draft_counts = tuple(
        (status, count)
        for status, count in session.execute(
            select(ProfilingDraft.status, func.count())
            .where(
                ProfilingDraft.account_id == account_id,
                ProfilingDraft.session_id == profiling_session_id,
            )
            .group_by(ProfilingDraft.status)
            .order_by(ProfilingDraft.status)
        )
    )
    now_utc = now.astimezone(UTC)
    pending = tuple(
        PendingReviewSummary(batch.id, batch.scope_key, _as_utc(batch.expires_at))
        for batch in session.scalars(
            select(ProfilingReviewBatch)
            .where(
                ProfilingReviewBatch.account_id == account_id,
                ProfilingReviewBatch.session_id == profiling_session_id,
                ProfilingReviewBatch.status == "PREPARED",
                ProfilingReviewBatch.expires_at > now_utc,
            )
            .order_by(ProfilingReviewBatch.created_at, ProfilingReviewBatch.id)
            .limit(10)
        )
    )
    return ProfilingWorkspaceSummary(
        session=view,
        protocol_state=protocol_state,
        protocol_blocked=protocol_blocked,
        draft_counts=draft_counts,
        pending_reviews=pending,
    )

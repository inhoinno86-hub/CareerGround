"""Deterministic verbatim candidate spans for an explicit profiling input.

Future AI adapters may propose character spans only. This module never calls a
provider, infers a fact, certifies atomicity, or approves a Claim.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.claim_review_workspace import ReviewUnavailable, propose_verbatim_draft
from careerground.domain.profiling_workspace import MAX_INPUT_CHARS, _as_utc, _owned_work
from careerground.domain.project_scope_guard import deleted_project_scope_exists
from careerground.storage.models import ProfilingDraft, ProfilingInput

MAX_DRAFT_SPANS = 5
MAX_DRAFT_SPAN_CHARS = 1_000
_BULLET_DRAFT_NAMESPACE = UUID("fe587042-75c0-446f-900b-3a9d857145df")


class DraftSpanRejected(ValueError):
    """The proposal cannot be mapped to bounded, exact source text."""


@dataclass(frozen=True)
class DraftSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or self.start < 0
            or self.end <= self.start
        ):
            raise DraftSpanRejected("invalid source span")


@dataclass(frozen=True)
class VerbatimCandidate:
    span: DraftSpan
    exact_text: str
    atomicity: str = "UNVERIFIED"


def validate_draft_spans(
    source_text: str, spans: Sequence[DraftSpan]
) -> tuple[VerbatimCandidate, ...]:
    """Accept only one to five nonoverlapping single-line source slices."""

    if (
        not isinstance(source_text, str)
        or not source_text
        or len(source_text) > MAX_INPUT_CHARS
        or not isinstance(spans, (tuple, list))
        or not 1 <= len(spans) <= MAX_DRAFT_SPANS
        or any(type(span) is not DraftSpan for span in spans)
    ):
        raise DraftSpanRejected("invalid source or span batch")
    ordered = sorted(spans, key=lambda span: (span.start, span.end))
    if any(left.end > right.start for left, right in pairwise(ordered)):
        raise DraftSpanRejected("overlapping source spans")
    candidates: list[VerbatimCandidate] = []
    for span in spans:
        if span.end > len(source_text) or span.end - span.start > MAX_DRAFT_SPAN_CHARS:
            raise DraftSpanRejected("source span outside bounded input")
        exact_text = source_text[span.start : span.end]
        if (
            not exact_text
            or exact_text != exact_text.strip()
            or "\n" in exact_text
            or "\r" in exact_text
        ):
            raise DraftSpanRejected("source span must be one exact trimmed line")
        candidates.append(VerbatimCandidate(span, exact_text))
    return tuple(candidates)


def extract_explicit_bullet_spans(source_text: str) -> tuple[DraftSpan, ...]:
    """Offline helper: select only the text of user-formatted `- ` or `* ` lines."""

    if not isinstance(source_text, str) or not source_text or len(source_text) > MAX_INPUT_CHARS:
        raise DraftSpanRejected("invalid source text")
    spans: list[DraftSpan] = []
    offset = 0
    for line in source_text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if content.strip():
            leading = len(content) - len(content.lstrip(" \t"))
            if content[leading : leading + 2] not in ("- ", "* "):
                raise DraftSpanRejected("only explicit bullet lines can be segmented")
            start = offset + leading + 2
            end = offset + len(content.rstrip(" \t"))
            spans.append(DraftSpan(start, end))
        offset += len(line)
    validate_draft_spans(source_text, spans)
    return tuple(spans)


def parse_untrusted_span_proposal(
    source_text: str, payload: Mapping[str, object]
) -> tuple[DraftSpan, ...]:
    """Accept only character ranges from an untrusted future AI adapter output.

    The adapter cannot choose owner, scope, Claim type, wording, decision, or
    canonical write. All other keys are rejected rather than ignored.
    """

    if type(payload) is not dict or set(payload) != {"spans"}:
        raise DraftSpanRejected("adapter output may contain spans only")
    raw_spans = payload["spans"]
    if type(raw_spans) is not list or not 1 <= len(raw_spans) <= MAX_DRAFT_SPANS:
        raise DraftSpanRejected("invalid adapter span list")
    spans = []
    for raw in raw_spans:
        if type(raw) is not dict or set(raw) != {"start", "end"}:
            raise DraftSpanRejected("adapter span may contain start and end only")
        spans.append(DraftSpan(raw["start"], raw["end"]))
    validate_draft_spans(source_text, spans)
    return tuple(spans)


def propose_verbatim_span_drafts(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    source_input_id: str,
    scope_key: str,
    claim_type: str,
    spans: Sequence[DraftSpan],
    now: datetime,
) -> tuple[ProfilingDraft, ...]:
    """Persist bounded candidate text in the temporary DRAFT workspace only."""

    source = session.scalar(
        select(ProfilingInput).where(
            ProfilingInput.id == source_input_id,
            ProfilingInput.account_id == account_id,
            ProfilingInput.session_id == profiling_session_id,
        )
    )
    if source is None:
        raise ReviewUnavailable
    candidates = validate_draft_spans(source.body, spans)
    return tuple(
        propose_verbatim_draft(
            session,
            account_id=account_id,
            profiling_session_id=profiling_session_id,
            source_input_id=source_input_id,
            scope_key=scope_key,
            claim_type=claim_type,
            exact_text=candidate.exact_text,
            now=now,
        )
        for candidate in candidates
    )


def _propose_source_drafts_once(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    source_input_id: str,
    scope_key: str,
    now: datetime,
    proposed_spans: Sequence[DraftSpan] | None = None,
) -> tuple[ProfilingDraft, ...]:
    """Make at most five temporary CONTRIBUTION drafts from exact source spans.

    Stable IDs make a repeated confirmed browser form return the same exact rows.
    The caller owns the transaction; a partial or changed set is rejected.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise DraftSpanRejected("aware time required")
    work, profile = _owned_work(session, account_id, profiling_session_id)
    if (
        work.status not in {"ACTIVE", "PAUSED"}
        or _as_utc(work.retention_expires_at) <= now
        or profile.version != work.base_profile_version
    ):
        raise ReviewUnavailable
    if deleted_project_scope_exists(
        session, account_id=account_id, profile_id=profile.id, scope_key=scope_key
    ):
        raise ReviewUnavailable
    source = session.scalar(
        select(ProfilingInput).where(
            ProfilingInput.id == source_input_id,
            ProfilingInput.account_id == account_id,
            ProfilingInput.session_id == profiling_session_id,
            ProfilingInput.content_kind.in_(
                ("USER_STATEMENT", "CORRECTION")
                if proposed_spans is not None
                else ("USER_STATEMENT",)
            ),
        )
    )
    if source is None or source.protocol_cycle != work.protocol_cycle:
        raise ReviewUnavailable
    spans = extract_explicit_bullet_spans(source.body) if proposed_spans is None else proposed_spans
    candidates = validate_draft_spans(source.body, spans)
    draft_ids = tuple(
        str(
            uuid5(
                _BULLET_DRAFT_NAMESPACE,
                f"{account_id}:{profiling_session_id}:{source_input_id}:{scope_key}:"
                f"CONTRIBUTION:{candidate.span.start}:{candidate.span.end}",
            )
        )
        for candidate in candidates
    )
    source_drafts = tuple(
        session.scalars(
            select(ProfilingDraft).where(
                ProfilingDraft.account_id == account_id,
                ProfilingDraft.session_id == profiling_session_id,
                ProfilingDraft.source_input_id == source_input_id,
            )
        )
    )
    if source_drafts and {draft.id for draft in source_drafts} != set(draft_ids):
        raise DraftSpanRejected("source already has a different draft set")
    existing = tuple(
        session.scalars(select(ProfilingDraft).where(ProfilingDraft.id.in_(draft_ids)))
    )
    if existing:
        by_id = {draft.id: draft for draft in existing}
        if len(by_id) != len(draft_ids) or any(
            (draft := by_id.get(draft_id)) is None
            or draft.account_id != account_id
            or draft.session_id != profiling_session_id
            or draft.source_input_id != source_input_id
            or draft.scope_key != scope_key
            or draft.claim_type != "CONTRIBUTION"
            or draft.exact_text != candidate.exact_text
            or draft.source_content_hash != hashlib.sha256(source.body.encode()).hexdigest()
            for draft_id, candidate in zip(draft_ids, candidates, strict=True)
        ):
            raise DraftSpanRejected("existing bullet drafts differ")
        return tuple(by_id[draft_id] for draft_id in draft_ids)
    return tuple(
        propose_verbatim_draft(
            session,
            account_id=account_id,
            profiling_session_id=profiling_session_id,
            source_input_id=source_input_id,
            scope_key=scope_key,
            claim_type="CONTRIBUTION",
            exact_text=candidate.exact_text,
            now=now,
            draft_id=draft_id,
        )
        for draft_id, candidate in zip(draft_ids, candidates, strict=True)
    )


def propose_explicit_bullet_drafts_once(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    source_input_id: str,
    scope_key: str,
    now: datetime,
) -> tuple[ProfilingDraft, ...]:
    """Preserve the existing browser path for explicitly formatted bullets."""
    return _propose_source_drafts_once(
        session,
        account_id=account_id,
        profiling_session_id=profiling_session_id,
        source_input_id=source_input_id,
        scope_key=scope_key,
        now=now,
    )


def propose_source_span_drafts_once(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    source_input_id: str,
    scope_key: str,
    spans: Sequence[DraftSpan],
    now: datetime,
) -> tuple[ProfilingDraft, ...]:
    """Validate untrusted ranges and persist one replay-safe, unapproved source set."""
    if not isinstance(spans, (tuple, list)) or not spans:
        raise DraftSpanRejected("source spans required")
    return _propose_source_drafts_once(
        session,
        account_id=account_id,
        profiling_session_id=profiling_session_id,
        source_input_id=source_input_id,
        scope_key=scope_key,
        now=now,
        proposed_spans=spans,
    )

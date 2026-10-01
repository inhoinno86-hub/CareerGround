"""Offline, provider-neutral proposal boundary for explicit JD excerpts.

This module returns an untrusted preview. It never writes canonical data,
classifies requirements, maps Claims, or certifies coverage.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.profiling_draft_extraction import (
    DraftSpan,
    DraftSpanRejected,
    extract_explicit_bullet_spans,
    validate_draft_spans,
)
from careerground.storage.models import Account, CareerProfile

MAX_PROPOSAL_SOURCE_CHARS = 6000


class JDProposalRejected(ValueError):
    """The owner, exact source, version, or bounded proposal is unavailable."""


class JDAnalyzer(Protocol):
    """Propose source positions from explicit text only; no identity or graph access."""

    mode: str

    def propose(self, source_text: str) -> object: ...


@dataclass(frozen=True)
class JDRequirementProposal:
    ordinal: int
    exact_text: str
    source_start: int
    source_end: int
    requirement_type: str = "UNCLASSIFIED"
    gap_status: str = "NOT_MAPPED"


@dataclass(frozen=True)
class JDAnalysisProposal:
    profile_id: str
    profile_version: int
    mode: str
    source_hash: str
    source_length: int
    requirements: tuple[JDRequirementProposal, ...]


class MockJDAnalyzer:
    """Deterministic local fixture for explicitly formatted bullets, not semantic AI."""

    mode = "MOCK_ONLY"

    def propose(self, source_text: str) -> dict[str, object]:
        try:
            spans = extract_explicit_bullet_spans(source_text)
        except DraftSpanRejected:
            raise JDProposalRejected from None
        return {
            "source_hash": hashlib.sha256(source_text.encode()).hexdigest(),
            "spans": [{"start": span.start, "end": span.end} for span in spans],
        }


def prepare_jd_analysis(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    source_text: str,
    analyzer: JDAnalyzer,
) -> JDAnalysisProposal:
    """Validate one source-bound untrusted proposal without storing any source."""

    if (
        type(account_id) is not str
        or not account_id
        or type(profile_id) is not str
        or not profile_id
        or type(profile_version) is not int
        or profile_version < 0
        or type(source_text) is not str
        or not 1 <= len(source_text) <= MAX_PROPOSAL_SOURCE_CHARS
        or "\x00" in source_text
        or getattr(analyzer, "mode", None) != "MOCK_ONLY"
    ):
        raise JDProposalRejected
    profile = session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.id == profile_id,
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
        .with_for_update(of=[Account, CareerProfile], read=True)
        .execution_options(populate_existing=True)
    )
    if profile is None or profile.version != profile_version:
        raise JDProposalRejected
    source_hash = hashlib.sha256(source_text.encode()).hexdigest()
    try:
        payload = analyzer.propose(source_text)
    except Exception:  # noqa: BLE001 - provider details and source never cross this boundary
        raise JDProposalRejected from None
    if (
        type(payload) is not dict
        or set(payload) != {"source_hash", "spans"}
        or type(payload["source_hash"]) is not str
        or payload["source_hash"] != source_hash
        or type(payload["spans"]) is not list
        or not 1 <= len(payload["spans"]) <= 5
    ):
        raise JDProposalRejected
    spans = []
    for item in payload["spans"]:
        if (
            type(item) is not dict
            or set(item) != {"start", "end"}
            or type(item["start"]) is not int
            or type(item["end"]) is not int
        ):
            raise JDProposalRejected
        try:
            spans.append(DraftSpan(item["start"], item["end"]))
        except DraftSpanRejected:
            raise JDProposalRejected from None
    if spans != sorted(spans, key=lambda span: (span.start, span.end)):
        raise JDProposalRejected
    try:
        candidates = validate_draft_spans(source_text, spans)
    except DraftSpanRejected:
        raise JDProposalRejected from None
    if len({item.exact_text for item in candidates}) != len(candidates):
        raise JDProposalRejected
    if any(len(item.exact_text.splitlines()) != 1 for item in candidates):
        raise JDProposalRejected
    return JDAnalysisProposal(
        profile_id=profile_id,
        profile_version=profile_version,
        mode="MOCK_ONLY",
        source_hash=source_hash,
        source_length=len(source_text),
        requirements=tuple(
            JDRequirementProposal(
                ordinal=index,
                exact_text=item.exact_text,
                source_start=item.span.start,
                source_end=item.span.end,
            )
            for index, item in enumerate(candidates, start=1)
        ),
    )

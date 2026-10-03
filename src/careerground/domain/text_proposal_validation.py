"""Offline, read-only boundaries for untrusted JD and R2 wording proposals.

These candidates are previews. Neither a plausible sentence nor an eligible source
reference establishes semantic fit, coverage, fact approval, or export readiness.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.jd_mapping import JDMappingRejected, require_eligible_claim_trace
from careerground.domain.resume_draft import ResumeDraftUnavailable, get_resume_trace
from careerground.storage.graph_models import Claim
from careerground.storage.models import Account, CareerProfile

MAX_SOURCE = 6000
MAX_WORDING = 2000
_INSTRUCTION = re.compile(
    r"(?:이전|위의|시스템|개발자).{0,16}(?:지시|명령|프롬프트).{0,16}(?:무시|따라)|(?:ignore|override).{0,24}(?:instructions|system)",
    re.IGNORECASE,
)
_SENSITIVE = re.compile(
    r"(?:\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b|\b\d{6}[- ]?[1-4]\d{6}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*\s*(?:년|개월|월|일|주|시간|명|건|회|%|퍼센트|배)?")
_ROLES = (
    "총괄",
    "주도",
    "리드",
    "팀장",
    "관리자",
    "책임자",
    "대표",
    "승인",
    "결정권",
    "소유",
    "담당",
)
_NEGATION = ("않", "못", "없", "제외", "불가", "미완", "비참여", "아님")
_PAST_ENDINGS = ("하였습니다", "했습니다", "하였다", "했다")


class TextProposalRejected(ValueError):
    """Sanitized typed refusal; input or provider exception is never attached."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OfflineTextAnalyzer(Protocol):
    mode: str

    def propose_jd(self, source_text: str) -> object: ...

    def propose_r2(self, exact_r1_text: str) -> object: ...


class MockTextAnalyzer:
    """Deterministic demonstration only; no inferred mapping or prose generator."""

    mode = "MOCK_ONLY"

    def propose_jd(self, source_text: str) -> object:
        rows = []
        offset = 0
        for line in source_text.splitlines(keepends=True):
            match = re.match(r"\s*[-*]\s+(.+?)\s*(?:\n|$)", line)
            if match:
                rows.append(
                    {
                        "start": offset + match.start(1),
                        "end": offset + match.end(1),
                        "claim_id": None,
                        "evidence_ids": [],
                    }
                )
            offset += len(line)
        return {"source_hash": _hash(source_text), "candidates": rows}

    def propose_r2(self, exact_r1_text: str) -> object:
        return {
            "source_hash": _hash(exact_r1_text),
            "proposed_text": exact_r1_text,
            "fact_review": "NO_NEW_FACTS",
        }


@dataclass(frozen=True)
class JDTextCandidate:
    ordinal: int
    exact_text: str
    source_start: int
    source_end: int
    claim_id: str | None
    evidence_ids: tuple[str, ...]
    requirement_type: str = "UNCLASSIFIED"
    gap_status: str = "NOT_MAPPED"
    relationship_status: str = "POTENTIAL_ONLY"


@dataclass(frozen=True)
class JDTextPreview:
    profile_id: str
    profile_version: int
    source_hash: str
    candidates: tuple[JDTextCandidate, ...]
    mode: str = "UNTRUSTED_PREVIEW"


@dataclass(frozen=True)
class R2WordingPreview:
    artifact_id: str
    unit_id: str
    profile_version: int
    source_hash: str
    proposed_text: str
    claim_id: str
    evidence_ids: tuple[str, ...]
    review_status: str = "REVIEW_REQUIRED"
    wording_level: str = "R2_PROPOSAL"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _owner(session: Session, account_id: str, profile_id: str, version: int) -> None:
    if (
        type(account_id) is not str
        or not account_id
        or type(profile_id) is not str
        or not profile_id
        or type(version) is not int
        or version < 0
    ):
        raise TextProposalRejected("INVALID_SCOPE")
    profile = session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.id == profile_id,
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if profile is None or profile.version != version:
        raise TextProposalRejected("STALE_OR_FOREIGN_SCOPE")


def _source(value: str, *, limit: int) -> None:
    if type(value) is not str or not 1 <= len(value) <= limit or "\x00" in value:
        raise TextProposalRejected("INVALID_SOURCE")
    if _SENSITIVE.search(value):
        raise TextProposalRejected("SENSITIVE_SOURCE")


def _trace(
    session: Session,
    account_id: str,
    profile_id: str,
    version: int,
    claim_id: str,
    evidence_ids: list[str],
):
    if (
        type(claim_id) is not str
        or not claim_id
        or type(evidence_ids) is not list
        or not evidence_ids
        or any(type(x) is not str or not x for x in evidence_ids)
        or len(set(evidence_ids)) != len(evidence_ids)
    ):
        raise TextProposalRejected("INVALID_REFERENCE")
    claim = session.scalar(
        select(Claim).where(
            Claim.id == claim_id,
            Claim.account_id == account_id,
            Claim.profile_id == profile_id,
            Claim.status == "ACTIVE",
        )
    )
    if claim is None:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE")
    try:
        trace = require_eligible_claim_trace(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=version,
            claim_id=claim_id,
        )
    except JDMappingRejected:
        raise TextProposalRejected("INELIGIBLE_REFERENCE") from None
    if claim.canonical_text != trace.claim.exact_text:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE")
    support = {item.evidence_id for item in trace.evidence if item.relation_type == "SUPPORTS"}
    if not set(evidence_ids) <= support:
        raise TextProposalRejected("INELIGIBLE_REFERENCE")
    return trace


def validate_jd_text_proposal(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    source_text: str,
    payload: object,
) -> JDTextPreview:
    """Check exact JD spans and optional source references without storing mappings."""
    _owner(session, account_id, profile_id, profile_version)
    _source(source_text, limit=MAX_SOURCE)
    if (
        type(payload) is not dict
        or set(payload) != {"source_hash", "candidates"}
        or payload["source_hash"] != _hash(source_text)
        or type(payload["candidates"]) is not list
        or not 1 <= len(payload["candidates"]) <= 5
    ):
        raise TextProposalRejected("INVALID_SCHEMA_OR_HASH")
    output = []
    previous_end = 0
    for index, row in enumerate(payload["candidates"], 1):
        if (
            type(row) is not dict
            or set(row) != {"start", "end", "claim_id", "evidence_ids"}
            or type(row["start"]) is not int
            or type(row["end"]) is not int
            or type(row["evidence_ids"]) is not list
        ):
            raise TextProposalRejected("INVALID_SCHEMA_OR_HASH")
        start, end = row["start"], row["end"]
        if start < previous_end or end <= start or end > len(source_text):
            raise TextProposalRejected("INVALID_SPAN")
        exact = source_text[start:end]
        if not exact.strip() or exact != exact.strip() or "\n" in exact or len(exact) > 2000:
            raise TextProposalRejected("INVALID_SPAN")
        if (start > 0 and source_text[start - 1].isalnum() and exact[0].isalnum()) or (
            end < len(source_text) and source_text[end].isalnum() and exact[-1].isalnum()
        ):
            raise TextProposalRejected("INVALID_SPAN")
        if _INSTRUCTION.search(exact):
            raise TextProposalRejected("INSTRUCTION_CONTENT")
        if row["claim_id"] is None:
            if row["evidence_ids"]:
                raise TextProposalRejected("INVALID_REFERENCE")
            evidence = ()
        else:
            _trace(
                session,
                account_id,
                profile_id,
                profile_version,
                row["claim_id"],
                row["evidence_ids"],
            )
            evidence = tuple(row["evidence_ids"])
        output.append(JDTextCandidate(index, exact, start, end, row["claim_id"], evidence))
        previous_end = end
    if len({item.exact_text for item in output}) != len(output):
        raise TextProposalRejected("DUPLICATE_CANDIDATE")
    return JDTextPreview(profile_id, profile_version, _hash(source_text), tuple(output))


def prepare_mock_jd_text_proposal(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    source_text: str,
    analyzer: OfflineTextAnalyzer,
) -> JDTextPreview:
    """Call a local deterministic analyzer with source only, then validate its output."""
    _owner(session, account_id, profile_id, profile_version)
    _source(source_text, limit=MAX_SOURCE)
    if getattr(analyzer, "mode", None) != "MOCK_ONLY":
        raise TextProposalRejected("PROVIDER_DISABLED")
    try:
        payload = analyzer.propose_jd(source_text)
    except Exception:  # noqa: BLE001 - provider/source details never become error text
        raise TextProposalRejected("ANALYZER_FAILED") from None
    return validate_jd_text_proposal(
        session,
        account_id=account_id,
        profile_id=profile_id,
        profile_version=profile_version,
        source_text=source_text,
        payload=payload,
    )


def _past_stem(token: str) -> str | None:
    for suffix in _PAST_ENDINGS:
        if len(token) > len(suffix) + 1 and token.endswith(suffix):
            return token[: -len(suffix)]
    return None


def _wording_guard(source: str, proposed: str) -> None:
    if _INSTRUCTION.search(proposed):
        raise TextProposalRejected("INSTRUCTION_CONTENT")
    if Counter(_NUMBER.findall(proposed)) - Counter(_NUMBER.findall(source)):
        raise TextProposalRejected("NEW_NUMBER_OR_DATE")
    if any(proposed.count(word) > source.count(word) for word in _ROLES):
        raise TextProposalRejected("NEW_ROLE_OR_AUTHORITY")
    if any(proposed.count(word) > source.count(word) for word in _NEGATION):
        raise TextProposalRejected("NEW_NEGATION")
    before = re.sub(r"\s+", " ", source.strip()).rstrip(".!")
    after = re.sub(r"\s+", " ", proposed.strip()).rstrip(".!")
    if before == after:
        return
    original = re.fullmatch(r"(.*?)([가-힣]+)", before)
    rewritten = re.fullmatch(r"(.*?)([가-힣]+)", after)
    if original is not None and rewritten is not None and original.group(1) == rewritten.group(1):
        stem = _past_stem(original.group(2))
        if stem is not None and stem == _past_stem(rewritten.group(2)):
            return
    raise TextProposalRejected("FACT_OR_QUALIFIER_CHANGED")


def validate_r2_wording_proposal(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    artifact_id: str,
    unit_id: str,
    payload: object,
) -> R2WordingPreview:
    """Conservatively accept only a source-preserving wording preview, never R3."""
    _owner(session, account_id, profile_id, profile_version)
    if any(type(x) is not str or not x for x in (artifact_id, unit_id)):
        raise TextProposalRejected("INVALID_SCOPE")
    try:
        artifact = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
    except ResumeDraftUnavailable:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE") from None
    if artifact.profile_version != profile_version or artifact.stale_relative_to_current_profile:
        raise TextProposalRejected("STALE_OR_FOREIGN_SCOPE")
    units = [unit for unit in artifact.units if unit.unit_id == unit_id]
    if len(units) != 1:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE")
    unit = units[0]
    if unit.wording_level != "R1" or unit.review_status not in {
        "REVIEW_REQUIRED",
        "WORDING_REVIEWED",
    }:
        raise TextProposalRejected("INELIGIBLE_REFERENCE")
    _source(unit.exact_text, limit=MAX_WORDING)
    if type(payload) is not dict or set(payload) != {
        "source_hash",
        "proposed_text",
        "fact_review",
        "claim_id",
        "evidence_ids",
    }:
        raise TextProposalRejected("INVALID_SCHEMA_OR_HASH")
    if payload["fact_review"] == "R3_NEEDS_FACT_REVIEW":
        raise TextProposalRejected("R3_NEEDS_FACT_REVIEW")
    if payload["fact_review"] != "NO_NEW_FACTS" or payload["source_hash"] != _hash(unit.exact_text):
        raise TextProposalRejected("INVALID_SCHEMA_OR_HASH")
    proposed = payload["proposed_text"]
    _source(proposed, limit=MAX_WORDING)
    if payload["claim_id"] != unit.claim_id or payload["evidence_ids"] != list(unit.evidence_ids):
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE")
    _trace(session, account_id, profile_id, profile_version, unit.claim_id, payload["evidence_ids"])
    _wording_guard(unit.exact_text, proposed)
    return R2WordingPreview(
        artifact_id,
        unit_id,
        profile_version,
        _hash(unit.exact_text),
        proposed,
        unit.claim_id,
        tuple(unit.evidence_ids),
    )


def prepare_mock_r2_wording_proposal(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    artifact_id: str,
    unit_id: str,
    analyzer: OfflineTextAnalyzer,
) -> R2WordingPreview:
    """Pass one R1 sentence to a local mock; refs stay server side."""
    _owner(session, account_id, profile_id, profile_version)
    if getattr(analyzer, "mode", None) != "MOCK_ONLY":
        raise TextProposalRejected("PROVIDER_DISABLED")
    try:
        trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
    except ResumeDraftUnavailable:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE") from None
    if trace.profile_version != profile_version or trace.stale_relative_to_current_profile:
        raise TextProposalRejected("STALE_OR_FOREIGN_SCOPE")
    units = [unit for unit in trace.units if unit.unit_id == unit_id]
    if len(units) != 1:
        raise TextProposalRejected("STALE_OR_FOREIGN_REFERENCE")
    unit = units[0]
    if unit.wording_level != "R1" or unit.review_status not in {
        "REVIEW_REQUIRED",
        "WORDING_REVIEWED",
    }:
        raise TextProposalRejected("INELIGIBLE_REFERENCE")
    _source(unit.exact_text, limit=MAX_WORDING)
    try:
        payload = analyzer.propose_r2(unit.exact_text)
    except Exception:  # noqa: BLE001 - no private source in exception chain
        raise TextProposalRejected("ANALYZER_FAILED") from None
    if type(payload) is not dict or set(payload) != {"source_hash", "proposed_text", "fact_review"}:
        raise TextProposalRejected("INVALID_SCHEMA_OR_HASH")
    return validate_r2_wording_proposal(
        session,
        account_id=account_id,
        profile_id=profile_id,
        profile_version=profile_version,
        artifact_id=artifact_id,
        unit_id=unit_id,
        payload={**payload, "claim_id": unit.claim_id, "evidence_ids": list(unit.evidence_ids)},
    )

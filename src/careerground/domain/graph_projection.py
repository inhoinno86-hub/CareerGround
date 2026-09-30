"""Owner-scoped exact-version Graph projections from immutable snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive


class GraphUnavailable(Exception):
    """The requested owner, profile version or Claim is unavailable."""


@dataclass(frozen=True)
class ClaimSummary:
    claim_id: str
    claim_type: str
    exact_text: str
    scope_key: str
    knowledge_status: str
    consistency_status: str
    usage_policy: str


@dataclass(frozen=True)
class ProfileView:
    profile_id: str
    profile_version: int
    claims: tuple[ClaimSummary, ...]
    constraint_count: int


@dataclass(frozen=True)
class EvidenceExcerptView:
    evidence_id: str
    exact_excerpt: str
    source_id: str
    original_input_ref: str
    source_content_hash: str
    relation_type: str
    source_availability: str = "SELECTED_EXCERPT_ONLY"


@dataclass(frozen=True)
class ClaimEvidenceView:
    claim: ClaimSummary
    profile_version: int
    evidence: tuple[EvidenceExcerptView, ...]
    reviewed: bool
    constraints: tuple[tuple[str, str], ...]


def get_career_profile(
    session: Session, *, account_id: str, profile_id: str, profile_version: int
) -> ProfileView:
    """Read only the exact stored version; no latest-version fallback."""

    snapshot = _snapshot(session, account_id, profile_id, profile_version)
    sections = snapshot["sections"]
    claims = tuple(
        _summary(row, sections) for row in sections["claims"] if row["status"] == "ACTIVE"
    )
    return ProfileView(
        profile_id=profile_id,
        profile_version=profile_version,
        claims=claims,
        constraint_count=sum(
            row.get("status", "ACTIVE") == "ACTIVE" for row in sections["claim_constraints"]
        ),
    )


def get_claim_evidence(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    claim_id: str,
) -> ClaimEvidenceView:
    """Resolve a Claim and its selected excerpts from one archived version."""

    snapshot = _snapshot(session, account_id, profile_id, profile_version)
    sections = snapshot["sections"]
    claim = next(
        (row for row in sections["claims"] if row["id"] == claim_id and row["status"] == "ACTIVE"),
        None,
    )
    if claim is None:
        raise GraphUnavailable
    sources = {row["id"]: row for row in sections["evidence_sources"]}
    evidence_rows = {row["id"]: row for row in sections["evidence_items"]}
    evidence = []
    for link in sections["evidence_claim_links"]:
        if link["claim_id"] != claim_id:
            continue
        item = evidence_rows.get(link["evidence_id"])
        source = sources.get(item["source_id"]) if item is not None else None
        if item is None or item["status"] != "ACTIVE" or source is None:
            raise GraphUnavailable
        evidence.append(
            EvidenceExcerptView(
                evidence_id=item["id"],
                exact_excerpt=item["content_text"],
                source_id=source["id"],
                original_input_ref=source["source_ref"],
                source_content_hash=source["content_hash"],
                relation_type=link["relation_type"],
            )
        )
    evidence.sort(key=lambda row: (row.evidence_id, row.relation_type))
    return ClaimEvidenceView(
        claim=_summary(claim, sections),
        profile_version=profile_version,
        evidence=tuple(evidence),
        reviewed=any(
            row["claim_id"] == claim_id and row["review_purpose"] == "FACT_CONFIRMATION"
            for row in sections["claim_reviews"]
        ),
        constraints=tuple(
            (row["constraint_type"], row["exact_text"])
            for row in sections["claim_constraints"]
            if row["scope_key"] == claim["scope_key"] and row.get("status", "ACTIVE") == "ACTIVE"
        ),
    )


def _snapshot(session: Session, account_id: str, profile_id: str, version: int) -> dict:
    try:
        snapshot = read_profile_archive(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=version,
        )
        sections = snapshot["sections"]
        for name in (
            "claims",
            "claim_assessments",
            "claim_constraints",
            "claim_reviews",
            "evidence_claim_links",
            "evidence_items",
            "evidence_sources",
        ):
            if not isinstance(sections[name], list):
                raise GraphUnavailable
        if snapshot["schema"] in {"canonical-foundation-v2", "canonical-foundation-v3"}:
            for name in ("claim_boundary_reviews", "claim_conflict_reviews"):
                if not isinstance(sections[name], list):
                    raise GraphUnavailable
        if snapshot["schema"] == "canonical-foundation-v3" and not isinstance(
            sections["claim_use_reviews"], list
        ):
            raise GraphUnavailable
        return snapshot
    except (ArchiveUnavailable, KeyError, TypeError) as exc:
        raise GraphUnavailable from exc


def _summary(claim: dict, sections: dict) -> ClaimSummary:
    assessments = [row for row in sections["claim_assessments"] if row["claim_id"] == claim["id"]]
    latest = max(assessments, key=lambda row: row["profile_version"], default=None)
    return ClaimSummary(
        claim_id=claim["id"],
        claim_type=claim["claim_type"],
        exact_text=claim["canonical_text"],
        scope_key=claim["scope_key"],
        knowledge_status=latest["knowledge_status"] if latest else "UNKNOWN",
        consistency_status=latest["consistency_status"] if latest else "NOT_EVALUATED",
        usage_policy=latest["usage_policy"] if latest else "REVIEW_REQUIRED",
    )

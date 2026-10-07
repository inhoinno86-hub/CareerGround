"""Bounded personal-data export with exact archived facts and explicit choices."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive
from careerground.domain.profile_export_selection import (
    ProfileSelectionRejected,
    resolve_profile_version,
    selection_values,
)
from careerground.storage.graph_models import EvidenceSource
from careerground.storage.models import (
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingSession,
)

MAX_EXPORT_BYTES = 4 * 1024 * 1024


class ProfileExportUnavailable(Exception):
    """The exact owner/version is absent or the requested scope is unsupported."""


@dataclass(frozen=True)
class CanonicalProfileExport:
    profile_id: str
    profile_version: int
    format: str
    content_hash: str
    content_json: str
    inclusion: dict


def export_profile_data(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int | str,
    format: str = "JSON",
    include_drafts: bool = False,
    include_expired_sources: bool = False,
    inclusion: dict | None = None,
    now: datetime | None = None,
) -> CanonicalProfileExport:
    """Build an exact export without a public route.

    `CURRENT` is explicit. Selected live drafts remain visibly unapproved;
    expired source bodies and erased payloads are never reconstructed.
    """

    if (
        format != "JSON"
        or type(include_drafts) is not bool
        or type(include_expired_sources) is not bool
        or include_drafts
        or include_expired_sources
    ):
        raise ProfileExportUnavailable
    try:
        choices = selection_values(inclusion)
        version = resolve_profile_version(
            session, account_id=account_id, profile_id=profile_id, selector=profile_version
        )
    except ProfileSelectionRejected:
        raise ProfileExportUnavailable from None
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ProfileExportUnavailable
    try:
        snapshot = read_profile_archive(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=version,
        )
        profile_view = get_career_profile(
            session,
            account_id=account_id,
            profile_id=profile_id,
            profile_version=version,
        )
        claims = []
        for claim in profile_view.claims if choices["claims"] else ():
            trace = get_claim_evidence(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=version,
                claim_id=claim.claim_id,
            )
            claims.append(
                {
                    "claim_id": claim.claim_id,
                    "claim_type": claim.claim_type,
                    "exact_text": claim.exact_text,
                    "scope_key": claim.scope_key,
                    "knowledge_status": claim.knowledge_status,
                    "consistency_status": claim.consistency_status,
                    "usage_policy": claim.usage_policy,
                    "fact_reviewed": trace.reviewed,
                    "constraints": [
                        {"constraint_type": kind, "exact_text": text}
                        for kind, text in trace.constraints
                    ],
                    "evidence": [
                        {
                            "evidence_id": item.evidence_id,
                            "exact_excerpt": item.exact_excerpt,
                            "relation_type": item.relation_type,
                            "source_id": item.source_id,
                            "original_input_ref": item.original_input_ref,
                            "source_content_hash": item.source_content_hash,
                            "source_availability": item.source_availability,
                        }
                        for item in trace.evidence
                        if choices["evidence"]
                    ],
                }
            )
        boundaries = snapshot["sections"]["claim_constraints"]
        if not isinstance(boundaries, list):
            raise ProfileExportUnavailable
        active_boundaries = [
            {
                "constraint_id": row["id"],
                "scope_key": row["scope_key"],
                "constraint_type": row["constraint_type"],
                "exact_text": row["exact_text"],
            }
            for row in boundaries
            if choices["boundaries"] and row.get("status", "ACTIVE") == "ACTIVE"
        ]
    except (ArchiveUnavailable, GraphUnavailable, KeyError, TypeError) as exc:
        raise ProfileExportUnavailable from exc
    drafts = []
    if choices["drafts"]:
        profile = session.get(CareerProfile, profile_id)
        if profile is None or profile.version != version:
            raise ProfileExportUnavailable
        rows = session.scalars(
            select(ProfilingDraft)
            .join(ProfilingSession, ProfilingSession.id == ProfilingDraft.session_id)
            .where(
                ProfilingDraft.account_id == account_id,
                ProfilingSession.account_id == account_id,
                ProfilingSession.profile_id == profile_id,
                ProfilingSession.status.in_(["ACTIVE", "PAUSED"]),
                ProfilingSession.retention_expires_at > now,
                ProfilingDraft.expires_at > now,
                ProfilingDraft.status.in_(["DRAFT", "IN_REVIEW", "EDIT_REQUIRED"]),
            )
            .order_by(ProfilingDraft.id)
            .limit(201)
        ).all()
        if len(rows) > 200:
            raise ProfileExportUnavailable
        drafts = [
            {
                "draft_id": row.id,
                "exact_text": row.exact_text,
                "status": row.status,
                "fact_review": "UNAPPROVED",
                "scope_key": row.scope_key,
            }
            for row in rows
        ]
    references = []
    if choices["unavailable_references"]:
        for source in session.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.account_id == account_id,
                EvidenceSource.profile_id == profile_id,
                EvidenceSource.created_in_version <= version,
            )
            .order_by(EvidenceSource.id)
        ):
            work = session.scalar(
                select(ProfilingSession)
                .join(ProfilingInput, ProfilingInput.session_id == ProfilingSession.id)
                .where(
                    ProfilingInput.id == source.source_ref,
                    ProfilingInput.account_id == account_id,
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.profile_id == profile_id,
                    ProfilingSession.status.in_(["ACTIVE", "PAUSED"]),
                    ProfilingSession.retention_expires_at > now,
                )
            )
            if work is None:
                references.append(
                    {
                        "source_id": source.id,
                        "source_ref": source.source_ref,
                        "availability": "UNAVAILABLE",
                        "content": "NOT_RECONSTRUCTED",
                    }
                )
    body = json.dumps(
        {
            "schema": "careerground-profile-export-v2"
            if choices["drafts"]
            else "careerground-canonical-profile-export-v1",
            "account_id": account_id,
            "profile_id": profile_id,
            "profile_version": version,
            "scope": "PERSONAL_DATA_WITH_UNAPPROVED_DRAFTS"
            if choices["drafts"]
            else "CANONICAL_ONLY",
            "inclusion": choices,
            "temporary_drafts": drafts if choices["drafts"] else "NOT_INCLUDED",
            "expired_source_bodies": "UNAVAILABLE",
            "unavailable_references": references,
            "claims": claims,
            "active_boundaries": active_boundaries,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(body.encode()) > MAX_EXPORT_BYTES:
        raise ProfileExportUnavailable
    return CanonicalProfileExport(
        profile_id=profile_id,
        profile_version=version,
        format="JSON",
        content_hash=hashlib.sha256(body.encode()).hexdigest(),
        content_json=body,
        inclusion=choices,
    )

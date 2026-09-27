"""Internal, in-memory canonical profile JSON export from one exact archive."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive
from careerground.storage.models import Account, CareerProfile

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


def export_profile_data(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int | str,
    format: str = "JSON",
    include_drafts: bool = False,
    include_expired_sources: bool = False,
) -> CanonicalProfileExport:
    """Build a bounded canonical-only export without a download or public route.

    `CURRENT` is explicit. Temporary drafts, expired source bodies and erased
    payloads are never reconstructed by this foundation path.
    """

    if (
        format != "JSON"
        or type(include_drafts) is not bool
        or type(include_expired_sources) is not bool
        or include_drafts
        or include_expired_sources
    ):
        raise ProfileExportUnavailable
    if profile_version == "CURRENT":
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
        if profile is None:
            raise ProfileExportUnavailable
        version = profile.version
    elif isinstance(profile_version, bool) or not isinstance(profile_version, int):
        raise ProfileExportUnavailable
    else:
        version = profile_version
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
        for claim in profile_view.claims:
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
            if row.get("status", "ACTIVE") == "ACTIVE"
        ]
    except (ArchiveUnavailable, GraphUnavailable, KeyError, TypeError) as exc:
        raise ProfileExportUnavailable from exc
    body = json.dumps(
        {
            "schema": "careerground-canonical-profile-export-v1",
            "account_id": account_id,
            "profile_id": profile_id,
            "profile_version": version,
            "scope": "CANONICAL_ONLY",
            "temporary_drafts": "NOT_INCLUDED",
            "expired_source_bodies": "UNAVAILABLE",
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
    )

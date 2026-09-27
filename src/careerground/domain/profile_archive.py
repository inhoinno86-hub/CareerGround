"""Exact, owner-scoped canonical snapshots; missing versions never fall back."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    ClaimConstraint,
    ClaimReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
    ProfileChangeSet,
)
from careerground.storage.models import Account, CareerProfile

MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
_SNAPSHOT_MODELS = (
    Claim,
    EvidenceSource,
    EvidenceItem,
    EvidenceClaimLink,
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    ClaimReview,
    ClaimConstraint,
    ProfileChangeSet,
)
_LEGACY_SNAPSHOT_MODELS = (
    Claim,
    EvidenceSource,
    EvidenceItem,
    EvidenceClaimLink,
    ClaimAssessment,
    ClaimReview,
    ClaimConstraint,
    ProfileChangeSet,
)


class ArchiveUnavailable(Exception):
    """The exact version is absent, inaccessible, erased, or corrupt."""


def ensure_profile_archive(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    profile_version: int,
    now: datetime,
) -> ProfileArchive:
    """Insert one exact snapshot, or reject drift from an existing snapshot."""

    if now.tzinfo is None or profile_version < 0:
        raise ValueError("aware timestamp and nonnegative version required")
    archive = session.scalar(
        select(ProfileArchive)
        .where(
            ProfileArchive.account_id == account_id,
            ProfileArchive.profile_id == profile_id,
            ProfileArchive.profile_version == profile_version,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if archive is not None:
        if not hmac.compare_digest(
            hashlib.sha256(archive.snapshot_json.encode()).hexdigest(), archive.content_hash
        ):
            raise ArchiveUnavailable("stored archive hash mismatch")
        try:
            stored = json.loads(archive.snapshot_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ArchiveUnavailable from exc
        if not isinstance(stored, dict):
            raise ArchiveUnavailable
        legacy = stored.get("schema") == "canonical-foundation-v1"
        if legacy:
            # Old snapshots predate boundary status and review journals. They
            # remain byte-identical; new rows or a revoked constraint would
            # mean the old version was changed without a profile increment.
            for model in (ClaimBoundaryReview, ClaimConflictReview):
                if (
                    session.scalar(
                        select(model.id)
                        .where(model.account_id == account_id, model.profile_id == profile_id)
                        .limit(1)
                    )
                    is not None
                ):
                    raise ArchiveUnavailable("new review row in legacy profile version")
            if (
                session.scalar(
                    select(ClaimConstraint.id)
                    .where(
                        ClaimConstraint.account_id == account_id,
                        ClaimConstraint.profile_id == profile_id,
                        ClaimConstraint.status != "ACTIVE",
                    )
                    .limit(1)
                )
                is not None
            ):
                raise ArchiveUnavailable("changed boundary in legacy profile version")
        elif stored.get("schema") != "canonical-foundation-v2":
            raise ArchiveUnavailable("unsupported archive schema")
        payload = _canonical_json(session, account_id, profile_id, profile_version, legacy=legacy)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        if (
            not hmac.compare_digest(archive.content_hash, digest)
            or archive.snapshot_json != payload
        ):
            raise ArchiveUnavailable("canonical state drifted from the archived version")
        return archive
    payload = _canonical_json(session, account_id, profile_id, profile_version)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    archive = ProfileArchive(
        id=str(uuid4()),
        account_id=account_id,
        profile_id=profile_id,
        profile_version=profile_version,
        snapshot_json=payload,
        content_hash=digest,
        created_at=now.astimezone(UTC),
    )
    session.add(archive)
    session.flush()
    return archive


def read_profile_archive(
    session: Session, *, account_id: str, profile_id: str, profile_version: int
) -> dict:
    """Return only a stored exact version for an active owner and profile."""

    if (
        isinstance(profile_version, bool)
        or not isinstance(profile_version, int)
        or profile_version < 0
    ):
        raise ArchiveUnavailable
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
    if profile is None or profile_version > profile.version:
        raise ArchiveUnavailable
    archive = session.scalar(
        select(ProfileArchive).where(
            ProfileArchive.account_id == account_id,
            ProfileArchive.profile_id == profile_id,
            ProfileArchive.profile_version == profile_version,
        )
    )
    if archive is None or not hmac.compare_digest(
        hashlib.sha256(archive.snapshot_json.encode()).hexdigest(), archive.content_hash
    ):
        raise ArchiveUnavailable
    try:
        value = json.loads(archive.snapshot_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ArchiveUnavailable from exc
    if (
        not isinstance(value, dict)
        or value.get("schema") not in {"canonical-foundation-v1", "canonical-foundation-v2"}
        or value.get("account_id") != account_id
        or value.get("profile_id") != profile_id
        or value.get("profile_version") != profile_version
    ):
        raise ArchiveUnavailable
    return value


def _canonical_json(
    session: Session, account_id: str, profile_id: str, version: int, *, legacy: bool = False
) -> str:
    sections = {}
    with session.no_autoflush:
        for model in _LEGACY_SNAPSHOT_MODELS if legacy else _SNAPSHOT_MODELS:
            rows = session.scalars(
                select(model)
                .where(model.account_id == account_id, model.profile_id == profile_id)
                .order_by(model.id)
            )
            sections[model.__tablename__] = [
                {
                    column.name: _json_value(getattr(row, column.name))
                    for column in model.__table__.columns
                    if not (legacy and model is ClaimConstraint and column.name == "status")
                }
                for row in rows
            ]
    payload = json.dumps(
        {
            "schema": "canonical-foundation-v1" if legacy else "canonical-foundation-v2",
            "account_id": account_id,
            "profile_id": profile_id,
            "profile_version": version,
            "sections": sections,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(payload.encode()) > MAX_SNAPSHOT_BYTES:
        raise ArchiveUnavailable("bounded archive snapshot exceeded")
    return payload


def _json_value(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        ).isoformat()
    return value

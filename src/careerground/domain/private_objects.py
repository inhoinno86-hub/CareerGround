"""Private, metadata-only original registry; no upload or public download route."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.storage.models import (
    Account,
    CareerProfile,
    PrivateObject,
    PrivateObjectVersion,
)
from careerground.workers.outbox import enqueue_event

ORIGINAL_RETENTION = timedelta(days=30)
MAX_EXPIRY_BATCH = 100


class PrivateObjectUnavailable(Exception):
    """An object is not in the active owner's view."""


class PrivateObjectInventoryMismatch(Exception):
    """Provider versions disagree with the private registry; erasure is blocked."""


class SyntheticVersionStore(Protocol):
    """Local test adapter only; no S3 credentials or network implementation exists."""

    def list_versions(self, object_id: str) -> set[str]: ...

    def delete_version(self, object_id: str, provider_version_id: str) -> None: ...


def register_upload_original(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    extraction_completed_at: datetime,
    now: datetime,
) -> PrivateObject:
    """The 30-day clock starts after extraction, never at login or ordinary chat."""

    return _register(
        session,
        account_id=account_id,
        profile_id=profile_id,
        object_class="UPLOAD_ORIGINAL",
        anchor_at=extraction_completed_at,
        now=now,
    )


def register_opted_in_recording(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    recording_completed_at: datetime,
    explicit_opt_in: bool,
    now: datetime,
) -> PrivateObject:
    """Raw recording metadata cannot be created through the default-off path."""

    if explicit_opt_in is not True:
        raise ValueError("explicit recording opt-in required")
    return _register(
        session,
        account_id=account_id,
        profile_id=profile_id,
        object_class="OPTIONAL_RECORDING",
        anchor_at=recording_completed_at,
        now=now,
    )


def _register(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    object_class: str,
    anchor_at: datetime,
    now: datetime,
) -> PrivateObject:
    now = _utc(now)
    anchor_at = _utc(anchor_at)
    if anchor_at > now or now >= anchor_at + ORIGINAL_RETENTION:
        raise ValueError("invalid or already expired retention anchor")
    profile = session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.id == profile_id,
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
        .with_for_update(of=CareerProfile)
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise PrivateObjectUnavailable
    obj = PrivateObject(
        id=str(uuid4()),
        account_id=account_id,
        profile_id=profile_id,
        object_class=object_class,
        status="ACTIVE",
        retention_anchor_at=anchor_at,
        retention_expires_at=anchor_at + ORIGINAL_RETENTION,
        created_at=now,
    )
    session.add(obj)
    return obj


def register_private_version(
    session: Session,
    *,
    account_id: str,
    object_id: str,
    provider_version_id: str,
    now: datetime,
) -> PrivateObjectVersion:
    """Record one opaque provider version; caller's transaction owns the commit."""

    now = _utc(now)
    if (
        not isinstance(provider_version_id, str)
        or not 1 <= len(provider_version_id) <= 256
        or not provider_version_id.isascii()
        or not provider_version_id.isprintable()
        or any(ch.isspace() for ch in provider_version_id)
    ):
        raise ValueError("opaque provider version ID required")
    obj = _owned_active_object(session, account_id=account_id, object_id=object_id, now=now)
    existing = session.scalar(
        select(PrivateObjectVersion).where(
            PrivateObjectVersion.object_id == object_id,
            PrivateObjectVersion.provider_version_id == provider_version_id,
        )
    )
    if existing is not None:
        return existing
    version = PrivateObjectVersion(
        id=str(uuid4()),
        object_id=obj.id,
        account_id=account_id,
        provider_version_id=provider_version_id,
        status="ACTIVE",
        created_at=now,
    )
    session.add(version)
    return version


def list_private_versions(
    session: Session, *, account_id: str, object_id: str, now: datetime
) -> tuple[PrivateObjectVersion, ...]:
    """Internal metadata only; deny expired/deleting objects at read time."""

    _owned_active_object(session, account_id=account_id, object_id=object_id, now=_utc(now))
    return tuple(
        session.scalars(
            select(PrivateObjectVersion)
            .where(
                PrivateObjectVersion.object_id == object_id,
                PrivateObjectVersion.account_id == account_id,
                PrivateObjectVersion.status == "ACTIVE",
            )
            .order_by(PrivateObjectVersion.created_at, PrivateObjectVersion.id)
        )
    )


def stage_expired_private_objects(session: Session, *, now: datetime, limit: int = 100) -> int:
    """Mark a bounded batch inaccessible; physical provider erasure is separate."""

    now = _utc(now)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_EXPIRY_BATCH:
        raise ValueError("invalid expiry batch limit")
    objects = list(
        session.scalars(
            select(PrivateObject)
            .where(
                PrivateObject.status == "ACTIVE",
                PrivateObject.retention_expires_at <= now,
            )
            .order_by(PrivateObject.retention_expires_at, PrivateObject.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for obj in objects:
        obj.status = "DELETING"
        for version in session.scalars(
            select(PrivateObjectVersion).where(
                PrivateObjectVersion.object_id == obj.id,
                PrivateObjectVersion.status == "ACTIVE",
            )
        ):
            version.status = "DELETE_PENDING"
            enqueue_event(
                session,
                event_type="PRIVATE_OBJECT_DELETE",
                target_id=version.id,
                handler_id=f"private-object:{version.id}",
                now=now,
            )
    return len(objects)


def erase_synthetic_object_versions(
    session: Session, *, object_id: str, adapter: SyntheticVersionStore
) -> int:
    """Offline rehearsal only: require a complete inventory and remove all versions.

    A real provider adapter must use a separate recoverable protocol. No external
    call is made by this function in a product worker or DB transaction.
    """

    obj = session.get(PrivateObject, object_id)
    if obj is None or obj.status != "DELETING":
        raise PrivateObjectUnavailable
    versions = list(
        session.scalars(
            select(PrivateObjectVersion).where(PrivateObjectVersion.object_id == object_id)
        )
    )
    known = {version.provider_version_id for version in versions}
    actual = adapter.list_versions(object_id)
    if not actual.issubset(known):
        raise PrivateObjectInventoryMismatch
    for version in versions:
        if version.provider_version_id in actual:
            adapter.delete_version(object_id, version.provider_version_id)
        version.status = "DELETED"
    if adapter.list_versions(object_id):
        raise PrivateObjectInventoryMismatch
    return len(versions)


def _owned_active_object(
    session: Session, *, account_id: str, object_id: str, now: datetime
) -> PrivateObject:
    obj = session.scalar(
        select(PrivateObject)
        .join(Account, Account.id == PrivateObject.account_id)
        .join(CareerProfile, CareerProfile.id == PrivateObject.profile_id)
        .where(
            PrivateObject.id == object_id,
            PrivateObject.account_id == account_id,
            PrivateObject.status == "ACTIVE",
            PrivateObject.retention_expires_at > now,
            Account.status == "ACTIVE",
            CareerProfile.status == "ACTIVE",
            CareerProfile.account_id == account_id,
        )
        .with_for_update(of=PrivateObject)
        .execution_options(populate_existing=True)
    )
    if obj is None:
        raise PrivateObjectUnavailable
    return obj


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware datetime required")
    return value.astimezone(UTC)

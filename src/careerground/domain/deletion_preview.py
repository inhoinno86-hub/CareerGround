"""Foundation-only deletion impact preview and non-mutating confirmation check.

This service cannot execute erasure. It covers only the tables that exist today;
future adapters must not expose it as a complete deletion tool to real users.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.storage.models import (
    Account,
    AuthIdentity,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)

_DIGEST_PATTERN = re.compile(r"v1\.([0-9]{10,13})\.([0-9a-f]{64})\Z")


class DeletionScope(StrEnum):
    ACCOUNT = "ACCOUNT"
    PROFILE = "PROFILE"


class DeletionTargetUnavailable(Exception):
    """Target is absent, not owned, or not available for a new preview."""


class DeletionConfirmationRejected(Exception):
    """Impact, timing, acknowledgement, or trusted step-up approval is invalid."""


@dataclass(frozen=True)
class DeletionImpactItem:
    kind: str
    target_id: str
    version: int | None = None
    state: str | None = None


@dataclass(frozen=True)
class DeletionPreview:
    scope: DeletionScope
    target_id: str
    items: tuple[DeletionImpactItem, ...]
    deletion_digest: str
    expires_at: datetime
    coverage: str = "FOUNDATION_ONLY"
    ready_to_execute: bool = False


@dataclass(frozen=True)
class VerifiedDeletionApproval:
    """Trusted adapter output, not a user-supplied token or model-provided field."""

    account_id: str
    scope: DeletionScope
    target_id: str
    expires_at: datetime


class DeletionPreviewService:
    def __init__(self, signing_secret: bytes, *, ttl_seconds: int = 300) -> None:
        if len(signing_secret) < 32:
            raise ValueError("deletion preview signing secret must be at least 32 bytes")
        if not 1 <= ttl_seconds <= 900:
            raise ValueError("deletion preview TTL must be between 1 and 900 seconds")
        self._secret = signing_secret
        self._ttl_seconds = ttl_seconds

    def preview(
        self,
        session: Session,
        *,
        account_id: str,
        scope: DeletionScope,
        target_id: str,
        now: datetime,
    ) -> DeletionPreview:
        now = self._require_utc(now)
        scope = self._scope(scope)
        with session.no_autoflush:
            items = self._collect_items(
                session, account_id=account_id, scope=scope, target_id=target_id
            )
        issued_at = int(now.timestamp())
        digest = self._digest(account_id, scope, target_id, items, issued_at)
        return DeletionPreview(
            scope=scope,
            target_id=target_id,
            items=items,
            deletion_digest=digest,
            expires_at=datetime.fromtimestamp(issued_at + self._ttl_seconds, UTC),
        )

    def confirm_intent(
        self,
        session: Session,
        *,
        account_id: str,
        scope: DeletionScope,
        target_id: str,
        deletion_digest: str,
        acknowledged_impact: bool,
        step_up: VerifiedDeletionApproval | None,
        now: datetime,
    ) -> DeletionPreview:
        """Recheck exact current impact and step-up; deliberately perform no write."""

        now = self._require_utc(now)
        try:
            scope = self._scope(scope)
        except DeletionTargetUnavailable as exc:
            raise DeletionConfirmationRejected from exc
        if (
            not isinstance(deletion_digest, str)
            or acknowledged_impact is not True
            or not isinstance(step_up, VerifiedDeletionApproval)
        ):
            raise DeletionConfirmationRejected
        match = _DIGEST_PATTERN.fullmatch(deletion_digest)
        if not match:
            raise DeletionConfirmationRejected
        issued_at = int(match.group(1))
        age = now.timestamp() - issued_at
        if age < 0 or age >= self._ttl_seconds:
            raise DeletionConfirmationRejected
        try:
            step_up_expires_at = self._require_utc(step_up.expires_at)
        except ValueError as exc:
            raise DeletionConfirmationRejected from exc
        if (
            step_up.account_id != account_id
            or step_up.scope != scope
            or step_up.target_id != target_id
            or step_up_expires_at <= now
        ):
            raise DeletionConfirmationRejected
        try:
            with session.no_autoflush:
                items = self._collect_items(
                    session, account_id=account_id, scope=scope, target_id=target_id
                )
        except DeletionTargetUnavailable as exc:
            raise DeletionConfirmationRejected from exc
        expected = self._digest(account_id, scope, target_id, items, issued_at)
        if not hmac.compare_digest(expected, deletion_digest):
            raise DeletionConfirmationRejected
        return DeletionPreview(
            scope=scope,
            target_id=target_id,
            items=items,
            deletion_digest=expected,
            expires_at=datetime.fromtimestamp(issued_at + self._ttl_seconds, UTC),
        )

    def _collect_items(
        self,
        session: Session,
        *,
        account_id: str,
        scope: DeletionScope,
        target_id: str,
    ) -> tuple[DeletionImpactItem, ...]:
        account = session.get(Account, account_id, populate_existing=True)
        if account is None or account.status != "ACTIVE":
            raise DeletionTargetUnavailable
        if scope == DeletionScope.PROFILE:
            try:
                profile = get_owned_profile(session, account_id=account_id, profile_id=target_id)
            except ResourceNotFound as exc:
                raise DeletionTargetUnavailable from exc
            items = [
                DeletionImpactItem(
                    kind="CAREER_PROFILE",
                    target_id=profile.id,
                    version=profile.version,
                    state=profile.status,
                ),
            ]
            items.extend(self._workspace_items(session, account_id, profile_id=profile.id))
            return tuple(sorted(items, key=lambda item: (item.kind, item.target_id)))
        if scope != DeletionScope.ACCOUNT or target_id != account_id:
            raise DeletionTargetUnavailable

        items = [DeletionImpactItem(kind="ACCOUNT", target_id=account_id, state=account.status)]
        identity_ids = session.scalars(
            select(AuthIdentity.id).where(AuthIdentity.account_id == account_id)
        ).all()
        items.extend(
            DeletionImpactItem(kind="AUTH_IDENTITY", target_id=identity_id)
            for identity_id in identity_ids
        )
        profiles = session.scalars(
            select(CareerProfile)
            .where(CareerProfile.account_id == account_id)
            .execution_options(populate_existing=True)
        ).all()
        items.extend(
            DeletionImpactItem(
                kind="CAREER_PROFILE",
                target_id=profile.id,
                version=profile.version,
                state=profile.status,
            )
            for profile in profiles
        )
        items.extend(self._workspace_items(session, account_id))
        return tuple(sorted(items, key=lambda item: (item.kind, item.target_id)))

    @staticmethod
    def _workspace_items(
        session: Session, account_id: str, *, profile_id: str | None = None
    ) -> list[DeletionImpactItem]:
        workspace_query = select(ProfilingSession).where(ProfilingSession.account_id == account_id)
        if profile_id is not None:
            workspace_query = workspace_query.where(ProfilingSession.profile_id == profile_id)
        workspaces = session.scalars(
            workspace_query.execution_options(populate_existing=True)
        ).all()
        if not workspaces:
            return []
        workspace_ids = [work.id for work in workspaces]
        items = [
            DeletionImpactItem(kind="PROFILING_SESSION", target_id=work.id, state=work.status)
            for work in workspaces
        ]
        input_ids = session.scalars(
            select(ProfilingInput.id).where(
                ProfilingInput.account_id == account_id,
                ProfilingInput.session_id.in_(workspace_ids),
            )
        ).all()
        items.extend(
            DeletionImpactItem(kind="PROFILING_INPUT", target_id=input_id) for input_id in input_ids
        )
        return items

    def _digest(
        self,
        account_id: str,
        scope: DeletionScope,
        target_id: str,
        items: tuple[DeletionImpactItem, ...],
        issued_at: int,
    ) -> str:
        payload = json.dumps(
            {
                "schema": "foundation-v1",
                "account_id": account_id,
                "scope": scope.value,
                "target_id": target_id,
                "issued_at": issued_at,
                "items": [asdict(item) for item in items],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"v1.{issued_at}.{hmac.new(self._secret, payload, hashlib.sha256).hexdigest()}"

    @staticmethod
    def _scope(scope: DeletionScope) -> DeletionScope:
        try:
            return DeletionScope(scope)
        except ValueError as exc:
            raise DeletionTargetUnavailable from exc

    @staticmethod
    def _require_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware UTC datetime required")
        return value.astimezone(UTC)

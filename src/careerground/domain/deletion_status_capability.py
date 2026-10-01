"""Internal, short-lived status proof for a confirmed synthetic deletion.

The issuer marker is passed only by trusted code immediately after explicit
deletion execution. It is not a request-body field, an OAuth scope, or a public
token issuer. No product route exposes this service. A restored database must
pass its independent quarantine reconciliation before either operation works.
"""

from __future__ import annotations

import base64
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careerground.domain.deletion_preview import DeletionScope, VerifiedDeletionApproval
from careerground.storage.models import (
    Account,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    ErasureLedger,
)

_PURPOSE = "SYNTHETIC_DELETION_STATUS_V1"
_TOKEN_KEYS = frozenset(
    {"purpose", "request_id", "account_id", "scope", "target_id", "expires_at", "nonce"}
)


class DeletionStatusCapabilityRejected(Exception):
    """The trusted issuance or exact status read is unavailable."""


@dataclass(frozen=True)
class TrustedDeletionStatusIssuer:
    """Trusted internal handoff from a completed deletion confirmation call.

    This Python type is a caller boundary, not cryptographic authorization by
    itself. The service also rechecks the stored request, ledger, approval and
    account/profile tombstone in the same transaction.
    """

    request_id: str
    approval: VerifiedDeletionApproval


@dataclass(frozen=True)
class DeletionStatusSnapshot:
    erasure_request_id: str
    status: str
    known_local_done: int
    pending_or_failed: int
    unverified: int
    expires_at: datetime
    coverage: str = "FOUNDATION_ONLY"
    ready_to_execute: bool = False


class DeletionStatusCapabilityService:
    """Issue and read one exact deletion's metadata without ACTIVE account auth."""

    def __init__(
        self,
        secret: bytes,
        *,
        restore_quarantine_ready: Callable[[], bool],
        ttl_seconds: int = 300,
    ) -> None:
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("status capability secret too short")
        if not callable(restore_quarantine_ready):
            raise TypeError("restore readiness callback required")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise ValueError("invalid status capability lifetime")
        self._secret = hmac.digest(secret, b"synthetic-deletion-status-capability-v1", "sha256")
        self._ready = restore_quarantine_ready
        self._ttl = timedelta(seconds=ttl_seconds)

    def issue(
        self,
        session: Session,
        *,
        trusted_issuer: TrustedDeletionStatusIssuer,
        now: datetime,
    ) -> str:
        """Return one bearer proof only after a trusted deletion transaction."""

        self._require_ready()
        now = _utc(now)
        if (
            type(trusted_issuer) is not TrustedDeletionStatusIssuer
            or type(trusted_issuer.request_id) is not str
            or not trusted_issuer.request_id
            or type(trusted_issuer.approval) is not VerifiedDeletionApproval
        ):
            raise DeletionStatusCapabilityRejected
        approval = trusted_issuer.approval
        if (
            type(approval.account_id) is not str
            or type(approval.target_id) is not str
            or type(approval.scope) is not DeletionScope
            or _utc(approval.expires_at) <= now
        ):
            raise DeletionStatusCapabilityRejected
        try:
            request = session.get(DeletionRequest, trusted_issuer.request_id)
            if (
                request is None
                or request.account_id != approval.account_id
                or request.scope != approval.scope.value
                or request.target_id != approval.target_id
                or request.status not in {"DELETING", "FAILED"}
                or _utc(request.created_at) > now
                or _utc(request.created_at) >= _utc(approval.expires_at)
                or not self._has_tombstone(session, request)
                or not self._has_ledger(session, request)
            ):
                raise DeletionStatusCapabilityRejected
        except SQLAlchemyError:
            raise DeletionStatusCapabilityRejected from None
        payload = {
            "purpose": _PURPOSE,
            "request_id": request.id,
            "account_id": request.account_id,
            "scope": request.scope,
            "target_id": request.target_id,
            "expires_at": (now + self._ttl).isoformat(),
            "nonce": secrets.token_urlsafe(32),
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.digest(self._secret, body, "sha256")
        return _b64(body) + "." + _b64(signature)

    def read(self, session: Session, *, capability: str, now: datetime) -> DeletionStatusSnapshot:
        """Read only bounded aggregate counts for the exact unexpired request."""

        self._require_ready()
        now = _utc(now)
        payload = self._verify(capability)
        try:
            expires_at = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (TypeError, ValueError):
            raise DeletionStatusCapabilityRejected from None
        if expires_at <= now:
            raise DeletionStatusCapabilityRejected
        try:
            request = session.scalar(
                select(DeletionRequest).where(
                    DeletionRequest.id == payload["request_id"],
                    DeletionRequest.account_id == payload["account_id"],
                    DeletionRequest.scope == payload["scope"],
                    DeletionRequest.target_id == payload["target_id"],
                )
            )
            if (
                request is None
                or not self._has_tombstone(session, request)
                or not self._has_ledger(session, request)
            ):
                raise DeletionStatusCapabilityRejected
            done, pending, unverified = session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    (DeletionWorkItem.action == "ERASE")
                                    & (DeletionWorkItem.status == "DONE"),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((DeletionWorkItem.status != "DONE", 1), else_=0)), 0
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    (DeletionWorkItem.action == "VERIFY")
                                    & (DeletionWorkItem.status != "DONE"),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(DeletionWorkItem.request_id == request.id)
            ).one()
        except SQLAlchemyError:
            raise DeletionStatusCapabilityRejected from None
        return DeletionStatusSnapshot(
            erasure_request_id=request.id,
            status="FAILED" if request.status == "FAILED" else "DELETING",
            known_local_done=done,
            pending_or_failed=pending,
            unverified=unverified,
            expires_at=expires_at,
        )

    def _verify(self, capability: str) -> dict[str, object]:
        if type(capability) is not str or not 1 <= len(capability) <= 1024:
            raise DeletionStatusCapabilityRejected
        if capability.count(".") != 1:
            raise DeletionStatusCapabilityRejected
        try:
            body_text, signature_text = capability.split(".")
            body = _unb64(body_text)
            signature = _unb64(signature_text)
            if (
                len(body) > 512
                or len(signature) != 32
                or not hmac.compare_digest(signature, hmac.digest(self._secret, body, "sha256"))
            ):
                raise DeletionStatusCapabilityRejected
            payload = json.loads(body)
            if (
                type(payload) is not dict
                or set(payload) != _TOKEN_KEYS
                or payload["purpose"] != _PURPOSE
                or any(
                    type(payload[key]) is not str or not payload[key]
                    for key in (
                        "request_id",
                        "account_id",
                        "scope",
                        "target_id",
                        "expires_at",
                        "nonce",
                    )
                )
                or payload["scope"] not in {scope.value for scope in DeletionScope}
                or len(payload["request_id"]) > 36
                or len(payload["account_id"]) > 36
                or len(payload["target_id"]) > 36
            ):
                raise DeletionStatusCapabilityRejected
            return payload
        except (UnicodeError, ValueError, TypeError, KeyError):
            raise DeletionStatusCapabilityRejected from None

    @staticmethod
    def _has_ledger(session: Session, request: DeletionRequest) -> bool:
        return (
            session.scalar(
                select(ErasureLedger.request_id).where(
                    ErasureLedger.request_id == request.id,
                    ErasureLedger.account_id == request.account_id,
                    ErasureLedger.scope == request.scope,
                    ErasureLedger.target_id == request.target_id,
                )
            )
            is not None
        )

    @staticmethod
    def _has_tombstone(session: Session, request: DeletionRequest) -> bool:
        account = session.get(Account, request.account_id)
        if request.scope == DeletionScope.ACCOUNT.value:
            return account is not None and account.status == "DELETING"
        if request.scope == DeletionScope.PROFILE.value:
            profile = session.get(CareerProfile, request.target_id)
            return (
                account is not None
                and account.status == "ACTIVE"
                and profile is not None
                and profile.account_id == request.account_id
                and profile.status == "DELETING"
            )
        return False

    def _require_ready(self) -> None:
        try:
            ready = self._ready()
        except Exception:  # noqa: BLE001 - no restore callback details leave this boundary
            raise DeletionStatusCapabilityRejected from None
        if ready is not True:
            raise DeletionStatusCapabilityRejected


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DeletionStatusCapabilityRejected
    return value.astimezone(UTC)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or len(value) % 4 == 1:
        raise ValueError("invalid encoding")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

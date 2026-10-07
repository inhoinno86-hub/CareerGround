"""Explicit, offline mock deletion journey for a fresh local demo database only.

No route or real step-up issuer lives here. Restored databases must use the
separate restore-quarantine reconciliation, never this fresh-store issuer.
The caller commits the transaction; a failure must roll it back.
"""

from __future__ import annotations

import hashlib
import hmac
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.deletion_execution import apply_deletion_work, execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionConfirmationRejected,
    DeletionPreviewService,
    DeletionScope,
    DeletionTargetUnavailable,
    VerifiedDeletionApproval,
)
from careerground.domain.deletion_status_capability import (
    DeletionStatusCapabilityRejected,
    DeletionStatusCapabilityService,
    DeletionStatusSnapshot,
    TrustedDeletionStatusIssuer,
)
from careerground.storage.models import Account, CareerProfile, DeletionRequest, DeletionWorkItem

_PREVIEW_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "profile_id",
        "profile_version",
        "browser_session_id",
        "scope",
        "target_id",
        "digest",
        "expires_at",
    }
)
_STEP_KEYS = _PREVIEW_KEYS | {"preview_token", "preview_hash", "step_expires_at"}
_ORDER = {
    "PARTIAL_LOCAL_DATA": -1,
    "PROFILING_INPUT": 0,
    "PROFILING_PROTOCOL_STEP": 1,
    "PROFILING_DRAFT": 2,
    "PROFILING_REVIEW_ITEM": 3,
    "PROFILING_REVIEW_BATCH": 4,
    "PROFILING_SESSION": 5,
    "PROFILE_LOCAL_DATA": 6,
    "AUTH_IDENTITY": 7,
    "CAREER_PROFILE": 8,
    "ACCOUNT": 9,
}


class MockDeletionJourneyRejected(Exception):
    """The exact local mock consent, owner, state, or impact is unavailable."""


@dataclass(frozen=True)
class PreviewView:
    scope: str
    target_id: str
    impact_counts: tuple[tuple[str, int], ...]
    preview_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    status_capability: str


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MockDeletionJourneyRejected
    return value.astimezone(UTC)


class MockDeletionJourney:
    """Local-only adapter; instantiate solely for a new synthetic test store."""

    def __init__(self, preview_secret: bytes, ledger_secret: bytes, status_secret: bytes):
        if any(
            type(value) is not bytes or len(value) < 32
            for value in (preview_secret, ledger_secret, status_secret)
        ):
            raise ValueError("short mock deletion secret")
        self._preview = DeletionPreviewService(preview_secret)
        self._ledger_secret = ledger_secret
        self._tokens = BrowserFormTokenCodec(
            hmac.digest(preview_secret, b"mock-deletion-browser-v1", "sha256")
        )
        self._status = DeletionStatusCapabilityService(
            status_secret, restore_quarantine_ready=lambda: True
        )
        # This cache is intentionally process-local and expires with its token.
        # After restart an already executed step cannot be replayed for a new proof.
        self._completed: dict[str, tuple[str, str, datetime]] = {}
        self._cache_lock = Lock()

    @staticmethod
    def _owner(session: Session, account_id: str, profile_id: str, *, lock: bool = False):
        account_query = select(Account).where(Account.id == account_id)
        profile_query = select(CareerProfile).where(
            CareerProfile.id == profile_id, CareerProfile.account_id == account_id
        )
        if lock:
            account_query = account_query.with_for_update()
            profile_query = profile_query.with_for_update()
        account = session.scalar(account_query.execution_options(populate_existing=True))
        profile = session.scalar(profile_query.execution_options(populate_existing=True))
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
        ):
            raise MockDeletionJourneyRejected
        return profile

    @staticmethod
    def _identity(account_id, profile_id, browser_session_id, scope):
        if (
            any(
                type(value) is not str or not 1 <= len(value) <= 128
                for value in (account_id, profile_id, browser_session_id)
            )
            or scope not in {scope.value for scope in DeletionScope}
            or type(scope) is not str
        ):
            raise MockDeletionJourneyRejected

    def preview(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        browser_session_id: str,
        scope: str,
        target_id: str | None = None,
        now: datetime,
    ) -> PreviewView:
        now = _utc(now)
        self._identity(account_id, profile_id, browser_session_id, scope)
        profile = self._owner(session, account_id, profile_id)
        if scope == "ACCOUNT":
            target = account_id
        elif scope == "PROFILE":
            target = profile.id
        elif type(target_id) is str and 1 <= len(target_id) <= 36:
            target = target_id
        else:
            raise MockDeletionJourneyRejected
        try:
            view = self._preview.preview(
                session,
                account_id=account_id,
                scope=DeletionScope(scope),
                target_id=target,
                now=now,
            )
        except DeletionTargetUnavailable:
            raise MockDeletionJourneyRejected from None
        payload = {
            "purpose": "MOCK_DELETION_PREVIEW_V1",
            "account_id": account_id,
            "profile_id": profile_id,
            "profile_version": profile.version,
            "browser_session_id": browser_session_id,
            "scope": scope,
            "target_id": target,
            "digest": view.deletion_digest,
            "expires_at": view.expires_at.isoformat(),
        }
        counts = Counter(item.kind for item in view.items)
        return PreviewView(
            scope,
            target,
            tuple(sorted(counts.items())),
            self._tokens.sign(payload),
            view.expires_at,
        )

    def _verify_preview(self, token, account_id, profile_id, browser_session_id, now):
        try:
            payload = self._tokens.verify(token, expected_keys=_PREVIEW_KEYS)
            expires = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError):
            raise MockDeletionJourneyRejected from None
        if (
            payload["purpose"] != "MOCK_DELETION_PREVIEW_V1"
            or payload["account_id"] != account_id
            or payload["profile_id"] != profile_id
            or payload["browser_session_id"] != browser_session_id
            or payload["scope"] not in {scope.value for scope in DeletionScope}
            or type(payload["profile_version"]) is not int
            or type(payload["digest"]) is not str
            or type(payload["target_id"]) is not str
            or (
                payload["scope"] in {"ACCOUNT", "PROFILE"}
                and payload["target_id"]
                != (account_id if payload["scope"] == "ACCOUNT" else profile_id)
            )
            or not 1 <= len(payload["target_id"]) <= 36
            or expires <= now
        ):
            raise MockDeletionJourneyRejected
        return payload, expires

    def reauthenticate(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        browser_session_id: str,
        preview_token: str,
        acknowledged_impact: bool,
        mock_reauthenticated: bool,
        now: datetime,
    ) -> str:
        now = _utc(now)
        self._identity(account_id, profile_id, browser_session_id, "PROFILE")
        if acknowledged_impact is not True or mock_reauthenticated is not True:
            raise MockDeletionJourneyRejected
        payload, expiry = self._verify_preview(
            preview_token, account_id, profile_id, browser_session_id, now
        )
        profile = self._owner(session, account_id, profile_id)
        if profile.version != payload["profile_version"]:
            raise MockDeletionJourneyRejected
        approval = VerifiedDeletionApproval(
            account_id, DeletionScope(payload["scope"]), payload["target_id"], expiry
        )
        try:
            self._preview.confirm_intent(
                session,
                account_id=account_id,
                scope=approval.scope,
                target_id=approval.target_id,
                deletion_digest=payload["digest"],
                acknowledged_impact=True,
                step_up=approval,
                now=now,
            )
        except DeletionConfirmationRejected:
            raise MockDeletionJourneyRejected from None
        step_expiry = min(expiry, now + timedelta(minutes=3))
        return self._tokens.sign(
            {
                **payload,
                "purpose": "MOCK_STEP_UP_V1",
                "preview_token": preview_token,
                "preview_hash": hashlib.sha256(preview_token.encode()).hexdigest(),
                "step_expires_at": step_expiry.isoformat(),
            }
        )

    def _verify_step(self, step_up_token, account_id, profile_id, browser_session_id, now):
        try:
            step = self._tokens.verify(step_up_token, expected_keys=_STEP_KEYS)
            step_expiry = _utc(datetime.fromisoformat(step["step_expires_at"]))
            preview, preview_expiry = self._verify_preview(
                step["preview_token"], account_id, profile_id, browser_session_id, now
            )
        except (BrowserFormTokenRejected, TypeError, ValueError):
            raise MockDeletionJourneyRejected from None
        if (
            step["purpose"] != "MOCK_STEP_UP_V1"
            or step_expiry <= now
            or step_expiry > preview_expiry
            or type(step["preview_hash"]) is not str
            or not hmac.compare_digest(
                step["preview_hash"], hashlib.sha256(step["preview_token"].encode()).hexdigest()
            )
            or any(step[key] != preview[key] for key in _PREVIEW_KEYS - {"purpose"})
        ):
            raise MockDeletionJourneyRejected
        return preview, step_expiry, step["preview_token"]

    def describe_step(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        browser_session_id: str,
        step_up_token: str,
        now: datetime,
    ) -> PreviewView:
        """Show the exact current impact again before the final browser action."""

        now = _utc(now)
        self._identity(account_id, profile_id, browser_session_id, "PROFILE")
        preview, step_expiry, preview_token = self._verify_step(
            step_up_token, account_id, profile_id, browser_session_id, now
        )
        profile = self._owner(session, account_id, profile_id)
        if profile.version != preview["profile_version"]:
            raise MockDeletionJourneyRejected
        approval = VerifiedDeletionApproval(
            account_id, DeletionScope(preview["scope"]), preview["target_id"], step_expiry
        )
        try:
            current = self._preview.confirm_intent(
                session,
                account_id=account_id,
                scope=approval.scope,
                target_id=approval.target_id,
                deletion_digest=preview["digest"],
                acknowledged_impact=True,
                step_up=approval,
                now=now,
            )
        except DeletionConfirmationRejected:
            raise MockDeletionJourneyRejected from None
        counts = Counter(item.kind for item in current.items)
        return PreviewView(
            preview["scope"],
            preview["target_id"],
            tuple(sorted(counts.items())),
            preview_token,
            step_expiry,
        )

    def execute(
        self,
        session: Session,
        *,
        account_id: str,
        profile_id: str,
        browser_session_id: str,
        step_up_token: str,
        confirmed: bool,
        now: datetime,
    ) -> ExecutionResult:
        now = _utc(now)
        self._identity(account_id, profile_id, browser_session_id, "PROFILE")
        if confirmed is not True:
            raise MockDeletionJourneyRejected
        preview, step_expiry, _ = self._verify_step(
            step_up_token, account_id, profile_id, browser_session_id, now
        )
        token_key = hmac.digest(self._ledger_secret, step_up_token.encode(), "sha256").hex()
        with self._cache_lock:
            self._completed = {
                key: value for key, value in self._completed.items() if value[2] > now
            }
            cached = self._completed.get(token_key)
            if cached is None and len(self._completed) >= 128:
                raise MockDeletionJourneyRejected
        # SQLite needs a write reservation before the first read. PostgreSQL
        # follows the same Account -> Profile lock order as deletion_execution.
        session.execute(
            update(Account).where(Account.id == account_id).values(status=Account.status)
        )
        existing = session.scalar(
            select(DeletionRequest).where(
                DeletionRequest.account_id == account_id,
                DeletionRequest.scope == preview["scope"],
                DeletionRequest.target_id == preview["target_id"],
            )
        )
        if existing is not None:
            with self._cache_lock:
                cached = self._completed.get(token_key)
            if (
                cached is None
                or cached[0] != existing.id
                or existing.impact_digest != preview["digest"]
            ):
                raise MockDeletionJourneyRejected
            return ExecutionResult(existing.id, cached[1])
        profile = self._owner(session, account_id, profile_id, lock=True)
        if profile.version != preview["profile_version"]:
            raise MockDeletionJourneyRejected
        approval = VerifiedDeletionApproval(
            account_id, DeletionScope(preview["scope"]), preview["target_id"], step_expiry
        )
        try:
            request = execute_synthetic_deletion(
                session,
                preview_service=self._preview,
                ledger_secret=self._ledger_secret,
                account_id=account_id,
                scope=approval.scope,
                target_id=approval.target_id,
                deletion_digest=preview["digest"],
                acknowledged_impact=True,
                step_up=approval,
                now=now,
            )
            session.flush()
            work = tuple(
                session.scalars(
                    select(DeletionWorkItem).where(
                        DeletionWorkItem.request_id == request.id,
                        DeletionWorkItem.action == "ERASE",
                    )
                )
            )
            for item in sorted(work, key=lambda item: (_ORDER.get(item.kind, 20), item.target_id)):
                apply_deletion_work(session, item.id)
            session.flush()
            capability = self._status.issue(
                session, trusted_issuer=TrustedDeletionStatusIssuer(request.id, approval), now=now
            )
        except (
            DeletionConfirmationRejected,
            DeletionStatusCapabilityRejected,
            ValueError,
            KeyError,
        ):
            raise MockDeletionJourneyRejected from None
        with self._cache_lock:
            self._completed[token_key] = (request.id, capability, step_expiry)
        return ExecutionResult(request.id, capability)

    def read_status(
        self, session: Session, *, capability: str, now: datetime
    ) -> DeletionStatusSnapshot:
        try:
            return self._status.read(session, capability=capability, now=_utc(now))
        except DeletionStatusCapabilityRejected:
            raise MockDeletionJourneyRejected from None

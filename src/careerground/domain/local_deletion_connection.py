"""Ephemeral synthetic connection approval; no production step-up provider."""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from careerground.domain.browser_operations import BrowserOperationService
from careerground.domain.deletion_preview import DeletionPreviewService, DeletionScope
from careerground.storage.graph_models import EvidenceItem
from careerground.storage.models import CareerProfile, ProfilingSession, ProjectScope


class LocalDeletionConnectionRejected(ValueError):
    pass


@dataclass
class PendingDeletion:
    id: str
    account_id: str
    profile_id: str
    profile_version: int
    scope: str
    target_id: str
    connection: str
    arguments: tuple
    created_at: datetime
    expires_at: datetime
    digest: str
    browser_state: dict | None = None
    step_up_token: str | None = None
    receipt_hash: str | None = None
    result: dict | None = None


class LocalDeletionConnection:
    """Only usable with loopback synthetic identities, browser proof, and mock journey."""

    def __init__(self, demo, journey):
        self.demo = demo
        self.journey = journey
        self.previews = DeletionPreviewService(demo.presentation_secret)
        self.pending: dict[str, PendingDeletion] = {}
        self.lock = threading.RLock()

    def request_or_execute(
        self,
        *,
        account_id,
        connection,
        connection_expires_at,
        scope,
        target_id,
        profile_version,
        idempotency_key,
        approval_receipt,
    ):
        if (
            type(scope) is not str
            or scope not in {item.value for item in DeletionScope}
            or type(profile_version) is not int
            or profile_version < 0
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", idempotency_key)
            or len(target_id) > 36
            or len(approval_receipt) > 256
        ):
            raise LocalDeletionConnectionRejected
        args = (scope, target_id, profile_version, idempotency_key)
        with self.lock:
            now = datetime.now(UTC)
            if type(connection_expires_at) is not int or connection_expires_at <= now.timestamp():
                raise LocalDeletionConnectionRejected
            self.pending = {key: row for key, row in self.pending.items() if row.expires_at > now}
            row = next(
                (
                    row
                    for row in self.pending.values()
                    if row.account_id == account_id
                    and row.connection == connection
                    and row.arguments[-1] == idempotency_key
                ),
                None,
            )
            if row is not None and row.arguments != args:
                raise LocalDeletionConnectionRejected
            if approval_receipt:
                if (
                    row is None
                    or row.receipt_hash != hashlib.sha256(approval_receipt.encode()).hexdigest()
                    or row.browser_state is None
                    or row.step_up_token is None
                ):
                    raise LocalDeletionConnectionRejected
                if row.result is not None:
                    return row.result
                if row.browser_state not in self.demo.browsers.values():
                    raise LocalDeletionConnectionRejected
                with self.demo.sessions() as session:
                    result = self.journey.execute(
                        session,
                        account_id=account_id,
                        profile_id=row.profile_id,
                        browser_session_id=row.browser_state["session_id"],
                        step_up_token=row.step_up_token,
                        confirmed=True,
                        now=datetime.now(UTC),
                    )
                    self.demo.before_deletion_commit(session)
                    session.commit()
                self.demo.after_deletion_commit()
                row.browser_state["deletion_capability"] = result.status_capability
                row.result = {
                    "status": "DELETING",
                    "erasure_request_id": result.request_id,
                    "coverage": "FOUNDATION_ONLY",
                    "completed_in_browser": True,
                    "ready_to_execute": False,
                    "mode": "MOCK_ONLY",
                }
                return row.result
            if row is None:
                if len(self.pending) >= 128:
                    raise LocalDeletionConnectionRejected
                with self.demo.sessions() as session:
                    if scope == "PROFILE":
                        profile = session.get(CareerProfile, target_id)
                    elif scope == "ACCOUNT":
                        profile = (
                            session.query(CareerProfile)
                            .filter_by(account_id=account_id, status="ACTIVE")
                            .one_or_none()
                        )
                    else:
                        model = {
                            "SESSION": ProfilingSession,
                            "EVIDENCE": EvidenceItem,
                            "PROJECT": ProjectScope,
                        }[scope]
                        target = session.get(model, target_id)
                        if (
                            target is None
                            or target.account_id != account_id
                            or (scope == "EVIDENCE" and target.status != "ACTIVE")
                            or (scope == "PROJECT" and target.status != "ACTIVE")
                            or (
                                scope == "SESSION"
                                and target.status not in {"ACTIVE", "PAUSED", "EXPIRED"}
                            )
                        ):
                            raise LocalDeletionConnectionRejected
                        profile = session.get(CareerProfile, target.profile_id)
                    if (
                        profile is None
                        or profile.account_id != account_id
                        or profile.status != "ACTIVE"
                        or profile.version != profile_version
                        or (scope == "ACCOUNT" and target_id != account_id)
                    ):
                        raise LocalDeletionConnectionRejected
                    view = self.previews.preview(
                        session,
                        account_id=account_id,
                        scope=DeletionScope(scope),
                        target_id=target_id,
                        now=now,
                    )
                row = PendingDeletion(
                    str(uuid4()),
                    account_id,
                    profile.id,
                    profile_version,
                    scope,
                    target_id,
                    connection,
                    args,
                    now,
                    min(
                        now + timedelta(seconds=300),
                        datetime.fromtimestamp(connection_expires_at, UTC),
                    ),
                    view.deletion_digest,
                )
                self.pending[row.id] = row
            return {
                "request_id": row.id,
                "status": "WAITING",
                "confirmation_path": "/demo/deletion/confirmation/" + row.id,
                "expires_at": row.expires_at.isoformat(),
                "mode": "MOCK_ONLY",
                "user_message": "삭제 영향과 별도 모의 재인증을 직접 확인한 뒤 이 연결의 삭제 실행을 승인하세요.",
            }

    def bind_browser(self, session, request_id, state):
        with self.lock:
            row = self.pending.get(request_id)
            if (
                row is None
                or row.expires_at <= datetime.now(UTC)
                or row.account_id != state["account_id"]
                or row.profile_id != state["profile_id"]
                or (row.browser_state is not None and row.browser_state is not state)
            ):
                raise LocalDeletionConnectionRejected
            from careerground.local_demo import ISSUER

            expected_connection = BrowserOperationService(
                self.demo.review_secret, self.demo.presentation_secret
            ).connection_key(
                ISSUER,
                "demo-subject-" + state["label"],
                "local-demo-" + state["session_id"],
                state.get("access_token", ""),
            )
            if expected_connection != row.connection:
                raise LocalDeletionConnectionRejected
            profile = session.get(CareerProfile, row.profile_id)
            view = self.previews.preview(
                session,
                account_id=row.account_id,
                scope=DeletionScope(row.scope),
                target_id=row.target_id,
                now=row.created_at,
            )
            if (
                profile is None
                or profile.version != row.profile_version
                or view.deletion_digest != row.digest
            ):
                raise LocalDeletionConnectionRejected
            row.browser_state = state
            return row

    def approve(self, session, state, step_up_token, request_id):
        with self.lock:
            row = self.bind_browser(session, request_id, state)
            view = self.journey.describe_step(
                session,
                account_id=state["account_id"],
                profile_id=state["profile_id"],
                browser_session_id=state["session_id"],
                step_up_token=step_up_token,
                now=datetime.now(UTC),
            )
            if view.scope != row.scope or view.target_id != row.target_id:
                raise LocalDeletionConnectionRejected
            if row.receipt_hash is not None:
                raise LocalDeletionConnectionRejected
            receipt = secrets.token_urlsafe(32)
            row.receipt_hash = hashlib.sha256(receipt.encode()).hexdigest()
            row.step_up_token = step_up_token
            return receipt

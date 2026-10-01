"""Trusted browser executes exact operations; MCP consumes short-lived metadata receipts.

An MCP confirmation request never approves or mutates canonical content. Browser
confirmation uses the existing session-bound services. Receipts bind the verified
OAuth account/subject/client and are only revealed after that browser commit.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from careerground.domain.artifact_operation_presentation import (
    ARTIFACT_ACTIONS,
    ArtifactOperationPresentationService,
    ArtifactOperationRejected,
    owned_jd_profile_id,
)
from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.claim_review_workspace import ClaimReviewPreparation
from careerground.domain.policy_review_presentation import (
    POLICY_ACTIONS,
    PolicyPresentationRejected,
    PolicyReviewPresentationService,
    owned_claim_profile_id,
)
from careerground.domain.profile_export import export_profile_data
from careerground.domain.profile_export_presentation import (
    ProfileExportPresentationRejected,
    ProfileExportPresentationService,
)
from careerground.domain.resume_export_presentation import (
    ResumeExportPresentationRejected,
    ResumeExportPresentationService,
)
from careerground.domain.resume_wording_presentation import (
    WordingPresentationRejected,
    WordingPresentationService,
)
from careerground.domain.resume_wording_review import WordingReviewService
from careerground.domain.review_presentation import (
    ReviewPresentationRejected,
    ReviewPresentationService,
)
from careerground.storage.jd_artifact_models import Artifact
from careerground.storage.models import (
    Account,
    BrowserOperation,
    CareerProfile,
    ProfilingReviewBatch,
)

OPERATIONS = (
    frozenset({"FACT_REVIEW", "WORDING_REVIEW", "PROFILE_EXPORT", "RESUME_EXPORT"})
    | POLICY_ACTIONS
    | ARTIFACT_ACTIONS
)
TTL = timedelta(minutes=5)
_FORM_KEYS = frozenset(
    {
        "purpose",
        "operation_id",
        "account_id",
        "browser_session_id",
        "action",
        "inner_token",
        "expires_at",
    }
)


class BrowserOperationRejected(Exception):
    """Confirmation, owner, connection or currently usable source is unavailable."""


class BrowserOperationUnavailable(BrowserOperationRejected):
    """Missing and foreign targets have the same public result."""


_PRESENTATION_ERRORS = (
    ReviewPresentationRejected,
    WordingPresentationRejected,
    ProfileExportPresentationRejected,
    ResumeExportPresentationRejected,
    PolicyPresentationRejected,
    ArtifactOperationRejected,
)


@dataclass(frozen=True)
class OperationPresentation:
    operation: BrowserOperation
    view: object
    confirmation_token: str


class BrowserOperationService:
    def __init__(self, review_secret: bytes, presentation_secret: bytes) -> None:
        self.secret = hmac.digest(review_secret, b"browser-operation-receipt-v1", "sha256")
        self.tokens = BrowserFormTokenCodec(presentation_secret)
        self.policy = PolicyReviewPresentationService(review_secret, presentation_secret)
        self.artifacts = ArtifactOperationPresentationService(presentation_secret)
        self.fact = ReviewPresentationService(
            ClaimReviewPreparation(review_secret), presentation_secret
        )
        self.wording_domain = WordingReviewService(
            hmac.digest(review_secret, b"synthetic-r1-wording-review-v1", "sha256")
        )
        self.wording = WordingPresentationService(self.wording_domain, presentation_secret)
        self.profile_export = ProfileExportPresentationService(presentation_secret)
        self.resume_export = ResumeExportPresentationService(
            self.wording_domain, presentation_secret
        )

    def _hash(self, purpose: str, *values: str) -> str:
        return hmac.new(
            self.secret,
            json.dumps([purpose, *values], separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()

    def connection_key(self, issuer: str, subject: str, client_id: str, credential: str) -> str:
        if (
            not all(type(value) is str and value for value in (issuer, subject, client_id))
            or len(client_id) > 128
        ):
            raise BrowserOperationRejected
        if type(credential) is not str or not 1 <= len(credential) <= 16384:
            raise BrowserOperationRejected
        return self._hash("connection", issuer, subject, client_id, credential)

    def request(
        self,
        session: Session,
        *,
        account_id: str,
        connection_key: str,
        client_id: str,
        action: str,
        target_id: str,
        profile_version: int,
        format: str,
        idempotency_key: str,
        now: datetime,
    ) -> BrowserOperation:
        now = _utc(now)
        if (
            action not in OPERATIONS
            or type(target_id) is not str
            or not 1 <= len(target_id) <= 36
            or type(profile_version) is not int
            or profile_version < 0
        ):
            raise BrowserOperationRejected
        if format not in (
            {"JSON", "MARKDOWN"}
            if action == "RESUME_EXPORT"
            else {"JSON"}
            if action == "PROFILE_EXPORT"
            else {"NONE"}
        ):
            raise BrowserOperationRejected
        if not 16 <= len(idempotency_key) <= 128 or any(
            char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
            for char in idempotency_key
        ):
            raise BrowserOperationRejected
        profile_id = target_id
        if action in {"JD_LINK", "R1_DRAFT"}:
            try:
                profile_id = owned_jd_profile_id(session, account_id, target_id)
            except ArtifactOperationRejected:
                raise BrowserOperationRejected from None
        elif action in POLICY_ACTIONS:
            try:
                profile_id = owned_claim_profile_id(session, account_id, target_id)
            except PolicyPresentationRejected:
                raise BrowserOperationRejected from None
        elif action == "FACT_REVIEW":
            batch = session.scalar(
                select(ProfilingReviewBatch).where(
                    ProfilingReviewBatch.id == target_id,
                    ProfilingReviewBatch.account_id == account_id,
                )
            )
            if batch is None or batch.base_profile_version != profile_version:
                raise BrowserOperationRejected
            profile_id = batch.profile_id
        elif action in {"WORDING_REVIEW", "RESUME_EXPORT"}:
            artifact = session.scalar(
                select(Artifact).where(Artifact.id == target_id, Artifact.account_id == account_id)
            )
            if artifact is None or artifact.profile_version != profile_version:
                raise BrowserOperationRejected
            profile_id = artifact.profile_id
        try:
            get_owned_profile(session, account_id=account_id, profile_id=profile_id)
        except ResourceNotFound:
            raise BrowserOperationRejected from None
        key = self._hash("request", account_id, connection_key, idempotency_key)
        existing = session.scalar(
            select(BrowserOperation).where(BrowserOperation.request_key == key)
        )
        if existing is not None:
            return self._same_request(existing, action, target_id, profile_version, format, now)
        candidate = BrowserOperation(
            id=str(uuid4()),
            account_id=account_id,
            profile_id=profile_id,
            connection_key=connection_key,
            client_id=client_id,
            request_key=key,
            action=action,
            target_id=target_id,
            profile_version=profile_version,
            format=format,
            status="WAITING",
            created_at=now,
            expires_at=now + TTL,
        )
        # Check availability with a synthetic non-user session; no approval is issued to MCP.
        self._view(session, candidate, "unapproved-request-check-session", now)
        try:
            with session.begin_nested():
                session.add(candidate)
                session.flush()
        except IntegrityError:
            existing = session.scalar(
                select(BrowserOperation).where(BrowserOperation.request_key == key)
            )
            if existing is None:
                raise BrowserOperationRejected from None
            return self._same_request(existing, action, target_id, profile_version, format, now)
        return candidate

    @staticmethod
    def _same_request(row, action, target_id, version, format, now):
        if (row.action, row.target_id, row.profile_version, row.format) != (
            action,
            target_id,
            version,
            format,
        ) or _utc(row.expires_at) <= now:
            raise BrowserOperationRejected
        return row

    def _owned(self, session, account_id, operation_id, now, *, lock=False):
        query = select(BrowserOperation).where(
            BrowserOperation.id == operation_id, BrowserOperation.account_id == account_id
        )
        if lock:
            query = query.with_for_update()
        row = session.scalar(query.execution_options(populate_existing=True))
        if row is None or _utc(row.expires_at) <= _utc(now):
            raise BrowserOperationRejected
        account = session.get(Account, account_id)
        if account is None or account.status != "ACTIVE":
            raise BrowserOperationRejected
        try:
            get_owned_profile(session, account_id=account_id, profile_id=row.profile_id)
        except ResourceNotFound:
            raise BrowserOperationRejected from None
        return row

    def _view(self, session, row, browser_session_id, now):
        try:
            if row.action in POLICY_ACTIONS | ARTIFACT_ACTIONS:
                self._lock_owner_profile(session, row)
            view = self._present_view(session, row, browser_session_id, now)
            version = (
                view.base_profile_version
                if row.action == "FACT_REVIEW"
                else view.review.profile_version
                if row.action == "WORDING_REVIEW"
                else view.profile_version
            )
            if version != row.profile_version:
                raise BrowserOperationRejected
            return view
        except _PRESENTATION_ERRORS:
            raise BrowserOperationRejected from None

    def _present_view(self, session, row, browser_session_id, now):
        common = {
            "account_id": row.account_id,
            "browser_session_id": browser_session_id,
            "now": now,
        }
        if row.action in ARTIFACT_ACTIONS:
            return self.artifacts.present(
                session, row=row, browser_session_id=browser_session_id, now=now
            )
        if row.action in POLICY_ACTIONS:
            return self.policy.present(
                session, row=row, browser_session_id=browser_session_id, now=now
            )
        if row.action == "FACT_REVIEW":
            return self.fact.present(session, batch_id=row.target_id, **common)
        if row.action == "WORDING_REVIEW":
            return self.wording.present(session, artifact_id=row.target_id, **common)
        if row.action == "PROFILE_EXPORT":
            return self.profile_export.present(
                session, profile_id=row.target_id, profile_version=row.profile_version, **common
            )
        return self.resume_export.present(
            session, artifact_id=row.target_id, format=row.format, **common
        )

    def present(self, session, *, account_id, browser_session_id, operation_id, now):
        row = self._owned(session, account_id, operation_id, now)
        if row.status != "WAITING":
            if row.browser_key != self._hash("browser", browser_session_id):
                raise BrowserOperationRejected
            return OperationPresentation(row, None, "")
        view = self._view(session, row, browser_session_id, now)
        if row.action in POLICY_ACTIONS | ARTIFACT_ACTIONS:
            return OperationPresentation(row, view, "")
        inner = (
            view.approval_token
            if row.action in {"FACT_REVIEW", "WORDING_REVIEW"}
            else view.export_token
        )
        return self._wrap_presentation(row, view, inner, account_id, browser_session_id)

    def _wrap_presentation(self, row, view, inner, account_id, browser_session_id):
        token = self.tokens.sign(
            {
                "purpose": "MCP_BROWSER_CONFIRMATION_V1",
                "operation_id": row.id,
                "account_id": account_id,
                "browser_session_id": browser_session_id,
                "action": row.action,
                "inner_token": inner,
                "expires_at": _utc(row.expires_at).isoformat(),
            }
        )
        return OperationPresentation(row, view, token)

    def prepare_policy(
        self, session, *, account_id, browser_session_id, operation_id, choice_token, fields, now
    ):
        row = self._owned(session, account_id, operation_id, now)
        if row.action not in POLICY_ACTIONS | ARTIFACT_ACTIONS or row.status != "WAITING":
            raise BrowserOperationRejected
        self._lock_owner_profile(session, row)
        try:
            service = self.policy if row.action in POLICY_ACTIONS else self.artifacts
            view = service.prepare(
                session,
                row=row,
                browser_session_id=browser_session_id,
                choice_token=choice_token,
                fields=fields,
                now=now,
            )
        except (PolicyPresentationRejected, ArtifactOperationRejected):
            raise BrowserOperationRejected from None
        return self._wrap_presentation(
            row, view, view.approval_token, account_id, browser_session_id
        )

    @staticmethod
    def _lock_owner_profile(session, row):
        account = session.scalar(
            select(Account)
            .where(Account.id == row.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        profile = session.scalar(
            select(CareerProfile)
            .where(CareerProfile.id == row.profile_id, CareerProfile.account_id == row.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
            or profile.version != row.profile_version
        ):
            raise BrowserOperationRejected

    def confirm(self, session, **kwargs):
        try:
            return self._confirm(session, **kwargs)
        except _PRESENTATION_ERRORS:
            raise BrowserOperationRejected from None

    def _confirm(
        self,
        session,
        *,
        account_id,
        browser_session_id,
        operation_id,
        confirmation_token,
        decisions=(),
        confirm_value=None,
        submission_fields=None,
        now,
    ):
        now = _utc(now)
        submission_fields = submission_fields or {}
        try:
            payload = self.tokens.verify(confirmation_token, expected_keys=_FORM_KEYS)
            expiry = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError):
            raise BrowserOperationRejected from None
        if (
            payload["purpose"],
            payload["operation_id"],
            payload["account_id"],
            payload["browser_session_id"],
        ) != (
            "MCP_BROWSER_CONFIRMATION_V1",
            operation_id,
            account_id,
            browser_session_id,
        ) or expiry <= now:
            raise BrowserOperationRejected
        # SQLite takes a write reservation before reading state; PostgreSQL also
        # serializes this row. Losing concurrent submissions observe the receipt.
        session.execute(
            update(BrowserOperation)
            .where(BrowserOperation.id == operation_id, BrowserOperation.account_id == account_id)
            .values(status=BrowserOperation.status)
        )
        row = self._owned(session, account_id, operation_id, now, lock=True)
        browser_key = self._hash("browser", browser_session_id)
        expected = (
            "confirm_artifact"
            if row.action in ARTIFACT_ACTIONS
            else "confirm_policy"
            if row.action in POLICY_ACTIONS
            else "reviewed"
            if row.action == "FACT_REVIEW"
            else "accept_r1"
            if row.action == "WORDING_REVIEW"
            else "download"
        )
        if confirm_value != expected or (row.action != "FACT_REVIEW" and decisions):
            raise BrowserOperationRejected
        if submission_fields and row.action not in POLICY_ACTIONS | ARTIFACT_ACTIONS:
            raise BrowserOperationRejected
        confirmation_key = self._hash(
            "confirmed",
            confirmation_token,
            json.dumps(
                [decisions, submission_fields] if submission_fields else decisions,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        if payload["action"] != row.action or expiry != _utc(row.expires_at):
            raise BrowserOperationRejected
        if row.status in {"DONE", "CONSUMED"}:
            if row.browser_key != browser_key or row.confirmation_key != confirmation_key:
                raise BrowserOperationRejected
            return row
        common = {"account_id": account_id, "browser_session_id": browser_session_id, "now": now}
        if row.action in POLICY_ACTIONS | ARTIFACT_ACTIONS:
            # Serialize distinct operations on the same owner before context
            # reads acquire archive SHARE locks. Otherwise two confirmations
            # can both hold SHARE and deadlock when domain submit upgrades it.
            self._lock_owner_profile(session, row)
            service = self.policy if row.action in POLICY_ACTIONS else self.artifacts
            result = service.submit(
                session,
                row=row,
                approval_token=payload["inner_token"],
                fields=submission_fields,
                browser_session_id=browser_session_id,
                now=now,
            )
        elif row.action == "FACT_REVIEW":
            change = self.fact.submit(
                session,
                batch_id=row.target_id,
                approval_token=payload["inner_token"],
                decisions=decisions,
                **common,
            )
            result = {
                "review_batch_id": row.target_id,
                "profile_id": row.profile_id,
                "version_after": change.version_after if change else row.profile_version,
            }
        elif row.action == "WORDING_REVIEW":
            review = self.wording.submit(
                session, artifact_id=row.target_id, approval_token=payload["inner_token"], **common
            )
            result = {
                "artifact_id": row.target_id,
                "review_id": review.id,
                "artifact_version": review.artifact_version,
                "profile_version": review.profile_version,
            }
        else:
            if row.action == "PROFILE_EXPORT":
                export = self.profile_export.submit(
                    session,
                    profile_id=row.target_id,
                    profile_version=row.profile_version,
                    export_token=payload["inner_token"],
                    **common,
                )
                size = len(export.content_json.encode())
            else:
                export = self.resume_export.submit(
                    session,
                    artifact_id=row.target_id,
                    format=row.format,
                    export_token=payload["inner_token"],
                    **common,
                )
                size = len(export.content_text.encode())
            result = {
                "resource_uri": "careerground://exports/" + row.id,
                "format": row.format,
                "profile_version": row.profile_version,
                "content_hash": export.content_hash,
                "content_bytes": size,
                "expires_at": _utc(row.expires_at).isoformat(),
            }
        row.browser_key = browser_key
        row.confirmation_key = confirmation_key
        row.result_json = json.dumps(
            {**result, "completed_in_browser": True}, sort_keys=True, separators=(",", ":")
        )
        row.status = "DONE"
        session.flush()
        return row

    def receipt(self, row):
        if row.status not in {"DONE", "CONSUMED"} or not row.browser_key:
            raise BrowserOperationRejected
        return row.id + "." + self._hash("receipt", row.id, row.connection_key, row.browser_key)

    def consume(
        self,
        session,
        *,
        account_id,
        connection_key,
        action,
        target_id,
        receipt,
        now,
        profile_version=None,
        format=None,
    ):
        if type(receipt) is not str or len(receipt) != 101 or receipt.count(".") != 1:
            raise BrowserOperationRejected
        operation_id = receipt.split(".")[0]
        row = self._owned(session, account_id, operation_id, now, lock=True)
        if (
            row.connection_key != connection_key
            or row.action != action
            or row.target_id != target_id
            or row.status not in {"DONE", "CONSUMED"}
            or not hmac.compare_digest(receipt, self.receipt(row))
        ):
            raise BrowserOperationRejected
        if (profile_version is not None and row.profile_version != profile_version) or (
            format is not None and row.format != format
        ):
            raise BrowserOperationRejected
        if row.status == "DONE":
            row.status = "CONSUMED"
            row.consumed_at = _utc(now)
        return json.loads(row.result_json)

    def read_export(self, session, *, account_id, connection_key, operation_id, now):
        row = self._owned(session, account_id, operation_id, now)
        if (
            row.connection_key != connection_key
            or row.status != "CONSUMED"
            or row.action not in {"PROFILE_EXPORT", "RESUME_EXPORT"}
        ):
            raise BrowserOperationRejected
        metadata = json.loads(row.result_json)
        if row.action == "PROFILE_EXPORT":
            export = export_profile_data(
                session,
                account_id=account_id,
                profile_id=row.target_id,
                profile_version=row.profile_version,
            )
            content = export.content_json
        else:
            export = self.wording_domain.export_resume(
                session, account_id=account_id, artifact_id=row.target_id, format=row.format
            )
            content = export.content_text
        if not hmac.compare_digest(export.content_hash, metadata["content_hash"]):
            raise BrowserOperationRejected
        return content


def prune_browser_operations(session: Session, *, now: datetime, limit: int = 100) -> int:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("invalid confirmation cleanup limit")
    query = (
        select(BrowserOperation.id)
        .where(BrowserOperation.expires_at <= _utc(now))
        .order_by(BrowserOperation.expires_at, BrowserOperation.id)
        .limit(limit)
    )
    if session.get_bind().dialect.name == "sqlite":
        return session.execute(
            delete(BrowserOperation).where(BrowserOperation.id.in_(query))
        ).rowcount
    rows = tuple(session.scalars(query.with_for_update(skip_locked=True)))
    if not rows:
        return 0
    return session.execute(
        delete(BrowserOperation).where(
            BrowserOperation.id.in_(rows), BrowserOperation.expires_at <= _utc(now)
        )
    ).rowcount


def _utc(value):
    if not isinstance(value, datetime):
        raise BrowserOperationRejected
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

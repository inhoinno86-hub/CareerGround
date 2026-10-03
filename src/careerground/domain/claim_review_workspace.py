"""Synthetic, temporary exact review preparation; no canonical promotion yet."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.project_scope_guard import deleted_project_scope_exists
from careerground.storage.models import (
    Account,
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)

REVIEW_TTL = timedelta(minutes=10)
_SCOPE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_CLAIM_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,31}\Z")
_PREPARE_KEY = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_PREPARE_NAMESPACE = UUID("539bb5b0-3862-4af4-bd60-48cf96d468d5")


class ReviewUnavailable(Exception):
    """Review or source is absent from this active owner's view."""


class ReviewStale(Exception):
    """The exact prepared wording, source or profile version changed."""


class ReviewIdempotencyConflict(Exception):
    """A preparation key was reused for a different review target."""


def propose_verbatim_draft(
    session: Session,
    *,
    account_id: str,
    profiling_session_id: str,
    source_input_id: str,
    scope_key: str,
    claim_type: str,
    exact_text: str,
    now: datetime,
    draft_id: str | None = None,
) -> ProfilingDraft:
    """Only a source substring may be proposed; no AI inference or approval occurs."""

    now = _utc(now)
    if (
        not isinstance(scope_key, str)
        or not _SCOPE.fullmatch(scope_key)
        or not isinstance(claim_type, str)
        or not _CLAIM_TYPE.fullmatch(claim_type)
        or not isinstance(exact_text, str)
        or not exact_text.strip()
        or len(exact_text) > 20_000
    ):
        raise ValueError("invalid bounded draft")
    work, profile = _owned_work(session, account_id, profiling_session_id)
    if work.status not in {"ACTIVE", "PAUSED"} or _stored_utc(work.retention_expires_at) <= now:
        raise ReviewUnavailable
    if deleted_project_scope_exists(
        session, account_id=account_id, profile_id=profile.id, scope_key=scope_key
    ):
        raise ReviewUnavailable
    source = session.scalar(
        select(ProfilingInput).where(
            ProfilingInput.id == source_input_id,
            ProfilingInput.session_id == work.id,
            ProfilingInput.account_id == account_id,
        )
    )
    if (
        source is None
        or source.protocol_cycle != work.protocol_cycle
        or exact_text not in source.body
    ):
        raise ReviewUnavailable
    draft = ProfilingDraft(
        id=draft_id or str(uuid4()),
        account_id=account_id,
        session_id=work.id,
        source_input_id=source.id,
        scope_key=scope_key,
        claim_type=claim_type,
        exact_text=exact_text,
        source_content_hash=hashlib.sha256(source.body.encode()).hexdigest(),
        status="DRAFT",
        created_at=now,
        expires_at=_stored_utc(work.retention_expires_at),
    )
    if profile.version != work.base_profile_version:
        raise ReviewStale
    session.add(draft)
    return draft


class ClaimReviewPreparation:
    def __init__(self, signing_secret: bytes) -> None:
        if len(signing_secret) < 32:
            raise ValueError("review signing secret too short")
        self._secret = signing_secret

    def prepare(
        self,
        session: Session,
        *,
        account_id: str,
        profiling_session_id: str,
        draft_ids: tuple[str, ...],
        now: datetime,
        batch_id: str | None = None,
    ) -> ProfilingReviewBatch:
        """Snapshot one to five drafts from one scope; the caller owns the commit."""

        now = _utc(now)
        if not 1 <= len(draft_ids) <= 5 or len(set(draft_ids)) != len(draft_ids):
            raise ValueError("review requires one to five distinct drafts")
        work, profile = _owned_work(session, account_id, profiling_session_id)
        if work.status not in {"ACTIVE", "PAUSED"} or _stored_utc(work.retention_expires_at) <= now:
            raise ReviewUnavailable
        if profile.version != work.base_profile_version:
            raise ReviewStale
        drafts = list(
            session.scalars(
                select(ProfilingDraft)
                .where(
                    ProfilingDraft.id.in_(draft_ids),
                    ProfilingDraft.account_id == account_id,
                    ProfilingDraft.session_id == work.id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        by_id = {draft.id: draft for draft in drafts}
        if len(by_id) != len(draft_ids):
            raise ReviewUnavailable
        ordered = [by_id[draft_id] for draft_id in draft_ids]
        if len({draft.scope_key for draft in ordered}) != 1:
            raise ValueError("mixed experience scopes are not reviewable together")
        if deleted_project_scope_exists(
            session, account_id=account_id, profile_id=profile.id, scope_key=ordered[0].scope_key
        ):
            raise ReviewUnavailable
        for draft in ordered:
            source = session.scalar(
                select(ProfilingInput).where(
                    ProfilingInput.id == draft.source_input_id,
                    ProfilingInput.session_id == work.id,
                    ProfilingInput.account_id == account_id,
                )
            )
            if (
                draft.status != "DRAFT"
                or _stored_utc(draft.expires_at) <= now
                or source is None
                or source.protocol_cycle != work.protocol_cycle
                or hashlib.sha256(source.body.encode()).hexdigest() != draft.source_content_hash
                or draft.exact_text not in source.body
            ):
                raise ReviewStale
        batch_id = batch_id or str(uuid4())
        expires_at = min(now + REVIEW_TTL, _stored_utc(work.retention_expires_at))
        items = [
            ProfilingReviewItem(
                id=str(uuid4()),
                account_id=account_id,
                session_id=work.id,
                batch_id=batch_id,
                draft_id=draft.id,
                source_input_id=draft.source_input_id,
                position=index,
                exact_text=draft.exact_text,
                claim_type=draft.claim_type,
                scope_key=draft.scope_key,
                source_content_hash=draft.source_content_hash,
                decision=None,
            )
            for index, draft in enumerate(ordered, start=1)
        ]
        batch = ProfilingReviewBatch(
            id=batch_id,
            account_id=account_id,
            session_id=work.id,
            profile_id=profile.id,
            scope_key=ordered[0].scope_key,
            base_profile_version=profile.version,
            review_digest=self._digest(
                account_id=account_id,
                session_id=work.id,
                profile_id=profile.id,
                scope_key=ordered[0].scope_key,
                batch_id=batch_id,
                base_profile_version=profile.version,
                expires_at=expires_at,
                items=items,
            ),
            status="PREPARED",
            created_at=now,
            expires_at=expires_at,
        )
        session.add(batch)
        session.add_all(items)
        for draft in ordered:
            draft.status = "IN_REVIEW"
        return batch

    def prepare_for_scope(
        self,
        session: Session,
        *,
        account_id: str,
        profiling_session_id: str,
        scope_key: str,
        base_profile_version: int,
        idempotency_key: str,
        now: datetime,
    ) -> ProfilingReviewBatch:
        """Prepare all current drafts in one scope, or replay an exact prior batch."""

        now = _utc(now)
        if (
            not isinstance(scope_key, str)
            or not _SCOPE.fullmatch(scope_key)
            or type(base_profile_version) is not int
            or base_profile_version < 0
            or not isinstance(idempotency_key, str)
            or not _PREPARE_KEY.fullmatch(idempotency_key)
        ):
            raise ValueError("invalid review preparation request")
        work, profile = _owned_work(session, account_id, profiling_session_id)
        if work.status not in {"ACTIVE", "PAUSED"} or _stored_utc(work.retention_expires_at) <= now:
            raise ReviewUnavailable
        if (
            profile.version != base_profile_version
            or work.base_profile_version != base_profile_version
        ):
            raise ReviewStale
        if deleted_project_scope_exists(
            session, account_id=account_id, profile_id=profile.id, scope_key=scope_key
        ):
            raise ReviewUnavailable
        batch_id = str(uuid5(_PREPARE_NAMESPACE, f"{account_id}:{idempotency_key}"))
        existing = session.get(ProfilingReviewBatch, batch_id)
        if existing is not None:
            if (
                existing.account_id != account_id
                or existing.session_id != profiling_session_id
                or existing.scope_key != scope_key
                or existing.base_profile_version != base_profile_version
            ):
                raise ReviewIdempotencyConflict
            self.get(session, account_id=account_id, batch_id=batch_id, now=now)
            return existing
        draft_ids = tuple(
            session.scalars(
                select(ProfilingDraft.id)
                .where(
                    ProfilingDraft.account_id == account_id,
                    ProfilingDraft.session_id == profiling_session_id,
                    ProfilingDraft.scope_key == scope_key,
                    ProfilingDraft.status == "DRAFT",
                )
                .order_by(ProfilingDraft.created_at, ProfilingDraft.id)
                .limit(6)
            )
        )
        if not draft_ids:
            raise ReviewUnavailable
        if len(draft_ids) > 5:
            raise ValueError("review scope exceeds five drafts")
        return self.prepare(
            session,
            account_id=account_id,
            profiling_session_id=profiling_session_id,
            draft_ids=draft_ids,
            now=now,
            batch_id=batch_id,
        )

    def get(
        self, session: Session, *, account_id: str, batch_id: str, now: datetime
    ) -> tuple[ProfilingReviewBatch, tuple[ProfilingReviewItem, ...]]:
        """Return the prepared snapshot, never rewrite it from current profile data."""

        now = _utc(now)
        row = session.execute(
            select(ProfilingReviewBatch, ProfilingSession)
            .join(Account, Account.id == ProfilingReviewBatch.account_id)
            .join(CareerProfile, CareerProfile.id == ProfilingReviewBatch.profile_id)
            .join(ProfilingSession, ProfilingSession.id == ProfilingReviewBatch.session_id)
            .where(
                ProfilingReviewBatch.id == batch_id,
                ProfilingReviewBatch.account_id == account_id,
                ProfilingSession.account_id == account_id,
                ProfilingSession.profile_id == ProfilingReviewBatch.profile_id,
                Account.status == "ACTIVE",
                CareerProfile.status == "ACTIVE",
                CareerProfile.account_id == account_id,
            )
            .execution_options(populate_existing=True)
        ).first()
        if row is None:
            raise ReviewUnavailable
        batch, work = row
        if (
            batch.status != "PREPARED"
            or _stored_utc(batch.expires_at) <= now
            or work.status not in {"ACTIVE", "PAUSED"}
            or _stored_utc(work.retention_expires_at) <= now
        ):
            raise ReviewUnavailable
        items = tuple(
            session.scalars(
                select(ProfilingReviewItem)
                .where(
                    ProfilingReviewItem.batch_id == batch_id,
                    ProfilingReviewItem.account_id == account_id,
                )
                .order_by(ProfilingReviewItem.position)
                .execution_options(populate_existing=True)
            )
        )
        if not 1 <= len(items) <= 5 or not hmac.compare_digest(
            batch.review_digest,
            self._digest(
                account_id=batch.account_id,
                session_id=batch.session_id,
                profile_id=batch.profile_id,
                scope_key=batch.scope_key,
                batch_id=batch.id,
                base_profile_version=batch.base_profile_version,
                expires_at=batch.expires_at,
                items=items,
            ),
        ):
            raise ReviewStale
        return batch, items

    def _digest(
        self,
        *,
        account_id: str,
        session_id: str,
        profile_id: str,
        scope_key: str,
        batch_id: str,
        base_profile_version: int,
        expires_at: datetime,
        items: tuple[ProfilingReviewItem, ...] | list[ProfilingReviewItem],
    ) -> str:
        payload = json.dumps(
            {
                "purpose": "FACT_CONFIRMATION",
                "account_id": account_id,
                "session_id": session_id,
                "profile_id": profile_id,
                "scope_key": scope_key,
                "batch_id": batch_id,
                "base_profile_version": base_profile_version,
                "expires_at": _stored_utc(expires_at).isoformat(),
                "items": [
                    {
                        "draft_id": item.draft_id,
                        "source_input_id": item.source_input_id,
                        "position": item.position,
                        "exact_text": item.exact_text,
                        "claim_type": item.claim_type,
                        "scope_key": item.scope_key,
                        "source_content_hash": item.source_content_hash,
                    }
                    for item in items
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()


def _owned_work(
    session: Session, account_id: str, profiling_session_id: str
) -> tuple[ProfilingSession, CareerProfile]:
    row = session.execute(
        select(ProfilingSession, CareerProfile)
        .join(Account, Account.id == ProfilingSession.account_id)
        .join(CareerProfile, CareerProfile.id == ProfilingSession.profile_id)
        .where(
            ProfilingSession.id == profiling_session_id,
            ProfilingSession.account_id == account_id,
            CareerProfile.account_id == account_id,
            Account.status == "ACTIVE",
            CareerProfile.status == "ACTIVE",
        )
        .with_for_update(of=[ProfilingSession, CareerProfile])
        .execution_options(populate_existing=True)
    ).first()
    if row is None:
        raise ReviewUnavailable
    return row[0], row[1]


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware datetime required")
    return value.astimezone(UTC)


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

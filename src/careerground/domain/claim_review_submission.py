"""Synthetic exact-review promotion; no public approval issuer or route exists."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewStale,
    ReviewUnavailable,
    _stored_utc,
)
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimConstraint,
    ClaimReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileChangeSet,
)
from careerground.storage.models import (
    Account,
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)

DECISIONS = frozenset({"ACCEPT", "EDIT", "FOLLOW_UP", "EXCLUDE_NOT_TRUE", "EXCLUDE_DO_NOT_USE"})


@dataclass(frozen=True)
class VerifiedReviewApproval:
    """Output of a future trusted user confirmation adapter, never a tool argument."""

    account_id: str
    batch_id: str
    review_digest: str
    decisions: tuple[tuple[str, str], ...]
    expires_at: datetime


class ReviewSubmissionRejected(Exception):
    """Approval was incomplete, stale, untrusted, or outside this owner scope."""


def submit_synthetic_review(
    session: Session,
    *,
    preparation: ClaimReviewPreparation,
    approval: VerifiedReviewApproval,
    now: datetime,
) -> ProfileChangeSet | None:
    """Apply a whole bounded batch atomically in the caller-owned transaction.

    This internal function is deliberately not exposed as an MCP or web command.
    The caller must supply a trusted approval for the exact displayed digest.
    """

    if type(approval) is not VerifiedReviewApproval or now.tzinfo is None:
        raise ReviewSubmissionRejected
    now = now.astimezone(UTC)
    if (
        approval.expires_at.tzinfo is None
        or _stored_utc(approval.expires_at) <= now
        or not isinstance(approval.review_digest, str)
        or not approval.account_id
        or not approval.batch_id
    ):
        raise ReviewSubmissionRejected
    if not 1 <= len(approval.decisions) <= 5:
        raise ReviewSubmissionRejected
    try:
        decision_map = dict(approval.decisions)
    except (TypeError, ValueError) as exc:
        raise ReviewSubmissionRejected from exc
    if len(decision_map) != len(approval.decisions) or any(
        not isinstance(item_id, str) or decision not in DECISIONS
        for item_id, decision in approval.decisions
    ):
        raise ReviewSubmissionRejected

    # Match deletion's account/profile/workspace lock order. A confirmed deletion
    # cannot race a promotion into an already blocked profile.
    account = session.scalar(
        select(Account).where(Account.id == approval.account_id).with_for_update()
    )
    batch = session.scalar(
        select(ProfilingReviewBatch).where(
            ProfilingReviewBatch.id == approval.batch_id,
            ProfilingReviewBatch.account_id == approval.account_id,
        )
    )
    if account is None or account.status != "ACTIVE" or batch is None:
        raise ReviewSubmissionRejected
    profile = session.scalar(
        select(CareerProfile)
        .where(
            CareerProfile.id == batch.profile_id, CareerProfile.account_id == approval.account_id
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if profile is None or profile.status != "ACTIVE":
        raise ReviewSubmissionRejected
    work = session.scalar(
        select(ProfilingSession)
        .where(
            ProfilingSession.id == batch.session_id,
            ProfilingSession.account_id == approval.account_id,
            ProfilingSession.profile_id == profile.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if work is None or work.status not in {"ACTIVE", "PAUSED"}:
        raise ReviewSubmissionRejected
    batch = session.scalar(
        select(ProfilingReviewBatch)
        .where(ProfilingReviewBatch.id == batch.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    items = tuple(
        session.scalars(
            select(ProfilingReviewItem)
            .where(
                ProfilingReviewItem.batch_id == batch.id,
                ProfilingReviewItem.account_id == approval.account_id,
            )
            .order_by(ProfilingReviewItem.position)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if (
        not 1 <= len(items) <= 5
        or set(decision_map) != {item.id for item in items}
        or not hmac.compare_digest(batch.review_digest, approval.review_digest)
    ):
        raise ReviewSubmissionRejected
    if batch.status == "SUBMITTED":
        if any(item.decision != decision_map[item.id] for item in items):
            raise ReviewSubmissionRejected
        return session.scalar(
            select(ProfileChangeSet).where(ProfileChangeSet.review_batch_id == batch.id)
        )
    if (
        batch.status != "PREPARED"
        or _stored_utc(batch.expires_at) <= now
        or _stored_utc(work.retention_expires_at) <= now
        or profile.version != batch.base_profile_version
        or work.base_profile_version != batch.base_profile_version
    ):
        raise ReviewStale
    try:
        checked_batch, checked_items = preparation.get(
            session, account_id=approval.account_id, batch_id=batch.id, now=now
        )
    except (ReviewUnavailable, ReviewStale) as exc:
        raise ReviewSubmissionRejected from exc
    if checked_batch.id != batch.id or tuple(item.id for item in checked_items) != tuple(
        item.id for item in items
    ):
        raise ReviewSubmissionRejected

    drafts: dict[str, ProfilingDraft] = {}
    sources: dict[str, ProfilingInput] = {}
    for item in items:
        draft = session.scalar(
            select(ProfilingDraft)
            .where(
                ProfilingDraft.id == item.draft_id,
                ProfilingDraft.account_id == approval.account_id,
                ProfilingDraft.session_id == work.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        source = session.scalar(
            select(ProfilingInput)
            .where(
                ProfilingInput.id == item.source_input_id,
                ProfilingInput.account_id == approval.account_id,
                ProfilingInput.session_id == work.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            draft is None
            or draft.status != "IN_REVIEW"
            or draft.scope_key != batch.scope_key
            or draft.claim_type != item.claim_type
            or draft.exact_text != item.exact_text
            or draft.source_input_id != item.source_input_id
            or _stored_utc(draft.expires_at) <= now
            or source is None
            or source.protocol_cycle != work.protocol_cycle
            or hashlib.sha256(source.body.encode()).hexdigest() != item.source_content_hash
            or item.exact_text not in source.body
        ):
            raise ReviewStale
        drafts[item.id] = draft
        sources[item.id] = source

    canonical = any(
        decision_map[item.id] in {"ACCEPT", "EXCLUDE_NOT_TRUE", "EXCLUDE_DO_NOT_USE"}
        for item in items
    )
    next_version = profile.version + 1 if canonical else profile.version
    change_set = None
    if canonical:
        ensure_profile_archive(
            session,
            account_id=approval.account_id,
            profile_id=profile.id,
            profile_version=profile.version,
            now=now,
        )
        change_set = ProfileChangeSet(
            id=str(uuid4()),
            account_id=approval.account_id,
            profile_id=profile.id,
            version_before=profile.version,
            version_after=next_version,
            review_batch_id=batch.id,
            review_digest=batch.review_digest,
            reason="CLAIM_REVIEW",
            created_at=now,
        )
        session.add(change_set)
        profile.version = next_version

    for item in items:
        decision = decision_map[item.id]
        item.decision = decision
        draft = drafts[item.id]
        if decision == "EDIT":
            draft.status = "EDIT_REQUIRED"
        elif decision == "FOLLOW_UP":
            draft.status = "DRAFT"
        elif decision.startswith("EXCLUDE_"):
            draft.status = "EXCLUDED"
            session.add(
                ClaimConstraint(
                    id=str(uuid4()),
                    account_id=approval.account_id,
                    profile_id=profile.id,
                    scope_key=batch.scope_key,
                    constraint_type=(
                        "NOT_TRUE" if decision == "EXCLUDE_NOT_TRUE" else "DO_NOT_USE"
                    ),
                    exact_text=item.exact_text,
                    review_batch_id=batch.id,
                    review_item_id=item.id,
                    review_digest=batch.review_digest,
                    created_in_version=next_version,
                    created_at=now,
                )
            )
        else:
            draft.status = "PROMOTED"
            _add_confirmed_claim(
                session,
                account_id=approval.account_id,
                profile_id=profile.id,
                batch=batch,
                item=item,
                source=sources[item.id],
                version=next_version,
                now=now,
            )
    batch.status = "SUBMITTED"
    batch.submitted_at = now
    session.flush()
    if canonical:
        ensure_profile_archive(
            session,
            account_id=approval.account_id,
            profile_id=profile.id,
            profile_version=next_version,
            now=now,
        )
    return change_set


def _add_confirmed_claim(
    session: Session,
    *,
    account_id: str,
    profile_id: str,
    batch: ProfilingReviewBatch,
    item: ProfilingReviewItem,
    source: ProfilingInput,
    version: int,
    now: datetime,
) -> None:
    source_id, evidence_id, claim_id = (str(uuid4()) for _ in range(3))
    session.add_all(
        [
            EvidenceSource(
                id=source_id,
                account_id=account_id,
                profile_id=profile_id,
                source_type="EXPLICIT_PROFILING_INPUT",
                source_ref=source.id,
                content_hash=item.source_content_hash,
                created_in_version=version,
                created_at=now,
            ),
            Claim(
                id=claim_id,
                account_id=account_id,
                profile_id=profile_id,
                scope_key=batch.scope_key,
                claim_type=item.claim_type,
                canonical_text=item.exact_text,
                created_in_version=version,
                status="ACTIVE",
                created_at=now,
            ),
        ]
    )
    session.flush()
    session.add(
        EvidenceItem(
            id=evidence_id,
            account_id=account_id,
            profile_id=profile_id,
            source_id=source_id,
            content_text=item.exact_text,
            content_hash=hashlib.sha256(item.exact_text.encode()).hexdigest(),
            created_in_version=version,
            status="ACTIVE",
            created_at=now,
        )
    )
    session.flush()
    session.add_all(
        [
            EvidenceClaimLink(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile_id,
                evidence_id=evidence_id,
                claim_id=claim_id,
                relation_type="SUPPORTS",
                created_in_version=version,
            ),
            ClaimAssessment(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile_id,
                claim_id=claim_id,
                knowledge_status="USER_CONFIRMED",
                consistency_status="NOT_EVALUATED",
                usage_policy="REVIEW_REQUIRED",
                profile_version=version,
                assessed_at=now,
            ),
            ClaimReview(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile_id,
                claim_id=claim_id,
                review_batch_id=batch.id,
                review_item_id=item.id,
                review_digest=batch.review_digest,
                review_purpose="FACT_CONFIRMATION",
                review_action="ACCEPT",
                base_profile_version=batch.base_profile_version,
                profile_version=version,
                reviewed_at=now,
            ),
        ]
    )

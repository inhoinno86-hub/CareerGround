"""Internal synthetic deletion foundation; no public execution adapter."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from careerground.domain.deletion_preview import (
    DeletionConfirmationRejected,
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    ClaimConstraint,
    ClaimReview,
    ClaimUseReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
    ProfileChangeSet,
)
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactClaimLink,
    ArtifactUnit,
    ArtifactWordingReview,
    JDRequirement,
    JobDescription,
    RequirementClaimMap,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    BrowserOperation,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    ErasureLedger,
    PrivateObject,
    PrivateObjectVersion,
    ProfilingDraft,
    ProfilingInput,
    ProfilingProtocolStep,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.workers.outbox import enqueue_event

KNOWN_KINDS = frozenset(
    {
        "ACCOUNT",
        "AUTH_IDENTITY",
        "CAREER_PROFILE",
        "PROFILING_SESSION",
        "PROFILING_INPUT",
        "PROFILING_PROTOCOL_STEP",
        "PROFILING_DRAFT",
        "PROFILING_REVIEW_BATCH",
        "PROFILING_REVIEW_ITEM",
    }
)
GRAPH_KINDS = frozenset(
    {
        "BROWSER_OPERATION",
        "PROFILE_CHANGE_SET",
        "PROFILE_ARCHIVE",
        "CLAIM",
        "EVIDENCE_SOURCE",
        "EVIDENCE_ITEM",
        "EVIDENCE_CLAIM_LINK",
        "CLAIM_ASSESSMENT",
        "CLAIM_REVIEW",
        "CLAIM_BOUNDARY_REVIEW",
        "CLAIM_CONFLICT_REVIEW",
        "CLAIM_USE_REVIEW",
        "CLAIM_CONSTRAINT",
    }
)
DERIVED_KINDS = frozenset(
    {
        "JOB_DESCRIPTION",
        "JD_REQUIREMENT",
        "REQUIREMENT_CLAIM_MAP",
        "ARTIFACT",
        "ARTIFACT_UNIT",
        "ARTIFACT_WORDING_REVIEW",
        "ARTIFACT_CLAIM_LINK",
    }
)
LOCAL_PROFILE_KINDS = GRAPH_KINDS | DERIVED_KINDS
UNVERIFIED_KINDS = LOCAL_PROFILE_KINDS | {"PRIVATE_OBJECT", "PRIVATE_OBJECT_VERSION"}

_LOCAL_DELETE_ORDER = (
    BrowserOperation,
    ArtifactClaimLink,
    ArtifactWordingReview,
    RequirementClaimMap,
    ArtifactUnit,
    Artifact,
    JDRequirement,
    JobDescription,
    ProfileArchive,
    ClaimBoundaryReview,
    ClaimConflictReview,
    ClaimUseReview,
    ClaimReview,
    ClaimAssessment,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    Claim,
    ClaimConstraint,
    ProfileChangeSet,
)


def ledger_signature(
    secret: bytes,
    *,
    request_id: str,
    account_id: str,
    scope: str,
    target_id: str,
    created_at: datetime,
) -> str:
    if len(secret) < 32:
        raise ValueError("ledger signing secret must be at least 32 bytes")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)  # SQLite drops timezone in tests.
    timestamp = created_at.astimezone(UTC).isoformat()
    message = f"{request_id}\x1f{account_id}\x1f{scope}\x1f{target_id}\x1f{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def execute_synthetic_deletion(
    session: Session,
    *,
    preview_service: DeletionPreviewService,
    ledger_secret: bytes,
    account_id: str,
    scope: DeletionScope,
    target_id: str,
    deletion_digest: str,
    acknowledged_impact: bool,
    step_up: VerifiedDeletionApproval | None,
    now: datetime,
) -> DeletionRequest:
    """Lock, reconfirm, block reads and stage work in one caller-owned transaction.

    Only an internal test harness may supply VerifiedDeletionApproval today. No
    real step-up issuer or public route exists, so this is not a product API.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware datetime required")
    now = now.astimezone(UTC)
    account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None or account.status != "ACTIVE":
        raise DeletionConfirmationRejected
    profiles = list(
        session.scalars(
            select(CareerProfile)
            .where(CareerProfile.account_id == account_id)
            .order_by(CareerProfile.id)
            .with_for_update()
        )
    )
    if scope == DeletionScope.PROFILE and target_id not in {p.id for p in profiles}:
        raise DeletionConfirmationRejected
    # Session writes already lock their workspace row; session creation locks its profile.
    session_ids = list(
        session.scalars(
            select(ProfilingSession.id)
            .where(ProfilingSession.account_id == account_id)
            .order_by(ProfilingSession.id)
            .with_for_update()
        )
    )
    object_ids = list(
        session.scalars(
            select(PrivateObject.id)
            .where(PrivateObject.account_id == account_id)
            .order_by(PrivateObject.id)
            .with_for_update()
        )
    )
    if object_ids:
        list(
            session.scalars(
                select(PrivateObjectVersion.id)
                .where(PrivateObjectVersion.object_id.in_(object_ids))
                .order_by(PrivateObjectVersion.id)
                .with_for_update()
            )
        )
    if session.scalar(
        select(DeletionRequest.id).where(
            DeletionRequest.account_id == account_id,
            DeletionRequest.scope == scope,
            DeletionRequest.target_id == target_id,
        )
    ):
        raise DeletionConfirmationRejected
    confirmed = preview_service.confirm_intent(
        session,
        account_id=account_id,
        scope=scope,
        target_id=target_id,
        deletion_digest=deletion_digest,
        acknowledged_impact=acknowledged_impact,
        step_up=step_up,
        now=now,
    )
    if scope == DeletionScope.ACCOUNT:
        account.status = "DELETING"
        affected_profiles = profiles
        affected_sessions = session_ids
    else:
        affected_profiles = [profile for profile in profiles if profile.id == target_id]
        affected_sessions = list(
            session.scalars(
                select(ProfilingSession.id).where(
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.profile_id == target_id,
                )
            )
        )
    for profile in affected_profiles:
        profile.status = "DELETING"
    if affected_sessions:
        for work in session.scalars(
            select(ProfilingSession).where(ProfilingSession.id.in_(affected_sessions))
        ):
            work.status = "DELETING"
    affected_object_ids = [
        item.target_id for item in confirmed.items if item.kind == "PRIVATE_OBJECT"
    ]
    if affected_object_ids:
        for obj in session.scalars(
            select(PrivateObject).where(PrivateObject.id.in_(affected_object_ids))
        ):
            obj.status = "DELETING"
        for version in session.scalars(
            select(PrivateObjectVersion).where(
                PrivateObjectVersion.object_id.in_(affected_object_ids),
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
    request = DeletionRequest(
        id=str(uuid4()),
        account_id=account_id,
        scope=scope.value,
        target_id=target_id,
        status="DELETING",
        impact_digest=confirmed.deletion_digest,
        created_at=now,
    )
    session.add(request)
    session.add(
        ErasureLedger(
            request_id=request.id,
            account_id=account_id,
            scope=scope.value,
            target_id=target_id,
            created_at=now,
            signature=ledger_signature(
                ledger_secret,
                request_id=request.id,
                account_id=account_id,
                scope=scope.value,
                target_id=target_id,
                created_at=now,
            ),
        )
    )
    for impact in confirmed.items:
        if impact.kind not in KNOWN_KINDS | UNVERIFIED_KINDS:
            raise DeletionConfirmationRejected
        action = "ERASE" if impact.kind in KNOWN_KINDS else "VERIFY"
        item = DeletionWorkItem(
            id=str(uuid4()),
            request_id=request.id,
            kind=impact.kind,
            target_id=impact.target_id,
            action=action,
            status="PENDING",
        )
        session.add(item)
        if action == "ERASE":
            enqueue_event(
                session,
                event_type="DELETION_WORK",
                target_id=item.id,
                handler_id=f"deletion:{item.id}",
                now=now,
            )
    if any(impact.kind in LOCAL_PROFILE_KINDS for impact in confirmed.items):
        for profile in affected_profiles:
            item = DeletionWorkItem(
                id=str(uuid4()),
                request_id=request.id,
                kind="PROFILE_LOCAL_DATA",
                target_id=profile.id,
                action="ERASE",
                status="PENDING",
            )
            session.add(item)
            enqueue_event(
                session,
                event_type="DELETION_WORK",
                target_id=item.id,
                handler_id=f"deletion:{item.id}",
                now=now,
            )
    # Every request remains incomplete until storage/provider/backup inventory exists.
    session.add(
        DeletionWorkItem(
            id=str(uuid4()),
            request_id=request.id,
            kind="UNVERIFIED_SCOPE",
            target_id="external-and-backups",
            action="VERIFY",
            status="PENDING",
        )
    )
    return request


def apply_deletion_work(session: Session, item_id: str) -> None:
    """Handle only current local tables, never an external provider or backup."""

    item = session.get(DeletionWorkItem, item_id)
    if item is None or item.action != "ERASE":
        raise ValueError("unsupported deletion item")
    request = session.get(DeletionRequest, item.request_id)
    if request is None or request.status not in {"DELETING", "FAILED"}:
        raise ValueError("unavailable deletion request")
    if item.status == "DONE":
        return
    account_id = request.account_id
    if item.kind == "AUTH_IDENTITY":
        session.execute(
            delete(AuthIdentity).where(
                AuthIdentity.id == item.target_id, AuthIdentity.account_id == account_id
            )
        )
    elif item.kind == "PROFILING_INPUT":
        session.execute(
            delete(ProfilingInput).where(
                ProfilingInput.id == item.target_id, ProfilingInput.account_id == account_id
            )
        )
    elif item.kind == "PROFILING_PROTOCOL_STEP":
        session.execute(
            delete(ProfilingProtocolStep).where(
                ProfilingProtocolStep.id == item.target_id,
                ProfilingProtocolStep.account_id == account_id,
            )
        )
    elif item.kind == "PROFILING_DRAFT":
        session.execute(
            delete(ProfilingDraft).where(
                ProfilingDraft.id == item.target_id, ProfilingDraft.account_id == account_id
            )
        )
    elif item.kind == "PROFILING_REVIEW_ITEM":
        session.execute(
            delete(ProfilingReviewItem).where(
                ProfilingReviewItem.id == item.target_id,
                ProfilingReviewItem.account_id == account_id,
            )
        )
    elif item.kind == "PROFILING_REVIEW_BATCH":
        session.execute(
            delete(ProfilingReviewBatch).where(
                ProfilingReviewBatch.id == item.target_id,
                ProfilingReviewBatch.account_id == account_id,
            )
        )
    elif item.kind == "PROFILING_SESSION":
        session.execute(
            delete(ProfilingInput).where(
                ProfilingInput.session_id == item.target_id, ProfilingInput.account_id == account_id
            )
        )
        session.execute(
            delete(ProfilingSession).where(
                ProfilingSession.id == item.target_id,
                ProfilingSession.account_id == account_id,
                ProfilingSession.status == "DELETING",
            )
        )
    elif item.kind == "PROFILE_LOCAL_DATA":
        profile = session.get(CareerProfile, item.target_id)
        if (
            profile is None
            or profile.account_id != account_id
            or profile.status != "DELETING"
            or (request.scope == "PROFILE" and request.target_id != profile.id)
        ):
            raise ValueError("graph profile tombstone missing")
        for model in _LOCAL_DELETE_ORDER:
            session.execute(
                delete(model).where(
                    model.account_id == account_id,
                    model.profile_id == profile.id,
                )
            )
        # Local inventory items become done only after all affected profiles
        # have no local rows; the request still retains external VERIFY work.
        affected_id = request.target_id if request.scope == "PROFILE" else None
        remaining = False
        for model in _LOCAL_DELETE_ORDER:
            query = select(model.id).where(model.account_id == account_id).limit(1)
            if affected_id is not None:
                query = query.where(model.profile_id == affected_id)
            if session.scalar(query) is not None:
                remaining = True
                break
        if not remaining:
            for graph_item in session.scalars(
                select(DeletionWorkItem).where(
                    DeletionWorkItem.request_id == request.id,
                    DeletionWorkItem.kind.in_(LOCAL_PROFILE_KINDS),
                    DeletionWorkItem.action == "VERIFY",
                )
            ):
                graph_item.status = "DONE"
    elif item.kind == "CAREER_PROFILE":
        profile = session.get(CareerProfile, item.target_id)
        if profile is None or profile.account_id != account_id or profile.status != "DELETING":
            raise ValueError("profile tombstone missing")
    elif item.kind == "ACCOUNT":
        account = session.get(Account, item.target_id)
        if account is None or account.id != account_id or account.status != "DELETING":
            raise ValueError("account tombstone missing")
    else:
        raise ValueError("unsupported deletion kind")
    item.status = "DONE"

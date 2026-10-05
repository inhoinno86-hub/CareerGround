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
from careerground.domain.profile_archive import ensure_profile_archive
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
    ProjectScope,
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
        "PROJECT_SCOPE",
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
    ProjectScope,
)

PARTIAL_SCOPES = frozenset({DeletionScope.SESSION, DeletionScope.EVIDENCE, DeletionScope.PROJECT})
_PARTIAL_DELETE_ORDER = (
    ("BROWSER_OPERATION", BrowserOperation),
    ("ARTIFACT_CLAIM_LINK", ArtifactClaimLink),
    ("ARTIFACT_WORDING_REVIEW", ArtifactWordingReview),
    ("REQUIREMENT_CLAIM_MAP", RequirementClaimMap),
    ("ARTIFACT_UNIT", ArtifactUnit),
    ("ARTIFACT", Artifact),
    ("PROFILE_ARCHIVE", ProfileArchive),
    ("CLAIM_BOUNDARY_REVIEW", ClaimBoundaryReview),
    ("CLAIM_CONFLICT_REVIEW", ClaimConflictReview),
    ("CLAIM_USE_REVIEW", ClaimUseReview),
    ("CLAIM_REVIEW", ClaimReview),
    ("CLAIM_ASSESSMENT", ClaimAssessment),
    ("EVIDENCE_CLAIM_LINK", EvidenceClaimLink),
    ("EVIDENCE_ITEM", EvidenceItem),
    ("EVIDENCE_SOURCE", EvidenceSource),
    ("CLAIM", Claim),
    ("CLAIM_CONSTRAINT", ClaimConstraint),
    ("PROFILE_CHANGE_SET", ProfileChangeSet),
    ("PROFILING_REVIEW_ITEM", ProfilingReviewItem),
    ("PROFILING_REVIEW_BATCH", ProfilingReviewBatch),
    ("PROFILING_DRAFT", ProfilingDraft),
    ("PROFILING_PROTOCOL_STEP", ProfilingProtocolStep),
    ("PROFILING_INPUT", ProfilingInput),
    ("PROFILING_SESSION", ProfilingSession),
)


def _delete_artifact_lineage(session: Session, model, *filters) -> int:
    """Delete R2 descendants before their R1 source under immediate FK checks.

    Both Artifact and ArtifactUnit can form a source chain. A bulk DELETE of all
    selected rows is rejected by SQLite's immediate RESTRICT constraints, even
    when every row in that same statement is selected for deletion.
    """

    source = (
        ArtifactUnit.source_artifact_unit_id
        if model is ArtifactUnit
        else Artifact.source_artifact_id
    )
    pending = {
        row_id: parent_id
        for row_id, parent_id in session.execute(select(model.id, source).where(*filters))
    }
    removed = 0
    while pending:
        referenced = {parent for parent in pending.values() if parent in pending}
        leaves = tuple(row_id for row_id in pending if row_id not in referenced)
        if not leaves:
            raise ValueError("artifact lineage cycle")
        result = session.execute(delete(model).where(model.id.in_(leaves), *filters))
        if result.rowcount != len(leaves):
            raise ValueError("artifact lineage changed")
        for row_id in leaves:
            del pending[row_id]
        removed += len(leaves)
    return removed


def ledger_signature(
    secret: bytes,
    *,
    request_id: str,
    account_id: str,
    scope: str,
    target_id: str,
    created_at: datetime,
    profile_id: str | None = None,
    profile_version_after: int | None = None,
) -> str:
    if len(secret) < 32:
        raise ValueError("ledger signing secret must be at least 32 bytes")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)  # SQLite drops timezone in tests.
    timestamp = created_at.astimezone(UTC).isoformat()
    if profile_id is None and profile_version_after is None:
        message = f"{request_id}\x1f{account_id}\x1f{scope}\x1f{target_id}\x1f{timestamp}".encode()
    elif (
        scope in {item.value for item in PARTIAL_SCOPES}
        and type(profile_id) is str
        and 1 <= len(profile_id) <= 36
        and type(profile_version_after) is int
        and profile_version_after >= 1
    ):
        message = (
            f"v2\x1f{request_id}\x1f{account_id}\x1f{scope}\x1f{target_id}"
            f"\x1f{profile_id}\x1f{profile_version_after}\x1f{timestamp}"
        ).encode()
    else:
        raise ValueError("invalid partial ledger metadata")
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

    A trusted internal adapter supplies VerifiedDeletionApproval. The isolated
    development Web adapter uses fresh OIDC authentication; the synthetic demo
    uses an explicit mock. Neither supplies a public production erasure API.
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
    elif scope == DeletionScope.PROFILE:
        affected_profiles = [profile for profile in profiles if profile.id == target_id]
        affected_sessions = list(
            session.scalars(
                select(ProfilingSession.id).where(
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.profile_id == target_id,
                )
            )
        )
    else:
        profile_guard = next(
            (item for item in confirmed.items if item.kind == "PROFILE_VERSION"), None
        )
        affected_profiles = [
            profile
            for profile in profiles
            if profile_guard is not None
            and profile.id == profile_guard.target_id
            and profile.version == profile_guard.version
            and profile.status == "ACTIVE"
        ]
        if len(affected_profiles) != 1:
            raise DeletionConfirmationRejected
        affected_sessions = [target_id] if scope == DeletionScope.SESSION else []
    if scope not in PARTIAL_SCOPES:
        for profile in affected_profiles:
            profile.status = "DELETING"
    if affected_sessions and scope not in PARTIAL_SCOPES:
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
    after_version = affected_profiles[0].version + 1 if scope in PARTIAL_SCOPES else None
    ledger_profile_id = affected_profiles[0].id if scope in PARTIAL_SCOPES else None
    session.add(
        ErasureLedger(
            request_id=request.id,
            account_id=account_id,
            scope=scope.value,
            target_id=target_id,
            profile_id=ledger_profile_id,
            profile_version_after=after_version,
            created_at=now,
            signature=ledger_signature(
                ledger_secret,
                request_id=request.id,
                account_id=account_id,
                scope=scope.value,
                target_id=target_id,
                created_at=now,
                profile_id=ledger_profile_id,
                profile_version_after=after_version,
            ),
        )
    )
    for impact in confirmed.items:
        if impact.kind not in KNOWN_KINDS | UNVERIFIED_KINDS | {
            "PROFILE_VERSION",
            "CLAIM_REASSESS",
        }:
            raise DeletionConfirmationRejected
        action = "ERASE" if scope in PARTIAL_SCOPES or impact.kind in KNOWN_KINDS else "VERIFY"
        item = DeletionWorkItem(
            id=str(uuid4()),
            request_id=request.id,
            kind=impact.kind,
            target_id=impact.target_id,
            action=action,
            status="PENDING",
        )
        session.add(item)
        if action == "ERASE" and scope not in PARTIAL_SCOPES:
            enqueue_event(
                session,
                event_type="DELETION_WORK",
                target_id=item.id,
                handler_id=f"deletion:{item.id}",
                now=now,
            )
    if scope in PARTIAL_SCOPES:
        item = DeletionWorkItem(
            id=str(uuid4()),
            request_id=request.id,
            kind="PARTIAL_LOCAL_DATA",
            target_id=ledger_profile_id,
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
    elif any(impact.kind in LOCAL_PROFILE_KINDS for impact in confirmed.items):
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
    if (
        request.scope in {scope.value for scope in PARTIAL_SCOPES}
        and item.kind != "PARTIAL_LOCAL_DATA"
    ):
        raise ValueError("partial deletion requires aggregate work")
    account_id = request.account_id
    if item.kind == "PARTIAL_LOCAL_DATA":
        _apply_partial_local_data(session, request, item)
    elif item.kind == "AUTH_IDENTITY":
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
            filters = (model.account_id == account_id, model.profile_id == profile.id)
            if model in {ArtifactUnit, Artifact}:
                _delete_artifact_lineage(session, model, *filters)
            else:
                session.execute(delete(model).where(*filters))
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


def _apply_partial_local_data(session: Session, request: DeletionRequest, aggregate) -> None:
    if request.scope not in {scope.value for scope in PARTIAL_SCOPES}:
        raise ValueError("partial work scope mismatch")
    ledger = session.get(ErasureLedger, request.id)
    if (
        ledger is None
        or ledger.profile_id != aggregate.target_id
        or type(ledger.profile_version_after) is not int
    ):
        raise ValueError("partial ledger missing")
    profile = session.scalar(
        select(CareerProfile)
        .where(
            CareerProfile.id == ledger.profile_id,
            CareerProfile.account_id == request.account_id,
            CareerProfile.status == "ACTIVE",
        )
        .with_for_update()
    )
    if profile is None or profile.version + 1 != ledger.profile_version_after:
        raise ValueError("profile version changed")
    work = list(
        session.scalars(
            select(DeletionWorkItem).where(
                DeletionWorkItem.request_id == request.id,
                DeletionWorkItem.action == "ERASE",
                DeletionWorkItem.id != aggregate.id,
            )
        )
    )
    by_kind: dict[str, set[str]] = {}
    for row in work:
        if row.status != "PENDING":
            raise ValueError("partial work already changed")
        by_kind.setdefault(row.kind, set()).add(row.target_id)
    if by_kind.get("PROFILE_VERSION") != {profile.id}:
        raise ValueError("partial profile guard missing")
    if request.scope == DeletionScope.PROJECT.value:
        project = session.scalar(
            select(ProjectScope).where(
                ProjectScope.id == request.target_id,
                ProjectScope.account_id == request.account_id,
                ProjectScope.profile_id == profile.id,
                ProjectScope.status == "ACTIVE",
            )
        )
        if project is None or by_kind.get("PROJECT_SCOPE") != {project.id}:
            raise ValueError("project guard missing")
        project.status = "DELETING"
    elif request.scope == DeletionScope.EVIDENCE.value:
        if request.target_id not in by_kind.get("EVIDENCE_ITEM", set()):
            raise ValueError("evidence guard missing")
    elif request.target_id not in by_kind.get("PROFILING_SESSION", set()):
        raise ValueError("session guard missing")

    allowed = {kind for kind, _ in _PARTIAL_DELETE_ORDER} | {
        "PROFILE_VERSION",
        "PROJECT_SCOPE",
        "CLAIM_REASSESS",
    }
    if set(by_kind) - allowed:
        raise ValueError("unknown partial work kind")
    for kind, model in _PARTIAL_DELETE_ORDER:
        targets = by_kind.get(kind)
        if not targets:
            continue
        filters = [model.id.in_(targets), model.account_id == request.account_id]
        if hasattr(model, "profile_id"):
            filters.append(model.profile_id == profile.id)
        deleted_count = (
            _delete_artifact_lineage(session, model, *filters)
            if model in {ArtifactUnit, Artifact}
            else session.execute(delete(model).where(*filters)).rowcount
        )
        if deleted_count != len(targets):
            raise ValueError("partial work target changed")
    session.flush()
    profile = session.get(CareerProfile, ledger.profile_id)
    for claim_id in sorted(by_kind.get("CLAIM_REASSESS", set())):
        claim = session.scalar(
            select(Claim).where(
                Claim.id == claim_id,
                Claim.account_id == request.account_id,
                Claim.profile_id == profile.id,
                Claim.status == "ACTIVE",
            )
        )
        if claim is None:
            raise ValueError("reassessment claim unavailable")
        previous = session.scalar(
            select(ClaimAssessment)
            .where(
                ClaimAssessment.account_id == request.account_id,
                ClaimAssessment.profile_id == profile.id,
                ClaimAssessment.claim_id == claim_id,
            )
            .order_by(ClaimAssessment.profile_version.desc())
            .limit(1)
        )
        session.add(
            ClaimAssessment(
                id=str(uuid4()),
                account_id=request.account_id,
                profile_id=profile.id,
                claim_id=claim_id,
                knowledge_status=previous.knowledge_status if previous else "UNKNOWN",
                consistency_status="NOT_EVALUATED",
                usage_policy="REVIEW_REQUIRED",
                profile_version=ledger.profile_version_after,
                assessed_at=(
                    request.created_at.replace(tzinfo=UTC)
                    if request.created_at.tzinfo is None
                    else request.created_at.astimezone(UTC)
                ),
            )
        )
    session.add(
        ProfileChangeSet(
            id=str(uuid4()),
            account_id=request.account_id,
            profile_id=profile.id,
            version_before=profile.version,
            version_after=ledger.profile_version_after,
            review_batch_id=request.id,
            review_digest=hashlib.sha256(request.impact_digest.encode()).hexdigest(),
            reason="PARTIAL_ERASURE",
            created_at=(
                request.created_at.replace(tzinfo=UTC)
                if request.created_at.tzinfo is None
                else request.created_at.astimezone(UTC)
            ),
        )
    )
    profile.version = ledger.profile_version_after
    session.flush()
    ensure_profile_archive(
        session,
        account_id=request.account_id,
        profile_id=profile.id,
        profile_version=profile.version,
        now=(
            request.created_at.replace(tzinfo=UTC)
            if request.created_at.tzinfo is None
            else request.created_at.astimezone(UTC)
        ),
    )
    for row in work:
        row.status = "DONE"

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

_DIGEST_PATTERN = re.compile(r"v1\.([0-9]{10,13})\.([0-9a-f]{64})\Z")


class DeletionScope(StrEnum):
    ACCOUNT = "ACCOUNT"
    PROFILE = "PROFILE"
    SESSION = "SESSION"
    EVIDENCE = "EVIDENCE"
    PROJECT = "PROJECT"


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
            items.extend(self._private_object_items(session, account_id, profile_id=profile.id))
            items.extend(self._graph_items(session, account_id, profile_id=profile.id))
            items.extend(self._derived_items(session, account_id, profile_id=profile.id))
            return tuple(sorted(items, key=lambda item: (item.kind, item.target_id)))
        if scope in {DeletionScope.SESSION, DeletionScope.EVIDENCE, DeletionScope.PROJECT}:
            return self._partial_items(session, account_id, scope, target_id)
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
        items.extend(self._private_object_items(session, account_id))
        items.extend(self._graph_items(session, account_id))
        items.extend(self._derived_items(session, account_id))
        return tuple(sorted(items, key=lambda item: (item.kind, item.target_id)))

    @staticmethod
    def _partial_items(session, account_id, scope, target_id):
        """Collect a fixed target and every stored profile payload that may quote it."""

        if scope == DeletionScope.SESSION:
            target = session.scalar(
                select(ProfilingSession).where(
                    ProfilingSession.id == target_id,
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.status.in_(("ACTIVE", "PAUSED", "EXPIRED")),
                )
            )
        elif scope == DeletionScope.EVIDENCE:
            target = session.scalar(
                select(EvidenceItem).where(
                    EvidenceItem.id == target_id,
                    EvidenceItem.account_id == account_id,
                    EvidenceItem.status == "ACTIVE",
                )
            )
        else:
            target = session.scalar(
                select(ProjectScope).where(
                    ProjectScope.id == target_id,
                    ProjectScope.account_id == account_id,
                    ProjectScope.status == "ACTIVE",
                )
            )
        if target is None:
            raise DeletionTargetUnavailable
        try:
            profile = get_owned_profile(
                session, account_id=account_id, profile_id=target.profile_id
            )
        except ResourceNotFound as exc:
            raise DeletionTargetUnavailable from exc

        def ids(model, *conditions):
            return set(
                session.scalars(
                    select(model.id).where(
                        model.account_id == account_id,
                        model.profile_id == profile.id,
                        *conditions,
                    )
                )
            )

        def account_ids(model, *conditions):
            return set(
                session.scalars(select(model.id).where(model.account_id == account_id, *conditions))
            )

        selected: dict[str, set[str]] = {
            "PROFILE_VERSION": {profile.id},
        }

        def include(kind, values):
            selected.setdefault(kind, set()).update(values)

        if scope == DeletionScope.SESSION:
            include("PROFILING_SESSION", {target.id})
            inputs = account_ids(ProfilingInput, ProfilingInput.session_id == target.id)
            include("PROFILING_INPUT", inputs)
            include(
                "PROFILING_PROTOCOL_STEP",
                account_ids(ProfilingProtocolStep, ProfilingProtocolStep.session_id == target.id),
            )
            include(
                "PROFILING_DRAFT",
                account_ids(ProfilingDraft, ProfilingDraft.session_id == target.id),
            )
            batches = account_ids(
                ProfilingReviewBatch, ProfilingReviewBatch.session_id == target.id
            )
            include("PROFILING_REVIEW_BATCH", batches)
            include(
                "PROFILING_REVIEW_ITEM",
                account_ids(ProfilingReviewItem, ProfilingReviewItem.session_id == target.id),
            )
            claims = set(
                session.scalars(
                    select(ClaimReview.claim_id).where(
                        ClaimReview.account_id == account_id,
                        ClaimReview.profile_id == profile.id,
                        ClaimReview.review_batch_id.in_(batches),
                    )
                )
            )
            constraints = ids(ClaimConstraint, ClaimConstraint.review_batch_id.in_(batches))
            sources = ids(EvidenceSource, EvidenceSource.source_ref.in_(inputs))
        elif scope == DeletionScope.EVIDENCE:
            claims, constraints, batches, sources = set(), set(), set(), set()
        else:
            include("PROJECT_SCOPE", {target.id})
            claims = ids(Claim, Claim.scope_key == target.scope_key)
            constraints = ids(ClaimConstraint, ClaimConstraint.scope_key == target.scope_key)
            batches = ids(ProfilingReviewBatch, ProfilingReviewBatch.scope_key == target.scope_key)
            include("PROFILING_REVIEW_BATCH", batches)
            include(
                "PROFILING_REVIEW_ITEM",
                account_ids(ProfilingReviewItem, ProfilingReviewItem.scope_key == target.scope_key),
            )
            include(
                "PROFILING_DRAFT",
                account_ids(ProfilingDraft, ProfilingDraft.scope_key == target.scope_key),
            )
            sources = set()

        evidence = {target.id} if scope == DeletionScope.EVIDENCE else set()
        evidence.update(ids(EvidenceItem, EvidenceItem.source_id.in_(sources)))
        evidence.update(
            session.scalars(
                select(EvidenceClaimLink.evidence_id).where(
                    EvidenceClaimLink.account_id == account_id,
                    EvidenceClaimLink.profile_id == profile.id,
                    EvidenceClaimLink.claim_id.in_(claims),
                )
            )
        )
        # A selected excerpt or project claim may have been copied from a raw
        # input. Close over every owned raw session that contains such a source:
        # one input can also contain other excerpts and temporary candidates.
        # The resulting wider impact is visible in the exact signed preview.
        candidate_sources = ids(
            EvidenceSource,
            EvidenceSource.id.in_(
                select(EvidenceItem.source_id).where(EvidenceItem.id.in_(evidence))
            ),
        )
        input_refs = set(
            session.scalars(
                select(EvidenceSource.source_ref).where(
                    EvidenceSource.account_id == account_id,
                    EvidenceSource.profile_id == profile.id,
                    EvidenceSource.id.in_(candidate_sources),
                )
            )
        )
        for kind, model in (
            ("PROFILING_DRAFT", ProfilingDraft),
            ("PROFILING_REVIEW_ITEM", ProfilingReviewItem),
        ):
            if selected.get(kind):
                input_refs.update(
                    session.scalars(
                        select(model.source_input_id).where(model.id.in_(selected[kind]))
                    )
                )
        review_item_ids = set()
        if claims:
            review_item_ids.update(
                session.scalars(
                    select(ClaimReview.review_item_id).where(
                        ClaimReview.account_id == account_id,
                        ClaimReview.profile_id == profile.id,
                        ClaimReview.claim_id.in_(claims),
                    )
                )
            )
        if constraints:
            review_item_ids.update(
                session.scalars(
                    select(ClaimConstraint.review_item_id).where(
                        ClaimConstraint.id.in_(constraints)
                    )
                )
            )
        if review_item_ids:
            input_refs.update(
                session.scalars(
                    select(ProfilingReviewItem.source_input_id).where(
                        ProfilingReviewItem.account_id == account_id,
                        ProfilingReviewItem.id.in_(review_item_ids),
                    )
                )
            )
        affected_sessions = set(
            session.scalars(
                select(ProfilingInput.session_id)
                .join(ProfilingSession, ProfilingSession.id == ProfilingInput.session_id)
                .where(
                    ProfilingInput.account_id == account_id,
                    ProfilingInput.id.in_(input_refs),
                    ProfilingSession.profile_id == profile.id,
                )
            )
        )
        if scope == DeletionScope.SESSION:
            affected_sessions.add(target.id)
        if affected_sessions:
            include("PROFILING_SESSION", affected_sessions)
            inputs = account_ids(ProfilingInput, ProfilingInput.session_id.in_(affected_sessions))
            include("PROFILING_INPUT", inputs)
            include(
                "PROFILING_PROTOCOL_STEP",
                account_ids(
                    ProfilingProtocolStep, ProfilingProtocolStep.session_id.in_(affected_sessions)
                ),
            )
            include(
                "PROFILING_DRAFT",
                account_ids(ProfilingDraft, ProfilingDraft.session_id.in_(affected_sessions)),
            )
            batches.update(
                account_ids(
                    ProfilingReviewBatch, ProfilingReviewBatch.session_id.in_(affected_sessions)
                )
            )
            include("PROFILING_REVIEW_BATCH", batches)
            include(
                "PROFILING_REVIEW_ITEM",
                account_ids(
                    ProfilingReviewItem, ProfilingReviewItem.session_id.in_(affected_sessions)
                ),
            )
            sources.update(ids(EvidenceSource, EvidenceSource.source_ref.in_(inputs)))
            evidence.update(ids(EvidenceItem, EvidenceItem.source_id.in_(sources)))
            constraints.update(ids(ClaimConstraint, ClaimConstraint.review_batch_id.in_(batches)))
        if evidence:
            candidate_sources = ids(
                EvidenceSource,
                EvidenceSource.id.in_(
                    select(EvidenceItem.source_id).where(EvidenceItem.id.in_(evidence))
                ),
            )
            for source_id in candidate_sources:
                if ids(EvidenceItem, EvidenceItem.source_id == source_id) <= evidence:
                    sources.add(source_id)
            retained_claims_losing_support = (
                set(
                    session.scalars(
                        select(EvidenceClaimLink.claim_id).where(
                            EvidenceClaimLink.account_id == account_id,
                            EvidenceClaimLink.profile_id == profile.id,
                            EvidenceClaimLink.evidence_id.in_(evidence),
                            EvidenceClaimLink.relation_type == "SUPPORTS",
                        )
                    )
                )
                - claims
            )
            include("CLAIM_REASSESS", retained_claims_losing_support)
        for kind, model, column, values in (
            ("CLAIM", Claim, Claim.id, claims),
            ("CLAIM_CONSTRAINT", ClaimConstraint, ClaimConstraint.id, constraints),
            ("EVIDENCE_SOURCE", EvidenceSource, EvidenceSource.id, sources),
            ("EVIDENCE_ITEM", EvidenceItem, EvidenceItem.id, evidence),
            ("EVIDENCE_CLAIM_LINK", EvidenceClaimLink, EvidenceClaimLink.evidence_id, evidence),
            ("EVIDENCE_CLAIM_LINK", EvidenceClaimLink, EvidenceClaimLink.claim_id, claims),
            ("CLAIM_ASSESSMENT", ClaimAssessment, ClaimAssessment.claim_id, claims),
            ("CLAIM_REVIEW", ClaimReview, ClaimReview.claim_id, claims),
            ("CLAIM_REVIEW", ClaimReview, ClaimReview.review_batch_id, batches),
            ("CLAIM_BOUNDARY_REVIEW", ClaimBoundaryReview, ClaimBoundaryReview.claim_id, claims),
            ("CLAIM_CONFLICT_REVIEW", ClaimConflictReview, ClaimConflictReview.claim_id, claims),
            ("CLAIM_USE_REVIEW", ClaimUseReview, ClaimUseReview.claim_id, claims),
            (
                "CLAIM_USE_REVIEW",
                ClaimUseReview,
                ClaimUseReview.claim_id,
                selected.get("CLAIM_REASSESS", set()),
            ),
            ("PROFILE_CHANGE_SET", ProfileChangeSet, ProfileChangeSet.review_batch_id, batches),
        ):
            if values:
                include(kind, ids(model, column.in_(values)))
        # Historical snapshots, wording, mapping and private MCP receipts may
        # retain exact erased text. Remove all of these for the owned profile.
        for kind, model in (
            ("BROWSER_OPERATION", BrowserOperation),
            ("PROFILE_ARCHIVE", ProfileArchive),
            ("REQUIREMENT_CLAIM_MAP", RequirementClaimMap),
            ("ARTIFACT_CLAIM_LINK", ArtifactClaimLink),
            ("ARTIFACT_WORDING_REVIEW", ArtifactWordingReview),
            ("ARTIFACT_UNIT", ArtifactUnit),
            ("ARTIFACT", Artifact),
        ):
            include(kind, ids(model))
        fingerprints = {}
        for kind, model, field in (
            ("PROJECT_SCOPE", ProjectScope, "scope_key"),
            ("PROFILING_INPUT", ProfilingInput, "body"),
            ("PROFILING_DRAFT", ProfilingDraft, "exact_text"),
            ("PROFILING_REVIEW_ITEM", ProfilingReviewItem, "exact_text"),
            ("CLAIM", Claim, "canonical_text"),
            ("CLAIM_CONSTRAINT", ClaimConstraint, "exact_text"),
            ("EVIDENCE_ITEM", EvidenceItem, "content_text"),
            ("PROFILE_ARCHIVE", ProfileArchive, "snapshot_json"),
            ("ARTIFACT_UNIT", ArtifactUnit, "exact_text"),
            ("BROWSER_OPERATION", BrowserOperation, "result_json"),
        ):
            if selected.get(kind):
                for row in session.scalars(select(model).where(model.id.in_(selected[kind]))):
                    text = getattr(row, field) or ""
                    fingerprints[(kind, row.id)] = hashlib.sha256(text.encode()).hexdigest()
        items = [
            DeletionImpactItem(
                kind,
                row_id,
                profile.version if kind == "PROFILE_VERSION" else None,
                fingerprints.get((kind, row_id)),
            )
            for kind, values in selected.items()
            for row_id in values
        ]
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
        step_ids = session.scalars(
            select(ProfilingProtocolStep.id).where(
                ProfilingProtocolStep.account_id == account_id,
                ProfilingProtocolStep.session_id.in_(workspace_ids),
            )
        ).all()
        items.extend(
            DeletionImpactItem(kind="PROFILING_PROTOCOL_STEP", target_id=step_id)
            for step_id in step_ids
        )
        draft_ids = session.scalars(
            select(ProfilingDraft.id).where(
                ProfilingDraft.account_id == account_id,
                ProfilingDraft.session_id.in_(workspace_ids),
            )
        ).all()
        items.extend(DeletionImpactItem(kind="PROFILING_DRAFT", target_id=id) for id in draft_ids)
        batch_ids = session.scalars(
            select(ProfilingReviewBatch.id).where(
                ProfilingReviewBatch.account_id == account_id,
                ProfilingReviewBatch.session_id.in_(workspace_ids),
            )
        ).all()
        items.extend(
            DeletionImpactItem(kind="PROFILING_REVIEW_BATCH", target_id=id) for id in batch_ids
        )
        if batch_ids:
            item_ids = session.scalars(
                select(ProfilingReviewItem.id).where(
                    ProfilingReviewItem.account_id == account_id,
                    ProfilingReviewItem.batch_id.in_(batch_ids),
                )
            ).all()
            items.extend(
                DeletionImpactItem(kind="PROFILING_REVIEW_ITEM", target_id=id) for id in item_ids
            )
        return items

    @staticmethod
    def _private_object_items(
        session: Session, account_id: str, *, profile_id: str | None = None
    ) -> list[DeletionImpactItem]:
        query = select(PrivateObject).where(PrivateObject.account_id == account_id)
        if profile_id is not None:
            query = query.where(PrivateObject.profile_id == profile_id)
        objects = session.scalars(query.execution_options(populate_existing=True)).all()
        if not objects:
            return []
        items = [
            DeletionImpactItem(kind="PRIVATE_OBJECT", target_id=obj.id, state=obj.status)
            for obj in objects
        ]
        for version in session.scalars(
            select(PrivateObjectVersion).where(
                PrivateObjectVersion.account_id == account_id,
                PrivateObjectVersion.object_id.in_([obj.id for obj in objects]),
            )
        ):
            items.append(
                DeletionImpactItem(
                    kind="PRIVATE_OBJECT_VERSION", target_id=version.id, state=version.status
                )
            )
        return items

    @staticmethod
    def _graph_items(
        session: Session, account_id: str, *, profile_id: str | None = None
    ) -> list[DeletionImpactItem]:
        items = []
        for kind, model in (
            ("PROFILE_CHANGE_SET", ProfileChangeSet),
            ("BROWSER_OPERATION", BrowserOperation),
            ("PROFILE_ARCHIVE", ProfileArchive),
            ("CLAIM", Claim),
            ("EVIDENCE_SOURCE", EvidenceSource),
            ("EVIDENCE_ITEM", EvidenceItem),
            ("EVIDENCE_CLAIM_LINK", EvidenceClaimLink),
            ("CLAIM_ASSESSMENT", ClaimAssessment),
            ("CLAIM_REVIEW", ClaimReview),
            ("CLAIM_BOUNDARY_REVIEW", ClaimBoundaryReview),
            ("CLAIM_CONFLICT_REVIEW", ClaimConflictReview),
            ("CLAIM_USE_REVIEW", ClaimUseReview),
            ("CLAIM_CONSTRAINT", ClaimConstraint),
            ("PROJECT_SCOPE", ProjectScope),
        ):
            query = select(model.id).where(model.account_id == account_id)
            if profile_id is not None:
                query = query.where(model.profile_id == profile_id)
            items.extend(
                DeletionImpactItem(kind=kind, target_id=row_id) for row_id in session.scalars(query)
            )
        return items

    @staticmethod
    def _derived_items(
        session: Session, account_id: str, *, profile_id: str | None = None
    ) -> list[DeletionImpactItem]:
        items = []
        for kind, model in (
            ("JOB_DESCRIPTION", JobDescription),
            ("JD_REQUIREMENT", JDRequirement),
            ("REQUIREMENT_CLAIM_MAP", RequirementClaimMap),
            ("ARTIFACT", Artifact),
            ("ARTIFACT_UNIT", ArtifactUnit),
            ("ARTIFACT_WORDING_REVIEW", ArtifactWordingReview),
            ("ARTIFACT_CLAIM_LINK", ArtifactClaimLink),
        ):
            query = select(model.id).where(model.account_id == account_id)
            if profile_id is not None:
                query = query.where(model.profile_id == profile_id)
            items.extend(
                DeletionImpactItem(kind=kind, target_id=row_id) for row_id in session.scalars(query)
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

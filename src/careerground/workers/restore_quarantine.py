"""Offline synthetic restore reconciliation against an independent signed ledger."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from datetime import UTC

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from careerground.domain.deletion_execution import ledger_signature
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
    ErasureLedger,
    PrivateObject,
    ProfilingInput,
    ProfilingSession,
    ProjectScope,
)


class QuarantineRejected(Exception):
    """Restored data must remain inaccessible."""


def signed_manifest(rows: Sequence[ErasureLedger], *, secret: bytes) -> str:
    """A trusted checkpoint must be stored separately from the backup and ledger."""

    if len(secret) < 32:
        raise ValueError("ledger signing secret too short")
    records = sorted((row.request_id, row.signature) for row in rows)
    message = "\n".join(f"{request_id}:{signature}" for request_id, signature in records)
    return hmac.new(secret, f"{len(records)}\n{message}".encode(), hashlib.sha256).hexdigest()


class RestoreQuarantine:
    """No serving adapter exists; readiness remains false until reconcile commits."""

    def __init__(self) -> None:
        self.ready = False

    def reconcile(
        self,
        session: Session,
        *,
        ledger_rows: Sequence[ErasureLedger],
        expected_manifest: str,
        secret: bytes,
    ) -> None:
        self.ready = False
        if not isinstance(expected_manifest, str) or not hmac.compare_digest(
            signed_manifest(ledger_rows, secret=secret), expected_manifest
        ):
            raise QuarantineRejected("ledger checkpoint mismatch")
        if len({row.request_id for row in ledger_rows}) != len(ledger_rows):
            raise QuarantineRejected("duplicate erasure record")
        try:
            for row in ledger_rows:
                expected = ledger_signature(
                    secret,
                    request_id=row.request_id,
                    account_id=row.account_id,
                    scope=row.scope,
                    target_id=row.target_id,
                    created_at=row.created_at,
                    profile_id=row.profile_id,
                    profile_version_after=row.profile_version_after,
                )
                if not hmac.compare_digest(row.signature, expected):
                    raise QuarantineRejected("erasure record failed authentication")
                if row.scope == "ACCOUNT" and row.target_id == row.account_id:
                    self._reject_graph(session, row.account_id)
                    if (
                        session.scalar(
                            select(PrivateObject.id)
                            .where(PrivateObject.account_id == row.account_id)
                            .limit(1)
                        )
                        is not None
                    ):
                        raise QuarantineRejected(
                            "private object versions require provider verification"
                        )
                    self._quarantine_account(session, row.account_id)
                elif row.scope == "PROFILE":
                    self._reject_graph(session, row.account_id, row.target_id)
                    if (
                        session.scalar(
                            select(PrivateObject.id)
                            .where(
                                PrivateObject.account_id == row.account_id,
                                PrivateObject.profile_id == row.target_id,
                            )
                            .limit(1)
                        )
                        is not None
                    ):
                        raise QuarantineRejected(
                            "private object versions require provider verification"
                        )
                    self._quarantine_profile(session, row.account_id, row.target_id)
                elif row.scope in {"SESSION", "EVIDENCE", "PROJECT"}:
                    self._reject_partial_restore(session, row, ledger_rows)
                else:
                    raise QuarantineRejected("invalid erasure scope")
            session.commit()
        except Exception:
            session.rollback()
            raise
        self.ready = True

    @staticmethod
    def _reject_partial_restore(
        session: Session, row: ErasureLedger, ledger_rows: Sequence[ErasureLedger]
    ) -> None:
        if any(
            later.account_id == row.account_id
            and (
                later.created_at.replace(tzinfo=UTC)
                if later.created_at.tzinfo is None
                else later.created_at.astimezone(UTC)
            )
            >= (
                row.created_at.replace(tzinfo=UTC)
                if row.created_at.tzinfo is None
                else row.created_at.astimezone(UTC)
            )
            and (
                later.scope == "ACCOUNT"
                or (later.scope == "PROFILE" and later.target_id == row.profile_id)
            )
            for later in ledger_rows
        ):
            return
        if (
            type(row.profile_id) is not str
            or type(row.profile_version_after) is not int
            or row.profile_version_after < 1
        ):
            raise QuarantineRejected("partial erasure checkpoint metadata missing")
        account = session.get(Account, row.account_id)
        profile = session.get(CareerProfile, row.profile_id)
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.account_id != row.account_id
            or profile.status != "ACTIVE"
            or profile.version < row.profile_version_after
        ):
            raise QuarantineRejected("restored partial profile is stale")
        if row.scope == "SESSION":
            if session.get(ProfilingSession, row.target_id) is not None:
                raise QuarantineRejected("erased session restored")
        elif row.scope == "EVIDENCE":
            if session.get(EvidenceItem, row.target_id) is not None:
                raise QuarantineRejected("erased evidence restored")
        else:
            project = session.get(ProjectScope, row.target_id)
            if (
                project is None
                or project.account_id != row.account_id
                or project.profile_id != profile.id
                or project.status != "DELETING"
            ):
                raise QuarantineRejected("project tombstone missing")
            if (
                session.scalar(
                    select(Claim.id)
                    .where(
                        Claim.account_id == row.account_id,
                        Claim.profile_id == profile.id,
                        Claim.scope_key == project.scope_key,
                    )
                    .limit(1)
                )
                is not None
            ):
                raise QuarantineRejected("erased project claim restored")
        for model in (ProfileArchive, Artifact, RequirementClaimMap, BrowserOperation):
            if (
                session.scalar(
                    select(model.id)
                    .where(
                        model.account_id == row.account_id,
                        model.profile_id == profile.id,
                        model.profile_version < row.profile_version_after,
                    )
                    .limit(1)
                )
                is not None
            ):
                raise QuarantineRejected("erased derived payload restored")

    def assert_ready(self) -> None:
        if not self.ready:
            raise QuarantineRejected("restored copy is still quarantined")

    @staticmethod
    def _reject_graph(session: Session, account_id: str, profile_id: str | None = None) -> None:
        for model in (
            BrowserOperation,
            ProfileChangeSet,
            ProfileArchive,
            Claim,
            EvidenceSource,
            EvidenceItem,
            EvidenceClaimLink,
            ClaimAssessment,
            ClaimReview,
            ClaimBoundaryReview,
            ClaimConflictReview,
            ClaimUseReview,
            ClaimConstraint,
            ProjectScope,
            ArtifactClaimLink,
            RequirementClaimMap,
            ArtifactUnit,
            ArtifactWordingReview,
            Artifact,
            JDRequirement,
            JobDescription,
        ):
            query = select(model.id).where(model.account_id == account_id).limit(1)
            if profile_id is not None:
                query = query.where(model.profile_id == profile_id)
            if session.scalar(query) is not None:
                raise QuarantineRejected("canonical graph requires erasure reconciliation")

    @staticmethod
    def _quarantine_account(session: Session, account_id: str) -> None:
        session.execute(delete(ProfilingInput).where(ProfilingInput.account_id == account_id))
        session.execute(delete(ProfilingSession).where(ProfilingSession.account_id == account_id))
        session.execute(delete(AuthIdentity).where(AuthIdentity.account_id == account_id))
        session.execute(
            update(CareerProfile)
            .where(CareerProfile.account_id == account_id)
            .values(status="DELETING")
        )
        session.execute(update(Account).where(Account.id == account_id).values(status="DELETING"))

    @staticmethod
    def _quarantine_profile(session: Session, account_id: str, profile_id: str) -> None:
        session_ids = list(
            session.scalars(
                select(ProfilingSession.id).where(
                    ProfilingSession.account_id == account_id,
                    ProfilingSession.profile_id == profile_id,
                )
            )
        )
        if session_ids:
            session.execute(
                delete(ProfilingInput).where(ProfilingInput.session_id.in_(session_ids))
            )
            session.execute(delete(ProfilingSession).where(ProfilingSession.id.in_(session_ids)))
        session.execute(
            update(CareerProfile)
            .where(CareerProfile.id == profile_id, CareerProfile.account_id == account_id)
            .values(status="DELETING")
        )

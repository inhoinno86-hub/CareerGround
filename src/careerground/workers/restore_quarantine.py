"""Offline synthetic restore reconciliation against an independent signed ledger."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence

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
    CareerProfile,
    ErasureLedger,
    PrivateObject,
    ProfilingInput,
    ProfilingSession,
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
                else:
                    raise QuarantineRejected("invalid erasure scope")
            session.commit()
        except Exception:
            session.rollback()
            raise
        self.ready = True

    def assert_ready(self) -> None:
        if not self.ready:
            raise QuarantineRejected("restored copy is still quarantined")

    @staticmethod
    def _reject_graph(session: Session, account_id: str, profile_id: str | None = None) -> None:
        for model in (
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

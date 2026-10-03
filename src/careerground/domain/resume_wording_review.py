"""Synthetic exact R1 wording review and in-memory text export."""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.resume_draft import (
    ResumeDraftUnavailable,
    ResumeTrace,
    ResumeUnitTrace,
    get_resume_trace,
)
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactUnit,
    ArtifactWordingReview,
)
from careerground.storage.models import Account, CareerProfile

REVIEW_TTL = timedelta(minutes=10)
MAX_RESUME_EXPORT_BYTES = 1024 * 1024


class WordingReviewRejected(Exception):
    """The exact draft, owner, evidence, boundary or approval is unavailable."""


@dataclass(frozen=True)
class WordingReviewView:
    review_id: str
    account_id: str
    artifact_id: str
    artifact_version: int
    profile_version: int
    unit_texts: tuple[tuple[str, str], ...]
    trace_units: tuple[ResumeUnitTrace, ...]
    review_digest: str
    expires_at: datetime


@dataclass(frozen=True)
class VerifiedWordingApproval:
    """Future trusted user-confirmation output, not a tool argument."""

    account_id: str
    review_id: str
    artifact_id: str
    review_digest: str
    expires_at: datetime


@dataclass(frozen=True)
class ResumeExport:
    artifact_id: str
    artifact_version: int
    profile_version: int
    format: str
    content_hash: str
    content_text: str
    wording_level: str = "R1"


class WordingReviewService:
    def __init__(self, signing_secret: bytes) -> None:
        if len(signing_secret) < 32:
            raise ValueError("wording signing secret too short")
        self._secret = signing_secret

    def prepare(
        self, session: Session, *, account_id: str, artifact_id: str, now: datetime
    ) -> WordingReviewView:
        """Show all fixed R1 units in one exact review; no mutation."""

        now = _utc(now)
        return self._view(
            session,
            account_id=account_id,
            artifact_id=artifact_id,
            review_id=str(uuid4()),
            expires_at=now + REVIEW_TTL,
        )

    def submit(
        self,
        session: Session,
        *,
        view: WordingReviewView,
        approval: VerifiedWordingApproval,
        now: datetime,
    ) -> ArtifactWordingReview:
        """Accept only the exact displayed R1 wording in the caller's transaction."""

        now = _utc(now)
        if (
            type(view) is not WordingReviewView
            or type(approval) is not VerifiedWordingApproval
            or approval.expires_at.tzinfo is None
            or _utc(approval.expires_at) <= now
            or _utc(view.expires_at) <= now
            or approval.account_id != view.account_id
            or approval.review_id != view.review_id
            or approval.artifact_id != view.artifact_id
            or _utc(approval.expires_at) != _utc(view.expires_at)
            or not hmac.compare_digest(approval.review_digest, view.review_digest)
        ):
            raise WordingReviewRejected
        account = session.scalar(
            select(Account)
            .where(Account.id == view.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        artifact = session.scalar(
            select(Artifact)
            .where(Artifact.id == view.artifact_id, Artifact.account_id == view.account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if account is None or account.status != "ACTIVE" or artifact is None:
            raise WordingReviewRejected
        profile = session.scalar(
            select(CareerProfile)
            .where(
                CareerProfile.id == artifact.profile_id,
                CareerProfile.account_id == view.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if profile is None or profile.status != "ACTIVE":
            raise WordingReviewRejected
        existing = session.scalar(
            select(ArtifactWordingReview).where(ArtifactWordingReview.id == view.review_id)
        )
        if existing is not None:
            if (
                existing.account_id != view.account_id
                or existing.artifact_id != view.artifact_id
                or not hmac.compare_digest(existing.review_digest, view.review_digest)
            ):
                raise WordingReviewRejected
            return existing
        if profile.version != artifact.profile_version:
            raise WordingReviewRejected
        current = self._view(
            session,
            account_id=view.account_id,
            artifact_id=view.artifact_id,
            review_id=view.review_id,
            expires_at=view.expires_at,
        )
        if current != view:
            raise WordingReviewRejected
        units = tuple(
            session.scalars(
                select(ArtifactUnit)
                .where(
                    ArtifactUnit.artifact_id == artifact.id,
                    ArtifactUnit.account_id == view.account_id,
                    ArtifactUnit.profile_id == artifact.profile_id,
                )
                .order_by(ArtifactUnit.ordinal)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if tuple((unit.id, unit.exact_text) for unit in units) != view.unit_texts:
            raise WordingReviewRejected
        if any(
            unit.wording_level != "R1" or unit.review_status != "REVIEW_REQUIRED" for unit in units
        ):
            raise WordingReviewRejected
        for unit in units:
            unit.review_status = "WORDING_REVIEWED"
        artifact.status = "WORDING_REVIEWED"
        review = ArtifactWordingReview(
            id=view.review_id,
            account_id=view.account_id,
            profile_id=artifact.profile_id,
            artifact_id=artifact.id,
            artifact_version=artifact.artifact_version,
            profile_version=artifact.profile_version,
            action="ACCEPT_R1",
            review_digest=view.review_digest,
            expires_at=view.expires_at,
            reviewed_at=now,
        )
        session.add(review)
        session.flush()
        return review

    def submit_prepared(
        self,
        session: Session,
        *,
        account_id: str,
        artifact_id: str,
        review_id: str,
        review_digest: str,
        expires_at: datetime,
        now: datetime,
    ) -> ArtifactWordingReview:
        """Rebuild a displayed review after a trusted adapter proves user intent."""

        try:
            now = _utc(now)
            expires_at = _utc(expires_at)
        except ValueError as exc:
            raise WordingReviewRejected from exc
        if (
            not all(
                isinstance(value, str) and value
                for value in (account_id, artifact_id, review_id, review_digest)
            )
            or expires_at <= now
        ):
            raise WordingReviewRejected
        existing = session.scalar(
            select(ArtifactWordingReview).where(ArtifactWordingReview.id == review_id)
        )
        if existing is None:
            view = self._view(
                session,
                account_id=account_id,
                artifact_id=artifact_id,
                review_id=review_id,
                expires_at=expires_at,
            )
            if not hmac.compare_digest(view.review_digest, review_digest):
                raise WordingReviewRejected
        else:
            # submit() checks the existing row and active owner before returning
            # it. Exact source rechecks remain mandatory for any later export.
            view = WordingReviewView(
                review_id=review_id,
                account_id=account_id,
                artifact_id=artifact_id,
                artifact_version=existing.artifact_version,
                profile_version=existing.profile_version,
                unit_texts=(),
                trace_units=(),
                review_digest=review_digest,
                expires_at=expires_at,
            )
        return self.submit(
            session,
            view=view,
            approval=VerifiedWordingApproval(
                account_id=account_id,
                review_id=review_id,
                artifact_id=artifact_id,
                review_digest=review_digest,
                expires_at=expires_at,
            ),
            now=now,
        )

    def export_resume(
        self,
        session: Session,
        *,
        account_id: str,
        artifact_id: str,
        format: str,
    ) -> ResumeExport:
        """Return reviewed text in memory after rechecking the current Graph."""

        if format not in {"JSON", "MARKDOWN"}:
            raise WordingReviewRejected
        artifact = session.scalar(
            select(Artifact)
            .where(Artifact.id == artifact_id, Artifact.account_id == account_id)
            .execution_options(populate_existing=True)
        )
        if artifact is None or artifact.status != "WORDING_REVIEWED":
            raise WordingReviewRejected
        profile = session.scalar(
            select(CareerProfile)
            .where(
                CareerProfile.id == artifact.profile_id,
                CareerProfile.account_id == account_id,
                CareerProfile.status == "ACTIVE",
            )
            .execution_options(populate_existing=True)
        )
        if profile is None or profile.version != artifact.profile_version:
            raise WordingReviewRejected
        review = session.scalar(
            select(ArtifactWordingReview)
            .where(
                ArtifactWordingReview.artifact_id == artifact.id,
                ArtifactWordingReview.account_id == account_id,
            )
            .execution_options(populate_existing=True)
        )
        expected_action = "ACCEPT_R2" if artifact.source_artifact_id is not None else "ACCEPT_R1"
        if (
            review is None
            or review.action != expected_action
            or review.artifact_version != artifact.artifact_version
            or review.profile_version != artifact.profile_version
        ):
            raise WordingReviewRejected
        try:
            trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
        except ResumeDraftUnavailable as exc:
            raise WordingReviewRejected from exc
        wording_level = "R2" if expected_action == "ACCEPT_R2" else "R1"
        if trace.stale_relative_to_current_profile or any(
            unit.review_status != "WORDING_REVIEWED" or unit.wording_level != wording_level
            for unit in trace.units
        ):
            raise WordingReviewRejected
        if not hmac.compare_digest(
            review.review_digest,
            self._digest(account_id, trace, review.id, _stored_utc(review.expires_at)),
        ):
            raise WordingReviewRejected
        if format == "JSON":
            body = json.dumps(
                {
                    "schema": "careerground-resume-text-v2"
                    if wording_level == "R2"
                    else "careerground-resume-text-v1",
                    "artifact_id": artifact.id,
                    "artifact_version": artifact.artifact_version,
                    "profile_version": artifact.profile_version,
                    "jd_id": artifact.jd_id,
                    **(
                        {"source_artifact_id": artifact.source_artifact_id}
                        if wording_level == "R2"
                        else {}
                    ),
                    "units": [
                        {
                            "text": unit.exact_text,
                            "wording_level": unit.wording_level,
                            "claim_id": unit.claim_id,
                            "evidence_ids": list(unit.evidence_ids),
                            "evidence_excerpts": list(unit.evidence_excerpts),
                            "original_input_refs": list(unit.original_input_refs),
                            **(
                                {"source_unit_id": unit.source_unit_id}
                                if wording_level == "R2"
                                else {}
                            ),
                        }
                        for unit in trace.units
                    ],
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            body = "\n".join(f"- {_markdown_text(unit.exact_text)}" for unit in trace.units) + "\n"
        if len(body.encode()) > MAX_RESUME_EXPORT_BYTES:
            raise WordingReviewRejected
        return ResumeExport(
            artifact_id=artifact.id,
            artifact_version=artifact.artifact_version,
            profile_version=artifact.profile_version,
            format=format,
            content_hash=hashlib.sha256(body.encode()).hexdigest(),
            content_text=body,
            wording_level=wording_level,
        )

    def _view(
        self,
        session: Session,
        *,
        account_id: str,
        artifact_id: str,
        review_id: str,
        expires_at: datetime,
    ) -> WordingReviewView:
        artifact = session.scalar(
            select(Artifact)
            .where(Artifact.id == artifact_id, Artifact.account_id == account_id)
            .execution_options(populate_existing=True)
        )
        if artifact is None or artifact.status != "REVIEW_REQUIRED":
            raise WordingReviewRejected
        try:
            trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
        except ResumeDraftUnavailable as exc:
            raise WordingReviewRejected from exc
        if trace.stale_relative_to_current_profile or any(
            unit.wording_level != "R1" or unit.review_status != "REVIEW_REQUIRED"
            for unit in trace.units
        ):
            raise WordingReviewRejected
        return WordingReviewView(
            review_id=review_id,
            account_id=account_id,
            artifact_id=artifact.id,
            artifact_version=artifact.artifact_version,
            profile_version=artifact.profile_version,
            unit_texts=tuple((unit.unit_id, unit.exact_text) for unit in trace.units),
            trace_units=trace.units,
            review_digest=self._digest(account_id, trace, review_id, expires_at),
            expires_at=_utc(expires_at),
        )

    def _digest(
        self, account_id: str, trace: ResumeTrace, review_id: str, expires_at: datetime
    ) -> str:
        if trace.source_artifact_id is not None:
            payload = {
                "purpose": "R2_EXACT_WORDING_APPROVAL",
                "review_id": review_id,
                "account_id": account_id,
                "artifact_id": trace.artifact_id,
                "source_artifact_id": trace.source_artifact_id,
                "artifact_version": trace.artifact_version,
                "profile_version": trace.profile_version,
                "jd_id": trace.jd_id,
                "expires_at": _utc(expires_at).isoformat(),
                "units": [
                    {
                        "unit_id": unit.unit_id,
                        "source_unit_id": unit.source_unit_id,
                        "exact_text": unit.exact_text,
                        "claim_id": unit.claim_id,
                        "evidence_ids": unit.evidence_ids,
                        "evidence_excerpts": unit.evidence_excerpts,
                        "original_input_refs": unit.original_input_refs,
                    }
                    for unit in trace.units
                ],
            }
            return hmac.new(
                self._secret,
                json.dumps(
                    payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode(),
                hashlib.sha256,
            ).hexdigest()
        payload = {
            "purpose": "R1_WORDING_REVIEW",
            "review_id": review_id,
            "account_id": account_id,
            "artifact_id": trace.artifact_id,
            "artifact_version": trace.artifact_version,
            "profile_version": trace.profile_version,
            "jd_id": trace.jd_id,
            "expires_at": _utc(expires_at).isoformat(),
            "units": [
                {
                    "unit_id": unit.unit_id,
                    "exact_text": unit.exact_text,
                    "claim_id": unit.claim_id,
                    "evidence_ids": unit.evidence_ids,
                    "evidence_excerpts": unit.evidence_excerpts,
                    "original_input_refs": unit.original_input_refs,
                }
                for unit in trace.units
            ],
        }
        return hmac.new(
            self._secret,
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()


def _markdown_text(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"([\\`*_{}\[\]()#+.!|~-])", r"\\\1", escaped)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\n  ")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return value.astimezone(UTC)


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

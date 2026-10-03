"""Exact, browser-bound approval of local synthetic R2 wording proposals.

The proposal and its source trace live only in a short-lived signed token until
the browser explicitly submits approval. R3 facts have a separate review path.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careerground.domain.resume_draft import ResumeDraftUnavailable, ResumeTrace, get_resume_trace
from careerground.domain.resume_wording_review import WordingReviewService
from careerground.domain.text_proposal_validation import (
    R2WordingPreview,
    TextProposalRejected,
    validate_r2_wording_proposal,
)
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactClaimLink,
    ArtifactUnit,
    ArtifactWordingReview,
)
from careerground.storage.models import Account, CareerProfile

R2_APPROVAL_TTL = timedelta(minutes=3)
_MAX_TOKEN_LENGTH = 40000
_TOKEN_KEYS = {
    "purpose",
    "account_id",
    "browser_session_id",
    "source_artifact_id",
    "source_artifact_version",
    "target_artifact_id",
    "profile_id",
    "profile_version",
    "jd_id",
    "units",
    "expires_at",
}


class R2ProposalRejected(Exception):
    """The exact proposal, source, owner, or approval is unavailable."""


class R2FactReviewRequired(R2ProposalRejected):
    """New facts require the existing profiling and fact-review flow first."""


@dataclass(frozen=True)
class R2ProposalView:
    source: ResumeTrace
    previews: tuple[R2WordingPreview, ...]
    target_artifact_id: str
    approval_token: str
    expires_at: datetime


class R2ProposalService:
    def __init__(self, signing_secret: bytes) -> None:
        if type(signing_secret) is not bytes or len(signing_secret) < 32:
            raise ValueError("R2 signing secret too short")
        self._secret = signing_secret
        self._wording = WordingReviewService(signing_secret)

    def prepare(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        source_artifact_id: str,
        proposals: tuple[dict[str, object], ...],
        now: datetime,
    ) -> R2ProposalView:
        """Validate 1–5 exact proposals without writing any candidate or artifact."""
        now = _utc(now)
        _identity(account_id, browser_session_id, source_artifact_id)
        if type(proposals) is not tuple or not 1 <= len(proposals) <= 5:
            raise R2ProposalRejected
        source, artifact = _source(session, account_id, source_artifact_id)
        if len(proposals) != len(source.units):
            raise R2ProposalRejected
        previews = []
        units = []
        for original, proposal in zip(source.units, proposals, strict=True):
            if (
                type(proposal) is not dict
                or set(proposal)
                != {
                    "unit_id",
                    "source_hash",
                    "proposed_text",
                    "fact_review",
                    "claim_id",
                    "evidence_ids",
                }
                or proposal["unit_id"] != original.unit_id
            ):
                raise R2ProposalRejected
            try:
                preview = validate_r2_wording_proposal(
                    session,
                    account_id=account_id,
                    profile_id=artifact.profile_id,
                    profile_version=artifact.profile_version,
                    artifact_id=source_artifact_id,
                    unit_id=original.unit_id,
                    payload={key: value for key, value in proposal.items() if key != "unit_id"},
                )
            except TextProposalRejected as exc:
                if exc.code == "R3_NEEDS_FACT_REVIEW":
                    raise R2FactReviewRequired from None
                raise R2ProposalRejected from None
            previews.append(preview)
            units.append(_unit_payload(original, preview.proposed_text))
        target_artifact_id = str(uuid4())
        expires_at = now + R2_APPROVAL_TTL
        payload = {
            "purpose": "R2_EXACT_PROPOSAL_APPROVAL_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "source_artifact_id": source_artifact_id,
            "source_artifact_version": source.artifact_version,
            "target_artifact_id": target_artifact_id,
            "profile_id": artifact.profile_id,
            "profile_version": artifact.profile_version,
            "jd_id": artifact.jd_id,
            "units": units,
            "expires_at": expires_at.isoformat(),
        }
        return R2ProposalView(
            source=source,
            previews=tuple(previews),
            target_artifact_id=target_artifact_id,
            approval_token=self._sign(payload),
            expires_at=expires_at,
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        approval_token: str,
        now: datetime,
    ) -> Artifact:
        """Persist a separate R2 artifact only after browser approval of exact text."""
        now = _utc(now)
        _identity(account_id, browser_session_id, "source")
        payload = self._verify(approval_token)
        try:
            expires_at = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (TypeError, ValueError) as exc:
            raise R2ProposalRejected from exc
        if (
            payload["purpose"] != "R2_EXACT_PROPOSAL_APPROVAL_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or expires_at <= now
            or type(payload["source_artifact_id"]) is not str
            or type(payload["target_artifact_id"]) is not str
            or type(payload["profile_id"]) is not str
            or type(payload["source_artifact_version"]) is not int
            or type(payload["profile_version"]) is not int
            or type(payload["units"]) is not list
            or not 1 <= len(payload["units"]) <= 5
        ):
            raise R2ProposalRejected
        account = session.scalar(
            select(Account)
            .where(Account.id == account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        profile = session.scalar(
            select(CareerProfile)
            .where(
                CareerProfile.id == payload["profile_id"], CareerProfile.account_id == account_id
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
        ):
            raise R2ProposalRejected
        source, source_artifact = _source(session, account_id, payload["source_artifact_id"])
        if (
            source.artifact_version != payload["source_artifact_version"]
            or source.profile_version != payload["profile_version"]
            or source.jd_id != payload["jd_id"]
            or source_artifact.profile_id != payload["profile_id"]
            or len(source.units) != len(payload["units"])
        ):
            raise R2ProposalRejected
        for original, row in zip(source.units, payload["units"], strict=True):
            if (
                type(row) is not dict
                or set(row)
                != {
                    "source_unit_id",
                    "source_text",
                    "source_hash",
                    "proposed_text",
                    "claim_id",
                    "evidence_ids",
                    "evidence_excerpts",
                    "original_input_refs",
                }
                or row != _unit_payload(original, row.get("proposed_text"))
            ):
                raise R2ProposalRejected
            try:
                validate_r2_wording_proposal(
                    session,
                    account_id=account_id,
                    profile_id=source_artifact.profile_id,
                    profile_version=source_artifact.profile_version,
                    artifact_id=source_artifact.id,
                    unit_id=original.unit_id,
                    payload={
                        "source_hash": row["source_hash"],
                        "proposed_text": row["proposed_text"],
                        "fact_review": "NO_NEW_FACTS",
                        "claim_id": row["claim_id"],
                        "evidence_ids": row["evidence_ids"],
                    },
                )
            except TextProposalRejected as exc:
                raise R2ProposalRejected from exc
        existing = session.get(Artifact, payload["target_artifact_id"])
        if existing is not None:
            if self._matches_existing(session, existing, payload, account_id):
                return existing
            raise R2ProposalRejected
        current = session.scalar(
            select(func.max(Artifact.artifact_version)).where(
                Artifact.account_id == account_id,
                Artifact.profile_id == profile.id,
                Artifact.artifact_type == "RESUME_TEXT",
            )
        )
        artifact = Artifact(
            id=payload["target_artifact_id"],
            account_id=account_id,
            profile_id=profile.id,
            source_artifact_id=source_artifact.id,
            artifact_type="RESUME_TEXT",
            artifact_version=(current or 0) + 1,
            profile_version=profile.version,
            jd_id=source_artifact.jd_id,
            status="WORDING_REVIEWED",
            created_at=now,
        )
        session.add(artifact)
        session.flush()
        for ordinal, row in enumerate(payload["units"], 1):
            unit = ArtifactUnit(
                id=str(uuid4()),
                account_id=account_id,
                profile_id=profile.id,
                artifact_id=artifact.id,
                source_artifact_unit_id=row["source_unit_id"],
                ordinal=ordinal,
                unit_type="RESUME_BULLET",
                exact_text=row["proposed_text"],
                wording_level="R2",
                review_status="WORDING_REVIEWED",
            )
            session.add(unit)
            session.flush()
            session.add(
                ArtifactClaimLink(
                    id=str(uuid4()),
                    account_id=account_id,
                    profile_id=profile.id,
                    artifact_unit_id=unit.id,
                    claim_id=row["claim_id"],
                    link_role="FACTUAL_BASIS",
                )
            )
        session.flush()
        try:
            trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact.id)
        except ResumeDraftUnavailable as exc:
            raise R2ProposalRejected from exc
        review_id = str(uuid4())
        session.add(
            ArtifactWordingReview(
                id=review_id,
                account_id=account_id,
                profile_id=profile.id,
                artifact_id=artifact.id,
                artifact_version=artifact.artifact_version,
                profile_version=artifact.profile_version,
                action="ACCEPT_R2",
                review_digest=self._wording._digest(account_id, trace, review_id, expires_at),
                expires_at=expires_at,
                reviewed_at=now,
            )
        )
        session.flush()
        return artifact

    def _sign(self, payload: dict[str, object]) -> str:
        body = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        token = f"{_b64(body)}.{_b64(signature)}"
        if len(token) > _MAX_TOKEN_LENGTH:
            raise R2ProposalRejected
        return token

    def _verify(self, token: str) -> dict[str, object]:
        if type(token) is not str or len(token) > _MAX_TOKEN_LENGTH or token.count(".") != 1:
            raise R2ProposalRejected
        try:
            body_part, signature_part = token.split(".")
            body = _unb64(body_part)
            signature = _unb64(signature_part)
            payload = json.loads(body)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise R2ProposalRejected from exc
        if (
            len(signature) != 32
            or not hmac.compare_digest(
                signature, hmac.new(self._secret, body, hashlib.sha256).digest()
            )
            or type(payload) is not dict
            or set(payload) != _TOKEN_KEYS
        ):
            raise R2ProposalRejected
        return payload

    def _matches_existing(
        self, session: Session, artifact: Artifact, payload: dict, account_id: str
    ) -> bool:
        if (
            artifact.account_id != account_id
            or artifact.profile_id != payload["profile_id"]
            or artifact.source_artifact_id != payload["source_artifact_id"]
            or artifact.profile_version != payload["profile_version"]
            or artifact.jd_id != payload["jd_id"]
            or artifact.status != "WORDING_REVIEWED"
        ):
            return False
        units = tuple(
            session.scalars(
                select(ArtifactUnit)
                .where(ArtifactUnit.artifact_id == artifact.id)
                .order_by(ArtifactUnit.ordinal)
            )
        )
        review = session.scalar(
            select(ArtifactWordingReview).where(
                ArtifactWordingReview.artifact_id == artifact.id,
                ArtifactWordingReview.account_id == account_id,
            )
        )
        if (
            review is None
            or review.action != "ACCEPT_R2"
            or review.profile_id != artifact.profile_id
            or review.artifact_version != artifact.artifact_version
            or review.profile_version != artifact.profile_version
            or _stored_utc(review.expires_at) != _utc(datetime.fromisoformat(payload["expires_at"]))
            or len(units) != len(payload["units"])
        ):
            return False
        if not all(
            unit.source_artifact_unit_id == row["source_unit_id"]
            and unit.exact_text == row["proposed_text"]
            and unit.wording_level == "R2"
            and unit.review_status == "WORDING_REVIEWED"
            and tuple(
                link.claim_id
                for link in session.scalars(
                    select(ArtifactClaimLink).where(
                        ArtifactClaimLink.artifact_unit_id == unit.id,
                        ArtifactClaimLink.account_id == account_id,
                        ArtifactClaimLink.profile_id == artifact.profile_id,
                        ArtifactClaimLink.link_role == "FACTUAL_BASIS",
                    )
                )
            )
            == (row["claim_id"],)
            for unit, row in zip(units, payload["units"], strict=True)
        ):
            return False
        try:
            trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact.id)
        except ResumeDraftUnavailable:
            return False
        return hmac.compare_digest(
            review.review_digest,
            self._wording._digest(account_id, trace, review.id, _stored_utc(review.expires_at)),
        )


def _source(session: Session, account_id: str, artifact_id: str) -> tuple[ResumeTrace, Artifact]:
    artifact = session.scalar(
        select(Artifact)
        .where(Artifact.id == artifact_id, Artifact.account_id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        artifact is None
        or artifact.status not in {"REVIEW_REQUIRED", "WORDING_REVIEWED"}
        or artifact.source_artifact_id is not None
    ):
        raise R2ProposalRejected
    try:
        trace = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
    except ResumeDraftUnavailable as exc:
        raise R2ProposalRejected from exc
    if trace.stale_relative_to_current_profile or any(
        unit.wording_level != "R1" or unit.review_status != artifact.status for unit in trace.units
    ):
        raise R2ProposalRejected
    return trace, artifact


def _unit_payload(source, proposed_text: object) -> dict[str, object]:
    return {
        "source_unit_id": source.unit_id,
        "source_text": source.exact_text,
        "source_hash": hashlib.sha256(source.exact_text.encode()).hexdigest(),
        "proposed_text": proposed_text,
        "claim_id": source.claim_id,
        "evidence_ids": list(source.evidence_ids),
        "evidence_excerpts": list(source.evidence_excerpts),
        "original_input_refs": list(source.original_input_refs),
    }


def _identity(account_id: str, browser_session_id: str, artifact_id: str) -> None:
    if (
        type(account_id) is not str
        or not account_id
        or type(browser_session_id) is not str
        or not 16 <= len(browser_session_id) <= 128
        or type(artifact_id) is not str
        or not artifact_id
    ):
        raise R2ProposalRejected


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise R2ProposalRejected
    return value.astimezone(UTC)


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or len(value) % 4 == 1:
        raise ValueError("invalid base64")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

"""Owner-selected exact R1 draft creation in the isolated synthetic browser."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.jd_mapping import (
    JDMappingRejected,
    get_jd_mapping,
    require_eligible_claim_trace,
)
from careerground.domain.profile_archive import ArchiveUnavailable, ensure_profile_archive
from careerground.domain.resume_draft import ResumeDraftUnavailable, generate_resume_draft
from careerground.storage.jd_artifact_models import Artifact, JobDescription
from careerground.storage.models import Account, CareerProfile

R1_DRAFT_TOKEN_TTL = timedelta(minutes=3)
_DRAFT_NAMESPACE = UUID("971147e8-7600-424d-a986-661944f4d608")
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "jd_id",
        "profile_version",
        "candidate_digest",
        "nonce",
        "expires_at",
    }
)


class ResumeDraftPresentationRejected(Exception):
    """The exact source, selection, owner, browser session, or version changed."""


@dataclass(frozen=True)
class R1Candidate:
    claim_id: str
    exact_text: str
    evidence: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ResumeDraftPresentation:
    jd_id: str
    profile_version: int
    candidates: tuple[R1Candidate, ...]
    draft_token: str


class ResumeDraftPresentationService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        jd_id: str,
        profile_version: int,
        now: datetime,
    ) -> ResumeDraftPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        _, candidates, digest = _candidates(
            session, account_id=account_id, jd_id=jd_id, profile_version=profile_version, now=now
        )
        token = self._tokens.sign(
            {
                "purpose": "R1_EXACT_DRAFT_V1",
                "account_id": account_id,
                "browser_session_id": browser_session_id,
                "jd_id": jd_id,
                "profile_version": profile_version,
                "candidate_digest": digest,
                "nonce": secrets.token_urlsafe(18),
                "expires_at": (now + R1_DRAFT_TOKEN_TTL).isoformat(),
            }
        )
        return ResumeDraftPresentation(jd_id, profile_version, candidates, token)

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        jd_id: str,
        profile_version: int,
        claim_ids: tuple[str, ...],
        draft_token: str,
        now: datetime,
    ) -> Artifact:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(draft_token, expected_keys=_TOKEN_KEYS)
            expiry = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ResumeDraftPresentationRejected from exc
        if (
            payload["purpose"] != "R1_EXACT_DRAFT_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["jd_id"] != jd_id
            or type(payload["profile_version"]) is not int
            or payload["profile_version"] != profile_version
            or type(payload["candidate_digest"]) is not str
            or type(payload["nonce"]) is not str
            or not 16 <= len(payload["nonce"]) <= 128
            or expiry <= now
            or type(claim_ids) is not tuple
            or not 1 <= len(claim_ids) <= 5
            or len(set(claim_ids)) != len(claim_ids)
            or any(type(claim_id) is not str or not claim_id for claim_id in claim_ids)
        ):
            raise ResumeDraftPresentationRejected
        account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
        jd = session.scalar(
            select(JobDescription).where(
                JobDescription.id == jd_id, JobDescription.account_id == account_id
            )
        )
        profile = (
            session.scalar(
                select(CareerProfile)
                .where(CareerProfile.id == jd.profile_id, CareerProfile.account_id == account_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if jd is not None
            else None
        )
        if (
            account is None
            or account.status != "ACTIVE"
            or profile is None
            or profile.status != "ACTIVE"
            or profile.version != profile_version
        ):
            raise ResumeDraftPresentationRejected
        profile_id, candidates, digest = _candidates(
            session, account_id=account_id, jd_id=jd_id, profile_version=profile_version, now=now
        )
        if not hmac.compare_digest(payload["candidate_digest"], digest) or not set(
            claim_ids
        ).issubset({candidate.claim_id for candidate in candidates}):
            raise ResumeDraftPresentationRejected
        artifact_id = str(uuid5(_DRAFT_NAMESPACE, f"{account_id}:{payload['nonce']}"))
        try:
            return generate_resume_draft(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile_version,
                jd_id=jd_id,
                claim_ids=claim_ids,
                now=now,
                artifact_id=artifact_id,
            )
        except ResumeDraftUnavailable as exc:
            raise ResumeDraftPresentationRejected from exc


def _candidates(
    session: Session,
    *,
    account_id: str,
    jd_id: str,
    profile_version: int,
    now: datetime,
) -> tuple[str, tuple[R1Candidate, ...], str]:
    try:
        mapping = get_jd_mapping(
            session, account_id=account_id, jd_id=jd_id, profile_version=profile_version
        )
        jd = session.scalar(
            select(JobDescription).where(
                JobDescription.id == jd_id, JobDescription.account_id == account_id
            )
        )
        if jd is None or mapping.stale_relative_to_current_profile:
            raise ResumeDraftPresentationRejected
        ensure_profile_archive(
            session,
            account_id=account_id,
            profile_id=jd.profile_id,
            profile_version=profile_version,
            now=now,
        )
        choices = []
        for claim_id in sorted(
            {claim_id for item in mapping.requirements for claim_id in item.linked_claim_ids}
        ):
            try:
                trace = require_eligible_claim_trace(
                    session,
                    account_id=account_id,
                    profile_id=jd.profile_id,
                    profile_version=profile_version,
                    claim_id=claim_id,
                )
            except JDMappingRejected:
                continue
            choices.append(
                R1Candidate(
                    claim_id=claim_id,
                    exact_text=trace.claim.exact_text,
                    evidence=tuple(
                        (item.exact_excerpt, item.original_input_ref)
                        for item in trace.evidence
                        if item.relation_type == "SUPPORTS"
                    ),
                )
            )
    except (JDMappingRejected, ArchiveUnavailable, ValueError) as exc:
        raise ResumeDraftPresentationRejected from exc
    digest = hashlib.sha256(
        json.dumps(
            {
                "jd_id": jd_id,
                "jd_version": mapping.jd_version,
                "profile_version": profile_version,
                "requirements": [
                    (item.requirement_id, item.exact_text, item.linked_claim_ids)
                    for item in mapping.requirements
                ],
                "candidates": [(item.claim_id, item.exact_text, item.evidence) for item in choices],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return jd.profile_id, tuple(choices), digest


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResumeDraftPresentationRejected
    return value.astimezone(UTC)


def _require_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise ResumeDraftPresentationRejected

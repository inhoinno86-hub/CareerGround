"""Exact owner-selected JD requirement to Claim link in the synthetic browser."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.graph_projection import GraphUnavailable, get_career_profile
from careerground.domain.jd_mapping import (
    JDMappingRejected,
    get_jd_mapping,
    link_jd_requirement_to_claim,
    require_eligible_claim_trace,
)
from careerground.domain.profile_archive import ArchiveUnavailable, ensure_profile_archive
from careerground.storage.jd_artifact_models import JobDescription, RequirementClaimMap
from careerground.storage.models import Account, CareerProfile

JD_LINK_TOKEN_TTL = timedelta(minutes=3)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "jd_id",
        "requirement_id",
        "claim_id",
        "profile_version",
        "display_digest",
        "expires_at",
    }
)


class JDLinkPresentationRejected(Exception):
    """An owner, exact source, browser choice, or current version is unavailable."""


@dataclass(frozen=True)
class JDLinkCandidate:
    claim_id: str
    exact_text: str


@dataclass(frozen=True)
class JDLinkPresentation:
    jd_id: str
    requirement_id: str
    claim_id: str
    profile_version: int
    requirement_text: str
    claim_text: str
    evidence: tuple[tuple[str, str], ...]
    link_token: str


class JDLinkPresentationService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def candidates(
        self, session: Session, *, account_id: str, jd_id: str, profile_version: int
    ) -> tuple[JDLinkCandidate, ...]:
        """Show only currently eligible archived Claims; semantic fit remains owner's choice."""

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
                return ()
            profile = get_career_profile(
                session,
                account_id=account_id,
                profile_id=jd.profile_id,
                profile_version=profile_version,
            )
            choices = []
            for claim in profile.claims:
                try:
                    require_eligible_claim_trace(
                        session,
                        account_id=account_id,
                        profile_id=jd.profile_id,
                        profile_version=profile_version,
                        claim_id=claim.claim_id,
                    )
                except JDMappingRejected:
                    continue
                choices.append(JDLinkCandidate(claim.claim_id, claim.exact_text))
            return tuple(choices)
        except (JDMappingRejected, GraphUnavailable) as exc:
            raise JDLinkPresentationRejected from exc

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        jd_id: str,
        requirement_id: str,
        claim_id: str,
        profile_version: int,
        now: datetime,
    ) -> JDLinkPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        requirement_text, claim_text, evidence, digest = _exact_display(
            session,
            account_id=account_id,
            jd_id=jd_id,
            requirement_id=requirement_id,
            claim_id=claim_id,
            profile_version=profile_version,
            now=now,
        )
        payload = {
            "purpose": "JD_CLAIM_LINK_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "jd_id": jd_id,
            "requirement_id": requirement_id,
            "claim_id": claim_id,
            "profile_version": profile_version,
            "display_digest": digest,
            "expires_at": (now + JD_LINK_TOKEN_TTL).isoformat(),
        }
        return JDLinkPresentation(
            jd_id,
            requirement_id,
            claim_id,
            profile_version,
            requirement_text,
            claim_text,
            evidence,
            self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        jd_id: str,
        requirement_id: str,
        claim_id: str,
        profile_version: int,
        link_token: str,
        now: datetime,
    ) -> RequirementClaimMap:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(link_token, expected_keys=_TOKEN_KEYS)
            expiry = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise JDLinkPresentationRejected from exc
        if (
            payload["purpose"] != "JD_CLAIM_LINK_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["jd_id"] != jd_id
            or payload["requirement_id"] != requirement_id
            or payload["claim_id"] != claim_id
            or type(payload["profile_version"]) is not int
            or payload["profile_version"] != profile_version
            or type(payload["display_digest"]) is not str
            or expiry <= now
        ):
            raise JDLinkPresentationRejected
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
            or jd is None
            or profile is None
            or profile.status != "ACTIVE"
            or profile.version != profile_version
        ):
            raise JDLinkPresentationRejected
        _, _, _, digest = _exact_display(
            session,
            account_id=account_id,
            jd_id=jd_id,
            requirement_id=requirement_id,
            claim_id=claim_id,
            profile_version=profile_version,
            now=now,
        )
        if not hmac.compare_digest(payload["display_digest"], digest):
            raise JDLinkPresentationRejected
        try:
            return link_jd_requirement_to_claim(
                session,
                account_id=account_id,
                jd_id=jd_id,
                requirement_id=requirement_id,
                claim_id=claim_id,
                profile_version=profile_version,
                now=now,
            )
        except JDMappingRejected as exc:
            raise JDLinkPresentationRejected from exc


def _exact_display(
    session: Session,
    *,
    account_id: str,
    jd_id: str,
    requirement_id: str,
    claim_id: str,
    profile_version: int,
    now: datetime,
) -> tuple[str, str, tuple[tuple[str, str], ...], str]:
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
            raise JDLinkPresentationRejected
        requirement = next(
            (item for item in mapping.requirements if item.requirement_id == requirement_id), None
        )
        if requirement is None:
            raise JDLinkPresentationRejected
        ensure_profile_archive(
            session,
            account_id=account_id,
            profile_id=jd.profile_id,
            profile_version=profile_version,
            now=now,
        )
        trace = require_eligible_claim_trace(
            session,
            account_id=account_id,
            profile_id=jd.profile_id,
            profile_version=profile_version,
            claim_id=claim_id,
        )
    except (JDMappingRejected, ArchiveUnavailable, ValueError) as exc:
        raise JDLinkPresentationRejected from exc
    evidence = tuple(
        (item.exact_excerpt, item.original_input_ref)
        for item in trace.evidence
        if item.relation_type == "SUPPORTS"
    )
    display = {
        "jd_id": jd_id,
        "jd_version": mapping.jd_version,
        "profile_version": profile_version,
        "requirement_id": requirement_id,
        "requirement_text": requirement.exact_text,
        "claim_id": claim_id,
        "claim_text": trace.claim.exact_text,
        "evidence": evidence,
    }
    digest = hashlib.sha256(
        json.dumps(display, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return requirement.exact_text, trace.claim.exact_text, evidence, digest


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise JDLinkPresentationRejected
    return value.astimezone(UTC)


def _require_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise JDLinkPresentationRejected

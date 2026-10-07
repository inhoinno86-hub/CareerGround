"""Explicit synthetic browser paste of user-selected JD requirement bullets."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.jd_analysis import JDExcerpt, JDUnavailable, record_pasted_jd_analysis
from careerground.domain.profile_archive import ArchiveUnavailable, ensure_profile_archive
from careerground.domain.profiling_draft_extraction import (
    DraftSpanRejected,
    extract_explicit_bullet_spans,
)
from careerground.storage.jd_artifact_models import JDRequirement, JobDescription
from careerground.storage.models import Account, CareerProfile

JD_PASTE_TOKEN_TTL = timedelta(minutes=10)
_PASTE_NAMESPACE = UUID("ca6ecaeb-ef61-479d-8a92-c59257746eb7")
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profile_id",
        "profile_version",
        "idempotency_key",
        "expires_at",
    }
)


class JDPastePresentationRejected(Exception):
    """The owned profile, selected excerpts or explicit browser intent changed."""


@dataclass(frozen=True)
class JDPastePresentation:
    profile_id: str
    profile_version: int
    paste_token: str


class JDPastePresentationService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        now: datetime,
    ) -> JDPastePresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        profile = _active_profile(session, account_id)
        if profile is None:
            raise JDPastePresentationRejected
        payload = {
            "purpose": "PASTED_JD_BULLET_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profile_id": profile.id,
            "profile_version": profile.version,
            "idempotency_key": secrets.token_urlsafe(18),
            "expires_at": (now + JD_PASTE_TOKEN_TTL).isoformat(),
        }
        return JDPastePresentation(profile.id, profile.version, self._tokens.sign(payload))

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        paste_token: str,
        selected_text: str,
        now: datetime,
    ) -> JobDescription:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id)
        try:
            payload = self._tokens.verify(paste_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
            spans = extract_explicit_bullet_spans(selected_text)
        except (BrowserFormTokenRejected, DraftSpanRejected, TypeError, ValueError) as exc:
            raise JDPastePresentationRejected from exc
        if (
            payload["purpose"] != "PASTED_JD_BULLET_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or type(payload["profile_id"]) is not str
            or type(payload["profile_version"]) is not int
            or type(payload["idempotency_key"]) is not str
            or not 16 <= len(payload["idempotency_key"]) <= 128
            or expires_at <= now
        ):
            raise JDPastePresentationRejected
        account = session.scalar(select(Account).where(Account.id == account_id).with_for_update())
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
            or profile.version != payload["profile_version"]
        ):
            raise JDPastePresentationRejected
        try:
            ensure_profile_archive(
                session,
                account_id=account_id,
                profile_id=profile.id,
                profile_version=profile.version,
                now=now,
            )
        except ArchiveUnavailable as exc:
            raise JDPastePresentationRejected from exc
        source_hash = hashlib.sha256(selected_text.encode()).hexdigest()
        exact = tuple(
            (position, selected_text[span.start : span.end], span.start, span.end)
            for position, span in enumerate(spans, start=1)
        )
        jd_id = str(uuid5(_PASTE_NAMESPACE, f"{account_id}:{payload['idempotency_key']}"))
        jd = session.get(JobDescription, jd_id)
        if jd is not None:
            rows = tuple(
                session.scalars(
                    select(JDRequirement)
                    .where(JDRequirement.jd_id == jd.id)
                    .order_by(JDRequirement.ordinal)
                )
            )
            if (
                jd.account_id != account_id
                or jd.profile_id != profile.id
                or jd.status != "ACTIVE"
                or jd.source_kind != "PASTED_TEXT"
                or jd.company_name is not None
                or jd.job_title is not None
                or jd.source_hash != source_hash
                or jd.source_length != len(selected_text)
                or tuple(
                    (row.ordinal, row.exact_text, row.source_start, row.source_end) for row in rows
                )
                != exact
            ):
                raise JDPastePresentationRejected
            return jd
        try:
            return record_pasted_jd_analysis(
                session,
                account_id=account_id,
                profile_id=profile.id,
                source_text=selected_text,
                excerpts=tuple(JDExcerpt(span.start, span.end) for span in spans),
                now=now,
                jd_id=jd_id,
            )
        except (JDUnavailable, ValueError) as exc:
            raise JDPastePresentationRejected from exc


def _active_profile(session: Session, account_id: str) -> CareerProfile | None:
    return session.scalar(
        select(CareerProfile)
        .join(Account, Account.id == CareerProfile.account_id)
        .where(
            CareerProfile.account_id == account_id,
            CareerProfile.status == "ACTIVE",
            Account.status == "ACTIVE",
        )
    )


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise JDPastePresentationRejected
    return value.astimezone(UTC)


def _require_identity(account_id: str, browser_session_id: str) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
    ):
        raise JDPastePresentationRejected

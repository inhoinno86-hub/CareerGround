"""Explicit, session-bound synthetic download of a reviewed R1 resume."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.resume_wording_review import (
    ResumeExport,
    WordingReviewRejected,
    WordingReviewService,
)

RESUME_EXPORT_TOKEN_TTL = timedelta(minutes=5)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "artifact_id",
        "format",
        "content_hash",
        "expires_at",
    }
)


class ResumeExportPresentationRejected(Exception):
    """The reviewed text or exact download intent is unavailable."""


@dataclass(frozen=True)
class ResumeExportPresentation:
    artifact_id: str
    artifact_version: int
    profile_version: int
    format: str
    content_hash: str
    content_bytes: int
    export_token: str


class ResumeExportPresentationService:
    def __init__(self, wording_service: WordingReviewService, signing_secret: bytes) -> None:
        self._wording = wording_service
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        artifact_id: str,
        format: str,
        now: datetime,
    ) -> ResumeExportPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, artifact_id, format)
        try:
            export = self._wording.export_resume(
                session, account_id=account_id, artifact_id=artifact_id, format=format
            )
        except WordingReviewRejected as exc:
            raise ResumeExportPresentationRejected from exc
        payload = {
            "purpose": "R1_RESUME_EXPORT_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "artifact_id": artifact_id,
            "format": format,
            "content_hash": export.content_hash,
            "expires_at": (now + RESUME_EXPORT_TOKEN_TTL).isoformat(),
        }
        return ResumeExportPresentation(
            artifact_id=artifact_id,
            artifact_version=export.artifact_version,
            profile_version=export.profile_version,
            format=format,
            content_hash=export.content_hash,
            content_bytes=len(export.content_text.encode()),
            export_token=self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        artifact_id: str,
        format: str,
        export_token: str,
        now: datetime,
    ) -> ResumeExport:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, artifact_id, format)
        try:
            payload = self._tokens.verify(export_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ResumeExportPresentationRejected from exc
        if (
            payload["purpose"] != "R1_RESUME_EXPORT_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["artifact_id"] != artifact_id
            or payload["format"] != format
            or type(payload["content_hash"]) is not str
            or expires_at <= now
        ):
            raise ResumeExportPresentationRejected
        try:
            export = self._wording.export_resume(
                session, account_id=account_id, artifact_id=artifact_id, format=format
            )
        except WordingReviewRejected as exc:
            raise ResumeExportPresentationRejected from exc
        if export.content_hash != payload["content_hash"]:
            raise ResumeExportPresentationRejected
        return export


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResumeExportPresentationRejected
    return value.astimezone(UTC)


def _require_identity(
    account_id: str, browser_session_id: str, artifact_id: str, format: str
) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(artifact_id, str)
        or not artifact_id
        or format not in {"JSON", "MARKDOWN"}
    ):
        raise ResumeExportPresentationRejected

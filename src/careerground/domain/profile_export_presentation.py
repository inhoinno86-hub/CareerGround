"""Browser intent boundary for a synthetic canonical-only JSON export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.profile_export import (
    CanonicalProfileExport,
    ProfileExportUnavailable,
    export_profile_data,
)

EXPORT_TOKEN_TTL = timedelta(minutes=5)
_TOKEN_KEYS = frozenset(
    {
        "purpose",
        "account_id",
        "browser_session_id",
        "profile_id",
        "profile_version",
        "content_hash",
        "expires_at",
    }
)


class ProfileExportPresentationRejected(Exception):
    """The exact archive or explicit browser download intent is unavailable."""


@dataclass(frozen=True)
class ProfileExportPresentation:
    profile_id: str
    profile_version: int
    content_hash: str
    content_bytes: int
    export_token: str


class ProfileExportPresentationService:
    def __init__(self, signing_secret: bytes) -> None:
        self._tokens = BrowserFormTokenCodec(signing_secret)

    def present(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profile_id: str,
        profile_version: int,
        now: datetime,
    ) -> ProfileExportPresentation:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profile_id, profile_version)
        try:
            export = export_profile_data(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile_version,
            )
        except ProfileExportUnavailable as exc:
            raise ProfileExportPresentationRejected from exc
        payload = {
            "purpose": "CANONICAL_PROFILE_EXPORT_FORM_V1",
            "account_id": account_id,
            "browser_session_id": browser_session_id,
            "profile_id": profile_id,
            "profile_version": profile_version,
            "content_hash": export.content_hash,
            "expires_at": (now + EXPORT_TOKEN_TTL).isoformat(),
        }
        return ProfileExportPresentation(
            profile_id=profile_id,
            profile_version=profile_version,
            content_hash=export.content_hash,
            content_bytes=len(export.content_json.encode()),
            export_token=self._tokens.sign(payload),
        )

    def submit(
        self,
        session: Session,
        *,
        account_id: str,
        browser_session_id: str,
        profile_id: str,
        profile_version: int,
        export_token: str,
        now: datetime,
    ) -> CanonicalProfileExport:
        now = _aware_utc(now)
        _require_identity(account_id, browser_session_id, profile_id, profile_version)
        try:
            payload = self._tokens.verify(export_token, expected_keys=_TOKEN_KEYS)
            expires_at = _aware_utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError) as exc:
            raise ProfileExportPresentationRejected from exc
        if (
            payload["purpose"] != "CANONICAL_PROFILE_EXPORT_FORM_V1"
            or payload["account_id"] != account_id
            or payload["browser_session_id"] != browser_session_id
            or payload["profile_id"] != profile_id
            or type(payload["profile_version"]) is not int
            or payload["profile_version"] != profile_version
            or type(payload["content_hash"]) is not str
            or expires_at <= now
        ):
            raise ProfileExportPresentationRejected
        try:
            export = export_profile_data(
                session,
                account_id=account_id,
                profile_id=profile_id,
                profile_version=profile_version,
            )
        except ProfileExportUnavailable as exc:
            raise ProfileExportPresentationRejected from exc
        if export.content_hash != payload["content_hash"]:
            raise ProfileExportPresentationRejected
        return export


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProfileExportPresentationRejected
    return value.astimezone(UTC)


def _require_identity(
    account_id: str, browser_session_id: str, profile_id: str, profile_version: int
) -> None:
    if (
        not isinstance(account_id, str)
        or not account_id
        or not isinstance(browser_session_id, str)
        or not 16 <= len(browser_session_id) <= 128
        or not isinstance(profile_id, str)
        or not profile_id
        or type(profile_version) is not int
        or profile_version < 0
    ):
        raise ProfileExportPresentationRejected

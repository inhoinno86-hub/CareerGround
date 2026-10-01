"""Explicit browser input and exact confirmation for selected JD/R1 operations."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.jd_link_presentation import (
    JDLinkPresentationRejected,
    JDLinkPresentationService,
)
from careerground.domain.jd_mapping import JDMappingRejected, get_jd_mapping
from careerground.domain.jd_paste_presentation import (
    JDPastePresentationRejected,
    JDPastePresentationService,
)
from careerground.domain.profile_archive import ArchiveUnavailable, read_profile_archive
from careerground.domain.profiling_draft_extraction import (
    DraftSpanRejected,
    extract_explicit_bullet_spans,
)
from careerground.domain.resume_draft_presentation import (
    ResumeDraftPresentationRejected,
    ResumeDraftPresentationService,
)
from careerground.storage.jd_artifact_models import JDRequirement, JobDescription

ARTIFACT_ACTIONS = frozenset({"JD_PASTE", "JD_LINK", "R1_DRAFT"})
ARTIFACT_FIELDS = frozenset({"selected_text", "requirement_id", "claim_id", "claim_ids"})
_CHOICE_KEYS = frozenset(
    {
        "purpose",
        "operation_id",
        "account_id",
        "browser_session_id",
        "action",
        "profile_version",
        "context_hash",
        "inner_token",
        "expires_at",
    }
)
_EXACT_KEYS = _CHOICE_KEYS | {"input_hash"}
_ERRORS = (
    ArchiveUnavailable,
    ResourceNotFound,
    JDMappingRejected,
    JDPastePresentationRejected,
    JDLinkPresentationRejected,
    ResumeDraftPresentationRejected,
    DraftSpanRejected,
)


class ArtifactOperationRejected(Exception):
    """Explicit source, browser intent, exact choices or current eligibility changed."""


@dataclass(frozen=True)
class ArtifactChoicePresentation:
    action: str
    profile_version: int
    context: dict
    choice_token: str


@dataclass(frozen=True)
class ArtifactExactPresentation:
    action: str
    profile_version: int
    context: dict
    fields: dict
    exact: object
    approval_token: str


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ArtifactOperationPresentationService:
    def __init__(self, presentation_secret):
        self.tokens = BrowserFormTokenCodec(presentation_secret)
        self.paste = JDPastePresentationService(presentation_secret)
        self.link = JDLinkPresentationService(presentation_secret)
        self.r1 = ResumeDraftPresentationService(presentation_secret)

    def _context(self, session, row, browser_session_id, now):
        try:
            profile = get_owned_profile(
                session, account_id=row.account_id, profile_id=row.profile_id
            )
            if profile.version != row.profile_version:
                raise ArtifactOperationRejected
            common = {
                "account_id": row.account_id,
                "browser_session_id": browser_session_id,
                "now": now,
            }
            if row.action == "JD_PASTE":
                view = self.paste.present(session, **common)
                if view.profile_id != row.profile_id or view.profile_version != row.profile_version:
                    raise ArtifactOperationRejected
                return {
                    "profile_id": row.profile_id,
                    "profile_version": row.profile_version,
                }, view.paste_token
            read_profile_archive(
                session,
                account_id=row.account_id,
                profile_id=row.profile_id,
                profile_version=row.profile_version,
            )
            mapping = get_jd_mapping(
                session,
                account_id=row.account_id,
                jd_id=row.target_id,
                profile_version=row.profile_version,
            )
            if mapping.stale_relative_to_current_profile or not 1 <= len(mapping.requirements) <= 5:
                raise ArtifactOperationRejected
            if row.action == "JD_LINK":
                candidates = self.link.candidates(
                    session,
                    account_id=row.account_id,
                    jd_id=row.target_id,
                    profile_version=row.profile_version,
                )
                inner = ""
            elif row.action == "R1_DRAFT":
                view = self.r1.present(
                    session, jd_id=row.target_id, profile_version=row.profile_version, **common
                )
                candidates, inner = view.candidates, view.draft_token
            else:
                raise ArtifactOperationRejected
            if not 1 <= len(candidates) <= 20:
                raise ArtifactOperationRejected
            return {
                "jd_id": row.target_id,
                "jd_version": mapping.jd_version,
                "profile_version": row.profile_version,
                "requirements": [asdict(item) for item in mapping.requirements],
                "candidates": [asdict(item) for item in candidates],
            }, inner
        except _ERRORS:
            raise ArtifactOperationRejected from None

    def _payload(self, row, browser_session_id, purpose, context, inner):
        return {
            "purpose": purpose,
            "operation_id": row.id,
            "account_id": row.account_id,
            "browser_session_id": browser_session_id,
            "action": row.action,
            "profile_version": row.profile_version,
            "context_hash": _hash(context),
            "inner_token": inner,
            "expires_at": _utc(row.expires_at).isoformat(),
        }

    def _verify(self, token, keys, row, browser_session_id, now, purpose):
        try:
            payload = self.tokens.verify(token, expected_keys=keys)
            expiry = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError):
            raise ArtifactOperationRejected from None
        if (
            (
                payload["purpose"],
                payload["operation_id"],
                payload["account_id"],
                payload["browser_session_id"],
                payload["action"],
                payload["profile_version"],
            )
            != (
                purpose,
                row.id,
                row.account_id,
                browser_session_id,
                row.action,
                row.profile_version,
            )
            or expiry <= now
            or expiry != _utc(row.expires_at)
        ):
            raise ArtifactOperationRejected
        return payload

    def present(self, session, *, row, browser_session_id, now):
        context, inner = self._context(session, row, browser_session_id, now)
        payload = self._payload(row, browser_session_id, "ARTIFACT_CHOICE_V1", context, inner)
        return ArtifactChoicePresentation(
            row.action, row.profile_version, context, self.tokens.sign(payload)
        )

    def _validate(self, row, fields, context):
        if type(fields) is not dict:
            raise ArtifactOperationRejected
        if row.action == "JD_PASTE":
            if (
                set(fields) != {"selected_text"}
                or type(fields["selected_text"]) is not str
                or len(fields["selected_text"]) > 6000
            ):
                raise ArtifactOperationRejected
            try:
                spans = extract_explicit_bullet_spans(fields["selected_text"])
            except DraftSpanRejected:
                raise ArtifactOperationRejected from None
            return tuple(fields["selected_text"][span.start : span.end] for span in spans)
        if row.action == "JD_LINK":
            if (
                set(fields) != {"requirement_id", "claim_id"}
                or any(type(value) is not str for value in fields.values())
                or fields["requirement_id"]
                not in {item["requirement_id"] for item in context["requirements"]}
                or fields["claim_id"] not in {item["claim_id"] for item in context["candidates"]}
            ):
                raise ArtifactOperationRejected
            return None
        if (
            set(fields) != {"claim_ids"}
            or type(fields["claim_ids"]) is not list
            or not 1 <= len(fields["claim_ids"]) <= 5
            or any(type(value) is not str for value in fields["claim_ids"])
            or len(set(fields["claim_ids"])) != len(fields["claim_ids"])
            or not set(fields["claim_ids"]).issubset(
                {item["claim_id"] for item in context["candidates"]}
            )
        ):
            raise ArtifactOperationRejected
        candidates = {item["claim_id"]: item for item in context["candidates"]}
        return tuple(candidates[identifier] for identifier in fields["claim_ids"])

    def prepare(self, session, *, row, browser_session_id, choice_token, fields, now):
        payload = self._verify(
            choice_token, _CHOICE_KEYS, row, browser_session_id, now, "ARTIFACT_CHOICE_V1"
        )
        context, _ = self._context(session, row, browser_session_id, now)
        if not hmac.compare_digest(payload["context_hash"], _hash(context)):
            raise ArtifactOperationRejected
        exact = self._validate(row, fields, context)
        inner = payload["inner_token"]
        if row.action == "JD_LINK":
            try:
                exact = self.link.present(
                    session,
                    account_id=row.account_id,
                    browser_session_id=browser_session_id,
                    jd_id=row.target_id,
                    profile_version=row.profile_version,
                    now=now,
                    **fields,
                )
            except JDLinkPresentationRejected:
                raise ArtifactOperationRejected from None
            inner = exact.link_token
        second = {
            **self._payload(row, browser_session_id, "ARTIFACT_EXACT_V1", context, inner),
            "input_hash": _hash(fields),
        }
        return ArtifactExactPresentation(
            row.action, row.profile_version, context, dict(fields), exact, self.tokens.sign(second)
        )

    def submit(self, session, *, row, browser_session_id, approval_token, fields, now):
        payload = self._verify(
            approval_token, _EXACT_KEYS, row, browser_session_id, now, "ARTIFACT_EXACT_V1"
        )
        context, _ = self._context(session, row, browser_session_id, now)
        if not hmac.compare_digest(
            payload["context_hash"], _hash(context)
        ) or not hmac.compare_digest(payload["input_hash"], _hash(fields)):
            raise ArtifactOperationRejected
        self._validate(row, fields, context)
        common = {
            "account_id": row.account_id,
            "browser_session_id": browser_session_id,
            "now": now,
        }
        try:
            if row.action == "JD_PASTE":
                jd = self.paste.submit(
                    session,
                    paste_token=payload["inner_token"],
                    selected_text=fields["selected_text"],
                    **common,
                )
                return {
                    "jd_id": jd.id,
                    "jd_version": jd.jd_version,
                    "profile_id": row.profile_id,
                    "profile_version": row.profile_version,
                    "requirement_count": session.scalar(
                        select(func.count())
                        .select_from(JDRequirement)
                        .where(JDRequirement.jd_id == jd.id)
                    ),
                    "analysis_kind": "SELECTED_EXCERPTS_ONLY",
                }
            if row.action == "JD_LINK":
                link = self.link.submit(
                    session,
                    jd_id=row.target_id,
                    profile_version=row.profile_version,
                    link_token=payload["inner_token"],
                    **common,
                    **fields,
                )
                return {
                    "link_id": link.id,
                    "jd_id": row.target_id,
                    "profile_version": row.profile_version,
                    "requirement_id": fields["requirement_id"],
                    "claim_id": fields["claim_id"],
                    "mapping_kind": "POTENTIAL",
                }
            artifact = self.r1.submit(
                session,
                jd_id=row.target_id,
                profile_version=row.profile_version,
                claim_ids=tuple(fields["claim_ids"]),
                draft_token=payload["inner_token"],
                **common,
            )
            return {
                "artifact_id": artifact.id,
                "artifact_version": artifact.artifact_version,
                "profile_version": row.profile_version,
                "wording_level": "R1",
                "review_required": True,
            }
        except _ERRORS:
            raise ArtifactOperationRejected from None


def owned_jd_profile_id(session, account_id, jd_id):
    value = session.scalar(
        select(JobDescription.profile_id).where(
            JobDescription.id == jd_id,
            JobDescription.account_id == account_id,
            JobDescription.status == "ACTIVE",
        )
    )
    if value is None:
        raise ArtifactOperationRejected
    return value

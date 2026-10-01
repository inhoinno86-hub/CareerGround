"""Two browser stages for exact conflict/boundary choices, without pending source copies."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.boundary_review import (
    BoundaryReviewRejected,
    BoundaryReviewService,
    VerifiedBoundaryApproval,
)
from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.conflict_review import (
    ConflictReviewRejected,
    ConflictReviewService,
    VerifiedConflictApproval,
)
from careerground.domain.graph_projection import GraphUnavailable, get_claim_evidence
from careerground.domain.profile_archive import (
    ArchiveUnavailable,
    ensure_profile_archive,
    read_profile_archive,
)
from careerground.storage.graph_models import Claim

POLICY_ACTIONS = frozenset({"CONFLICT_REVIEW", "BOUNDARY_REVIEW"})
CONFLICT_FIELDS = frozenset({"conflict_link_id", "resolution", "explanation"})
BOUNDARY_FIELDS = frozenset(
    {
        "evidence_id",
        "action",
        "constraint_id",
        "proposed_boundary_text",
        "allowed_wording",
        "remaining_prohibited_expansion",
    }
)
_CONTEXT_KEYS = frozenset(
    {
        "purpose",
        "operation_id",
        "account_id",
        "browser_session_id",
        "action",
        "profile_version",
        "context_hash",
        "expires_at",
    }
)
_EXACT_KEYS = _CONTEXT_KEYS | {"input_hash", "review_digest"}


class PolicyPresentationRejected(Exception):
    """No submitted value or database detail belongs in the public failure."""


@dataclass(frozen=True)
class PolicyContext:
    profile_id: str
    profile_version: int
    claim_id: str
    claim_text: str
    assessment: tuple[str, str, str]
    evidence: tuple[tuple[str, str, str, str, str], ...]
    boundaries: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PolicyChoicePresentation:
    context: PolicyContext
    action: str
    profile_version: int
    choice_token: str


@dataclass(frozen=True)
class PolicyExactPresentation:
    context: PolicyContext
    action: str
    profile_version: int
    review: object
    fields: dict[str, str]
    approval_token: str


def _hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PolicyReviewPresentationService:
    def __init__(self, review_secret, presentation_secret):
        self.tokens = BrowserFormTokenCodec(presentation_secret)
        self.conflict = ConflictReviewService(
            hmac.digest(review_secret, b"browser-conflict-review-v1", "sha256")
        )
        self.boundary = BoundaryReviewService(
            hmac.digest(review_secret, b"browser-boundary-review-v1", "sha256")
        )

    def _context(self, session, row) -> PolicyContext:
        try:
            profile = get_owned_profile(
                session, account_id=row.account_id, profile_id=row.profile_id
            )
            if profile.version != row.profile_version:
                raise PolicyPresentationRejected
            snapshot = read_profile_archive(
                session,
                account_id=row.account_id,
                profile_id=row.profile_id,
                profile_version=row.profile_version,
            )
            # The read above requires an existing archive; this recheck cannot
            # silently create a missing archive while rendering a GET.
            ensure_profile_archive(
                session,
                account_id=row.account_id,
                profile_id=row.profile_id,
                profile_version=row.profile_version,
                now=_utc(row.created_at),
            )
            trace = get_claim_evidence(
                session,
                account_id=row.account_id,
                profile_id=row.profile_id,
                profile_version=row.profile_version,
                claim_id=row.target_id,
            )
        except (ResourceNotFound, ArchiveUnavailable, GraphUnavailable):
            raise PolicyPresentationRejected from None
        items = {item["id"]: item for item in snapshot["sections"]["evidence_items"]}
        refs = {item.evidence_id: item.original_input_ref for item in trace.evidence}
        evidence = tuple(
            sorted(
                (
                    link["id"],
                    link["evidence_id"],
                    link["relation_type"],
                    items[link["evidence_id"]]["content_text"],
                    refs[link["evidence_id"]],
                )
                for link in snapshot["sections"]["evidence_claim_links"]
                if link["claim_id"] == row.target_id
            )
        )
        boundaries = tuple(
            sorted(
                (item["id"], item["exact_text"])
                for item in snapshot["sections"]["claim_constraints"]
                if item["scope_key"] == trace.claim.scope_key
                and item.get("status", "ACTIVE") == "ACTIVE"
            )
        )
        if not evidence or len(evidence) > 5 or len(boundaries) > 5:
            raise PolicyPresentationRejected
        if row.action == "CONFLICT_REVIEW" and not any(
            item[2] == "CONTRADICTS" for item in evidence
        ):
            raise PolicyPresentationRejected
        return PolicyContext(
            row.profile_id,
            row.profile_version,
            row.target_id,
            trace.claim.exact_text,
            (
                trace.claim.knowledge_status,
                trace.claim.consistency_status,
                trace.claim.usage_policy,
            ),
            evidence,
            boundaries,
        )

    def present(self, session, *, row, browser_session_id, now):
        if row.action not in POLICY_ACTIONS or _utc(row.expires_at) <= now:
            raise PolicyPresentationRejected
        context = self._context(session, row)
        payload = self._payload(row, browser_session_id, "POLICY_CHOICE_V1", context)
        return PolicyChoicePresentation(
            context, row.action, row.profile_version, self.tokens.sign(payload)
        )

    def _payload(self, row, browser_session_id, purpose, context):
        return {
            "purpose": purpose,
            "operation_id": row.id,
            "account_id": row.account_id,
            "browser_session_id": browser_session_id,
            "action": row.action,
            "profile_version": row.profile_version,
            "context_hash": _hash(asdict(context)),
            "expires_at": _utc(row.expires_at).isoformat(),
        }

    def _verify(self, token, keys, row, browser_session_id, now, purpose):
        try:
            payload = self.tokens.verify(token, expected_keys=keys)
            expiry = _utc(datetime.fromisoformat(payload["expires_at"]))
        except (BrowserFormTokenRejected, TypeError, ValueError):
            raise PolicyPresentationRejected from None
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
            raise PolicyPresentationRejected
        return payload

    def _build(self, session, row, fields, now, context):
        expected = CONFLICT_FIELDS if row.action == "CONFLICT_REVIEW" else BOUNDARY_FIELDS
        if (
            type(fields) is not dict
            or set(fields) != expected
            or any(type(value) is not str or len(value) > 2000 for value in fields.values())
        ):
            raise PolicyPresentationRejected
        common = {
            "account_id": row.account_id,
            "profile_id": row.profile_id,
            "claim_id": row.target_id,
            "review_id": row.id,
            "expires_at": _utc(row.expires_at),
            "now": now,
        }
        try:
            if row.action == "CONFLICT_REVIEW":
                if fields["conflict_link_id"] not in {
                    item[0] for item in context.evidence if item[2] == "CONTRADICTS"
                }:
                    raise PolicyPresentationRejected
                return self.conflict.prepare(session, **common, **fields)
            if fields["evidence_id"] not in {item[1] for item in context.evidence}:
                raise PolicyPresentationRejected
            if fields["constraint_id"] and fields["constraint_id"] not in {
                item[0] for item in context.boundaries
            }:
                raise PolicyPresentationRejected
            values = {
                **fields,
                "constraint_id": fields["constraint_id"] or None,
                "proposed_boundary_text": fields["proposed_boundary_text"] or None,
            }
            return self.boundary.prepare(session, **common, **values)
        except (ConflictReviewRejected, BoundaryReviewRejected):
            raise PolicyPresentationRejected from None

    def prepare(self, session, *, row, browser_session_id, choice_token, fields, now):
        payload = self._verify(
            choice_token, _CONTEXT_KEYS, row, browser_session_id, now, "POLICY_CHOICE_V1"
        )
        context = self._context(session, row)
        if not hmac.compare_digest(payload["context_hash"], _hash(asdict(context))):
            raise PolicyPresentationRejected
        review = self._build(session, row, fields, now, context)
        exact = {
            **self._payload(row, browser_session_id, "POLICY_EXACT_V1", context),
            "input_hash": _hash(fields),
            "review_digest": review.review_digest,
        }
        return PolicyExactPresentation(
            context, row.action, row.profile_version, review, dict(fields), self.tokens.sign(exact)
        )

    def submit(self, session, *, row, browser_session_id, approval_token, fields, now):
        payload = self._verify(
            approval_token, _EXACT_KEYS, row, browser_session_id, now, "POLICY_EXACT_V1"
        )
        context = self._context(session, row)
        if not hmac.compare_digest(
            payload["context_hash"], _hash(asdict(context))
        ) or not hmac.compare_digest(payload["input_hash"], _hash(fields)):
            raise PolicyPresentationRejected
        view = self._build(session, row, fields, now, context)
        if not hmac.compare_digest(payload["review_digest"], view.review_digest):
            raise PolicyPresentationRejected
        try:
            if row.action == "CONFLICT_REVIEW":
                approval = VerifiedConflictApproval(
                    row.account_id, row.id, view.resolution, view.review_digest, view.expires_at
                )
                review = self.conflict.submit(session, view=view, approval=approval, now=now)
            else:
                approval = VerifiedBoundaryApproval(
                    row.account_id, row.id, view.action, view.review_digest, view.expires_at
                )
                review = self.boundary.submit(session, view=view, approval=approval, now=now)
        except (ConflictReviewRejected, BoundaryReviewRejected):
            raise PolicyPresentationRejected from None
        return {
            "review_id": review.id,
            "claim_id": row.target_id,
            "profile_id": row.profile_id,
            "version_after": review.profile_version,
        }


def owned_claim_profile_id(session, account_id, claim_id):
    profile_id = session.scalar(
        select(Claim.profile_id).where(
            Claim.id == claim_id, Claim.account_id == account_id, Claim.status == "ACTIVE"
        )
    )
    if profile_id is None:
        raise PolicyPresentationRejected
    return profile_id

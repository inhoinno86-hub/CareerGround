"""Local synthetic product-MCP foundation; deliberately has no ASGI entrypoint.

This factory uses a distinct product scope and database-backed account gate. It
must not be pointed at real user data before provider and erasure gates pass.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.types import ASGIApp

from careerground.domain.authorization import (
    AuthenticationRequired,
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewIdempotencyConflict,
    ReviewStale,
    ReviewUnavailable,
)
from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.jd_analysis import JDUnavailable, get_jd_analysis
from careerground.domain.jd_mapping import JDMappingRejected, get_jd_mapping
from careerground.domain.profiling_protocol_workspace import get_protocol_question_plan
from careerground.domain.profiling_workspace import (
    InputKind,
    ProfilingExpired,
    ProfilingIdempotencyConflict,
    ProfilingPaused,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    append_explicit_profiling_input,
    pause_profiling_session,
    start_profiling_session,
)
from careerground.domain.profiling_workspace import (
    get_profiling_session as read_profiling_session,
)
from careerground.domain.resume_draft import ResumeDraftUnavailable, get_resume_trace
from careerground.mcp.account_access import ActiveAccountTokenVerifier
from careerground.mcp.oauth_resource import (
    JwtTokenVerifier,
    LocalMetadataPathAlias,
    McpOAuthSettings,
    OAuthToolDeclarations,
)
from careerground.storage.graph_models import Claim

PROFILE_READ_SCOPE = "career.profile.read"
PROFILE_WRITE_SCOPE = "career.profile.write"
ARTIFACT_READ_SCOPE = "career.artifact.read"

_TOOL_ARGUMENTS = {
    "get_account_profile": frozenset(),
    "get_owned_profile_metadata": frozenset({"profile_id"}),
    "get_profiling_session": frozenset({"profiling_session_id"}),
    "get_career_profile": frozenset({"profile_id", "profile_version"}),
    "get_claim_evidence": frozenset({"claim_id", "profile_version"}),
    "get_claim_review": frozenset({"review_batch_id"}),
    "get_jd_analysis": frozenset({"jd_id", "profile_version"}),
    "get_resume_trace": frozenset({"artifact_id"}),
    "start_profiling": frozenset({"profile_id", "goal", "policy_version", "idempotency_key"}),
    "add_profiling_input": frozenset(
        {
            "profiling_session_id",
            "base_profile_version",
            "content",
            "content_kind",
            "idempotency_key",
        }
    ),
    "pause_profiling": frozenset({"profiling_session_id"}),
    "prepare_claim_review": frozenset(
        {"profiling_session_id", "experience_scope_id", "base_profile_version", "idempotency_key"}
    ),
}


class StrictProductMCPServer(MCPServer):
    """Reject surplus or missing tool fields before the SDK discards them."""

    async def call_tool(self, name: str, arguments: dict[str, Any], context=None):
        allowed = _TOOL_ARGUMENTS.get(name)
        if allowed is None or set(arguments) != allowed:
            raise ToolError("Unsupported tool arguments")
        return await super().call_tool(name, arguments, context)


class AccountProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)


class ProfileMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    profile_id: str | None = Field(default=None, min_length=1)
    version: int | None = Field(default=None, ge=0)


class ProfilingSessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    session_id: str | None = None
    status: str | None = None
    base_profile_version: int | None = Field(default=None, ge=0)
    current_profile_version: int | None = Field(default=None, ge=0)
    last_activity_at: datetime | None = None
    retention_expires_at: datetime | None = None


class ProfilingStartOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    base_profile_version: int | None = None
    protocol_state: str | None = None
    retention_expires_at: datetime | None = None
    collection_scope: str | None = None


class ProfilingInputOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    input_id: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    protocol_cycle: int | None = None
    retention_expires_at: datetime | None = None


class ProfilingPauseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    retention_expires_at: datetime | None = None


class ClaimSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: str
    exact_text: str
    scope_key: str
    knowledge_status: str
    consistency_status: str
    usage_policy: str


class CareerProfileOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    profile_id: str | None = None
    profile_version: int | None = None
    claims: list[ClaimSummaryOutput] = Field(default_factory=list)
    constraint_count: int | None = None


class EvidenceExcerptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    exact_excerpt: str
    source_id: str
    original_input_ref: str
    source_content_hash: str
    relation_type: str
    source_availability: str


class ClaimConstraintOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_type: str
    exact_text: str


class ClaimEvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    claim: ClaimSummaryOutput | None = None
    profile_version: int | None = None
    evidence: list[EvidenceExcerptOutput] = Field(default_factory=list)
    reviewed: bool | None = None
    constraints: list[ClaimConstraintOutput] = Field(default_factory=list)


class ClaimReviewItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    position: int
    exact_text: str
    claim_type: str
    scope_key: str
    source_input_id: str
    decision: str | None = None


class ClaimReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    review_batch_id: str | None = None
    profile_id: str | None = None
    base_profile_version: int | None = None
    current_profile_version: int | None = None
    base_version_compatible: bool | None = None
    review_digest: str | None = None
    expires_at: datetime | None = None
    scope_key: str | None = None
    items: list[ClaimReviewItemOutput] = Field(default_factory=list)


class ClaimReviewPrepareOutput(ClaimReviewOutput):
    ok: bool
    error_code: str | None = None


class JDRequirementOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    exact_text: str
    source_start: int
    source_end: int
    requirement_id: str
    linked_claim_ids: list[str] = Field(default_factory=list)
    gap_status: str


class JDAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    jd_id: str | None = None
    jd_version: int | None = None
    profile_version: int | None = None
    stale_relative_to_current_profile: bool | None = None
    source_hash: str | None = None
    source_length: int | None = None
    requirements: list[JDRequirementOutput] = Field(default_factory=list)


class ResumeUnitTraceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str
    exact_text: str
    claim_id: str
    evidence_ids: list[str]
    evidence_excerpts: list[str]
    original_input_refs: list[str]
    wording_level: str
    review_status: str


class ResumeTraceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    artifact_id: str | None = None
    artifact_version: int | None = None
    profile_version: int | None = None
    jd_id: str | None = None
    stale_relative_to_current_profile: bool | None = None
    units: list[ResumeUnitTraceOutput] = Field(default_factory=list)


def build_product_foundation_app(
    settings: McpOAuthSettings,
    *,
    session_factory: Callable[[], Session],
    review_signing_secret: bytes,
    signing_key: Callable[[str], object] | None = None,
) -> ASGIApp:
    """Build isolated product auth/ownership checks for synthetic local tests."""

    review_preparation = ClaimReviewPreparation(review_signing_secret)
    verifier = ActiveAccountTokenVerifier(
        JwtTokenVerifier(
            settings,
            required_scope=frozenset(
                {PROFILE_READ_SCOPE, PROFILE_WRITE_SCOPE, ARTIFACT_READ_SCOPE}
            ),
            signing_key=signing_key,
        ),
        issuer=settings.issuer,
        session_factory=session_factory,
    )
    server = StrictProductMCPServer(
        name="careerground-product-foundation",
        version="0.1.0",
        instructions="Synthetic-only CareerGround foundation with scoped profiling input and read tools.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[],
            validate_token_resource=True,
        ),
    )

    def current_account_id(session: Session, required_scope: str = PROFILE_READ_SCOPE) -> str:
        access = get_access_token()
        if access is None or not access.subject or required_scope not in access.scopes:
            raise PermissionError("Authentication required")
        try:
            return resolve_account_id(session, VerifiedIdentity(settings.issuer, access.subject))
        except AuthenticationRequired as exc:
            raise PermissionError("Authentication required") from exc

    @server.tool(
        name="get_account_profile",
        title="Get linked CareerGround account",
        description="Return only a stable, opaque account ID for the authenticated connection.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta={"openai/profile": True},
        structured_output=True,
    )
    def get_account_profile() -> AccountProfile:
        with session_factory() as session:
            return AccountProfile(id=current_account_id(session))

    @server.tool(
        name="get_owned_profile_metadata",
        title="Get owned profile metadata",
        description="Return only ID and version of an owned profile, or found=false.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_owned_profile_metadata(profile_id: str) -> ProfileMetadata:
        with session_factory() as session:
            try:
                account_id = current_account_id(session)
                profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
            except ResourceNotFound:
                return ProfileMetadata(found=False)
            return ProfileMetadata(found=True, profile_id=profile.id, version=profile.version)

    @server.tool(
        name="get_profiling_session",
        title="Get owned profiling session metadata",
        description="Return only status, versions, and retention times for an owned session.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_profiling_session_tool(profiling_session_id: str) -> ProfilingSessionMetadata:
        with session_factory() as session:
            try:
                account_id = current_account_id(session)
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
            except (ProfilingUnavailable, ProfilingExpired):
                return ProfilingSessionMetadata(found=False)
            return ProfilingSessionMetadata(
                found=True,
                session_id=view.id,
                status=view.status,
                base_profile_version=view.base_profile_version,
                current_profile_version=view.current_profile_version,
                last_activity_at=view.last_activity_at,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="start_profiling",
        title="Start explicit CareerGround profiling",
        description="Create one temporary synthetic profiling session for an explicitly requested task.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def start_profiling_tool(
        profile_id: str, goal: str, policy_version: str, idempotency_key: str
    ) -> ProfilingStartOutput:
        if goal != "ADD_EXPERIENCE" or policy_version != "product-policy-v0.1":
            return ProfilingStartOutput(ok=False, error_code="VALIDATION_FAILED")
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
                work = start_profiling_session(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    base_profile_version=profile.version,
                    now=datetime.now(UTC),
                    idempotency_key=idempotency_key,
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                plan = get_protocol_question_plan(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except (ResourceNotFound, ProfilingUnavailable):
                return ProfilingStartOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingStartOutput(ok=False, error_code="SESSION_EXPIRED")
            except ProfilingVersionConflict:
                return ProfilingStartOutput(ok=False, error_code="VERSION_CONFLICT")
            except ProfilingIdempotencyConflict:
                return ProfilingStartOutput(ok=False, error_code="IDEMPOTENCY_CONFLICT")
            except ProfilingValidationError:
                return ProfilingStartOutput(ok=False, error_code="VALIDATION_FAILED")
            return ProfilingStartOutput(
                ok=True,
                profiling_session_id=view.id,
                session_status=view.status,
                base_profile_version=view.base_profile_version,
                protocol_state=plan.state.value,
                retention_expires_at=view.retention_expires_at,
                collection_scope="Only content explicitly sent to this CareerGround session",
            )

    @server.tool(
        name="add_profiling_input",
        title="Add explicit CareerGround task input",
        description="Store one bounded statement or correction in an owned temporary session.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def add_profiling_input_tool(
        profiling_session_id: str,
        base_profile_version: int,
        content: str,
        content_kind: str,
        idempotency_key: str,
    ) -> ProfilingInputOutput:
        if (
            type(base_profile_version) is not int
            or base_profile_version < 0
            or content_kind not in (InputKind.USER_STATEMENT, InputKind.CORRECTION)
        ):
            return ProfilingInputOutput(ok=False, error_code="VALIDATION_FAILED")
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                item = append_explicit_profiling_input(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    base_profile_version=base_profile_version,
                    content=content,
                    content_kind=InputKind(content_kind),
                    idempotency_key=idempotency_key,
                    now=datetime.now(UTC),
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except ProfilingUnavailable:
                return ProfilingInputOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingInputOutput(ok=False, error_code="SESSION_EXPIRED")
            except ProfilingPaused:
                return ProfilingInputOutput(ok=False, error_code="SESSION_PAUSED")
            except ProfilingVersionConflict:
                return ProfilingInputOutput(ok=False, error_code="VERSION_CONFLICT")
            except ProfilingIdempotencyConflict:
                return ProfilingInputOutput(ok=False, error_code="IDEMPOTENCY_CONFLICT")
            except ProfilingValidationError:
                return ProfilingInputOutput(ok=False, error_code="VALIDATION_FAILED")
            return ProfilingInputOutput(
                ok=True,
                input_id=item.id,
                profiling_session_id=view.id,
                session_status=view.status,
                protocol_cycle=view.protocol_cycle,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="pause_profiling",
        title="Pause explicit CareerGround profiling",
        description="Pause one owned temporary session without extending its retention.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def pause_profiling_tool(profiling_session_id: str) -> ProfilingPauseOutput:
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                work = pause_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except ProfilingUnavailable:
                return ProfilingPauseOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingPauseOutput(ok=False, error_code="SESSION_EXPIRED")
            return ProfilingPauseOutput(
                ok=True,
                profiling_session_id=view.id,
                session_status=view.status,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="get_career_profile",
        title="Get exact career profile version",
        description="Return canonical Claim summaries only from an owned, stored profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_career_profile_tool(profile_id: str, profile_version: int) -> CareerProfileOutput:
        if isinstance(profile_version, bool) or profile_version < 0:
            return CareerProfileOutput(found=False)
        with session_factory() as session:
            account_id = current_account_id(session)
            try:
                view = get_career_profile(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                )
            except GraphUnavailable:
                return CareerProfileOutput(found=False)
            return CareerProfileOutput(
                found=True,
                profile_id=view.profile_id,
                profile_version=view.profile_version,
                claims=[ClaimSummaryOutput.model_validate(asdict(claim)) for claim in view.claims],
                constraint_count=view.constraint_count,
            )

    @server.tool(
        name="get_claim_evidence",
        title="Get exact Claim evidence",
        description="Return selected evidence excerpts and constraints from one owned, stored profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_claim_evidence_tool(claim_id: str, profile_version: int) -> ClaimEvidenceOutput:
        if isinstance(profile_version, bool) or profile_version < 0:
            return ClaimEvidenceOutput(found=False)
        with session_factory() as session:
            account_id = current_account_id(session)
            profile_id = session.scalar(
                select(Claim.profile_id).where(
                    Claim.id == claim_id,
                    Claim.account_id == account_id,
                )
            )
            if profile_id is None:
                return ClaimEvidenceOutput(found=False)
            try:
                view = get_claim_evidence(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                    claim_id=claim_id,
                )
            except GraphUnavailable:
                return ClaimEvidenceOutput(found=False)
            return ClaimEvidenceOutput(
                found=True,
                claim=ClaimSummaryOutput.model_validate(asdict(view.claim)),
                profile_version=view.profile_version,
                evidence=[
                    EvidenceExcerptOutput.model_validate(asdict(item)) for item in view.evidence
                ],
                reviewed=view.reviewed,
                constraints=[
                    ClaimConstraintOutput(constraint_type=kind, exact_text=text)
                    for kind, text in view.constraints
                ],
            )

    @server.tool(
        name="get_claim_review",
        title="Get exact pending Claim review",
        description="Return an owned, unexpired review snapshot without renewing its digest or expiry.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_claim_review_tool(review_batch_id: str) -> ClaimReviewOutput:
        with session_factory() as session:
            account_id = current_account_id(session)
            try:
                batch, items = review_preparation.get(
                    session,
                    account_id=account_id,
                    batch_id=review_batch_id,
                    now=datetime.now(UTC),
                )
                profile = get_owned_profile(
                    session, account_id=account_id, profile_id=batch.profile_id
                )
            except (ReviewUnavailable, ReviewStale, ResourceNotFound):
                return ClaimReviewOutput(found=False)
            return ClaimReviewOutput(
                found=True,
                review_batch_id=batch.id,
                profile_id=batch.profile_id,
                base_profile_version=batch.base_profile_version,
                current_profile_version=profile.version,
                base_version_compatible=profile.version == batch.base_profile_version,
                review_digest=batch.review_digest,
                expires_at=batch.expires_at,
                scope_key=batch.scope_key,
                items=[
                    ClaimReviewItemOutput(
                        review_item_id=item.id,
                        position=item.position,
                        exact_text=item.exact_text,
                        claim_type=item.claim_type,
                        scope_key=item.scope_key,
                        source_input_id=item.source_input_id,
                        decision=item.decision,
                    )
                    for item in items
                ],
            )

    @server.tool(
        name="prepare_claim_review",
        title="Prepare an exact temporary Claim review",
        description="Snapshot one owned experience scope of up to five existing drafts; never approves Claims.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def prepare_claim_review_tool(
        profiling_session_id: str,
        experience_scope_id: str,
        base_profile_version: int,
        idempotency_key: str,
    ) -> ClaimReviewPrepareOutput:
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                batch = review_preparation.prepare_for_scope(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    scope_key=experience_scope_id,
                    base_profile_version=base_profile_version,
                    idempotency_key=idempotency_key,
                    now=datetime.now(UTC),
                )
                session.flush()
                batch, items = review_preparation.get(
                    session, account_id=account_id, batch_id=batch.id, now=datetime.now(UTC)
                )
                profile = get_owned_profile(
                    session, account_id=account_id, profile_id=batch.profile_id
                )
                session.commit()
            except (ReviewUnavailable, ResourceNotFound):
                return ClaimReviewPrepareOutput(ok=False, found=False, error_code="NOT_FOUND")
            except ReviewStale:
                return ClaimReviewPrepareOutput(ok=False, found=False, error_code="REVIEW_STALE")
            except ReviewIdempotencyConflict:
                return ClaimReviewPrepareOutput(
                    ok=False, found=False, error_code="IDEMPOTENCY_CONFLICT"
                )
            except ValueError:
                return ClaimReviewPrepareOutput(
                    ok=False, found=False, error_code="VALIDATION_FAILED"
                )
            return ClaimReviewPrepareOutput(
                ok=True,
                found=True,
                review_batch_id=batch.id,
                profile_id=batch.profile_id,
                base_profile_version=batch.base_profile_version,
                current_profile_version=profile.version,
                base_version_compatible=profile.version == batch.base_profile_version,
                review_digest=batch.review_digest,
                expires_at=batch.expires_at,
                scope_key=batch.scope_key,
                items=[
                    ClaimReviewItemOutput(
                        review_item_id=item.id,
                        position=item.position,
                        exact_text=item.exact_text,
                        claim_type=item.claim_type,
                        scope_key=item.scope_key,
                        source_input_id=item.source_input_id,
                        decision=item.decision,
                    )
                    for item in items
                ],
            )

    @server.tool(
        name="get_jd_analysis",
        title="Get owned JD excerpts",
        description="Return stored JD excerpts and recorded Claim links at one exact profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_jd_analysis_tool(jd_id: str, profile_version: int) -> JDAnalysisOutput:
        if type(profile_version) is not int or profile_version < 0:
            return JDAnalysisOutput(found=False)
        with session_factory() as session:
            account_id = current_account_id(session, ARTIFACT_READ_SCOPE)
            try:
                view = get_jd_analysis(session, account_id=account_id, jd_id=jd_id)
                mapping = get_jd_mapping(
                    session,
                    account_id=account_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                )
            except (JDUnavailable, JDMappingRejected):
                return JDAnalysisOutput(found=False)
            if len(view.requirements) != len(mapping.requirements) or any(
                excerpt[1] != links.exact_text
                for excerpt, links in zip(view.requirements, mapping.requirements, strict=True)
            ):
                return JDAnalysisOutput(found=False)
            return JDAnalysisOutput(
                found=True,
                jd_id=view.jd_id,
                jd_version=view.jd_version,
                profile_version=mapping.profile_version,
                stale_relative_to_current_profile=mapping.stale_relative_to_current_profile,
                source_hash=view.source_hash,
                source_length=view.source_length,
                requirements=[
                    JDRequirementOutput(
                        ordinal=ordinal,
                        exact_text=exact_text,
                        source_start=start,
                        source_end=end,
                        requirement_id=links.requirement_id,
                        linked_claim_ids=list(links.linked_claim_ids),
                        gap_status=links.gap_status,
                    )
                    for (ordinal, exact_text, start, end), links in zip(
                        view.requirements, mapping.requirements, strict=True
                    )
                ],
            )

    @server.tool(
        name="get_resume_trace",
        title="Get owned R1 resume draft trace",
        description="Return exact R1 draft units and their eligible Claim and selected Evidence references.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_resume_trace_tool(artifact_id: str) -> ResumeTraceOutput:
        with session_factory() as session:
            account_id = current_account_id(session, ARTIFACT_READ_SCOPE)
            try:
                view = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
            except ResumeDraftUnavailable:
                return ResumeTraceOutput(found=False)
            return ResumeTraceOutput(
                found=True,
                artifact_id=view.artifact_id,
                artifact_version=view.artifact_version,
                profile_version=view.profile_version,
                jd_id=view.jd_id,
                stale_relative_to_current_profile=view.stale_relative_to_current_profile,
                units=[ResumeUnitTraceOutput.model_validate(asdict(unit)) for unit in view.units],
            )

    hostname = urlsplit(settings.resource_url).netloc
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*"],
            allowed_origins=["https://chatgpt.com"],
        ),
    )
    declarations = OAuthToolDeclarations(
        app,
        tool_scopes={
            "get_account_profile": PROFILE_READ_SCOPE,
            "get_owned_profile_metadata": PROFILE_READ_SCOPE,
            "get_profiling_session": PROFILE_READ_SCOPE,
            "get_career_profile": PROFILE_READ_SCOPE,
            "get_claim_evidence": PROFILE_READ_SCOPE,
            "get_claim_review": PROFILE_READ_SCOPE,
            "get_jd_analysis": ARTIFACT_READ_SCOPE,
            "get_resume_trace": ARTIFACT_READ_SCOPE,
            "start_profiling": PROFILE_WRITE_SCOPE,
            "add_profiling_input": PROFILE_WRITE_SCOPE,
            "pause_profiling": PROFILE_WRITE_SCOPE,
            "prepare_claim_review": PROFILE_WRITE_SCOPE,
        },
    )
    return LocalMetadataPathAlias(declarations, urlsplit(settings.resource_url).path)

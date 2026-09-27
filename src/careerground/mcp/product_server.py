"""Local, read-only product-MCP foundation; deliberately has no ASGI entrypoint.

This factory uses a distinct product scope and database-backed account gate. It
must not be pointed at real user data before provider and erasure gates pass.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
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
    ReviewStale,
    ReviewUnavailable,
)
from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.profiling_workspace import (
    ProfilingExpired,
    ProfilingUnavailable,
)
from careerground.domain.profiling_workspace import (
    get_profiling_session as read_profiling_session,
)
from careerground.mcp.account_access import ActiveAccountTokenVerifier
from careerground.mcp.oauth_resource import (
    JwtTokenVerifier,
    LocalMetadataPathAlias,
    McpOAuthSettings,
    OAuthToolDeclarations,
)
from careerground.storage.graph_models import Claim

PROFILE_READ_SCOPE = "career.profile.read"


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
        JwtTokenVerifier(settings, required_scope=PROFILE_READ_SCOPE, signing_key=signing_key),
        issuer=settings.issuer,
        session_factory=session_factory,
    )
    server = MCPServer(
        name="careerground-product-foundation",
        version="0.1.0",
        instructions="Read-only synthetic account, workspace, and exact-version career profile foundation.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[PROFILE_READ_SCOPE],
            validate_token_resource=True,
        ),
    )

    def current_account_id(session: Session) -> str:
        access = get_access_token()
        if access is None or not access.subject or PROFILE_READ_SCOPE not in access.scopes:
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
        },
    )
    return LocalMetadataPathAlias(declarations, urlsplit(settings.resource_url).path)

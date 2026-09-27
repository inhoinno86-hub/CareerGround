"""Local, read-only product-MCP foundation; deliberately has no ASGI entrypoint.

This factory uses a distinct product scope and database-backed account gate. It
must not be pointed at real user data before provider and erasure gates pass.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.types import ASGIApp

from careerground.domain.authorization import (
    AuthenticationRequired,
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
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


def build_product_foundation_app(
    settings: McpOAuthSettings,
    *,
    session_factory: Callable[[], Session],
    signing_key: Callable[[str], object] | None = None,
) -> ASGIApp:
    """Build isolated product auth/ownership checks for synthetic local tests."""

    verifier = ActiveAccountTokenVerifier(
        JwtTokenVerifier(settings, required_scope=PROFILE_READ_SCOPE, signing_key=signing_key),
        issuer=settings.issuer,
        session_factory=session_factory,
    )
    server = MCPServer(
        name="careerground-product-foundation",
        version="0.1.0",
        instructions="Read-only account and profile metadata foundation. No career claims are served.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[PROFILE_READ_SCOPE],
            validate_token_resource=True,
        ),
    )

    def current_account_id() -> str:
        access = get_access_token()
        if access is None or not access.subject or PROFILE_READ_SCOPE not in access.scopes:
            raise PermissionError("Authentication required")
        with session_factory() as session:
            try:
                return resolve_account_id(
                    session, VerifiedIdentity(settings.issuer, access.subject)
                )
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
        return AccountProfile(id=current_account_id())

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
        access = get_access_token()
        if access is None or not access.subject or PROFILE_READ_SCOPE not in access.scopes:
            raise PermissionError("Authentication required")
        with session_factory() as session:
            try:
                account_id = resolve_account_id(
                    session, VerifiedIdentity(settings.issuer, access.subject)
                )
                profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
            except AuthenticationRequired as exc:
                raise PermissionError("Authentication required") from exc
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
        access = get_access_token()
        if access is None or not access.subject or PROFILE_READ_SCOPE not in access.scopes:
            raise PermissionError("Authentication required")
        with session_factory() as session:
            try:
                account_id = resolve_account_id(
                    session, VerifiedIdentity(settings.issuer, access.subject)
                )
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
            except AuthenticationRequired as exc:
                raise PermissionError("Authentication required") from exc
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
        },
    )
    return LocalMetadataPathAlias(declarations, urlsplit(settings.resource_url).path)

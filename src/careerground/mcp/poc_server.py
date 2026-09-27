"""Fail-closed, synthetic-only MCP OAuth resource-server probe.

This sidecar has no database connection and exposes no CareerGround product data.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.types import ASGIApp

from careerground.mcp.account_access import ActiveAccountTokenVerifier
from careerground.mcp.oauth_resource import (
    JwtTokenVerifier as ScopedJwtTokenVerifier,
)
from careerground.mcp.oauth_resource import (
    LocalMetadataPathAlias,
    McpOAuthSettings,
    OAuthToolDeclarations,
)

PROBE_SCOPE = "careerground:probe"


class PocProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)


@dataclass(frozen=True)
class PocSettings(McpOAuthSettings):
    @classmethod
    def from_environment(cls) -> PocSettings:
        issuer = os.environ.get("CAREERGROUND_POC_ISSUER", "")
        resource_url = os.environ.get("CAREERGROUND_POC_RESOURCE_URL", "")
        if not issuer or not resource_url:
            raise ValueError("POC issuer and external resource URL must both be configured")
        return cls(issuer=issuer, resource_url=resource_url)


class JwtTokenVerifier(ScopedJwtTokenVerifier):
    """Keep the PoC's probe-only scope as the backward-compatible default."""

    def __init__(
        self,
        settings: PocSettings,
        *,
        signing_key: Callable[[str], object] | None = None,
    ) -> None:
        super().__init__(settings, required_scope=PROBE_SCOPE, signing_key=signing_key)


def build_app(
    settings: PocSettings,
    *,
    signing_key: Callable[[str], object] | None = None,
) -> ASGIApp:
    """Build the database-free, synthetic-only development PoC."""

    return _build_app(settings, JwtTokenVerifier(settings, signing_key=signing_key))


def build_account_guarded_probe_app(
    settings: PocSettings,
    *,
    session_factory: Callable[[], Session],
    signing_key: Callable[[str], object] | None = None,
) -> ASGIApp:
    """Exercise the product account gate with synthetic tools, never product data."""

    verifier = ActiveAccountTokenVerifier(
        JwtTokenVerifier(settings, signing_key=signing_key),
        issuer=settings.issuer,
        session_factory=session_factory,
    )
    return _build_app(settings, verifier)


def _build_app(settings: PocSettings, verifier: TokenVerifier) -> ASGIApp:
    server = MCPServer(
        name="careerground-auth-poc",
        version="0.1.0",
        instructions="Synthetic authentication probe only. No career records or writes exist here.",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[PROBE_SCOPE],
            validate_token_resource=True,
        ),
    )

    @server.tool(
        name="get_poc_identity",
        title="Check CareerGround test identity",
        description="Confirm the linked synthetic test identity. Returns no career or email data.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta={"openai/profile": True},
        structured_output=True,
    )
    def get_poc_identity() -> PocProfile:
        access = get_access_token()
        if access is None or not access.subject or PROBE_SCOPE not in access.scopes:
            raise PermissionError("Authentication required")
        identity = hashlib.sha256(f"{settings.issuer}\0{access.subject}".encode()).hexdigest()[:24]
        return PocProfile(id=f"poc_{identity}")

    hostname = urlsplit(settings.resource_url).netloc
    app: Starlette = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*"],
            allowed_origins=["https://chatgpt.com"],
        ),
    )
    return LocalMetadataPathAlias(
        OAuthToolDeclarations(app, tool_scopes={"get_poc_identity": PROBE_SCOPE}),
        urlsplit(settings.resource_url).path,
    )

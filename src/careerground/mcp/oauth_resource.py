"""Shared OAuth resource-server validation and MCP HTTP metadata adapters."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken
from starlette.types import ASGIApp, Receive, Scope, Send

_TUNNEL_RESOURCE_PATH = re.compile(r"/v1/mcp/tunnel_[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class McpOAuthSettings:
    issuer: str
    resource_url: str

    def __post_init__(self) -> None:
        issuer = urlsplit(self.issuer)
        resource = urlsplit(self.resource_url)
        for name, parsed in (("issuer", issuer), ("resource_url", resource)):
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"{name} must be an HTTPS URL without userinfo or query")
        if issuer.path != "/" or not self.issuer.endswith("/"):
            raise ValueError("issuer must be the exact Auth0 issuer URL ending in /")
        if resource.path != "/mcp" and not _TUNNEL_RESOURCE_PATH.fullmatch(resource.path):
            raise ValueError("resource_url must be a /mcp or /v1/mcp/tunnel_<id> URL")

    @property
    def jwks_url(self) -> str:
        return self.issuer + ".well-known/jwks.json"


class JwtTokenVerifier:
    """Validate signed RS256 access tokens without logging or returning their raw claims."""

    def __init__(
        self,
        settings: McpOAuthSettings,
        *,
        required_scope: str | frozenset[str],
        signing_key: Callable[[str], object] | None = None,
    ) -> None:
        self.settings = settings
        if isinstance(required_scope, str):
            accepted_scopes = frozenset({required_scope}) if required_scope else frozenset()
        elif isinstance(required_scope, frozenset) and all(
            isinstance(scope, str) and scope for scope in required_scope
        ):
            accepted_scopes = required_scope
        else:
            accepted_scopes = frozenset()
        if not accepted_scopes:
            raise ValueError("at least one accepted scope is required")
        self.accepted_scopes = accepted_scopes
        self._signing_key = (
            signing_key
            or PyJWKClient(
                settings.jwks_url, cache_jwk_set=True, lifespan=300, timeout=5
            ).get_signing_key_from_jwt
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await asyncio.to_thread(self._verify, token)

    def _verify(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                return None
            key = self._signing_key(token)
            if hasattr(key, "key"):
                key = key.key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.resource_url,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
                leeway=30,
            )
            subject = claims.get("sub")
            client_id = claims.get("azp")
            scope = claims.get("scope", "")
            if (
                not isinstance(subject, str)
                or not subject
                or not isinstance(client_id, str)
                or not client_id
                or not isinstance(scope, str)
            ):
                return None
            scopes = scope.split()
            if not self.accepted_scopes.intersection(scopes):
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=claims["exp"],
                resource=self.settings.resource_url,
                subject=subject,
            )
        except (jwt.PyJWTError, ValueError, OSError, KeyError):
            return None


class OAuthToolDeclarations:
    """Add top-level securitySchemes until the MCP SDK exposes them directly."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        tool_scopes: dict[str, str | tuple[str, ...]],
        functional_headers: bool = False,
    ) -> None:
        self.app = app
        self.tool_scopes = tool_scopes
        self.functional_headers = functional_headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/mcp":
            await self.app(scope, receive, send)
            return

        response_start: dict[str, Any] | None = None
        body_parts: list[bytes] = []
        buffering = False

        async def send_with_declaration(message: dict[str, Any]) -> None:
            nonlocal response_start, buffering
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                buffering = b"application/json" in headers.get(b"content-type", b"")
                if buffering:
                    response_start = message
                else:
                    await send(message)
                return
            if message["type"] != "http.response.body" or not buffering:
                await send(message)
                return
            body_parts.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            body = b"".join(body_parts)
            retry_after = None
            try:
                payload = json.loads(body)
                tools = payload.get("result", {}).get("tools", [])
                for tool in tools:
                    required_scope = self.tool_scopes.get(tool.get("name"))
                    if required_scope:
                        scopes = (
                            (required_scope,) if isinstance(required_scope, str) else required_scope
                        )
                        tool["securitySchemes"] = [
                            {"type": "oauth2", "scopes": [value]} for value in dict.fromkeys(scopes)
                        ]
                if tools:
                    body = json.dumps(payload, separators=(",", ":")).encode()
                if self.functional_headers:
                    error = payload.get("result", {}).get("structuredContent", {}).get("error", {})
                    retry = error.get("retry_after_seconds")
                    if error.get("code") == "RATE_LIMITED" and type(retry) is int and retry > 0:
                        retry_after = retry
            except (ValueError, AttributeError, TypeError):
                pass
            assert response_start is not None
            headers = [
                (name, value)
                for name, value in response_start.get("headers", [])
                if name.lower() != b"content-length"
            ]
            headers.append((b"content-length", str(len(body)).encode()))
            if self.functional_headers:
                headers.append((b"cache-control", b"no-store"))
            if retry_after is not None:
                headers.append((b"retry-after", str(retry_after).encode()))
            await send(
                {
                    **response_start,
                    "headers": headers,
                    "status": 429 if retry_after is not None else response_start["status"],
                }
            )
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, send_with_declaration)


class LocalMetadataPathAlias:
    """Keep local /mcp discovery when the OAuth resource is a tunnel URL."""

    def __init__(self, app: ASGIApp, resource_path: str) -> None:
        self.app = app
        self.resource_path = resource_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and self.resource_path != "/mcp"
            and scope.get("path") == "/.well-known/oauth-protected-resource/mcp"
        ):
            path = "/.well-known/oauth-protected-resource" + self.resource_path
            scope = {**scope, "path": path, "raw_path": path.encode()}
        await self.app(scope, receive, send)

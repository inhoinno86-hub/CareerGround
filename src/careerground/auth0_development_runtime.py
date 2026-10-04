"""Opt-in loopback Auth0 trial, with a separate disposable database.

Uses the existing development client. Does not create tenants, change callbacks,
open a tunnel, use a configured product database, or call a model API.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt
import uvicorn
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from careerground.config import Auth0Settings
from careerground.domain.authorization import VerifiedIdentity
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.providers.oidc_identity import (
    IdentityClientSettings,
    IdentityLoginRejected,
    IdentityOnlyLogin,
    StableAccountAdmission,
)
from careerground.storage.models import Base
from careerground.web.authenticated_management import AuthenticatedManagement


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_request(request: Request) -> dict:
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        # A successful token/discovery response is small; never log its body.
        if response.geturl() != request.full_url:
            raise IdentityLoginRejected
        body = response.read(65537)
        if len(body) > 65536:
            raise IdentityLoginRejected
    data = json.loads(body)
    if type(data) is not dict:
        raise IdentityLoginRejected
    return data


def discover(settings: Auth0Settings) -> tuple[IdentityClientSettings, str]:
    domain = settings.domain
    if (
        not domain
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for character in domain)
        or "." not in domain
    ):
        raise ValueError("Invalid Auth0 development domain")
    issuer = "https://" + domain + "/"
    origin = settings.app_base_url.rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("APP_BASE_URL must be a loopback HTTP origin for this trial")
    metadata = _json_request(Request(issuer + ".well-known/openid-configuration"))
    if metadata.get("issuer") != issuer or "S256" not in metadata.get(
        "code_challenge_methods_supported", []
    ):
        raise ValueError("Auth0 discovery issuer/PKCE mismatch")
    for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        endpoint = metadata.get(name)
        endpoint_url = urlsplit(endpoint) if type(endpoint) is str else None
        if endpoint_url is None or (
            endpoint_url.scheme != "https"
            or endpoint_url.netloc != domain
            or endpoint_url.query
            or endpoint_url.fragment
        ):
            raise ValueError("Unexpected Auth0 discovery endpoint")
    return (
        IdentityClientSettings(
            issuer,
            settings.client_id,
            metadata["authorization_endpoint"],
            metadata["token_endpoint"],
            origin + "/auth/callback",
        ),
        metadata["jwks_uri"],
    )


class Auth0DevelopmentRuntime:
    def __init__(self, settings: Auth0Settings, mcp_settings: McpOAuthSettings):
        client_settings, jwks_url = discover(settings)
        if client_settings.issuer != mcp_settings.issuer:
            raise ValueError("Web and MCP must use the same Auth0 issuer")
        self.origin = settings.app_base_url.rstrip("/")
        self.port = urlsplit(self.origin).port or 80
        self.folder = tempfile.TemporaryDirectory(prefix="careerground-auth0-login-")
        path = Path(self.folder.name) / "auth-trial.sqlite"
        path.touch(mode=0o600)
        self.engine = create_engine(
            "sqlite+pysqlite:///" + str(path),
            hide_parameters=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        admission_secret = secrets.token_bytes(32)

        def exchange(body):
            try:
                return _json_request(
                    Request(
                        client_settings.token_endpoint,
                        data=urlencode({**body, "client_secret": settings.client_secret}).encode(),
                        headers={"content-type": "application/x-www-form-urlencoded"},
                    )
                )
            except Exception:  # noqa: BLE001 - suppress private upstream payloads
                raise IdentityLoginRejected from None

        def admit(identity: VerifiedIdentity):
            # Opt-in development only: explicit browser setup admits a verified
            # identity. No public runtime/tunnel or model-provided subject exists.
            return StableAccountAdmission(
                issuer=client_settings.issuer,
                secret=admission_secret,
                admitted_subjects=frozenset({identity.subject}),
            )(identity)

        self.app = AuthenticatedManagement(
            login=IdentityOnlyLogin(
                client_settings,
                exchange_code=exchange,
                signing_key=jwt.PyJWKClient(jwks_url, timeout=5).get_signing_key_from_jwt,
            ),
            origin=self.origin,
            session_factory=self.sessions,
            account_admission=admit,
            review_secret=secrets.token_bytes(32),
            presentation_secret=secrets.token_bytes(32),
            mcp_settings=mcp_settings,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (
            scope.get("client", ("", 0))[0] not in {"127.0.0.1", "::1"}
            or dict(scope.get("headers", [])).get(b"host") != urlsplit(self.origin).netloc.encode()
        ):
            from starlette.responses import Response

            await Response(status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def close(self):
        self.engine.dispose()
        self.folder.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-development-login", action="store_true")
    args = parser.parse_args()
    if not args.allow_development_login:
        parser.error("--allow-development-login is required for actual Auth0 identity verification")
    runtime = None
    try:
        settings = Auth0Settings.from_environment()
        if settings is None:
            raise ValueError("Auth0 development settings are required")
        runtime = Auth0DevelopmentRuntime(
            settings,
            McpOAuthSettings(
                issuer=os.environ.get("CAREERGROUND_POC_ISSUER", ""),
                resource_url=os.environ.get("CAREERGROUND_POC_RESOURCE_URL", ""),
            ),
        )
        print("Auth0 discovery verified; isolated trial: " + runtime.origin, flush=True)
        print("Use synthetic career text only. No tunnel or model API is started.", flush=True)
        uvicorn.run(
            runtime, host="127.0.0.1", port=runtime.port, access_log=False, log_level="error"
        )
    except Exception:  # noqa: BLE001 - startup errors must not expose configuration
        # HTTP/client/SQL exceptions can contain secrets and provider identifiers.
        parser.exit(1, "Auth0 development trial could not start; configuration was not changed.\n")
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    main()

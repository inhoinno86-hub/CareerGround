"""Opt-in loopback Auth0 trial, with separate disposable or private persistent data.

Uses the existing development client. Does not create tenants, change callbacks,
open a tunnel, use a configured product database, or call a model API.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
import signal
import tempfile
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt
import uvicorn
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from careerground.config import Auth0Settings
from careerground.domain.authorization import VerifiedIdentity
from careerground.mcp.authenticated_development_ingress import AuthenticatedDevelopmentMcpIngress
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.providers.oidc_identity import (
    IdentityClientSettings,
    IdentityLoginRejected,
    IdentityOnlyLogin,
    StableAccountAdmission,
)
from careerground.storage.authenticated_development_store import AuthenticatedDevelopmentStore
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations
from careerground.storage.development_deletion_passkeys import DevelopmentDeletionPasskeys
from careerground.storage.models import Base
from careerground.web.authenticated_management import AuthenticatedManagement
from careerground.workers.retention_runner import run_retention_cycle


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
    def __init__(
        self,
        settings: Auth0Settings,
        mcp_settings: McpOAuthSettings,
        *,
        state_dir: Path | None = None,
        allow_profile_deletion: bool = False,
        require_deletion_mfa: bool = False,
        allow_retention: bool = False,
        passkey_dir: Path | None = None,
        initialize_passkeys: bool = False,
        allow_passkey_enrollment: bool = False,
        connection_denials_dir: Path | None = None,
        connection_client_id: str | None = None,
        initialize_connection_denials: bool = False,
    ):
        if allow_profile_deletion and state_dir is None:
            raise ValueError("A separate persistent development store is required for deletion")
        if type(require_deletion_mfa) is not bool or (
            require_deletion_mfa and not allow_profile_deletion
        ):
            raise ValueError("MFA requires explicitly enabled development profile deletion")
        if type(allow_retention) is not bool or (allow_retention and state_dir is None):
            raise ValueError("Retention requires the separate persistent development store")
        self.allow_retention = allow_retention
        if (
            type(initialize_passkeys) is not bool
            or type(allow_passkey_enrollment) is not bool
            or ((initialize_passkeys or allow_passkey_enrollment) and passkey_dir is None)
            or (passkey_dir is not None and (not allow_profile_deletion or require_deletion_mfa))
        ):
            raise ValueError(
                "Passkeys require isolated profile deletion and explicit registry flags"
            )
        if (
            type(initialize_connection_denials) is not bool
            or (
                (initialize_connection_denials or connection_client_id is not None)
                and connection_denials_dir is None
            )
            or (
                connection_denials_dir is not None
                and (state_dir is None or not connection_client_id)
            )
        ):
            raise ValueError(
                "Connection controls require isolated state and an explicit target client"
            )
        client_settings, jwks_url = discover(settings)
        if client_settings.issuer != mcp_settings.issuer:
            raise ValueError("Web and MCP must use the same Auth0 issuer")
        self.origin = settings.app_base_url.rstrip("/")
        self.mcp_settings = mcp_settings
        self.port = urlsplit(self.origin).port or 80
        self.folder = None
        self.store = None
        self.passkeys = None
        self.connection_denials = None
        if state_dir is not None:
            self.store = AuthenticatedDevelopmentStore(
                state_dir, client_settings, mcp_settings.resource_url
            )
            self.engine, self.sessions = self.store.engine, self.store.sessions
            admission_secret = self.store.admission_secret
            review_secret = self.store.review_secret
            presentation_secret = self.store.presentation_secret
        else:
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
            review_secret = secrets.token_bytes(32)
            presentation_secret = secrets.token_bytes(32)

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

        try:
            if connection_denials_dir is not None:
                directories = [self.store.state_dir]
                if passkey_dir is not None:
                    directories.append(Path(passkey_dir))
                if any(
                    Path(connection_denials_dir) == directory
                    or Path(connection_denials_dir) in directory.parents
                    or directory in Path(connection_denials_dir).parents
                    for directory in directories
                ):
                    raise ValueError("Separate connection denial directory required")
                self.connection_denials = DevelopmentConnectionRevocations(
                    connection_denials_dir,
                    issuer=client_settings.issuer,
                    initialize=initialize_connection_denials,
                )
            if passkey_dir is not None:
                if any(
                    first == second or first in second.parents
                    for first, second in (
                        (Path(passkey_dir), self.store.state_dir),
                        (self.store.state_dir, Path(passkey_dir)),
                    )
                ):
                    raise ValueError("Separate passkey directory required")
                self.passkeys = DevelopmentDeletionPasskeys(
                    passkey_dir,
                    origin=self.origin,
                    store_binding=hashlib.sha256(
                        self.store.admission_secret + self.store.binding_digest.encode()
                    ).hexdigest(),
                    initialize=initialize_passkeys,
                )
            self.app = AuthenticatedManagement(
                login=IdentityOnlyLogin(
                    client_settings,
                    exchange_code=exchange,
                    signing_key=jwt.PyJWKClient(jwks_url, timeout=5).get_signing_key_from_jwt,
                ),
                origin=self.origin,
                session_factory=self.sessions,
                account_admission=admit,
                review_secret=review_secret,
                presentation_secret=presentation_secret,
                mcp_settings=mcp_settings,
                deletion_store=self.store if allow_profile_deletion else None,
                require_deletion_mfa=require_deletion_mfa,
                deletion_passkeys=self.passkeys,
                allow_passkey_enrollment=allow_passkey_enrollment,
                connection_registry=self.connection_denials,
                connection_client_id=connection_client_id,
            )
        except BaseException:
            self.close()
            raise

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
        if self.connection_denials is not None:
            self.connection_denials.close()
        if self.passkeys is not None:
            self.passkeys.close()
        self.engine.dispose()
        if self.store is not None:
            self.store.close()
        if self.folder is not None:
            self.folder.cleanup()


async def serve(runtime: Auth0DevelopmentRuntime, mcp_port: int | None = None):
    stopping = asyncio.Event()
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                runtime, host="127.0.0.1", port=runtime.port, access_log=False, log_level="error"
            )
        )
    ]
    if mcp_port is not None:
        if not 1024 <= mcp_port <= 65535 or mcp_port == runtime.port:
            raise ValueError("Separate unprivileged MCP loopback port required")
        servers.append(
            uvicorn.Server(
                uvicorn.Config(
                    AuthenticatedDevelopmentMcpIngress(
                        runtime.app, runtime.mcp_settings.resource_url
                    ),
                    host="127.0.0.1",
                    port=mcp_port,
                    access_log=False,
                    log_level="error",
                    lifespan="off",
                )
            )
        )
    loop = asyncio.get_running_loop()

    def stop():
        stopping.set()
        for server in servers:
            server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop)
    for server in servers:
        server.capture_signals = nullcontext
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    if runtime.allow_retention:
        tasks.append(asyncio.create_task(_retention_loop(runtime.store, stopping)))
    try:
        # If either listener exits/fails to bind, stop the other as well.
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop()
        await asyncio.gather(*tasks)
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


async def _retention_loop(store: AuthenticatedDevelopmentStore, stopping: asyncio.Event):
    """Bounded local expiry only; a persistent store must be explicitly opted in."""
    while not stopping.is_set():
        try:
            completed, failed = await asyncio.to_thread(
                run_retention_cycle,
                store.sessions,
                now=datetime.now(UTC),
                batches=1,
                batch_size=100,
            )
            logging.getLogger(__name__).info(
                "development_retention completed=%d failed=%d", completed, failed
            )
        except Exception:  # noqa: BLE001 - errors must not disclose private DB contents
            logging.getLogger(__name__).error("development_retention unavailable; runtime stopping")
            return
        try:
            await asyncio.wait_for(stopping.wait(), timeout=60)
        except TimeoutError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-development-login", action="store_true")
    parser.add_argument(
        "--allow-development-profile-deletion",
        action="store_true",
        help="Enable local PROFILE deletion with fresh OIDC exchange and separate Web approval; persistent development store required",
    )
    parser.add_argument(
        "--require-development-deletion-mfa",
        action="store_true",
        help="Request provider MFA and accept only signed mfa for deletion; provider configuration required",
    )
    parser.add_argument(
        "--allow-development-retention",
        action="store_true",
        help="Run bounded expiry sweeps in the separate persistent development store only",
    )
    parser.add_argument(
        "--development-deletion-passkey-dir",
        type=Path,
        help="Separate opt-in deletion passkey public-key registry, exact loopback origin/store",
    )
    parser.add_argument("--initialize-development-passkeys", action="store_true")
    parser.add_argument("--allow-development-passkey-enrollment", action="store_true")
    parser.add_argument("--development-connection-denials-dir", type=Path)
    parser.add_argument("--development-connection-client-id")
    parser.add_argument("--initialize-development-connection-denials", action="store_true")
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Separate owner-only authenticated development store; retained on exit",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        help="Separate loopback product-MCP listener for the existing private tunnel",
    )
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
            state_dir=args.state_dir,
            allow_profile_deletion=args.allow_development_profile_deletion,
            require_deletion_mfa=args.require_development_deletion_mfa,
            allow_retention=args.allow_development_retention,
            passkey_dir=args.development_deletion_passkey_dir,
            initialize_passkeys=args.initialize_development_passkeys,
            allow_passkey_enrollment=args.allow_development_passkey_enrollment,
            connection_denials_dir=args.development_connection_denials_dir,
            connection_client_id=args.development_connection_client_id,
            initialize_connection_denials=args.initialize_development_connection_denials,
        )
        print("Auth0 discovery verified; isolated development: " + runtime.origin, flush=True)
        print(
            "Data retained on exit."
            if runtime.store is not None
            else "Disposable data removed on exit.",
            flush=True,
        )
        print("Use synthetic career text only. No tunnel or model API is started.", flush=True)
        asyncio.run(serve(runtime, args.mcp_port))
    except Exception:  # noqa: BLE001 - startup errors must not expose configuration
        # HTTP/client/SQL exceptions can contain secrets and provider identifiers.
        parser.exit(1, "Auth0 development trial could not start; configuration was not changed.\n")
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    main()

"""Loopback disposable signed A/B fixture for BrowserOS; no real provider.

Synthetic login helpers are mounted only by this explicitly named test script.
WebAuthn registration/assertion still uses the browser and real server verifier.
"""

from __future__ import annotations

import argparse
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import uvicorn
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from careerground.storage.development_connection_revocations import DevelopmentConnectionRevocations
from careerground.web.authenticated_management import LOGIN_COOKIE
from careerground.web.development_passkeys import PASSKEY_ENROLLMENT_COOKIE
from tests import test_authenticated_management as foundation
from tests.test_development_deletion_passkeys import DevelopmentDeletionPasskeyTests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5016)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("use an unprivileged loopback port")
    foundation.ORIGIN = f"http://localhost:{args.port}"
    DevelopmentDeletionPasskeyTests.setUpClass()
    fixture = DevelopmentDeletionPasskeyTests()
    fixture.setUp()
    app = fixture.base.app
    fixture.base.now = time.time()
    app._clock = time.time
    app.browser._clock = time.time
    app.login._clock = time.time
    fixture.fx.auth_time = lambda: int(time.time())
    denials = DevelopmentConnectionRevocations(
        fixture.path.parent / "denials", issuer=foundation.ISSUER, initialize=True
    )
    from careerground.mcp.oauth_resource import McpOAuthSettings
    from careerground.web.authenticated_management import AuthenticatedManagement

    app = AuthenticatedManagement(
        login=fixture.base.login,
        origin=foundation.ORIGIN,
        session_factory=fixture.fx.store.sessions,
        account_admission=fixture.fx.store.admit,
        review_secret=fixture.fx.store.review_secret,
        presentation_secret=fixture.fx.store.presentation_secret,
        mcp_settings=McpOAuthSettings(foundation.ISSUER, foundation.RESOURCE),
        signing_key=lambda _: fixture.base.key.public_key(),
        deletion_store=fixture.fx.store,
        deletion_passkeys=fixture.registry,
        allow_passkey_enrollment=True,
        connection_registry=denials,
        connection_client_id="synthetic-mcp-client",
        clock=time.time,
    )
    fixture.base.app = app

    @app.web.get("/synthetic-login/{user}", include_in_schema=False)
    async def synthetic_login(user: str):
        if user not in {"a", "b"}:
            raise HTTPException(404)
        binding = secrets.token_urlsafe(32)
        query = parse_qs(urlsplit(app.login.begin(binding)).query)
        fixture.base.nonce = query["nonce"][0]
        response = RedirectResponse(
            "/auth/callback?" + urlencode({"code": "user-" + user, "state": query["state"][0]}),
            status_code=303,
        )
        response.set_cookie(
            LOGIN_COOKIE, binding, max_age=180, secure=True, httponly=True, samesite="lax", path="/"
        )
        return response

    @app.web.get("/synthetic-reauth", include_in_schema=False)
    async def synthetic_reauth(request: Request):
        # An explicit test helper, not a production bypass or an auth proof.
        from careerground.web.authenticated_deletion import REAUTH_COOKIE

        binding = request.cookies.get(PASSKEY_ENROLLMENT_COOKIE) or request.cookies.get(
            REAUTH_COOKIE
        )
        query = dict(request.query_params)
        if (
            not binding
            or set(query) != {"state", "nonce", "user"}
            or query["user"] not in {"a", "b"}
        ):
            raise HTTPException(400)
        fixture.base.nonce = query["nonce"]
        return RedirectResponse(
            "/auth/callback?"
            + urlencode({"code": "user-" + query["user"], "state": query["state"]}),
            status_code=303,
        )

    try:
        print("Disposable signed A/B + WebAuthn fixture: " + foundation.ORIGIN, flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error", access_log=False)
    finally:
        denials.close()
        fixture.doCleanups()


if __name__ == "__main__":
    main()

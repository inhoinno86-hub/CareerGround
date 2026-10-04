"""Disposable BrowserOS fixture: two signed synthetic identities, no providers.

The /synthetic-login/a and /synthetic-login/b routes are test conveniences only;
they are never mounted in the Auth0 development runtime or public application.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import uvicorn
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from careerground.web.authenticated_management import LOGIN_COOKIE
from tests import test_authenticated_management as fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5015)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("use an unprivileged loopback port")
    origin = f"http://127.0.0.1:{args.port}"
    # All provider input comes from the repository's signed synthetic fixture.
    fixtures.ORIGIN = origin
    fixtures.AuthenticatedManagementTests.setUpClass()
    fixture = fixtures.AuthenticatedManagementTests()
    fixture.setUp()

    @fixture.app.web.get("/synthetic-login/{user}", include_in_schema=False)
    async def synthetic_login(user: str):
        if user not in {"a", "b"}:
            raise HTTPException(404)
        binding = secrets.token_urlsafe(32)
        query = parse_qs(urlsplit(fixture.login.begin(binding)).query)
        fixture.nonce = query["nonce"][0]
        response = RedirectResponse(
            "/auth/callback?"
            + urlencode(
                {
                    "code": "user-" + user,
                    "state": query["state"][0],
                }
            ),
            status_code=303,
        )
        response.set_cookie(
            LOGIN_COOKIE,
            binding,
            max_age=180,
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.headers["cache-control"] = "no-store"
        return response

    try:
        print("Signed synthetic BrowserOS fixture: " + origin, flush=True)
        uvicorn.run(
            fixture.app, host="127.0.0.1", port=args.port, log_level="error", access_log=False
        )
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()

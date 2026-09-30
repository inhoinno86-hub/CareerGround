"""Optional Auth0 browser-session bridge for the isolated review factory.

The caller supplies an AuthClient and test database; this module creates no
Auth0 tenant, network connection, product route, or account mapping.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    AuthenticationRequired,
    VerifiedIdentity,
    resolve_account_id,
)
from careerground.web.review_foundation import TrustedBrowserIdentity

_COOKIE_PREFIX = "_a0_session_"
_MAX_COOKIE_PARTS = 8
_MAX_COOKIE_BYTES = 32_768


class BrowserSessionReader(Protocol):
    async def require_session(self, request: Request, response: Response) -> dict: ...


class Auth0ReviewIdentityAdapter:
    """Resolve a verified SDK session to an active account on every request."""

    def __init__(
        self,
        auth_client: BrowserSessionReader,
        *,
        issuer: str,
        session_factory: Callable[[], Session],
        binding_secret: bytes,
    ) -> None:
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.netloc != parsed.hostname
            or parsed.path != "/"
            or parsed.query
            or parsed.fragment
            or not isinstance(binding_secret, bytes)
            or len(binding_secret) < 32
        ):
            raise ValueError("invalid Auth0 review identity configuration")
        self._auth_client = auth_client
        self._issuer = issuer
        self._session_factory = session_factory
        self._secret = binding_secret

    async def __call__(self, request: Request, response: Response) -> TrustedBrowserIdentity | None:
        cookie_material = _session_cookie_material(request)
        if cookie_material is None:
            return None
        try:
            browser_session = await self._auth_client.require_session(request, response)
        except (HTTPException, ValueError, TypeError):
            return None
        if type(browser_session) is not dict:
            return None
        user = browser_session.get("user")
        if type(user) is not dict:
            return None
        subject = user.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            return None
        try:
            account_id = await asyncio.to_thread(self._active_account_id, subject)
        except (AuthenticationRequired, SQLAlchemyError):
            return None
        material = b"\0".join(
            (
                b"CG_REVIEW_BROWSER_V1",
                self._issuer.encode(),
                subject.encode(),
                cookie_material,
            )
        )
        binding = hmac.new(self._secret, material, hashlib.sha256).hexdigest()
        return TrustedBrowserIdentity(account_id=account_id, session_id=binding)

    def _active_account_id(self, subject: str) -> str:
        with self._session_factory() as session:
            return resolve_account_id(session, VerifiedIdentity(self._issuer, subject))


def _session_cookie_material(request: Request) -> bytes | None:
    parts: dict[int, str] = {}
    for name, value in request.cookies.items():
        if not name.startswith("_a0_session"):
            continue
        if not name.startswith(_COOKIE_PREFIX):
            return None
        suffix = name[len(_COOKIE_PREFIX) :]
        if len(suffix) != 1 or not suffix.isascii() or not suffix.isdecimal():
            return None
        index = int(suffix)
        if index >= _MAX_COOKIE_PARTS or not isinstance(value, str) or not value:
            return None
        parts[index] = value
    if not parts or set(parts) != set(range(len(parts))):
        return None
    material = "".join(parts[index] for index in range(len(parts))).encode()
    return material if len(material) <= _MAX_COOKIE_BYTES else None

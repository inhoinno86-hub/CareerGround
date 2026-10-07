"""First-party sessions for a verified identity, without copying host credentials.

An OAuth adapter calls issue after verification and explicit account enrollment.
No login route or external provider is mounted by importing this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from fastapi import Request, Response
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    AuthenticationRequired,
    VerifiedIdentity,
    resolve_account_id,
)
from careerground.web.review_foundation import TrustedBrowserIdentity

COOKIE = "__Host-careerground-session"


@dataclass(frozen=True, repr=False)
class _Session:
    identity: VerifiedIdentity
    account_id: str
    expires_at: float


class VerifiedBrowserSessions:
    """Bounded process-local cookies; account authorization is fresh on every read."""

    def __init__(self, session_factory: Callable[[], Session], *, clock=time.time):
        self._factory, self._clock = session_factory, clock
        self._sessions: dict[str, _Session] = {}
        self._lock = Lock()

    @staticmethod
    def _key(cookie: str) -> str:
        return hashlib.sha256(cookie.encode()).hexdigest()

    def issue(self, identity: VerifiedIdentity, response: Response) -> None:
        if type(identity) is not VerifiedIdentity:
            raise PermissionError
        with self._factory() as session:
            account = resolve_account_id(session, identity)
        cookie = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock:
            self._sessions = {
                key: row for key, row in self._sessions.items() if row.expires_at > now
            }
            if len(self._sessions) >= 128:
                raise PermissionError
            self._sessions[self._key(cookie)] = _Session(identity, account, now + 3600)
        response.set_cookie(
            COOKIE, cookie, max_age=3600, secure=True, httponly=True, samesite="lax", path="/"
        )
        response.headers["cache-control"] = "no-store"

    async def __call__(self, request: Request, response: Response) -> TrustedBrowserIdentity | None:
        values = [value for name, value in request.headers.raw if name.lower() == b"cookie"]
        if sum(value.count((COOKIE + "=").encode()) for value in values) != 1:
            return None
        cookie = request.cookies.get(COOKIE, "")
        if not 32 <= len(cookie) <= 128:
            return None
        key = self._key(cookie)
        with self._lock:
            row = self._sessions.get(key)
            if row is None or row.expires_at <= self._clock():
                self._sessions.pop(key, None)
                return None
        try:
            account = await asyncio.to_thread(self._resolve, row.identity)
            if account != row.account_id:
                with self._lock:
                    self._sessions.pop(key, None)
                return None
        except AuthenticationRequired:
            # A removed mapping or blocked account permanently loses this session.
            with self._lock:
                self._sessions.pop(key, None)
            return None
        except Exception:  # noqa: BLE001 - authorization errors fail closed
            return None
        # Revocation may have happened while the DB read was in flight.
        with self._lock:
            if self._sessions.get(key) is not row or row.expires_at <= self._clock():
                return None
        return TrustedBrowserIdentity(account_id=account, session_id=key)

    def _resolve(self, identity):
        with self._factory() as session:
            return resolve_account_id(session, identity)

    def revoke(self, request: Request, response: Response) -> None:
        cookie = request.cookies.get(COOKIE, "")
        with self._lock:
            self._sessions.pop(self._key(cookie), None)
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        response.headers["cache-control"] = "no-store"

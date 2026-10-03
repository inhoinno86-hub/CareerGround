"""Database-backed account gate for future private MCP requests.

The synthetic PoC intentionally does not use this gate. Private MCP entrypoints
must wrap their JWT verifier with it before registering any product-data tools.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from mcp.server.auth.provider import AccessToken, TokenVerifier
from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.authorization import (
    AuthenticationRequired,
    VerifiedIdentity,
    resolve_account_id,
)
from careerground.storage.models import Account, AuthIdentity


class ActiveAccountTokenVerifier:
    """Reject a verified token unless its identity maps to an ACTIVE account now.

    A fresh database session is opened for every verification, so neither token
    validity nor a previously successful request caches account authorization.
    """

    def __init__(
        self,
        token_verifier: TokenVerifier,
        *,
        issuer: str,
        session_factory: Callable[[], Session],
        token_is_revoked: Callable[[str], bool] | None = None,
        enrollment_account_id: Callable[[VerifiedIdentity], str | None] | None = None,
        enrollment_scope: str = "career.profile.write",
    ) -> None:
        self._token_verifier = token_verifier
        self._issuer = issuer
        self._session_factory = session_factory
        self._token_is_revoked = token_is_revoked
        self._enrollment_account_id = enrollment_account_id
        self._enrollment_scope = enrollment_scope

    async def verify_token(self, token: str) -> AccessToken | None:
        if self._token_is_revoked is not None:
            try:
                if self._token_is_revoked(token):
                    return None
            except Exception:  # noqa: BLE001 - unavailable revocation gate must fail closed
                return None
        access = await self._token_verifier.verify_token(token)
        if access is None or not access.subject:
            return None
        if not await asyncio.to_thread(
            self._has_active_account, access.subject, self._enrollment_scope in access.scopes
        ):
            return None
        return access

    def _has_active_account(self, subject: str, enrollment_scope: bool = False) -> bool:
        try:
            with self._session_factory() as session:
                identity = VerifiedIdentity(self._issuer, subject)
                try:
                    resolve_account_id(session, identity)
                except AuthenticationRequired:
                    if not enrollment_scope or self._enrollment_account_id is None:
                        return False
                    # Linked blocked accounts never enter enrollment. An erased
                    # identity's stable admission ID also remains unavailable.
                    if (
                        session.scalar(
                            select(AuthIdentity.id).where(
                                AuthIdentity.issuer == self._issuer, AuthIdentity.subject == subject
                            )
                        )
                        is not None
                    ):
                        return False
                    admission = self._enrollment_account_id(identity)
                    return bool(admission) and session.get(Account, admission) is None
            return True
        except Exception:  # noqa: BLE001 - enrollment adapter failure must deny access
            # Unknown, disabled, deleted, or temporarily unreadable: deny.
            return False

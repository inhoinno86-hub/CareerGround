"""Identity-only OIDC relying-party boundary, inactive until explicitly wired.

Token exchange and JWKS resolution are trusted injected adapters. This module
does not discover endpoints, open a network connection, request inference access,
issue MCP credentials, or register an OAuth client. Transactions are process-local
and deliberately become unusable after restart.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import jwt

from careerground.domain.authorization import VerifiedIdentity

REAUTHENTICATION_TRANSACTION_TTL_SECONDS = 600
FRESH_AUTHENTICATION_MAX_AGE_SECONDS = 180
MFA_AUTHENTICATION_CONTEXT = "http://schemas.openid.net/pape/policies/2007/06/multi-factor"


class IdentityLoginRejected(Exception):
    """A login failed without disclosing credentials or provider responses."""


def _url(value: str, *, callback: bool = False) -> None:
    if type(value) is not str or not 1 <= len(value) <= 2048:
        raise ValueError("Invalid identity URL")
    try:
        p = urlsplit(value)
        valid = p.scheme == "https" or (
            callback and p.scheme == "http" and p.hostname in {"127.0.0.1", "localhost", "::1"}
        )
        if (
            not valid
            or not p.hostname
            or p.username is not None
            or p.password is not None
            or p.query
            or p.fragment
            or any(c.isspace() or ord(c) < 32 for c in value)
            or "\\" in value
            or "%" in p.netloc
            or (p.port is not None and not 1 <= p.port <= 65535)
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Invalid identity URL") from None


@dataclass(frozen=True)
class IdentityClientSettings:
    issuer: str
    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str

    def __post_init__(self):
        if type(self.issuer) is not str or len(self.issuer) > 512:
            raise ValueError("Invalid identity issuer")
        for value in (self.issuer, self.authorization_endpoint, self.token_endpoint):
            _url(value)
        _url(self.redirect_uri, callback=True)
        if (
            type(self.client_id) is not str
            or not 1 <= len(self.client_id) <= 255
            or any(c.isspace() for c in self.client_id)
        ):
            raise ValueError("Registered identity client required")


@dataclass(frozen=True, repr=False)
class _Transaction:
    binding: str
    verifier: str
    nonce: str
    expires_at: float
    reauthentication: bool = False
    requested_at: float = 0


@dataclass(frozen=True, repr=False)
class FreshIdentityAuthentication:
    """Signed provider exchange freshness, not proof of upstream MFA/password entry."""

    identity: VerifiedIdentity
    authenticated_at: int
    authentication_methods: tuple[str, ...] = ()


class IdentityOnlyLogin:
    """One-use S256/state/nonce before trusting a signed identity-only token."""

    def __init__(
        self,
        settings: IdentityClientSettings,
        *,
        exchange_code: Callable[[dict[str, str]], object],
        signing_key: Callable[[str], object],
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self._exchange = exchange_code
        self._signing_key = signing_key
        self._clock = clock
        self._transactions: dict[str, _Transaction] = {}
        self._lock = Lock()

    def begin(self, browser_binding: str) -> str:
        return self._begin(browser_binding, reauthentication=False)

    def begin_reauthentication(self, browser_binding: str, *, require_mfa: bool = False) -> str:
        if type(require_mfa) is not bool:
            raise IdentityLoginRejected
        return self._begin(browser_binding, reauthentication=True, require_mfa=require_mfa)

    def _begin(
        self, browser_binding: str, *, reauthentication: bool, require_mfa: bool = False
    ) -> str:
        if (
            type(browser_binding) is not str
            or not browser_binding.isascii()
            or not 32 <= len(browser_binding) <= 256
        ):
            raise IdentityLoginRejected
        now = self._clock()
        state, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        with self._lock:
            self._transactions = {
                key: value for key, value in self._transactions.items() if value.expires_at > now
            }
            if len(self._transactions) >= 128:
                raise IdentityLoginRejected
            self._transactions[state] = _Transaction(
                browser_binding,
                verifier,
                nonce,
                now + (REAUTHENTICATION_TRANSACTION_TTL_SECONDS if reauthentication else 180),
                reauthentication,
                now,
            )
        return (
            self.settings.authorization_endpoint
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "client_id": self.settings.client_id,
                    "redirect_uri": self.settings.redirect_uri,
                    "scope": "openid profile email",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge.decode().rstrip("="),
                    "code_challenge_method": "S256",
                    **({"max_age": "0", "prompt": "login"} if reauthentication else {}),
                    **({"acr_values": MFA_AUTHENTICATION_CONTEXT} if require_mfa else {}),
                }
            )
        )

    def finish(self, *, state: str, code: str, browser_binding: str) -> VerifiedIdentity:
        return self._finish(state, code, browser_binding, reauthentication=False).identity

    def finish_reauthentication(
        self, *, state: str, code: str, browser_binding: str
    ) -> FreshIdentityAuthentication:
        return self._finish(state, code, browser_binding, reauthentication=True)

    def _finish(self, state, code, browser_binding, *, reauthentication):
        if type(state) is not str or not 1 <= len(state) <= 128:
            raise IdentityLoginRejected
        with self._lock:
            transaction = self._transactions.pop(state, None)
        if (
            transaction is None
            or transaction.reauthentication is not reauthentication
            or type(code) is not str
            or not 1 <= len(code) <= 4096
            or type(browser_binding) is not str
            or not browser_binding.isascii()
            or not 32 <= len(browser_binding) <= 256
            or transaction.expires_at <= self._clock()
            or not hmac.compare_digest(transaction.binding, browser_binding)
        ):
            raise IdentityLoginRejected
        try:
            response = self._exchange(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.settings.client_id,
                    "redirect_uri": self.settings.redirect_uri,
                    "code_verifier": transaction.verifier,
                }
            )
            token = response.get("id_token") if type(response) is dict else None
            if type(token) is not str or len(token) > 16384:
                raise IdentityLoginRejected
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or type(header.get("kid")) is not str:
                raise IdentityLoginRejected
            key = self._signing_key(token)
            claims = jwt.decode(
                token,
                getattr(key, "key", key),
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.client_id,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
                leeway=5,
            )
            if (
                type(claims.get("nonce")) is not str
                or not hmac.compare_digest(claims["nonce"], transaction.nonce)
                or type(claims.get("sub")) is not str
                or not 1 <= len(claims["sub"]) <= 255
                or any(ord(c) < 32 for c in claims["sub"])
                or type(claims["exp"]) not in (int, float)
                or type(claims["iat"]) not in (int, float)
                or (claims.get("azp") is not None and claims["azp"] != self.settings.client_id)
                or (type(claims["aud"]) is list and len(claims["aud"]) > 1 and "azp" not in claims)
            ):
                raise IdentityLoginRejected
            auth_time = claims.get("auth_time")
            if reauthentication and (
                type(auth_time) is not int
                or auth_time < int(transaction.requested_at)
                or auth_time > self._clock() + 5
                or auth_time > claims["iat"] + 5
                or self._clock() - auth_time > FRESH_AUTHENTICATION_MAX_AGE_SECONDS
            ):
                raise IdentityLoginRejected
            methods = claims.get("amr", [])
            if reauthentication and (
                type(methods) is not list
                or len(methods) > 16
                or any(type(value) is not str or not 1 <= len(value) <= 64 for value in methods)
            ):
                raise IdentityLoginRejected
            # Email/name/picture and raw tokens are neither ownership keys nor persisted.
            return FreshIdentityAuthentication(
                VerifiedIdentity(self.settings.issuer, claims["sub"]),
                auth_time if reauthentication else 0,
                tuple(methods) if reauthentication else (),
            )
        except Exception:  # noqa: BLE001 - upstream credentials never enter error output
            raise IdentityLoginRejected from None


class StableAccountAdmission:
    """Server allowlist plus a persistent key produce retry/erasure-stable IDs.

    The key and admitted subjects are deployment configuration, never tool input.
    Key rotation must retain previous admissions/tombstones; replacing the key is
    not a supported way to re-enroll deleted identities.
    """

    def __init__(self, *, issuer: str, secret: bytes, admitted_subjects: frozenset[str]):
        _url(issuer)
        if (
            len(issuer) > 512
            or type(secret) is not bytes
            or len(secret) < 32
            or type(admitted_subjects) is not frozenset
            or any(
                type(sub) is not str or not 1 <= len(sub) <= 255 or any(ord(c) < 32 for c in sub)
                for sub in admitted_subjects
            )
        ):
            raise ValueError("Invalid account admission configuration")
        self._issuer, self._secret, self._subjects = issuer, secret, admitted_subjects

    def __call__(self, identity: VerifiedIdentity) -> str | None:
        if (
            type(identity) is not VerifiedIdentity
            or identity.issuer != self._issuer
            or identity.subject not in self._subjects
        ):
            return None
        material = (
            b"CG_ACCOUNT_ADMISSION_V1\0"
            + identity.issuer.encode()
            + b"\0"
            + identity.subject.encode()
        )
        digest = hmac.new(self._secret, material, hashlib.sha256).digest()
        return str(UUID(bytes=digest[:16], version=5))

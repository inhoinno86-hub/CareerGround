"""Bounded public metadata fetch and RAM-only verification-key cache.

Only the reviewed issuer's fixed URLs are used; tokens cannot supply fetch URLs.
"""

import threading
import time
from urllib.parse import urlsplit

import httpx
import jwt

from .oidc import AccessTokenPolicy
from .session import Rejected, parse


class ProviderVerifier:
    def __init__(self, config, *, transport=None, clock=time.monotonic):
        issuer = config["issuer"]
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port
            or parsed.path != "/"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Fixed HTTPS tenant issuer required")
        self.issuer = issuer
        self.audience, self.client_id = config["audience"], config["client_id"]
        self._transport, self._clock = transport, clock
        self._lock = threading.Lock()
        self._policy = None
        self._updated = float("-inf")
        self._attempted = float("-inf")
        metadata = self._fetch(".well-known/openid-configuration")
        expected = {
            "issuer": issuer,
            "jwks_uri": issuer + ".well-known/jwks.json",
            "authorization_endpoint": issuer + "authorize",
            "token_endpoint": issuer + "oauth/token",
        }
        if any(metadata.get(k) != v for k, v in expected.items()) or (
            "S256" not in metadata.get("code_challenge_methods_supported", [])
        ):
            raise ValueError("Provider metadata does not match reviewed configuration")
        self._refresh()

    def _fetch(self, path):
        try:
            with (
                httpx.Client(
                    timeout=10, follow_redirects=False, transport=self._transport, trust_env=False
                ) as client,
                client.stream(
                    "GET", self.issuer + path, headers={"Accept": "application/json"}
                ) as response,
            ):
                if response.status_code != 200:
                    raise ValueError("metadata status")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise ValueError("metadata bound")
            value = parse(bytes(raw), 65536)
            if not isinstance(value, dict):
                raise TypeError("metadata object")
            return value
        except (httpx.HTTPError, ValueError, TypeError, Rejected) as error:
            raise Rejected("OIDC_KEYS_UNAVAILABLE", status=503) from error

    def _refresh(self):
        self._attempted = self._clock()
        try:
            policy = AccessTokenPolicy(
                issuer=self.issuer,
                audience=self.audience,
                client_id=self.client_id,
                jwks=self._fetch(".well-known/jwks.json"),
            )
        except ValueError as error:
            raise Rejected("OIDC_KEYS_UNAVAILABLE", status=503) from error
        self._policy, self._updated = policy, self._clock()

    def verify(self, token):
        if not isinstance(token, str) or not 1 <= len(token) <= 16384:
            raise Rejected("UNAUTHENTICATED", status=401)
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 128
                or any(k in header for k in ("jku", "x5u", "crit"))
            ):
                raise ValueError("header")
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise Rejected("UNAUTHENTICATED", status=401) from error
        with self._lock:
            now = self._clock()
            if now - self._updated >= 300:
                if now - self._attempted < 30:
                    raise Rejected("OIDC_KEYS_UNAVAILABLE", status=503)
                self._refresh()
            elif kid not in self._policy._keys and now - self._attempted >= 30:
                self._refresh()
            policy = self._policy
        return policy.verify(token)

"""Offline OIDC access-token policy, shared by the actual OIDC runtime.

The caller must supply a reviewed issuer, client, audience and trusted public JWKS.
No discovery, network fetch, login, token persistence or provider registration here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from .session import Rejected


@dataclass(frozen=True)
class Principal:
    owner_binding: str
    expires_at: int


class AccessTokenPolicy:
    def __init__(self, *, issuer, audience, client_id, jwks):
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not issuer.endswith("/")
            or not isinstance(audience, str)
            or not audience
            or not isinstance(client_id, str)
            or not client_id
        ):
            raise ValueError("Explicit HTTPS issuer, audience and native client required")
        if not isinstance(jwks, dict) or set(jwks) != {"keys"}:
            raise ValueError("Trusted public JWKS required")
        rows = jwks["keys"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
            raise ValueError("Bounded public JWKS required")
        keys = {}
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("kty") != "RSA"
                or row.get("alg", "RS256") != "RS256"
                or row.get("use", "sig") != "sig"
                or row.get("key_ops", ["verify"]) != ["verify"]
                or any(name in row for name in ("d", "p", "q", "dp", "dq", "qi", "oth"))
                or not isinstance(row.get("kid"), str)
                or not 1 <= len(row["kid"]) <= 128
                or row["kid"] in keys
            ):
                raise ValueError("Unique public RS256 signing keys required")
            try:
                key = jwt.PyJWK.from_dict(row, algorithm="RS256").key
            except (jwt.PyJWTError, ValueError, TypeError, KeyError) as error:
                raise ValueError("Invalid public signing key") from error
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError("RSA public key must be at least 2048 bits")
            keys[row["kid"]] = key
        self._keys = keys
        self._issuer, self._audience, self._client_id = issuer, audience, client_id

    def verify(self, token: str) -> Principal:
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise ValueError("token bound")
            header = jwt.get_unverified_header(token)
            # Never fetch keys from a token-supplied URL or choose its algorithm.
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or header.get("typ", "JWT") not in {"JWT", "at+jwt"}
                or any(name in header for name in ("jku", "x5u", "crit"))
                or not isinstance(kid, str)
                or kid not in self._keys
            ):
                raise ValueError("header policy")
            claims = jwt.decode(
                token,
                self._keys[kid],
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["iss", "aud", "sub", "exp", "iat"]},
                leeway=0,
            )
            if (
                not isinstance(claims["sub"], str)
                or not 1 <= len(claims["sub"]) <= 256
                or type(claims["exp"]) is not int
                or type(claims["iat"]) is not int
                or not isinstance(claims.get("scope"), str)
                or "use:interview" not in claims["scope"].split()
                or not any(name in claims for name in ("azp", "client_id"))
                or any(
                    claims[name] != self._client_id
                    for name in ("azp", "client_id")
                    if name in claims
                )
            ):
                raise ValueError("claims policy")
            binding = hashlib.sha256(
                (self._issuer + "\x00" + claims["sub"]).encode("utf-8", errors="strict")
            ).hexdigest()
            return Principal(owner_binding="oidc-" + binding, expires_at=claims["exp"])
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError) as error:
            raise Rejected("UNAUTHENTICATED", status=401) from error

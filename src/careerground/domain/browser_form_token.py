"""Small HMAC envelope for synthetic browser forms; callers validate purpose and fields."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping


class BrowserFormTokenRejected(Exception):
    """The signed form token is malformed, modified, or has unexpected fields."""


class BrowserFormTokenCodec:
    def __init__(self, signing_secret: bytes) -> None:
        if not isinstance(signing_secret, bytes) or len(signing_secret) < 32:
            raise ValueError("browser form signing secret too short")
        self._secret = signing_secret

    def sign(self, payload: Mapping[str, object]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_b64(body)}.{_b64(signature)}"

    def verify(self, token: str, *, expected_keys: frozenset[str]) -> dict[str, object]:
        if not isinstance(token, str) or len(token) > 4096 or token.count(".") != 1:
            raise BrowserFormTokenRejected
        try:
            body_text, signature_text = token.split(".")
            body = _unb64(body_text)
            signature = _unb64(signature_text)
            payload = json.loads(body)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise BrowserFormTokenRejected from exc
        if (
            len(signature) != hashlib.sha256().digest_size
            or not hmac.compare_digest(
                signature, hmac.new(self._secret, body, hashlib.sha256).digest()
            )
            or type(payload) is not dict
            or set(payload) != expected_keys
        ):
            raise BrowserFormTokenRejected
        return payload


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or len(value) % 4 == 1:
        raise ValueError("invalid base64")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)

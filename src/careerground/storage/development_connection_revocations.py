"""Opt-in, single-process local connection denial; no provider grant mutation.

Stores only keyed identity/client digests in a separate private directory. This
is not enabled by a normal runtime and has no model-facing mutation interface.
Restoring the entire directory to an old version requires an independent anchor;
the local signature alone cannot detect that rollback.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import secrets
import stat
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit

from mcp.server.auth.provider import AccessToken

from careerground.domain.authorization import VerifiedIdentity
from careerground.storage.development_files import (
    DevelopmentStoreRejected,
    _new_file,
    _private_file,
    _replace_private,
)


class DevelopmentConnectionRevocations:
    def __init__(self, path: Path, *, issuer: str, initialize: bool = False):
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path != "/"
            or parsed.query
            or parsed.fragment
            or not issuer.endswith("/")
            or type(initialize) is not bool
        ):
            raise DevelopmentStoreRejected
        self.path, self.issuer = Path(path), issuer
        self._fd = None
        self._lock = RLock()
        if (
            not self.path.is_absolute()
            or ".." in self.path.parts
            or any(p.is_symlink() for p in (self.path, *self.path.parents))
        ):
            raise DevelopmentStoreRejected
        fresh = not self.path.exists()
        if fresh and not initialize:
            raise DevelopmentStoreRejected
        if fresh:
            self.path.mkdir(mode=0o700)
        mode = self.path.lstat()
        if (
            not stat.S_ISDIR(mode.st_mode)
            or mode.st_uid != os.getuid()
            or stat.S_IMODE(mode.st_mode) != 0o700
        ):
            raise DevelopmentStoreRejected
        try:
            if not fresh and {p.name for p in self.path.iterdir()} != {
                "key",
                "denials.json",
                "lock",
            }:
                raise DevelopmentStoreRejected
            self._fd = os.open(self.path / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            _private_file(self.path / "lock", expected_size=0)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if fresh:
                _new_file(self.path / "key", secrets.token_bytes(32))
            self._key = _private_file(self.path / "key", expected_size=32)
            if fresh:
                _new_file(self.path / "denials.json", self._encode([]))
            self._read()
        except BaseException:
            self.close()
            raise

    def _encode(self, entries):
        payload = {"version": 1, "issuer": self.issuer, "denials": entries}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return json.dumps(
            {
                "payload": payload,
                "signature": hmac.new(self._key, body, hashlib.sha256).hexdigest(),
            },
            sort_keys=True,
        ).encode()

    def _read(self):
        try:
            envelope = json.loads(_private_file(self.path / "denials.json", max_size=400000))
            payload = envelope["payload"]
            entries = payload["denials"]
            if (
                set(envelope) != {"payload", "signature"}
                or set(payload) != {"version", "issuer", "denials"}
                or type(payload["version"]) is not int
                or payload["version"] != 1
                or payload["issuer"] != self.issuer
                or type(entries) is not list
                or len(entries) > 4096
                or any(
                    type(item) is not str
                    or len(item) != 64
                    or any(c not in "0123456789abcdef" for c in item)
                    for item in entries
                )
                or entries != sorted(set(entries))
                or self._encode(entries)
                != _private_file(self.path / "denials.json", max_size=400000)
            ):
                raise DevelopmentStoreRejected
            return entries
        except (OSError, ValueError, KeyError, TypeError, DevelopmentStoreRejected):
            raise DevelopmentStoreRejected from None

    def _digest(self, subject: str, client_id: str):
        if any(type(v) is not str or not 1 <= len(v) <= 255 for v in (subject, client_id)):
            raise DevelopmentStoreRejected
        return hmac.new(
            self._key, json.dumps([self.issuer, subject, client_id]).encode(), hashlib.sha256
        ).hexdigest()

    def block(self, identity: VerifiedIdentity, client_id: str):
        """Trusted local caller only; no raw token, model ID, or public route."""
        if type(identity) is not VerifiedIdentity or identity.issuer != self.issuer:
            raise DevelopmentStoreRejected
        with self._lock:
            entries = self._read()
            digest = self._digest(identity.subject, client_id)
            if digest not in entries:
                if len(entries) >= 4096:
                    raise DevelopmentStoreRejected
                _replace_private(
                    self.path / "denials.json", self._encode(sorted([*entries, digest]))
                )

    def is_revoked(self, access: AccessToken) -> bool:
        """Called only after signature/issuer/audience/scope validation by the gate."""
        with self._lock:
            return self._digest(access.subject, access.client_id) in self._read()

    def close(self):
        """Release the exclusive local registry lock."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._key = None

    def is_blocked(self, identity: VerifiedIdentity, client_id: str) -> bool:
        """Trusted Web owner status; does not turn a cookie into an access token."""
        if type(identity) is not VerifiedIdentity or identity.issuer != self.issuer:
            raise DevelopmentStoreRejected
        with self._lock:
            return self._digest(identity.subject, client_id) in self._read()

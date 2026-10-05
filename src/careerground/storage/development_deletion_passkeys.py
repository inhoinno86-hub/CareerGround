"""Opt-in single-process WebAuthn credentials for isolated development deletion.

Public keys only. Exact store/origin binding; no identity-provider account linking,
passwords, model routes or automatic enrollment/recovery. Entire-directory rollback
and a compromised local operator require an independent production trust boundary.
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

from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from careerground.storage.development_files import (
    DevelopmentStoreRejected,
    _new_file,
    _private_file,
    _replace_private,
)


class DevelopmentDeletionPasskeys:
    def __init__(self, path: Path, *, origin: str, store_binding: str, initialize: bool = False):
        url = urlsplit(origin)
        if (
            url.scheme not in {"http", "https"}
            or url.hostname not in {"localhost", "127.0.0.1"}
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
            or type(store_binding) is not str
            or len(store_binding) != 64
            or any(c not in "0123456789abcdef" for c in store_binding)
            or type(initialize) is not bool
        ):
            raise DevelopmentStoreRejected
        self.path, self.origin, self.rp_id = Path(path), origin, url.hostname
        self.binding = {"origin": origin, "store": store_binding}
        self._fd, self._key, self._lock = None, None, RLock()
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
            if not fresh and {p.name for p in self.path.iterdir()} != {"key", "keys.json", "lock"}:
                raise DevelopmentStoreRejected
            self._fd = os.open(self.path / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            _private_file(self.path / "lock", expected_size=0)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if fresh:
                _new_file(self.path / "key", secrets.token_bytes(32))
            self._key = _private_file(self.path / "key", expected_size=32)
            if fresh:
                _new_file(self.path / "keys.json", self._encode({}))
            self._read()
        except BaseException:
            self.close()
            raise

    def _encode(self, records):
        payload = {"version": 1, "binding": self.binding, "credentials": records}
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
            raw = _private_file(self.path / "keys.json", max_size=1_000_000)
            envelope = json.loads(raw)
            payload, records = envelope["payload"], envelope["payload"]["credentials"]
            if (
                set(envelope) != {"payload", "signature"}
                or set(payload) != {"version", "binding", "credentials"}
                or type(payload["version"]) is not int
                or payload["version"] != 1
                or payload["binding"] != self.binding
                or type(records) is not dict
                or len(records) > 128
                or not hmac.compare_digest(raw, self._encode(records))
            ):
                raise DevelopmentStoreRejected
            ids = set()
            for owner, row in records.items():
                if (
                    len(owner) != 64
                    or any(c not in "0123456789abcdef" for c in owner)
                    or set(row) != {"id", "public_key", "count"}
                    or any(type(row[k]) is not str for k in ("id", "public_key"))
                    or not 1 <= len(base64url_to_bytes(row["id"])) <= 1024
                    or not 1 <= len(base64url_to_bytes(row["public_key"])) <= 4096
                    or type(row["count"]) is not int
                    or not 0 <= row["count"] <= 2**32 - 1
                    or row["id"] in ids
                ):
                    raise DevelopmentStoreRejected
                ids.add(row["id"])
            return records
        except Exception:  # noqa: BLE001 - credential/parser payloads are private
            raise DevelopmentStoreRejected from None

    def _owner(self, account_id):
        if type(account_id) is not str or not 1 <= len(account_id) <= 255:
            raise DevelopmentStoreRejected
        return hmac.new(self._key, account_id.encode(), hashlib.sha256).hexdigest()

    def has_credential(self, account_id):
        with self._lock:
            return self._owner(account_id) in self._read()

    def registration_options(self, account_id, challenge):
        with self._lock:
            records = self._read()
            if self._owner(account_id) in records or len(records) >= 128:
                raise DevelopmentStoreRejected
            return json.loads(
                options_to_json(
                    generate_registration_options(
                        rp_id=self.rp_id,
                        rp_name="CareerGround development deletion",
                        user_id=bytes.fromhex(self._owner(account_id)),
                        user_name="CareerGround local profile",
                        challenge=challenge,
                        authenticator_selection=AuthenticatorSelectionCriteria(
                            resident_key=ResidentKeyRequirement.PREFERRED,
                            user_verification=UserVerificationRequirement.REQUIRED,
                        ),
                        timeout=120000,
                    )
                )
            )

    def register(self, account_id, challenge, credential):
        """Caller must have a consumed, fresh, same-owner enrollment ceremony."""
        with self._lock:
            records = self._read()
            owner = self._owner(account_id)
            if owner in records or len(records) >= 128:
                raise DevelopmentStoreRejected
            verified = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                require_user_verification=True,
            )
            credential_id = bytes_to_base64url(verified.credential_id)
            if any(row["id"] == credential_id for row in records.values()):
                raise DevelopmentStoreRejected
            records[owner] = {
                "id": credential_id,
                "public_key": bytes_to_base64url(verified.credential_public_key),
                "count": verified.sign_count,
            }
            _replace_private(self.path / "keys.json", self._encode(records))

    def authentication_options(self, account_id, challenge):
        with self._lock:
            row = self._read()[self._owner(account_id)]
            return json.loads(
                options_to_json(
                    generate_authentication_options(
                        rp_id=self.rp_id,
                        challenge=challenge,
                        allow_credentials=[
                            PublicKeyCredentialDescriptor(id=base64url_to_bytes(row["id"]))
                        ],
                        user_verification=UserVerificationRequirement.REQUIRED,
                        timeout=120000,
                    )
                )
            )

    def verify(self, account_id, challenge, credential):
        """Verify signed UP/UV, origin, RP, challenge, owner key and counter."""
        with self._lock:
            records = self._read()
            row = records[self._owner(account_id)]
            verified = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                credential_public_key=base64url_to_bytes(row["public_key"]),
                credential_current_sign_count=row["count"],
                require_user_verification=True,
            )
            if verified.credential_id != base64url_to_bytes(row["id"]):
                raise DevelopmentStoreRejected
            # A non-discoverable response can omit userHandle; if provided it
            # must match our opaque per-account user ID, never choose an owner.
            response = json.loads(credential) if type(credential) is str else credential
            handle = response["response"].get("userHandle")
            if handle is not None and base64url_to_bytes(handle) != bytes.fromhex(
                self._owner(account_id)
            ):
                raise DevelopmentStoreRejected
            row["count"] = verified.new_sign_count
            _replace_private(self.path / "keys.json", self._encode(records))

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._key = None

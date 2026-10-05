"""Restart-safe, single-process authenticated development data; synthetic text only.

Uses its own marker and keys, never opens or upgrades the synthetic demo store.
The issuer/client/resource binding cannot be changed by editing runtime flags.
Sessions stay process-local. This is not a production signup or backup service.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import stat
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from careerground.development_runtime import (
    _check_sqlite_integrity,
    _expected_schema_signatures,
    _schema_signature,
)
from careerground.domain.authorization import VerifiedIdentity
from careerground.providers.oidc_identity import IdentityClientSettings, StableAccountAdmission
from careerground.storage.development_checkpoint import SignedDeletionCheckpoint
from careerground.storage.development_files import (
    DevelopmentStoreRejected,
    _new_file,
    _private_file,
    _sqlite_engine,
)
from careerground.storage.models import Account, AuthIdentity, Base
from careerground.workers.restore_quarantine import signed_manifest

_MARKER_NAME = ".careerground-authenticated-v1"
_MARKER = b"careerground-authenticated-development-v1\n"
_KEYS = ("admission.key", "review.key", "presentation.key", "ledger.key", "status.key")
_FILES = {
    _MARKER_NAME,
    "binding.json",
    "key-digests.json",
    "authenticated.sqlite",
    ".runtime.lock",
    "ledger.json",
    "manifest",
    *_KEYS,
}


class AuthenticatedDevelopmentStore(SignedDeletionCheckpoint):
    def __init__(self, state_dir: Path, client: IdentityClientSettings, resource_url: str):
        raw = Path(state_dir).expanduser()
        if not raw.is_absolute() or ".." in raw.parts:
            raise DevelopmentStoreRejected
        if any(ancestor.is_symlink() for ancestor in (raw, *raw.parents)):
            raise DevelopmentStoreRejected
        self.state_dir = raw
        self.engine = None
        self._lock_fd = None
        self.client = client
        # No token, secret, subject, email or career text enters this binding.
        binding = (
            json.dumps(
                {"issuer": client.issuer, "client_id": client.client_id, "resource": resource_url},
                sort_keys=True,
            )
            + "\n"
        ).encode()
        fresh = not raw.exists()
        if fresh:
            raw.mkdir(mode=0o700)
        mode = raw.lstat()
        if (
            not stat.S_ISDIR(mode.st_mode)
            or mode.st_uid != os.getuid()
            or stat.S_IMODE(mode.st_mode) != 0o700
        ):
            raise DevelopmentStoreRejected
        if not fresh:
            if {p.name for p in raw.iterdir()} != _FILES:
                raise DevelopmentStoreRejected
            if _private_file(raw / _MARKER_NAME, expected_size=len(_MARKER)) != _MARKER:
                raise DevelopmentStoreRejected
            if _private_file(raw / "binding.json", max_size=4096) != binding:
                raise DevelopmentStoreRejected
        try:
            fd = os.open(raw / ".runtime.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            self._lock_fd = fd
            mode = os.fstat(fd)
            if (
                not stat.S_ISREG(mode.st_mode)
                or mode.st_uid != os.getuid()
                or stat.S_IMODE(mode.st_mode) != 0o600
            ):
                raise DevelopmentStoreRejected
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if fresh:
                if {p.name for p in raw.iterdir()} != {".runtime.lock"}:
                    raise DevelopmentStoreRejected
                for name in _KEYS:
                    _new_file(raw / name, secrets.token_bytes(32))
                _new_file(raw / "binding.json", binding)
                _new_file(raw / "authenticated.sqlite", b"")
                _new_file(raw / "ledger.json", b"[]\n")
                _new_file(
                    raw / "manifest",
                    (
                        signed_manifest(
                            [], secret=_private_file(raw / "ledger.key", expected_size=32)
                        )
                        + "\n"
                    ).encode(),
                )
            for name in _KEYS:
                setattr(
                    self,
                    name.replace(".key", "_secret"),
                    _private_file(raw / name, expected_size=32),
                )
            key_digests = {
                name: hashlib.sha256(getattr(self, name.replace(".key", "_secret"))).hexdigest()
                for name in _KEYS
            }
            digest_bytes = (json.dumps(key_digests, sort_keys=True) + "\n").encode()
            if fresh:
                _new_file(raw / "key-digests.json", digest_bytes)
            elif _private_file(raw / "key-digests.json", max_size=4096) != digest_bytes:
                raise DevelopmentStoreRejected
            self.database_path = raw / "authenticated.sqlite"
            _private_file(self.database_path)
            self.engine = _sqlite_engine(self.database_path)
            if fresh:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    Base.metadata.create_all(connection)
            if _schema_signature(self.engine) != _expected_schema_signatures()[0]:
                raise DevelopmentStoreRejected
            _check_sqlite_integrity(self.engine)
            self.sessions = sessionmaker(self.engine)
            self._reconcile_checkpoint(self.sessions)
            with self.sessions() as session:
                for identity in session.scalars(select(AuthIdentity)):
                    expected = self.admit(VerifiedIdentity(identity.issuer, identity.subject))
                    account = session.get(Account, identity.account_id)
                    if expected != identity.account_id or account is None:
                        raise DevelopmentStoreRejected
            if fresh:
                _new_file(raw / _MARKER_NAME, _MARKER)
            # Ensure the marker/keys and initialized SQLite directory entries persist.
            directory_fd = os.open(raw, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            self.close()
            raise

    def admit(self, identity: VerifiedIdentity) -> str | None:
        return StableAccountAdmission(
            issuer=self.client.issuer,
            secret=self.admission_secret,
            admitted_subjects=frozenset({identity.subject}),
        )(identity)

    def close(self):
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
        for name in _KEYS:
            setattr(self, name.replace(".key", "_secret"), None)

    @property
    def binding_digest(self) -> str:
        return hashlib.sha256(
            _private_file(self.state_dir / "binding.json", max_size=4096)
        ).hexdigest()

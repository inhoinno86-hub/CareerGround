"""Private local store files shared by synthetic and authenticated runtimes."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from sqlalchemy import create_engine, event


class DevelopmentStoreRejected(Exception):
    """The supplied directory, schema, key, or independent erasure checkpoint is unsafe."""


def _private_file(
    path: Path, *, expected_size: int | None = None, max_size: int | None = None
) -> bytes:
    try:
        mode = path.lstat()
    except OSError:
        raise DevelopmentStoreRejected from None
    if (
        not stat.S_ISREG(mode.st_mode)
        or mode.st_uid != os.getuid()
        or stat.S_IMODE(mode.st_mode) != 0o600
    ):
        raise DevelopmentStoreRejected
    if expected_size is not None and mode.st_size != expected_size:
        raise DevelopmentStoreRejected
    if max_size is not None and mode.st_size > max_size:
        raise DevelopmentStoreRejected
    try:
        return path.read_bytes()
    except OSError:
        raise DevelopmentStoreRejected from None


def _new_file(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _replace_private(path: Path, content: bytes) -> None:
    temporary = path.with_name("." + path.name + "-" + secrets.token_hex(8))
    _new_file(temporary, content)
    try:
        os.replace(temporary, path)
        folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        temporary.unlink(missing_ok=True)


def _sqlite_engine(path: Path):
    engine = create_engine("sqlite+pysqlite:///" + str(path), hide_parameters=True)

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    return engine

"""Owned loopback synthetic development store with restart-safe local data.

This is not a production authentication service. Only a newly marked owner-only
directory can be opened. Browser sessions and RS256 connection tokens are
deliberately process-local; canonical SQLite data and review keys persist.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import secrets
import socket
import sqlite3
import stat
import time
from contextlib import closing
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

import uvicorn
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, MetaData, create_engine, event, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from careerground.domain.deletion_execution import ledger_signature
from careerground.domain.synthetic_deletion_journey import MockDeletionJourney
from careerground.local_demo import ACCOUNTS, ISSUER, LocalDemo
from careerground.storage.models import Account, AuthIdentity, Base, CareerProfile, ErasureLedger
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

_MARKER = b"careerground-synthetic-development-v1\n"
_DB = "synthetic.sqlite"
_KEY_NAMES = ("review.key", "presentation.key", "ledger.key", "status.key")
_LOCK = ".runtime.lock"
_FILES = {".careerground-development-v1", _DB, *_KEY_NAMES, "ledger.json", "manifest", _LOCK}
_LEDGER_FIELDS = frozenset(
    {"request_id", "account_id", "scope", "target_id", "created_at", "signature"}
)
_LEGACY_REVISION = "20261001_0019"
_CURRENT_REVISION = "20261003_0020"


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


def _schema_signature(engine) -> tuple:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.connect() as connection:
        ancillary = tuple(
            connection.exec_driver_sql(
                "SELECT type, name FROM sqlite_master WHERE type IN ('trigger', 'view') ORDER BY type, name"
            )
        )
        header = (
            connection.exec_driver_sql("PRAGMA user_version").scalar(),
            connection.exec_driver_sql("PRAGMA application_id").scalar(),
        )
    result = []
    for table in sorted(tables):
        columns = tuple(
            sorted(
                (c["name"], str(c["type"]), bool(c["nullable"]), c["primary_key"], c["default"])
                for c in inspector.get_columns(table)
            )
        )
        foreign_keys = tuple(
            sorted(
                (
                    fk["name"] or "",
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                    fk["options"].get("ondelete") or "",
                )
                for fk in inspector.get_foreign_keys(table)
            )
        )
        unique = tuple(
            sorted(
                (item["name"] or "", tuple(item["column_names"]))
                for item in inspector.get_unique_constraints(table)
            )
        )
        checks = tuple(
            sorted(
                (item["name"] or "", " ".join(item["sqltext"].split()))
                for item in inspector.get_check_constraints(table)
            )
        )
        indexes = tuple(
            sorted(
                (item["name"], tuple(item["column_names"]), bool(item["unique"]))
                for item in inspector.get_indexes(table)
            )
        )
        primary = tuple(inspector.get_pk_constraint(table)["constrained_columns"])
        options = tuple(sorted(inspector.get_table_options(table).items()))
        result.append((table, columns, foreign_keys, unique, checks, indexes, primary, options))
    return tuple(result), ancillary, header


def _legacy_metadata() -> MetaData:
    """The exact synthetic 0019 DDL: current metadata minus 0020's changes."""
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name != "project_scopes":
            table.to_metadata(metadata)
    for table_name, column_name, constraint_name in (
        ("artifacts", "source_artifact_id", "fk_artifact_owned_source"),
        ("artifact_units", "source_artifact_unit_id", "fk_artifact_unit_owned_source"),
    ):
        table = metadata.tables[table_name]
        table.constraints.remove(next(c for c in table.constraints if c.name == constraint_name))
        table._columns.remove(table.c[column_name])
    metadata.tables["browser_operations"]._columns.remove(
        metadata.tables["browser_operations"].c.export_options_json
    )
    for name in ("profile_id", "profile_version_after"):
        metadata.tables["erasure_ledger"]._columns.remove(metadata.tables["erasure_ledger"].c[name])
    for table_name, constraint_name, expression in (
        ("deletion_requests", "ck_deletion_requests_scope", "scope IN ('ACCOUNT', 'PROFILE')"),
        ("erasure_ledger", "ck_erasure_ledger_scope", "scope IN ('ACCOUNT', 'PROFILE')"),
        ("artifact_wording_reviews", "ck_wording_review_action", "action IN ('ACCEPT_R1')"),
    ):
        table = metadata.tables[table_name]
        table.constraints.remove(next(c for c in table.constraints if c.name == constraint_name))
        table.append_constraint(CheckConstraint(expression, name=constraint_name))
    return metadata


@lru_cache(maxsize=1)
def _expected_schema_signatures() -> tuple[tuple, tuple]:
    current_engine = create_engine("sqlite+pysqlite://", hide_parameters=True)
    legacy_engine = create_engine("sqlite+pysqlite://", hide_parameters=True)
    try:
        Base.metadata.create_all(current_engine)
        _legacy_metadata().create_all(legacy_engine)
        return _schema_signature(current_engine), _schema_signature(legacy_engine)
    finally:
        current_engine.dispose()
        legacy_engine.dispose()


def _check_sqlite_integrity(engine) -> None:
    with engine.connect() as connection:
        if connection.exec_driver_sql("PRAGMA integrity_check").scalar() != "ok":
            raise DevelopmentStoreRejected
        if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
            raise DevelopmentStoreRejected


def _legacy_data_digest(connection: sqlite3.Connection, legacy_signature: tuple) -> str:
    """Compare every pre-existing cell before and after DDL, without logging data."""
    digest = hashlib.sha256()
    for table, columns, *_ in legacy_signature[0]:
        names = tuple(column[0] for column in columns)
        quoted = ",".join('"' + name + '"' for name in names)
        rows = connection.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
        digest.update(table.encode())
        for row in sorted(rows, key=repr):
            digest.update(repr(row).encode())
    return digest.hexdigest()


class DevelopmentRuntime(LocalDemo):
    """LocalDemo's Web/MCP application over one explicitly marked SQLite store."""

    def __init__(self, port: int, state_dir: str | Path, *, upgrade_store: bool = False):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid local port")
        if not isinstance(state_dir, (str, Path)):
            raise DevelopmentStoreRejected
        raw = Path(state_dir).expanduser()
        if type(upgrade_store) is not bool:
            raise DevelopmentStoreRejected
        if not raw.is_absolute() or ".." in raw.parts:
            raise DevelopmentStoreRejected
        for ancestor in (raw, *raw.parents):
            if ancestor.is_symlink():
                raise DevelopmentStoreRejected
        self.state_dir = raw
        self._new = not raw.exists()
        self._upgrade_store = upgrade_store
        self.upgrade_backup_path: Path | None = None
        if self._new and upgrade_store:
            raise DevelopmentStoreRejected
        if self._new:
            raw.mkdir(mode=0o700)
        directory = raw.lstat()
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.getuid()
            or stat.S_IMODE(directory.st_mode) != 0o700
        ):
            raise DevelopmentStoreRejected
        if not self._new:
            marker = raw / ".careerground-development-v1"
            if _private_file(marker, expected_size=len(_MARKER)) != _MARKER:
                raise DevelopmentStoreRejected
        lock_path = raw / _LOCK
        self._lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            lock_mode = os.fstat(self._lock_fd)
            if (
                not stat.S_ISREG(lock_mode.st_mode)
                or lock_mode.st_uid != os.getuid()
                or stat.S_IMODE(lock_mode.st_mode) != 0o600
            ):
                raise DevelopmentStoreRejected
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            os.close(self._lock_fd)
            self._lock_fd = None
            raise DevelopmentStoreRejected from None
        except BaseException:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise
        try:
            self._open_store(port)
        except BaseException:
            if hasattr(self, "engine"):
                self.engine.dispose()
            self._release_lock()
            raise

    def _release_lock(self):
        fd = getattr(self, "_lock_fd", None)
        if fd is not None:
            self._lock_fd = None
            os.close(fd)

    def _open_store(self, port: int):
        raw = self.state_dir
        present = {item.name for item in raw.iterdir()}
        if self._new:
            if present != {_LOCK}:
                raise DevelopmentStoreRejected
            for name in _KEY_NAMES:
                _new_file(raw / name, secrets.token_bytes(32))
            _new_file(raw / "ledger.json", b"[]\n")
            _new_file(
                raw / "manifest",
                signed_manifest(
                    [], secret=_private_file(raw / "ledger.key", expected_size=32)
                ).encode()
                + b"\n",
            )
        elif present != _FILES:
            raise DevelopmentStoreRejected
        self.review_secret = _private_file(raw / "review.key", expected_size=32)
        self.presentation_secret = _private_file(raw / "presentation.key", expected_size=32)
        self.ledger_secret = _private_file(raw / "ledger.key", expected_size=32)
        self.status_secret = _private_file(raw / "status.key", expected_size=32)
        self.database_path = raw / _DB
        if self._new:
            _new_file(self.database_path, b"")
        else:
            _private_file(self.database_path)
        preflight_engine = _sqlite_engine(self.database_path)

        try:
            if self._new:
                # SQLite normally commits each DDL statement separately here.
                # A fresh, still unmarked store can initialize its schema in
                # one transaction and avoid dozens of disk syncs.
                with preflight_engine.begin() as connection:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    Base.metadata.create_all(connection)
            else:
                expected_current, expected_legacy = _expected_schema_signatures()
                actual = _schema_signature(preflight_engine)
                if actual == expected_legacy:
                    if not self._upgrade_store:
                        raise DevelopmentStoreRejected
                    preflight_engine.dispose()
                    self.upgrade_backup_path = self._upgrade_legacy_store(expected_legacy)
                    preflight_engine = _sqlite_engine(self.database_path)
                elif actual != expected_current:
                    raise DevelopmentStoreRejected
            self._validate_schema(preflight_engine)
            preflight_sessions = sessionmaker(preflight_engine)
            self._reconcile_checkpoint(preflight_sessions)
            if not self._new:
                self._validate_accounts(preflight_sessions)
        except (OSError, sqlite3.DatabaseError, SQLAlchemyError, ValueError) as exc:
            preflight_engine.dispose()
            raise DevelopmentStoreRejected from exc
        except BaseException:
            preflight_engine.dispose()
            raise
        preflight_engine.dispose()
        self.seed_accounts = self._new
        self._revoked: dict[str, int] = {}
        self._revoked_lock = Lock()
        self.deletion_journey = MockDeletionJourney(
            self.presentation_secret, self.ledger_secret, self.status_secret
        )
        super().__init__(port, runtime_store=self)
        if self._new:
            _new_file(raw / ".careerground-development-v1", _MARKER)

    def _validate_schema(self, engine):
        expected_current, _ = _expected_schema_signatures()
        if _schema_signature(engine) != expected_current:
            raise DevelopmentStoreRejected
        _check_sqlite_integrity(engine)

    def _upgrade_legacy_store(self, expected_legacy: tuple) -> Path:
        """Migrate a private sibling copy, validate it, then atomically replace SQLite."""
        raw = self.state_dir
        parent = raw.parent.lstat()
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o022
        ):
            raise DevelopmentStoreRejected
        # The signed independent checkpoint is checked before any copy or DDL.
        self._ledger_rows()
        original = _sqlite_engine(self.database_path)
        backup = raw.parent / f".{raw.name}-pre-{_CURRENT_REVISION}-{secrets.token_hex(12)}.sqlite"
        stage = raw.parent / f".{raw.name}-upgrade-{secrets.token_hex(12)}.sqlite"
        swapped = False
        try:
            if _schema_signature(original) != expected_legacy:
                raise DevelopmentStoreRejected
            _check_sqlite_integrity(original)
            _new_file(backup, b"")
            _new_file(stage, b"")
            with closing(sqlite3.connect(str(self.database_path))) as source:
                source.execute("PRAGMA query_only=ON")
                with closing(sqlite3.connect(str(backup))) as destination:
                    source.backup(destination)
            with closing(sqlite3.connect(str(backup))) as source:
                old_digest = _legacy_data_digest(source, expected_legacy)
                with closing(sqlite3.connect(str(stage))) as destination:
                    source.backup(destination)
            for path in (backup, stage):
                _private_file(path)
                with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                    os.fsync(stream.fileno())
            stage_engine = create_engine("sqlite+pysqlite:///" + str(stage), hide_parameters=True)
            try:
                # This migration rebuilds SQLite tables on the private copy.
                # Its transaction boundary is the final atomic file swap.
                migration_path = (
                    Path(__file__).resolve().parents[2]
                    / "migrations/versions/20261003_0020_local_contract_completion.py"
                )
                spec = importlib.util.spec_from_file_location(
                    "careerground_local_0020", migration_path
                )
                if spec is None or spec.loader is None:
                    raise DevelopmentStoreRejected
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                if (
                    migration.revision != _CURRENT_REVISION
                    or migration.down_revision != _LEGACY_REVISION
                ):
                    raise DevelopmentStoreRejected
                with stage_engine.begin() as connection:
                    context = MigrationContext.configure(connection)
                    with Operations.context(context):
                        migration.upgrade()
                self._validate_schema(stage_engine)
                with closing(sqlite3.connect(str(stage))) as connection:
                    if _legacy_data_digest(connection, expected_legacy) != old_digest:
                        raise DevelopmentStoreRejected
            finally:
                stage_engine.dispose()
            stage_preflight = _sqlite_engine(stage)
            try:
                sessions = sessionmaker(stage_preflight)
                self._reconcile_checkpoint(sessions)
                self._validate_accounts(sessions)
                self._validate_schema(stage_preflight)
            finally:
                stage_preflight.dispose()
            original.dispose()
            os.replace(stage, self.database_path)
            swapped = True
            folder = os.open(raw, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
            return backup
        except (OSError, sqlite3.DatabaseError, ImportError) as exc:
            raise DevelopmentStoreRejected from exc
        finally:
            original.dispose()
            stage.unlink(missing_ok=True)
            if not swapped:
                backup.unlink(missing_ok=True)

    @staticmethod
    def _validate_accounts(sessions):
        with sessions() as session:
            for label, (account_id, profile_id) in ACCOUNTS.items():
                account = session.get(Account, account_id)
                profile = session.get(CareerProfile, profile_id)
                identity = session.get(AuthIdentity, "demo-identity-" + label)
                if (
                    account is None
                    or profile is None
                    or profile.account_id != account_id
                    or (
                        account.status == "ACTIVE"
                        and (
                            identity is None
                            or identity.account_id != account_id
                            or identity.issuer != ISSUER
                            or identity.subject != "demo-subject-" + label
                        )
                    )
                ):
                    raise DevelopmentStoreRejected

    def _ledger_rows(self):
        raw = _private_file(self.state_dir / "ledger.json", max_size=1_000_000)
        try:
            records = json.loads(raw)
            if type(records) is not list or len(records) > 1000:
                raise DevelopmentStoreRejected
            rows = []
            for record in records:
                partial = type(record) is dict and record.get("scope") in {
                    "SESSION",
                    "EVIDENCE",
                    "PROJECT",
                }
                fields = (
                    _LEDGER_FIELDS | {"profile_id", "profile_version_after"}
                    if partial
                    else _LEDGER_FIELDS
                )
                if type(record) is not dict or set(record) != fields:
                    raise DevelopmentStoreRejected
                if any(type(record[key]) is not str for key in fields - {"profile_version_after"}):
                    raise DevelopmentStoreRejected
                if partial and (
                    not record["profile_id"]
                    or type(record["profile_version_after"]) is not int
                    or record["profile_version_after"] < 1
                ):
                    raise DevelopmentStoreRejected
                created = datetime.fromisoformat(record["created_at"])
                if created.tzinfo is None or created.utcoffset() is None:
                    raise DevelopmentStoreRejected
                row = ErasureLedger(
                    request_id=record["request_id"],
                    account_id=record["account_id"],
                    scope=record["scope"],
                    target_id=record["target_id"],
                    created_at=created.astimezone(UTC),
                    signature=record["signature"],
                    profile_id=record.get("profile_id"),
                    profile_version_after=record.get("profile_version_after"),
                )
                expected = ledger_signature(
                    self.ledger_secret,
                    request_id=row.request_id,
                    account_id=row.account_id,
                    scope=row.scope,
                    target_id=row.target_id,
                    created_at=row.created_at,
                    profile_id=row.profile_id,
                    profile_version_after=row.profile_version_after,
                )
                if not secrets.compare_digest(expected, row.signature):
                    raise DevelopmentStoreRejected
                rows.append(row)
            manifest = (
                _private_file(self.state_dir / "manifest", expected_size=65).decode("ascii").strip()
            )
            if not secrets.compare_digest(
                manifest, signed_manifest(rows, secret=self.ledger_secret)
            ):
                raise DevelopmentStoreRejected
            return rows
        except (UnicodeError, ValueError, KeyError, TypeError):
            raise DevelopmentStoreRejected from None

    def _reconcile_checkpoint(self, sessions):
        rows = self._ledger_rows()

        def identity(row):
            timestamp = row.created_at
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return (
                row.request_id,
                row.account_id,
                row.scope,
                row.target_id,
                row.profile_id,
                row.profile_version_after,
                timestamp.astimezone(UTC),
                row.signature,
            )

        identities = {identity(row) for row in rows}
        with sessions() as session:
            stored = {identity(row) for row in session.scalars(select(ErasureLedger))}
            if not stored.issubset(identities):
                raise DevelopmentStoreRejected
            if rows:
                gate = RestoreQuarantine()
                try:
                    gate.reconcile(
                        session,
                        ledger_rows=rows,
                        expected_manifest=signed_manifest(rows, secret=self.ledger_secret),
                        secret=self.ledger_secret,
                    )
                except QuarantineRejected:
                    raise DevelopmentStoreRejected from None

    def before_deletion_commit(self, session):
        """Write the independent signed checkpoint before the DB commit.

        A crash can leave a checkpoint ahead of SQLite; startup then either
        safely reconciles a clean old copy or refuses a copy with old graph.
        """

        rows = tuple(session.scalars(select(ErasureLedger).order_by(ErasureLedger.request_id)))
        if len(rows) > 1000:
            raise DevelopmentStoreRejected
        records = [
            {
                "request_id": row.request_id,
                "account_id": row.account_id,
                "scope": row.scope,
                "target_id": row.target_id,
                "created_at": (
                    row.created_at.replace(tzinfo=UTC)
                    if row.created_at.tzinfo is None
                    else row.created_at.astimezone(UTC)
                ).isoformat(),
                "signature": row.signature,
                **(
                    {
                        "profile_id": row.profile_id,
                        "profile_version_after": row.profile_version_after,
                    }
                    if row.scope in {"SESSION", "EVIDENCE", "PROJECT"}
                    else {}
                ),
            }
            for row in rows
        ]
        _replace_private(
            self.state_dir / "ledger.json",
            (json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        _replace_private(
            self.state_dir / "manifest",
            (signed_manifest(rows, secret=self.ledger_secret) + "\n").encode(),
        )

    def token_is_revoked(self, token: str) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        with self._revoked_lock:
            self._revoked = {key: expiry for key, expiry in self._revoked.items() if expiry > now}
            return digest in self._revoked

    def revoke_token(self, token: str, expires_at: int) -> None:
        if type(token) is not str or not token or type(expires_at) is not int:
            raise ValueError("invalid local token")
        now = int(time.time())
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._revoked_lock:
            self._revoked = {key: expiry for key, expiry in self._revoked.items() if expiry > now}
            if len(self._revoked) >= 128 and digest not in self._revoked:
                raise ValueError("local revocation capacity reached")
            if expires_at > now:
                self._revoked[digest] = expires_at

    def after_deletion_commit(self) -> None:
        """The write-ahead ledger checkpoint is already durable before commit."""

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.browsers.clear()
        self.revoked_tokens.clear()
        self._revoked.clear()
        self.deletion_connection.pending.clear()
        self.deletion_connection = None
        self.key = None
        self.tokens = None
        self.review_secret = None
        self.presentation_secret = None
        self.ledger_secret = None
        self.status_secret = None
        self.deletion_journey = None
        self.web = None
        self.mcp = None
        self.engine.dispose()
        self._release_lock()


def main():
    parser = argparse.ArgumentParser(
        description="Persistent synthetic CareerGround on 127.0.0.1 only"
    )
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument(
        "--upgrade-store",
        action="store_true",
        help="explicitly upgrade an exact legacy 0019 synthetic store; keeps a private sibling SQLite backup",
    )
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0..65535")
    with socket.socket() as sock:
        # A browser can leave accepted connections in TIME_WAIT after shutdown.
        # Reuse the closed listener address for an immediate local restart.
        # SO_REUSEPORT is intentionally not enabled: live listeners still fail.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", args.port))
        with DevelopmentRuntime(
            sock.getsockname()[1], Path(args.state_dir), upgrade_store=args.upgrade_store
        ) as runtime:
            if runtime.upgrade_backup_path is not None:
                print(f"0019 저장소의 원본 SQLite 백업: {runtime.upgrade_backup_path}", flush=True)

            class ReadyServer(uvicorn.Server):
                async def startup(self, sockets=None):
                    await super().startup(sockets=sockets)
                    if self.started:
                        print(
                            f"합성 데이터 개발 저장소: {runtime.origin}/demo (종료: Ctrl+C)",
                            flush=True,
                        )

            server = ReadyServer(
                uvicorn.Config(runtime, log_level="warning", access_log=False, proxy_headers=False)
            )
            try:
                server.run(sockets=[sock])
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()

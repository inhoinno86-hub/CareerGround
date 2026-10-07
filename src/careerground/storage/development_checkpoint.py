"""Independent signed deletion checkpoint for private local development stores.

DB-only rollback is checked; rolling back all local files together is outside
this boundary and requires an external anchor before operational use.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from careerground.domain.deletion_execution import ledger_signature
from careerground.storage.development_files import (
    DevelopmentStoreRejected,
    _private_file,
    _replace_private,
)
from careerground.storage.models import ErasureLedger
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

_LEDGER_FIELDS = frozenset(
    {"request_id", "account_id", "scope", "target_id", "created_at", "signature"}
)


class SignedDeletionCheckpoint:
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

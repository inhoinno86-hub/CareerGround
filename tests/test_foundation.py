"""Synthetic first-slice checks. SQLite is a test double, not PostgreSQL validation."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.config import Settings
from careerground.domain.authorization import (
    AuthenticationRequired,
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.domain.contracts import (
    ErrorResponse,
    IdempotencyKey,
    OutboxEventRef,
    SuccessResponse,
)
from careerground.storage.models import Account, AuthIdentity, Base, CareerProfile
from careerground.web.app import app

ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add_all(
                [
                    Account(id="acct-synthetic-a", status="ACTIVE"),
                    Account(id="acct-synthetic-b", status="ACTIVE"),
                    AuthIdentity(
                        id="identity-synthetic-a",
                        account_id="acct-synthetic-a",
                        issuer="https://issuer-a.example",
                        subject="subject-001",
                    ),
                    AuthIdentity(
                        id="identity-synthetic-b",
                        account_id="acct-synthetic-b",
                        issuer="https://issuer-b.example",
                        subject="subject-001",
                    ),
                    CareerProfile(
                        id="profile-synthetic-a", account_id="acct-synthetic-a", version=0
                    ),
                    CareerProfile(
                        id="profile-synthetic-b", account_id="acct-synthetic-b", version=0
                    ),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_issuer_and_subject_pair_resolves_distinct_accounts(self) -> None:
        with Session(self.engine) as session:
            account_a = resolve_account_id(
                session, VerifiedIdentity("https://issuer-a.example", "subject-001")
            )
            account_b = resolve_account_id(
                session, VerifiedIdentity("https://issuer-b.example", "subject-001")
            )
        self.assertEqual(account_a, "acct-synthetic-a")
        self.assertEqual(account_b, "acct-synthetic-b")

    def test_unknown_or_disabled_identity_is_not_authenticated(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(AuthenticationRequired):
                resolve_account_id(session, VerifiedIdentity("https://issuer-a.example", "unknown"))
            session.get(Account, "acct-synthetic-a").status = "DISABLED"
            session.commit()
            with self.assertRaises(AuthenticationRequired):
                resolve_account_id(
                    session, VerifiedIdentity("https://issuer-a.example", "subject-001")
                )

    def test_profile_lookup_is_scoped_before_read(self) -> None:
        with Session(self.engine) as session:
            account_a = resolve_account_id(
                session, VerifiedIdentity("https://issuer-a.example", "subject-001")
            )
            owned = get_owned_profile(
                session, account_id=account_a, profile_id="profile-synthetic-a"
            )
            self.assertEqual(owned.version, 0)
            for other_id in ("profile-synthetic-b", "not-a-profile"):
                with self.subTest(other_id=other_id), self.assertRaises(ResourceNotFound):
                    get_owned_profile(session, account_id=account_a, profile_id=other_id)

    def test_database_constraints_reject_duplicate_identity_and_owner(self) -> None:
        with Session(self.engine) as session:
            session.add(
                AuthIdentity(
                    id="duplicate-identity",
                    account_id="acct-synthetic-b",
                    issuer="https://issuer-a.example",
                    subject="subject-001",
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.add(
                CareerProfile(id="second-profile-a", account_id="acct-synthetic-a", version=0)
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_database_constraints_reject_dangling_owner_and_negative_version(self) -> None:
        with Session(self.engine) as session:
            session.add(CareerProfile(id="dangling", account_id="missing-account", version=0))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.add(
                CareerProfile(id="negative-version", account_id="acct-synthetic-a", version=-1)
            )
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_only_health_routes_exist_before_provider_auth(self) -> None:
        client = TestClient(app)
        self.assertEqual(client.get("/health/live").json(), {"status": "live"})
        with patch.dict(os.environ, {"CAREERGROUND_DATABASE_URL": ""}):
            self.assertEqual(client.get("/health/ready").status_code, 503)
        self.assertEqual(client.get("/profiles/profile-synthetic-a").status_code, 404)

    def test_runtime_configuration_requires_postgresql_psycopg(self) -> None:
        old = os.environ.get("CAREERGROUND_DATABASE_URL")
        try:
            os.environ["CAREERGROUND_DATABASE_URL"] = "sqlite:///unsafe-local.db"
            with self.assertRaises(ValueError):
                Settings.from_environment()
        finally:
            if old is None:
                os.environ.pop("CAREERGROUND_DATABASE_URL", None)
            else:
                os.environ["CAREERGROUND_DATABASE_URL"] = old

    def test_common_tool_dtos_fail_closed_on_unknown_fields_and_codes(self) -> None:
        valid = SuccessResponse.model_validate(
            {"status": "ok", "data": {}, "next_actions": [], "user_message": "준비됨"}
        )
        self.assertEqual(valid.status, "ok")
        with self.assertRaises(ValidationError):
            SuccessResponse.model_validate(
                {
                    "status": "ok",
                    "data": {},
                    "next_actions": [],
                    "user_message": "준비됨",
                    "token": "not-allowed",
                }
            )
        with self.assertRaises(ValidationError):
            ErrorResponse.model_validate(
                {
                    "status": "error",
                    "error": {"code": "UNKNOWN", "message": "x", "recoverable": False},
                }
            )

    def test_package_errors_are_typed_and_idempotency_keys_are_bounded(self) -> None:
        response = ErrorResponse.model_validate(
            {
                "status": "error",
                "error": {
                    "code": "PACKAGE_SIGNATURE_INVALID",
                    "message": "invalid package",
                    "recoverable": False,
                },
            }
        )
        self.assertEqual(response.error.code, "PACKAGE_SIGNATURE_INVALID")
        adapter = TypeAdapter(IdempotencyKey)
        self.assertEqual(adapter.validate_python("synthetic-key-0001"), "synthetic-key-0001")
        for value in ("short", "contains space 0001", "x" * 129):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_outbox_reference_cannot_carry_raw_content(self) -> None:
        event = {
            "event_id": "event-001",
            "account_id": "acct-synthetic-a",
            "aggregate_type": "PROFILE",
            "aggregate_id": "profile-synthetic-a",
            "aggregate_version": 1,
            "event_type": "PROFILE_UPDATED",
            "occurred_at": datetime.now(UTC),
        }
        self.assertEqual(OutboxEventRef.model_validate(event).event_type, "PROFILE_UPDATED")
        with self.assertRaises(ValidationError):
            OutboxEventRef.model_validate({**event, "raw_content": "private career text"})
        with self.assertRaises(ValidationError):
            OutboxEventRef.model_validate(
                {**event, "occurred_at": datetime.fromisoformat("2026-09-23T00:00:00")}
            )

    def test_postgresql_migration_renders_offline(self) -> None:
        environment = dict(os.environ)
        environment["CAREERGROUND_DATABASE_URL"] = (
            "postgresql+psycopg://synthetic:placeholder@localhost:54329/careerground_dev"
        )
        process = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        for table in ("accounts", "auth_identities", "career_profiles"):
            self.assertIn(f"CREATE TABLE {table}", process.stdout)
        self.assertIn("uq_auth_identity_issuer_subject", process.stdout)


if __name__ == "__main__":
    unittest.main()

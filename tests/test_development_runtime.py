"""Persistent synthetic store, fresh browser credentials, and restore gate."""

from __future__ import annotations

import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from careerground.development_runtime import (
    DevelopmentRuntime,
    DevelopmentStoreRejected,
    _expected_schema_signatures,
    _legacy_metadata,
    _schema_signature,
)
from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.local_demo import ACCOUNTS, COOKIE
from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import Artifact, ArtifactUnit
from careerground.storage.models import CareerProfile


class DevelopmentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "owned-state"
        self.port = 8091

    @staticmethod
    def hidden(page, name):
        found = re.search(rf"name='{name}' value='([^']*)'", page)
        assert found is not None
        return unescape(found.group(1))

    def client(self, runtime):
        return TestClient(runtime, base_url=runtime.origin, client=("127.0.0.1", 43123))

    def choose(self, client, label="a"):
        page = client.get("/demo")
        result = client.post(
            "/demo/account",
            data={"form_token": self.hidden(page.text, "form_token"), "account": label},
            follow_redirects=False,
        )
        self.assertEqual(result.status_code, 303)

    def legacy_store(self):
        """Copy an app-seeded 0020 fixture into exact 0019 synthetic DDL."""
        runtime = DevelopmentRuntime(self.port, self.state)
        try:
            with runtime.sessions() as session:
                session.add(
                    Claim(
                        id="synthetic-pre-upgrade-claim",
                        account_id=ACCOUNTS["a"][0],
                        profile_id=ACCOUNTS["a"][1],
                        scope_key="upgrade",
                        claim_type="CONTRIBUTION",
                        canonical_text="retained synthetic fact",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=datetime(2026, 10, 2, tzinfo=UTC),
                    )
                )
                session.get(CareerProfile, ACCOUNTS["a"][1]).version = 1
                session.flush()
                ensure_profile_archive(
                    session,
                    account_id=ACCOUNTS["a"][0],
                    profile_id=ACCOUNTS["a"][1],
                    profile_version=1,
                    now=datetime(2026, 10, 2, tzinfo=UTC),
                )
                jd = record_pasted_jd_analysis(
                    session,
                    account_id=ACCOUNTS["a"][0],
                    profile_id=ACCOUNTS["a"][1],
                    source_text="Python required",
                    excerpts=(JDExcerpt(0, 6),),
                    now=datetime(2026, 10, 2, tzinfo=UTC),
                )
                session.add(
                    Artifact(
                        id="synthetic-pre-upgrade-artifact",
                        account_id=ACCOUNTS["a"][0],
                        profile_id=ACCOUNTS["a"][1],
                        artifact_type="RESUME_TEXT",
                        artifact_version=1,
                        profile_version=1,
                        jd_id=jd.id,
                        status="REVIEW_REQUIRED",
                        created_at=datetime(2026, 10, 2, tzinfo=UTC),
                    )
                )
                session.flush()
                session.add(
                    ArtifactUnit(
                        id="synthetic-pre-upgrade-unit",
                        account_id=ACCOUNTS["a"][0],
                        profile_id=ACCOUNTS["a"][1],
                        artifact_id="synthetic-pre-upgrade-artifact",
                        ordinal=1,
                        unit_type="RESUME_BULLET",
                        exact_text="retained synthetic fact",
                        wording_level="R1",
                        review_status="REVIEW_REQUIRED",
                    )
                )
                session.commit()
        finally:
            runtime.close()
        current_copy = Path(self.temp.name) / "fixture-current.sqlite"
        database = self.state / "synthetic.sqlite"
        shutil.copyfile(database, current_copy)
        database.unlink()
        metadata = _legacy_metadata()
        engine = create_engine("sqlite+pysqlite:///" + str(database))
        try:
            metadata.create_all(engine)
        finally:
            engine.dispose()
        with sqlite3.connect(str(database)) as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("ATTACH DATABASE ? AS prior", (str(current_copy),))
            for table in metadata.sorted_tables:
                columns = ",".join('"' + column.name + '"' for column in table.columns)
                connection.execute(
                    f'INSERT INTO main."{table.name}" ({columns}) '
                    f'SELECT {columns} FROM prior."{table.name}"'
                )
            connection.commit()
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        database.chmod(0o600)
        current_copy.unlink()
        with create_engine("sqlite+pysqlite:///" + str(database)).connect() as connection:
            self.assertEqual(_schema_signature(connection.engine), _expected_schema_signatures()[1])
        return database

    def test_restart_keeps_graph_and_keys_but_invalidates_browser_and_jwt(self):
        runtime = DevelopmentRuntime(self.port, self.state)
        client = self.client(runtime)
        try:
            self.choose(client)
            old_cookie = client.cookies.get(COOKIE)
            old_token = runtime._access_token(runtime.browsers[old_cookie])
            with runtime.sessions() as session:
                session.add(
                    Claim(
                        id="synthetic-restart-claim",
                        account_id=ACCOUNTS["a"][0],
                        profile_id=ACCOUNTS["a"][1],
                        scope_key="restart",
                        claim_type="CONTRIBUTION",
                        canonical_text="synthetic saved fact",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=datetime(2026, 10, 2, tzinfo=UTC),
                    )
                )
                session.get(CareerProfile, ACCOUNTS["a"][1]).version = 1
                session.commit()
            review_key = runtime.review_secret
            presentation_key = runtime.presentation_secret
        finally:
            client.close()
            runtime.close()
        self.assertTrue((self.state / "synthetic.sqlite").exists())
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertTrue(
            all(
                (self.state / name).stat().st_mode & 0o777 == 0o600
                for name in (
                    "review.key",
                    "presentation.key",
                    "ledger.key",
                    "status.key",
                    "synthetic.sqlite",
                )
            )
        )
        reopened = DevelopmentRuntime(self.port, self.state)
        fresh = self.client(reopened)
        try:
            self.assertEqual(reopened.review_secret, review_key)
            self.assertEqual(reopened.presentation_secret, presentation_key)
            with reopened.sessions() as session:
                self.assertIsNotNone(session.get(Claim, "synthetic-restart-claim"))
                self.assertEqual(session.get(CareerProfile, ACCOUNTS["a"][1]).version, 1)
            fresh.cookies.set(COOKIE, old_cookie)
            self.assertEqual(fresh.get("/profiling/start").status_code, 401)
            response = fresh.post(
                "/mcp",
                headers={
                    "authorization": "Bearer " + old_token,
                    "accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            self.assertEqual(response.status_code, 401)
            fresh.cookies.clear()
            self.choose(fresh)
            self.assertEqual(fresh.get("/profiling/start").status_code, 200)
        finally:
            fresh.close()
            reopened.close()

    def test_logout_revokes_exact_connection_and_keeps_saved_data(self):
        runtime = DevelopmentRuntime(self.port, self.state)
        client = self.client(runtime)
        try:
            self.choose(client)
            cookie = client.cookies.get(COOKIE)
            token = runtime._access_token(runtime.browsers[cookie])
            page = client.get("/demo")
            self.assertEqual(page.status_code, 200)
            logout_form = page.text.split("action='/demo/logout'", 1)[1]
            logout = client.post(
                "/demo/logout",
                data={"form_token": self.hidden(logout_form, "form_token")},
                follow_redirects=False,
            )
            self.assertEqual(logout.status_code, 303)
            self.assertEqual(client.get("/profiling/start").status_code, 401)
            response = client.post(
                "/mcp",
                headers={
                    "authorization": "Bearer " + token,
                    "accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            self.assertEqual(response.status_code, 401)
            self.choose(client)
            self.assertEqual(client.get("/profiling/start").status_code, 200)
            self.assertEqual(runtime.token_is_revoked(token), True)
        finally:
            client.close()
            runtime.close()

    def test_unmarked_extra_symlink_and_corrupt_store_fail_closed(self):
        unmarked = Path(self.temp.name) / "unmarked"
        unmarked.mkdir(mode=0o700)
        (unmarked / "synthetic.sqlite").write_bytes(b"not a database")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, unmarked)
        runtime = DevelopmentRuntime(self.port, self.state)
        runtime.close()
        extra = self.state / "unexpected.txt"
        extra.write_text("x")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state)
        extra.unlink()
        link = Path(self.temp.name) / "alias"
        link.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, link)
        key = self.state / "review.key"
        key.write_bytes(b"bad")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state)

    def test_second_process_handle_cannot_open_live_state(self):
        first = DevelopmentRuntime(self.port, self.state)
        try:
            with self.assertRaises(DevelopmentStoreRejected):
                DevelopmentRuntime(self.port + 1, self.state)
        finally:
            first.close()
        reopened = DevelopmentRuntime(self.port, self.state)
        reopened.close()

    def test_explicit_exact_0019_upgrade_preserves_data_and_private_backup(self):
        database = self.legacy_store()
        before = database.read_bytes()
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state)
        self.assertEqual(database.read_bytes(), before)
        runtime = DevelopmentRuntime(self.port, self.state, upgrade_store=True)
        try:
            backup = runtime.upgrade_backup_path
            self.assertIsNotNone(backup)
            self.assertEqual(backup.parent, self.state.parent)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            backup_engine = create_engine("sqlite+pysqlite:///" + str(backup))
            try:
                self.assertEqual(_schema_signature(backup_engine), _expected_schema_signatures()[1])
                with backup_engine.connect() as connection:
                    self.assertEqual(
                        connection.exec_driver_sql(
                            "SELECT canonical_text FROM claims WHERE id='synthetic-pre-upgrade-claim'"
                        ).scalar(),
                        "retained synthetic fact",
                    )
            finally:
                backup_engine.dispose()
            self.assertEqual((self.state / "synthetic.sqlite").stat().st_mode & 0o777, 0o600)
            with runtime.sessions() as session:
                self.assertIsNotNone(session.get(Claim, "synthetic-pre-upgrade-claim"))
                self.assertEqual(session.get(CareerProfile, ACCOUNTS["a"][1]).version, 1)
                self.assertEqual(
                    session.get(ArtifactUnit, "synthetic-pre-upgrade-unit").exact_text,
                    "retained synthetic fact",
                )
                self.assertEqual(
                    session.get(Artifact, "synthetic-pre-upgrade-artifact").source_artifact_id,
                    None,
                )
            inspector = inspect(runtime.engine)
            self.assertIn("project_scopes", inspector.get_table_names())
            self.assertIn(
                "source_artifact_id",
                {item["name"] for item in inspector.get_columns("artifacts")},
            )
            self.assertIn(
                "fk_artifact_owned_source",
                {item["name"] for item in inspector.get_foreign_keys("artifacts")},
            )
        finally:
            runtime.close()
        reopened = DevelopmentRuntime(self.port, self.state, upgrade_store=True)
        try:
            self.assertIsNone(reopened.upgrade_backup_path)
            with reopened.sessions() as session:
                self.assertIsNotNone(session.get(Claim, "synthetic-pre-upgrade-claim"))
        finally:
            reopened.close()
        backup.unlink()

    def test_upgrade_rejects_unknown_legacy_schema_without_changing_store(self):
        database = self.legacy_store()
        with sqlite3.connect(str(database)) as connection:
            connection.execute("CREATE TABLE unexpected_legacy_table (id INTEGER)")
        before = database.read_bytes()
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state, upgrade_store=True)
        self.assertEqual(database.read_bytes(), before)
        self.assertEqual(
            {item.name for item in self.state.iterdir()},
            {
                ".careerground-development-v1",
                "synthetic.sqlite",
                "review.key",
                "presentation.key",
                "ledger.key",
                "status.key",
                "ledger.json",
                "manifest",
                ".runtime.lock",
            },
        )

    def test_upgrade_rejects_bad_checkpoint_and_failed_stage_without_swap(self):
        database = self.legacy_store()
        original = database.read_bytes()
        manifest = self.state / "manifest"
        valid_manifest = manifest.read_bytes()
        manifest.write_bytes(b"0" * 64 + b"\n")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state, upgrade_store=True)
        self.assertEqual(database.read_bytes(), original)
        self.assertEqual(list(self.state.parent.glob(f".{self.state.name}-pre-*.sqlite")), [])
        manifest.write_bytes(valid_manifest)

        original_validate = DevelopmentRuntime._validate_schema

        def fail_stage(runtime, engine):
            if Path(engine.url.database) != database:
                raise DevelopmentStoreRejected
            return original_validate(runtime, engine)

        with (
            patch.object(DevelopmentRuntime, "_validate_schema", fail_stage),
            self.assertRaises(DevelopmentStoreRejected),
        ):
            DevelopmentRuntime(self.port, self.state, upgrade_store=True)
        self.assertEqual(database.read_bytes(), original)
        self.assertEqual(list(self.state.parent.glob(f".{self.state.name}-pre-*.sqlite")), [])

    def test_write_ahead_ledger_refuses_predelete_graph_snapshot(self):
        runtime = DevelopmentRuntime(self.port, self.state)
        now = datetime(2026, 10, 2, 12, tzinfo=UTC)
        try:
            with runtime.sessions() as session:
                session.add(
                    Claim(
                        id="synthetic-erasure-claim",
                        account_id=ACCOUNTS["a"][0],
                        profile_id=ACCOUNTS["a"][1],
                        scope_key="erase",
                        claim_type="CONTRIBUTION",
                        canonical_text="private synthetic source",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=now,
                    )
                )
                session.get(CareerProfile, ACCOUNTS["a"][1]).version = 1
                session.commit()
        finally:
            runtime.close()
        old_copy = Path(self.temp.name) / "before-delete.sqlite"
        shutil.copyfile(self.state / "synthetic.sqlite", old_copy)
        running = DevelopmentRuntime(self.port, self.state)
        try:
            with running.sessions() as session:
                preview = running.deletion_journey.preview(
                    session,
                    account_id=ACCOUNTS["a"][0],
                    profile_id=ACCOUNTS["a"][1],
                    browser_session_id="synthetic-browser-session",
                    scope="ACCOUNT",
                    now=now,
                )
                step = running.deletion_journey.reauthenticate(
                    session,
                    account_id=ACCOUNTS["a"][0],
                    profile_id=ACCOUNTS["a"][1],
                    browser_session_id="synthetic-browser-session",
                    preview_token=preview.preview_token,
                    acknowledged_impact=True,
                    mock_reauthenticated=True,
                    now=now + timedelta(seconds=1),
                )
                running.deletion_journey.execute(
                    session,
                    account_id=ACCOUNTS["a"][0],
                    profile_id=ACCOUNTS["a"][1],
                    browser_session_id="synthetic-browser-session",
                    step_up_token=step,
                    confirmed=True,
                    now=now + timedelta(seconds=2),
                )
                running.before_deletion_commit(session)
                session.commit()
        finally:
            running.close()
        after_delete = DevelopmentRuntime(self.port, self.state)
        survivor = self.client(after_delete)
        try:
            self.choose(survivor, "b")
            self.assertEqual(survivor.get("/profiling/start").status_code, 200)
        finally:
            survivor.close()
            after_delete.close()
        shutil.copyfile(old_copy, self.state / "synthetic.sqlite")
        with self.assertRaises(DevelopmentStoreRejected):
            DevelopmentRuntime(self.port, self.state)


if __name__ == "__main__":
    unittest.main()

"""Synthetic private-object retention and all-version erasure rehearsal."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.private_objects import (
    PrivateObjectInventoryMismatch,
    PrivateObjectUnavailable,
    erase_synthetic_object_versions,
    list_private_versions,
    register_opted_in_recording,
    register_private_version,
    register_upload_original,
    stage_expired_private_objects,
)
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    OutboxEvent,
    PrivateObject,
    PrivateObjectVersion,
)
from careerground.workers.private_object_retention import run_synthetic_version_cycle


class MemoryVersionStore:
    def __init__(self) -> None:
        self.objects: dict[str, set[str]] = {}

    def list_versions(self, object_id: str) -> set[str]:
        return set(self.objects.get(object_id, set()))

    def delete_version(self, object_id: str, provider_version_id: str) -> None:
        self.objects[object_id].discard(provider_version_id)


class PrivateObjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 27, 12, tzinfo=UTC)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=0),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_separate_30_day_anchors_and_recording_default_off(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(ValueError):
                register_opted_in_recording(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    recording_completed_at=self.now,
                    explicit_opt_in=False,
                    now=self.now,
                )
            self.assertEqual(session.scalar(select(func.count()).select_from(PrivateObject)), 0)
            upload = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now - timedelta(days=2),
                now=self.now,
            )
            recording = register_opted_in_recording(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                recording_completed_at=self.now,
                explicit_opt_in=True,
                now=self.now,
            )
            session.flush()
            self.assertEqual(upload.retention_expires_at, self.now + timedelta(days=28))
            self.assertEqual(recording.retention_expires_at, self.now + timedelta(days=30))
            self.assertNotEqual(upload.id, recording.id)
            session.commit()

    def test_owner_and_expiry_guards_version_idempotency(self) -> None:
        with Session(self.engine) as session:
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now,
                now=self.now,
            )
            session.flush()
            first = register_private_version(
                session,
                account_id="acct-a",
                object_id=obj.id,
                provider_version_id="synthetic-v1",
                now=self.now,
            )
            session.flush()
            replay = register_private_version(
                session,
                account_id="acct-a",
                object_id=obj.id,
                provider_version_id="synthetic-v1",
                now=self.now,
            )
            self.assertEqual(first.id, replay.id)
            with self.assertRaises(PrivateObjectUnavailable):
                list_private_versions(session, account_id="acct-b", object_id=obj.id, now=self.now)
            with self.assertRaises(PrivateObjectUnavailable):
                list_private_versions(
                    session,
                    account_id="acct-a",
                    object_id=obj.id,
                    now=self.now + timedelta(days=30),
                )
            self.assertEqual(
                len(
                    list_private_versions(
                        session, account_id="acct-a", object_id=obj.id, now=self.now
                    )
                ),
                1,
            )

    def test_bounded_expiry_and_all_versions_including_old_version(self) -> None:
        store = MemoryVersionStore()
        with Session(self.engine) as session:
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now - timedelta(days=30),
                now=self.now - timedelta(days=1),
            )
            current = register_upload_original(
                session,
                account_id="acct-b",
                profile_id="profile-b",
                extraction_completed_at=self.now,
                now=self.now,
            )
            session.flush()
            for version_id in ("synthetic-v1", "synthetic-v2"):
                register_private_version(
                    session,
                    account_id="acct-a",
                    object_id=obj.id,
                    provider_version_id=version_id,
                    now=self.now - timedelta(days=1),
                )
            session.commit()
            object_id = obj.id
            current_id = current.id
            store.objects[object_id] = {"synthetic-v1", "synthetic-v2", "untracked-version"}
        with Session(self.engine) as session:
            self.assertEqual(stage_expired_private_objects(session, now=self.now, limit=1), 1)
            session.commit()
        with Session(self.engine) as session:
            self.assertEqual(session.get(PrivateObject, object_id).status, "DELETING")
            self.assertEqual(session.get(PrivateObject, current_id).status, "ACTIVE")
            with self.assertRaises(PrivateObjectInventoryMismatch):
                erase_synthetic_object_versions(session, object_id=object_id, adapter=store)
            self.assertEqual(len(store.list_versions(object_id)), 3)
            store.objects[object_id].remove("untracked-version")
            self.assertEqual(
                erase_synthetic_object_versions(session, object_id=object_id, adapter=store), 2
            )
            session.commit()
            self.assertEqual(store.list_versions(object_id), set())
            self.assertEqual(
                set(
                    session.scalars(
                        select(PrivateObjectVersion.status).where(
                            PrivateObjectVersion.object_id == object_id
                        )
                    )
                ),
                {"DELETED"},
            )
            self.assertEqual(session.get(PrivateObject, object_id).status, "DELETING")

    def test_expiry_staging_rollback_and_account_block(self) -> None:
        with Session(self.engine) as session:
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now - timedelta(days=30),
                now=self.now - timedelta(days=1),
            )
            session.commit()
            object_id = obj.id
        with Session(self.engine) as session:
            self.assertEqual(stage_expired_private_objects(session, now=self.now), 1)
            session.rollback()
            self.assertEqual(session.get(PrivateObject, object_id).status, "ACTIVE")
            session.get(Account, "acct-a").status = "DELETING"
            session.commit()
            with self.assertRaises(PrivateObjectUnavailable):
                list_private_versions(
                    session, account_id="acct-a", object_id=object_id, now=self.now
                )

    def test_staged_versions_replay_with_fake_adapter_and_receipts(self) -> None:
        store = MemoryVersionStore()
        with Session(self.engine) as session:
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now - timedelta(days=30),
                now=self.now - timedelta(days=1),
            )
            session.flush()
            for version_id in ("synthetic-v1", "synthetic-v2"):
                register_private_version(
                    session,
                    account_id="acct-a",
                    object_id=obj.id,
                    provider_version_id=version_id,
                    now=self.now - timedelta(days=1),
                )
            session.commit()
            object_id = obj.id
            store.objects[object_id] = {"synthetic-v1", "synthetic-v2"}
        with Session(self.engine) as session:
            self.assertEqual(stage_expired_private_objects(session, now=self.now), 1)
            session.commit()
            self.assertEqual(session.scalar(select(func.count()).select_from(OutboxEvent)), 2)
        factory = lambda: Session(self.engine)
        self.assertEqual(run_synthetic_version_cycle(factory, adapter=store, now=self.now), (2, 0))
        self.assertEqual(run_synthetic_version_cycle(factory, adapter=store, now=self.now), (0, 0))
        self.assertEqual(store.list_versions(object_id), set())
        with factory() as session:
            self.assertEqual(set(session.scalars(select(PrivateObjectVersion.status))), {"DELETED"})
            self.assertEqual(set(session.scalars(select(OutboxEvent.status))), {"DONE"})
            self.assertEqual(session.get(PrivateObject, object_id).status, "DELETING")

    def test_fake_adapter_failure_retries_without_losing_event(self) -> None:
        class CrashAfterDelete(MemoryVersionStore):
            def __init__(self) -> None:
                super().__init__()
                self.crash_once = True

            def delete_version(self, object_id: str, provider_version_id: str) -> None:
                super().delete_version(object_id, provider_version_id)
                if self.crash_once:
                    self.crash_once = False
                    raise RuntimeError("synthetic interruption")

        store = CrashAfterDelete()
        with Session(self.engine) as session:
            obj = register_upload_original(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                extraction_completed_at=self.now - timedelta(days=30),
                now=self.now - timedelta(days=1),
            )
            session.flush()
            version = register_private_version(
                session,
                account_id="acct-a",
                object_id=obj.id,
                provider_version_id="synthetic-v1",
                now=self.now - timedelta(days=1),
            )
            session.commit()
            store.objects[obj.id] = {"synthetic-v1"}
            version_id = version.id
        with Session(self.engine) as session:
            stage_expired_private_objects(session, now=self.now)
            session.commit()
        factory = lambda: Session(self.engine)
        self.assertEqual(run_synthetic_version_cycle(factory, adapter=store, now=self.now), (0, 1))
        with factory() as session:
            self.assertEqual(session.get(PrivateObjectVersion, version_id).status, "DELETE_PENDING")
            event_row = session.scalar(select(OutboxEvent))
            self.assertEqual((event_row.status, event_row.attempts), ("PENDING", 1))
        self.assertEqual(
            run_synthetic_version_cycle(
                factory, adapter=store, now=self.now + timedelta(seconds=20)
            ),
            (1, 0),
        )
        with factory() as session:
            self.assertEqual(session.get(PrivateObjectVersion, version_id).status, "DELETED")


if __name__ == "__main__":
    unittest.main()

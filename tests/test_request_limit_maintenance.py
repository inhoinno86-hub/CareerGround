"""Request-independent quota cleanup and payload-free local counters."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from careerground.domain.safe_events import (
    record_request_limit_cleanup,
    record_result,
    security_metrics_snapshot,
)
from careerground.storage.models import Base, RequestLimitBucket
from careerground.workers.request_limit_maintenance import (
    RequestLimitMaintenanceUnavailable,
    delete_expired_request_limit_batch,
    main,
    run_request_limit_cleanup_cycle,
    run_scheduled_request_limit_cleanup,
)


class RequestLimitMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="careerground-quota-test-")
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "quota.sqlite3"
        self.engine = create_engine(
            f"sqlite:///{database_path}", connect_args={"timeout": 5}, hide_parameters=True
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = lambda: Session(self.engine)

    def seed(self, *, expired: int, live: int = 0) -> None:
        with self.sessions() as session:
            session.add_all(
                [
                    RequestLimitBucket(
                        bucket_key=f"{number:064x}",
                        window_start=60,
                        requests=1,
                        expires_at=120 if number < expired else 180,
                    )
                    for number in range(expired + live)
                ]
            )
            session.commit()

    def rows(self) -> int:
        with self.sessions() as session:
            return session.scalar(select(func.count()).select_from(RequestLimitBucket))

    def test_boundary_bounded_batch_and_caller_transaction(self) -> None:
        self.seed(expired=5, live=2)
        with self.sessions() as session:
            self.assertEqual(delete_expired_request_limit_batch(session, now=120, limit=2), 2)
            session.rollback()
        self.assertEqual(self.rows(), 7)

        result = run_request_limit_cleanup_cycle(
            self.sessions, now=120, batch_size=2, max_batches=2
        )
        self.assertEqual(
            (result.deleted_buckets, result.batches, result.budget_exhausted), (4, 2, True)
        )
        self.assertEqual(self.rows(), 3)
        result = run_request_limit_cleanup_cycle(self.sessions, now=120, batch_size=2)
        self.assertEqual(
            (result.deleted_buckets, result.batches, result.budget_exhausted), (1, 1, False)
        )
        self.assertEqual(self.rows(), 2)
        with self.sessions() as session:
            self.assertEqual(set(session.scalars(select(RequestLimitBucket.expires_at))), {180})
        self.assertEqual(run_request_limit_cleanup_cycle(self.sessions, now=120).deleted_buckets, 0)

    def test_finite_schedule_runs_without_request_and_sees_new_expiry(self) -> None:
        self.seed(expired=0, live=1)
        times = iter((120.5, 180.25))
        slept = []
        results = run_scheduled_request_limit_cleanup(
            self.sessions,
            cycles=2,
            interval_seconds=3,
            clock=lambda: next(times),
            sleep=slept.append,
        )
        self.assertEqual(slept, [3])
        self.assertEqual([result.deleted_buckets for result in results], [0, 1])
        self.assertEqual(self.rows(), 0)

    def test_simultaneous_cleaners_delete_each_row_once(self) -> None:
        self.seed(expired=120, live=3)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: run_request_limit_cleanup_cycle(
                        self.sessions, now=120, batch_size=50, max_batches=5
                    ),
                    range(2),
                )
            )
        self.assertEqual(sum(result.deleted_buckets for result in results), 120)
        self.assertEqual(self.rows(), 3)

    def test_invalid_arguments_never_touch_database(self) -> None:
        def forbidden_session():
            self.fail("database must not be opened")

        for values in (
            {"now": True},
            {"now": -1},
            {"now": 2**63},
            {"now": 120, "batch_size": False},
            {"now": 120, "batch_size": 501},
            {"now": 120, "max_batches": 21},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                run_request_limit_cleanup_cycle(forbidden_session, **values)
        for values in (
            {"cycles": 0, "interval_seconds": 1},
            {"cycles": 25, "interval_seconds": 1},
            {"cycles": 1, "interval_seconds": 0},
            {"cycles": 1, "interval_seconds": 3601},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                run_scheduled_request_limit_cleanup(forbidden_session, **values)

    def test_database_failure_hides_driver_and_key_values(self) -> None:
        private = "private-source-and-account-id"

        def broken_session():
            raise IntegrityError("synthetic SQL", {"private": private}, Exception(private))

        before = security_metrics_snapshot()["request_limit_cleanup"]["ERROR"]
        with (
            self.assertLogs("careerground.security", level="INFO") as captured,
            self.assertRaises(RequestLimitMaintenanceUnavailable) as failure,
        ):
            run_request_limit_cleanup_cycle(broken_session, now=120)
        self.assertIsNone(failure.exception.__cause__)
        self.assertNotIn(private, str(failure.exception))
        self.assertNotIn(private, " ".join(captured.output))
        self.assertEqual(security_metrics_snapshot()["request_limit_cleanup"]["ERROR"], before + 1)

    def test_fixed_label_metrics_are_detached_and_saturate(self) -> None:
        private = "private-source-and-account-id"
        before = security_metrics_snapshot()
        with self.assertLogs("careerground.security", level="INFO") as captured:
            record_result("web", "RATE_LIMITED")
            record_result("mcp", "INTERNAL_ERROR")
            record_request_limit_cleanup("OK", deleted_buckets=3)
        snapshot = security_metrics_snapshot()
        self.assertEqual(
            snapshot["requests"]["web"]["RATE_LIMITED"],
            before["requests"]["web"]["RATE_LIMITED"] + 1,
        )
        self.assertEqual(
            snapshot["requests"]["mcp"]["INTERNAL_ERROR"],
            before["requests"]["mcp"]["INTERNAL_ERROR"] + 1,
        )
        self.assertEqual(
            snapshot["request_limit_cleanup"]["deleted_buckets"],
            before["request_limit_cleanup"]["deleted_buckets"] + 3,
        )
        self.assertNotIn(private, json.dumps(snapshot) + " ".join(captured.output))
        snapshot["requests"]["web"]["RATE_LIMITED"] = -1
        self.assertGreaterEqual(security_metrics_snapshot()["requests"]["web"]["RATE_LIMITED"], 1)
        with self.assertRaises(ValueError):
            record_result(private, "OK")
        with self.assertRaises(ValueError):
            record_request_limit_cleanup(private)
        with self.assertRaises(ValueError):
            record_request_limit_cleanup("OK", deleted_buckets=10_001)

        import careerground.domain.safe_events as events

        current = events._request_counts["web", "RATE_LIMITED"]
        with patch.object(events, "_MAX_COUNT", current + 1):
            record_result("web", "RATE_LIMITED")
            record_result("web", "RATE_LIMITED")
            self.assertEqual(
                security_metrics_snapshot()["requests"]["web"]["RATE_LIMITED"], current + 1
            )

    def test_cli_rejects_remote_and_non_test_databases(self) -> None:
        for url in (
            "postgresql+psycopg://user:password@127.0.0.1/careerground_prod",
            "postgresql+psycopg://user:password@example.invalid/careerground_test",
            "sqlite:///unsafe_test",
        ):
            with (
                self.subTest(url=url),
                patch.dict(os.environ, {"CAREERGROUND_TEST_DATABASE_URL": url}),
                self.assertRaises(RuntimeError),
            ):
                main(["--cycles", "1"])
        with (
            patch.dict(os.environ, {"CAREERGROUND_TEST_DATABASE_URL": ""}),
            self.assertRaises(RuntimeError),
        ):
            main(["--cycles", "1"])


class PostgreSQLRequestLimitMaintenanceTests(unittest.TestCase):
    def test_concurrent_cycles_use_skip_locked_on_local_test_database(self) -> None:
        raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL", "")
        if not raw_url:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("CAREERGROUND_TEST_DATABASE_URL required")
            self.skipTest("local test PostgreSQL not configured")
        url = make_url(raw_url)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing non-loopback or non-test database")

        engine = create_engine(url, hide_parameters=True, pool_pre_ping=True)
        prefix = uuid4().hex
        keys = [f"{prefix}{index:032x}" for index in range(38)]
        try:
            with Session(engine) as session:
                session.add_all(
                    RequestLimitBucket(
                        bucket_key=key,
                        window_start=60,
                        requests=1,
                        expires_at=120 if index < 37 else 180,
                    )
                    for index, key in enumerate(keys)
                )
                session.commit()

            factory = lambda: Session(engine)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(
                    executor.map(
                        lambda _: run_request_limit_cleanup_cycle(
                            factory, now=120, batch_size=7, max_batches=10
                        ),
                        range(2),
                    )
                )
            self.assertEqual(sum(result.deleted_buckets for result in results), 37)
            with factory() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(RequestLimitBucket)
                        .where(RequestLimitBucket.bucket_key.in_(keys))
                    ),
                    1,
                )
        finally:
            with Session(engine) as session:
                session.execute(
                    delete(RequestLimitBucket).where(RequestLimitBucket.bucket_key.in_(keys))
                )
                session.commit()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

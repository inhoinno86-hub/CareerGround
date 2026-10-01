"""Bounded, request-independent expiry of local request-limit counters."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import create_engine, delete, select, tuple_
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careerground.domain.safe_events import record_request_limit_cleanup
from careerground.storage.models import RequestLimitBucket

MAX_BATCH_SIZE = 500
MAX_BATCHES = 20
MAX_CYCLES = 24
MAX_INTERVAL_SECONDS = 3_600


class RequestLimitMaintenanceUnavailable(Exception):
    """Database maintenance failed; no driver details leave this boundary."""


@dataclass(frozen=True)
class CleanupResult:
    deleted_buckets: int
    batches: int
    budget_exhausted: bool


def delete_expired_request_limit_batch(session: Session, *, now: int, limit: int = 100) -> int:
    """Delete one bounded batch in the caller's transaction; never commit here.

    PostgreSQL skips rows locked by another maintenance cycle. SQLite is for
    local verification and serializes competing writes at the database level.
    """

    if type(now) is not int or not 0 <= now <= 2**63 - 1:
        raise ValueError("invalid cleanup time")
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError("invalid cleanup batch size")
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RequestLimitMaintenanceUnavailable

    query = (
        select(RequestLimitBucket.bucket_key, RequestLimitBucket.window_start)
        .where(RequestLimitBucket.expires_at <= now)
        .order_by(
            RequestLimitBucket.expires_at,
            RequestLimitBucket.bucket_key,
            RequestLimitBucket.window_start,
        )
        .limit(limit)
    )
    if dialect == "sqlite":
        # A single DELETE statement avoids two cleaners upgrading read locks.
        result = session.execute(
            delete(RequestLimitBucket).where(
                tuple_(RequestLimitBucket.bucket_key, RequestLimitBucket.window_start).in_(query)
            )
        )
        return result.rowcount or 0

    keys = tuple(session.execute(query.with_for_update(skip_locked=True)).all())
    if not keys:
        return 0
    result = session.execute(
        delete(RequestLimitBucket).where(
            tuple_(RequestLimitBucket.bucket_key, RequestLimitBucket.window_start).in_(keys)
        )
    )
    return result.rowcount or 0


def run_request_limit_cleanup_cycle(
    session_factory: Callable[[], Session],
    *,
    now: int,
    batch_size: int = 100,
    max_batches: int = 10,
) -> CleanupResult:
    """Commit each small batch, never returning row keys or database messages."""

    if type(now) is not int or not 0 <= now <= 2**63 - 1:
        raise ValueError("invalid cleanup time")
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("invalid cleanup batch size")
    if type(max_batches) is not int or not 1 <= max_batches <= MAX_BATCHES:
        raise ValueError("invalid cleanup batch count")

    deleted = 0
    batches = 0
    try:
        for _ in range(max_batches):
            with session_factory() as session:
                count = delete_expired_request_limit_batch(session, now=now, limit=batch_size)
                session.commit()
            batches += 1
            deleted += count
            record_request_limit_cleanup("OK", deleted_buckets=count)
            if count < batch_size:
                return CleanupResult(deleted, batches, False)
    except SQLAlchemyError:
        record_request_limit_cleanup("ERROR")
        raise RequestLimitMaintenanceUnavailable from None
    except RequestLimitMaintenanceUnavailable:
        record_request_limit_cleanup("ERROR")
        raise
    return CleanupResult(deleted, batches, True)


def run_scheduled_request_limit_cleanup(
    session_factory: Callable[[], Session],
    *,
    cycles: int,
    interval_seconds: int,
    batch_size: int = 100,
    max_batches: int = 10,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[CleanupResult, ...]:
    """Run a finite independent schedule; no application request is needed."""

    if type(cycles) is not int or not 1 <= cycles <= MAX_CYCLES:
        raise ValueError("invalid cleanup cycle count")
    if type(interval_seconds) is not int or not 1 <= interval_seconds <= MAX_INTERVAL_SECONDS:
        raise ValueError("invalid cleanup interval")
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("invalid cleanup batch size")
    if type(max_batches) is not int or not 1 <= max_batches <= MAX_BATCHES:
        raise ValueError("invalid cleanup batch count")
    results = []
    for index in range(cycles):
        if index:
            sleep(interval_seconds)
        now = clock()
        if type(now) not in {int, float} or not 0 <= now <= 2**63 - 1:
            raise ValueError("invalid cleanup time")
        results.append(
            run_request_limit_cleanup_cycle(
                session_factory, now=int(now), batch_size=batch_size, max_batches=max_batches
            )
        )
    return tuple(results)


def main(argv: Sequence[str] | None = None) -> int:
    """Explicit loopback PostgreSQL test CLI; never configures a daemon."""

    parser = argparse.ArgumentParser(description="Run finite local request-limit cleanup")
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-batches", type=int, default=10)
    args = parser.parse_args(argv)

    raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL", "")
    if not raw_url:
        raise RuntimeError("explicit CAREERGROUND_TEST_DATABASE_URL required")
    url = make_url(raw_url)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").endswith("_test")
    ):
        raise RuntimeError("refusing non-loopback or non-test database")
    # Validate schedule parameters before attempting to connect to the database.
    if type(args.cycles) is not int or not 1 <= args.cycles <= MAX_CYCLES:
        raise ValueError("invalid cleanup cycle count")
    if (
        type(args.interval_seconds) is not int
        or not 1 <= args.interval_seconds <= MAX_INTERVAL_SECONDS
    ):
        raise ValueError("invalid cleanup interval")
    if type(args.batch_size) is not int or not 1 <= args.batch_size <= MAX_BATCH_SIZE:
        raise ValueError("invalid cleanup batch size")
    if type(args.max_batches) is not int or not 1 <= args.max_batches <= MAX_BATCHES:
        raise ValueError("invalid cleanup batch count")

    engine = create_engine(
        url, hide_parameters=True, pool_pre_ping=True, connect_args={"connect_timeout": 5}
    )
    try:
        results = run_scheduled_request_limit_cleanup(
            lambda: Session(engine),
            cycles=args.cycles,
            interval_seconds=args.interval_seconds,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
        )
        for index, result in enumerate(results, start=1):
            print(
                f"request_limit_cleanup cycle={index} deleted_buckets={result.deleted_buckets} "
                f"batches={result.batches} budget_exhausted={result.budget_exhausted}"
            )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

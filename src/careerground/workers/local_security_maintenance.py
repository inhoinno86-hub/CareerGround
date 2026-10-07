"""Finite local schedule for idle quota and confirmation metadata expiry."""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careerground.domain.browser_operations import prune_browser_operations
from careerground.workers.request_limit_maintenance import run_request_limit_cleanup_cycle

logger = logging.getLogger("careerground.security")


def run_local_security_maintenance(
    session_factory,
    *,
    cycles=1,
    interval_seconds=60,
    batch_size=100,
    max_batches=10,
    clock=time.time,
    sleep=time.sleep,
):
    if type(cycles) is not int or not 1 <= cycles <= 24:
        raise ValueError("invalid maintenance cycles")
    if type(interval_seconds) is not int or not 1 <= interval_seconds <= 3600:
        raise ValueError("invalid maintenance interval")
    if (
        type(batch_size) is not int
        or not 1 <= batch_size <= 500
        or type(max_batches) is not int
        or not 1 <= max_batches <= 20
    ):
        raise ValueError("invalid maintenance budget")
    results = []
    for index in range(cycles):
        if index:
            sleep(interval_seconds)
        now = int(clock())
        quotas = run_request_limit_cleanup_cycle(
            session_factory, now=now, batch_size=batch_size, max_batches=max_batches
        )
        removed = 0
        try:
            for _ in range(max_batches):
                with session_factory() as session:
                    count = prune_browser_operations(
                        session, now=datetime.fromtimestamp(now, UTC), limit=batch_size
                    )
                    session.commit()
                removed += count
                if count < batch_size:
                    break
        except SQLAlchemyError:
            logger.info("browser_operation_cleanup result=ERROR")
            raise RuntimeError("local confirmation maintenance unavailable") from None
        logger.info("browser_operation_cleanup result=OK deleted_operations=%d", removed)
        results.append({"deleted_buckets": quotas.deleted_buckets, "deleted_operations": removed})
    return tuple(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    raw = os.environ.get("CAREERGROUND_TEST_DATABASE_URL", "")
    if not raw:
        raise RuntimeError("explicit local test database URL required")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1"}
        or not (url.database or "").endswith("_test")
    ):
        raise RuntimeError("refusing non-loopback or non-test database")
    engine = create_engine(url, hide_parameters=True)
    try:
        results = run_local_security_maintenance(
            lambda: Session(engine), cycles=args.cycles, interval_seconds=args.interval_seconds
        )
        print(
            "local_security_maintenance cycles="
            + str(len(results))
            + " deleted_buckets="
            + str(sum(row["deleted_buckets"] for row in results))
            + " deleted_operations="
            + str(sum(row["deleted_operations"] for row in results))
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

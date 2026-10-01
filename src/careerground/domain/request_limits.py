"""Atomic database-backed account quotas shared by synthetic MCP/Web factories."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careerground.storage.models import RequestLimitBucket


@dataclass(frozen=True)
class RequestLimitPolicy:
    """Local defaults; production thresholds require load and abuse evaluation."""

    read_requests: int = 120
    write_requests: int = 60
    window_seconds: int = 60

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 1
            for value in (self.read_requests, self.write_requests, self.window_seconds)
        ):
            raise ValueError("request limits must be positive integers")


class RequestLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Request limit reached")
        self.retry_after_seconds = retry_after_seconds


class RequestLimitStoreUnavailable(Exception):
    """Deny requests when the shared guard cannot reserve a quota."""


DEFAULT_REQUEST_LIMITS = RequestLimitPolicy()


class AccountRequestLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        secret: bytes,
        *,
        policy: RequestLimitPolicy = DEFAULT_REQUEST_LIMITS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if type(secret) is not bytes or len(secret) < 32:
            raise ValueError("request limiter secret too short")
        self.sessions = session_factory
        self.secret = secret
        self.policy = policy
        self.clock = clock

    def consume(self, account_id: str, lane: str) -> None:
        if type(account_id) is not str or not account_id or lane not in {"read", "write"}:
            raise ValueError("invalid quota identity")
        now = self.clock()
        if not math.isfinite(now) or now < 0:
            raise RequestLimitStoreUnavailable
        start = int(now) // self.policy.window_seconds * self.policy.window_seconds
        expires = start + self.policy.window_seconds
        key = hmac.new(
            self.secret, f"request-quota-v1:{lane}:{account_id}".encode(), hashlib.sha256
        ).hexdigest()
        maximum = self.policy.read_requests if lane == "read" else self.policy.write_requests
        try:
            with self.sessions() as session:
                dialect = session.get_bind().dialect.name
                if dialect not in {"postgresql", "sqlite"}:
                    raise RequestLimitStoreUnavailable
                session.execute(
                    delete(RequestLimitBucket).where(RequestLimitBucket.expires_at <= int(now))
                )
                insert = pg_insert if dialect == "postgresql" else sqlite_insert
                reservation = (
                    insert(RequestLimitBucket)
                    .values(
                        bucket_key=key,
                        window_start=start,
                        expires_at=expires,
                        requests=1,
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            RequestLimitBucket.bucket_key,
                            RequestLimitBucket.window_start,
                        ],
                        set_={"requests": RequestLimitBucket.requests + 1},
                        where=RequestLimitBucket.requests < maximum,
                    )
                    .returning(RequestLimitBucket.requests)
                )
                accepted = session.scalar(reservation)
                session.commit()
        except SQLAlchemyError:
            raise RequestLimitStoreUnavailable from None
        if accepted is None:
            raise RequestLimitExceeded(max(1, math.ceil(expires - now)))

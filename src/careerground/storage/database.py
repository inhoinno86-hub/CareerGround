"""Production PostgreSQL engine construction; tests may inject an in-memory engine."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine

from careerground.config import Settings


def make_engine(settings: Settings) -> Engine:
    if not settings.database_url:
        raise RuntimeError("CAREERGROUND_DATABASE_URL is required for database access")
    return create_engine(settings.database_url, pool_pre_ping=True)

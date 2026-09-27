"""Small, strict runtime configuration for the local foundation."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None

    @classmethod
    def from_environment(cls) -> Settings:
        value = os.environ.get("CAREERGROUND_DATABASE_URL")
        if value and not value.startswith("postgresql+psycopg://"):
            raise ValueError("CAREERGROUND_DATABASE_URL must use the postgresql+psycopg driver")
        return cls(database_url=value)


_AUTH0_NAMES = (
    "AUTH0_DOMAIN",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_SECRET",
    "APP_BASE_URL",
)


@dataclass(frozen=True)
class Auth0Settings:
    domain: str
    client_id: str
    client_secret: str
    secret: str
    app_base_url: str

    @classmethod
    def from_environment(cls) -> Auth0Settings | None:
        """Return None when login is not configured; fail closed when half-configured."""

        values = [os.environ.get(name, "") for name in _AUTH0_NAMES]
        if not any(values):
            return None
        missing = [name for name, value in zip(_AUTH0_NAMES, values) if not value]
        if missing:
            raise ValueError(f"Auth0 login is partially configured; missing {', '.join(missing)}")
        return cls(*values)

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

"""Strict common Plugin response DTOs; tool-specific payloads arrive in later stories."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

IdempotencyKey = Annotated[
    str,
    StringConstraints(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


class FunctionalErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEW_EXPIRED = "REVIEW_EXPIRED"
    BOUNDARY_BLOCKED = "BOUNDARY_BLOCKED"
    CONTRADICTION_BLOCKED = "CONTRADICTION_BLOCKED"
    SESSION_PAUSED = "SESSION_PAUSED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    PACKAGE_EXPIRED = "PACKAGE_EXPIRED"
    PACKAGE_REVOKED = "PACKAGE_REVOKED"
    PACKAGE_ALREADY_USED = "PACKAGE_ALREADY_USED"
    PACKAGE_SUBJECT_MISMATCH = "PACKAGE_SUBJECT_MISMATCH"
    PACKAGE_AUDIENCE_MISMATCH = "PACKAGE_AUDIENCE_MISMATCH"
    PACKAGE_SIGNATURE_INVALID = "PACKAGE_SIGNATURE_INVALID"
    PACKAGE_SCHEMA_UNSUPPORTED = "PACKAGE_SCHEMA_UNSUPPORTED"
    PACKAGE_REFERENCE_INVALID = "PACKAGE_REFERENCE_INVALID"
    PACKAGE_SCOPE_TOO_LARGE = "PACKAGE_SCOPE_TOO_LARGE"
    PACKAGE_SOURCE_UNAVAILABLE = "PACKAGE_SOURCE_UNAVAILABLE"


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: FunctionalErrorCode
    message: str = Field(min_length=1)
    recoverable: bool
    next_action: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["error"] = "error"
    error: ToolError


class SuccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    data: dict[str, object]
    next_actions: list[str]
    user_message: str = Field(min_length=1)


class OutboxEventRef(BaseModel):
    """Payload-free transactional event reference; storage implementation is later."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    aggregate_type: Literal["PROFILE", "SESSION", "ARTIFACT", "PACKAGE", "DELETION"]
    aggregate_id: str = Field(min_length=1)
    aggregate_version: int = Field(ge=0)
    event_type: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

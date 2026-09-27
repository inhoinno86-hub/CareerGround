"""Initial identity/profile tables. Later migrations add policy-domain tables."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED', 'DELETING', 'ERASED')",
            name="ck_accounts_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_auth_identity_issuer_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CareerProfile(Base):
    __tablename__ = "career_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_career_profiles_account_id"),
        UniqueConstraint("id", "account_id", name="uq_career_profile_owner_pair"),
        CheckConstraint("version >= 0", name="ck_career_profiles_version"),
        CheckConstraint(
            "status IN ('ACTIVE', 'DELETING', 'ERASED')", name="ck_career_profiles_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DeletionRequest(Base):
    """Minimal restricted tracking row; never store source text here."""

    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint("scope IN ('ACCOUNT', 'PROFILE')", name="ck_deletion_requests_scope"),
        CheckConstraint(
            "status IN ('DELETING', 'ERASED', 'FAILED')", name="ck_deletion_requests_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    impact_digest: Mapped[str] = mapped_column(String(96), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionWorkItem(Base):
    """Object identifier and action only; future workers own retries and erasure."""

    __tablename__ = "deletion_work_items"
    __table_args__ = (
        UniqueConstraint(
            "request_id", "kind", "target_id", "action", name="uq_deletion_work_item_target"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'DONE', 'FAILED')", name="ck_deletion_work_items_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deletion_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(512), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class ProfilingSession(Base):
    """Explicit CareerGround work session, not an ordinary chat conversation."""

    __tablename__ = "profiling_sessions"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_profiling_session_owner_pair"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profiling_session_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'EXPIRED', 'DELETING', 'ERASED')",
            name="ck_profiling_sessions_status",
        ),
        CheckConstraint("base_profile_version >= 0", name="ck_profiling_sessions_base_version"),
        CheckConstraint(
            "retention_expires_at > last_activity_at", name="ck_profiling_sessions_retention"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfilingInput(Base):
    """One explicitly submitted input, with no general-chat ingestion path."""

    __tablename__ = "profiling_inputs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_input_owned_session",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("session_id", "idempotency_key", name="uq_profiling_input_idempotency"),
        CheckConstraint(
            "content_kind IN ('USER_STATEMENT', 'SELECTED_CHAT_EXCERPT', "
            "'PASTED_DOCUMENT_EXCERPT', 'CORRECTION')",
            name="ck_profiling_inputs_kind",
        ),
        CheckConstraint("length(body) BETWEEN 1 AND 20000", name="ck_profiling_inputs_body_size"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

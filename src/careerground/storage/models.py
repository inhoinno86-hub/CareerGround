"""Initial identity/profile tables. Later migrations add policy-domain tables."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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


class RequestLimitBucket(Base):
    """Short-lived HMAC account/lane counter; contains no source, token or raw ID."""

    __tablename__ = "request_limit_buckets"
    __table_args__ = (
        CheckConstraint("requests >= 1", name="ck_request_limit_requests"),
        CheckConstraint("window_start >= 0", name="ck_request_limit_window"),
        CheckConstraint("expires_at > window_start", name="ck_request_limit_expiry"),
    )

    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class BrowserOperation(Base):
    """Expiring MCP confirmation and metadata receipt; never stores source text/tokens."""

    __tablename__ = "browser_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_browser_operation_owned_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint("request_key", name="uq_browser_operation_request"),
        CheckConstraint(
            "action IN ('FACT_REVIEW', 'WORDING_REVIEW', 'PROFILE_EXPORT', 'RESUME_EXPORT', 'CONFLICT_REVIEW', 'BOUNDARY_REVIEW', 'JD_PASTE', 'JD_LINK', 'R1_DRAFT')",
            name="ck_browser_operation_action",
        ),
        CheckConstraint(
            "status IN ('WAITING', 'DONE', 'CONSUMED')", name="ck_browser_operation_status"
        ),
        CheckConstraint("profile_version >= 0", name="ck_browser_operation_version"),
        CheckConstraint("expires_at > created_at", name="ck_browser_operation_expiry"),
        CheckConstraint(
            "format IN ('NONE', 'JSON', 'MARKDOWN')", name="ck_browser_operation_format"
        ),
        CheckConstraint(
            "(status = 'WAITING' AND browser_key IS NULL AND confirmation_key IS NULL AND result_json IS NULL) OR (status IN ('DONE', 'CONSUMED') AND browser_key IS NOT NULL AND confirmation_key IS NOT NULL AND result_json IS NOT NULL)",
            name="ck_browser_operation_completion",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connection_key: Mapped[str] = mapped_column(String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="WAITING")
    browser_key: Mapped[str | None] = mapped_column(String(64))
    confirmation_key: Mapped[str | None] = mapped_column(String(64))
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
        CheckConstraint("protocol_cycle >= 0", name="ck_profiling_sessions_cycle"),
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
    protocol_cycle: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
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
        UniqueConstraint("id", "account_id", name="uq_profiling_input_owner_pair"),
        UniqueConstraint("id", "account_id", "session_id", name="uq_profiling_input_scope_pair"),
        UniqueConstraint(
            "id", "account_id", "session_id", "protocol_cycle", name="uq_profiling_input_cycle_pair"
        ),
        CheckConstraint("protocol_cycle >= 0", name="ck_profiling_inputs_cycle"),
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
    protocol_cycle: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfilingProtocolStep(Base):
    """Temporary question delivery and sourced observation for one protocol state."""

    __tablename__ = "profiling_protocol_steps"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "protocol_cycle", "state", name="uq_profiling_protocol_step_state"
        ),
        ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_protocol_step_owned_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_input_id", "account_id", "session_id", "protocol_cycle"],
            [
                "profiling_inputs.id",
                "profiling_inputs.account_id",
                "profiling_inputs.session_id",
                "profiling_inputs.protocol_cycle",
            ],
            name="fk_profiling_protocol_step_owned_input",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "state IN ('CONTEXT_DISCOVERY', 'ROLE_DISCOVERY', 'PROJECT_DISCOVERY', "
            "'RESPONSIBILITY_DISCOVERY', 'CONTRIBUTION_DISCOVERY', 'OWNERSHIP_PROBING', "
            "'TECHNICAL_DEPTH_PROBING', 'VALIDATION_PROBING', 'OUTCOME_PROBING', "
            "'EVIDENCE_CAPTURE', 'CLAIM_DRAFTING', 'CLAIM_CONFIRMATION', 'BOUNDARY_CHECK')",
            name="ck_profiling_protocol_step_state",
        ),
        CheckConstraint("asked_count BETWEEN 0 AND 2", name="ck_profiling_protocol_step_count"),
        CheckConstraint("protocol_cycle >= 0", name="ck_profiling_protocol_step_cycle"),
        CheckConstraint(
            "observation_status IS NULL OR observation_status IN "
            "('SATISFIED', 'UNKNOWN', 'CONFLICT')",
            name="ck_profiling_protocol_step_observation",
        ),
        CheckConstraint(
            "(asked_count = 0 AND first_delivery_key IS NULL AND second_delivery_key IS NULL) "
            "OR (asked_count = 1 AND first_delivery_key IS NOT NULL "
            "AND second_delivery_key IS NULL) OR (asked_count = 2 "
            "AND first_delivery_key IS NOT NULL AND second_delivery_key IS NOT NULL)",
            name="ck_profiling_protocol_step_delivery",
        ),
        CheckConstraint(
            "observation_status IS NULL OR observation_status = 'UNKNOWN' "
            "OR source_input_id IS NOT NULL",
            name="ck_profiling_protocol_step_source",
        ),
        CheckConstraint(
            "observation_status NOT IN ('UNKNOWN', 'CONFLICT') OR "
            "(reason IS NOT NULL AND length(reason) BETWEEN 1 AND 1000)",
            name="ck_profiling_protocol_step_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    protocol_cycle: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    asked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_delivery_key: Mapped[str | None] = mapped_column(String(128))
    second_delivery_key: Mapped[str | None] = mapped_column(String(128))
    observation_status: Mapped[str | None] = mapped_column(String(16))
    source_input_id: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEvent(Base):
    """Reference-only internal event. No arbitrary payload or source text column."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("handler_id", name="uq_outbox_handler_id"),
        Index("ix_outbox_pending", "status", "next_attempt_at", "id"),
        CheckConstraint(
            "event_type IN ('RETENTION_SWEEP', 'DELETION_WORK', 'PRIVATE_OBJECT_DELETE')",
            name="ck_outbox_event_type",
        ),
        CheckConstraint("status IN ('PENDING', 'DONE', 'DEAD')", name="ck_outbox_status"),
        CheckConstraint("attempts >= 0 AND attempts <= 5", name="ck_outbox_attempts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    handler_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxReceipt(Base):
    """A handler's canonical mutation and this receipt commit together."""

    __tablename__ = "outbox_receipts"

    handler_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ErasureLedger(Base):
    """Independent reference-only deny list for quarantined restore."""

    __tablename__ = "erasure_ledger"
    __table_args__ = (
        CheckConstraint("scope IN ('ACCOUNT', 'PROFILE')", name="ck_erasure_ledger_scope"),
    )

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)


class PrivateObject(Base):
    """Opaque registry entry for an explicitly scoped private original."""

    __tablename__ = "private_objects"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_private_object_owner_pair"),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_private_object_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "object_class IN ('UPLOAD_ORIGINAL', 'OPTIONAL_RECORDING')",
            name="ck_private_objects_class",
        ),
        CheckConstraint("status IN ('ACTIVE', 'DELETING')", name="ck_private_objects_status"),
        CheckConstraint(
            "retention_expires_at > retention_anchor_at", name="ck_private_objects_retention"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    object_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    retention_anchor_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PrivateObjectVersion(Base):
    """Every provider version ID must be inventoried before erasure can be verified."""

    __tablename__ = "private_object_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["object_id", "account_id"],
            ["private_objects.id", "private_objects.account_id"],
            name="fk_private_object_version_owned_object",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "object_id", "provider_version_id", name="uq_private_object_provider_version"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DELETE_PENDING', 'DELETED')",
            name="ck_private_object_versions_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider_version_id: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfilingDraft(Base):
    """Temporary proposed atomic wording, never part of the canonical profile."""

    __tablename__ = "profiling_drafts"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_profiling_draft_owner_pair"),
        UniqueConstraint(
            "id", "account_id", "session_id", "scope_key", name="uq_profiling_draft_scope_pair"
        ),
        ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_draft_owned_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_input_id", "account_id", "session_id"],
            ["profiling_inputs.id", "profiling_inputs.account_id", "profiling_inputs.session_id"],
            name="fk_profiling_draft_owned_input",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'IN_REVIEW', 'EDIT_REQUIRED', 'EXCLUDED', 'PROMOTED')",
            name="ck_profiling_drafts_status",
        ),
        CheckConstraint("length(exact_text) BETWEEN 1 AND 20000", name="ck_profiling_drafts_text"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_input_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfilingReviewBatch(Base):
    """Exact temporary review snapshot for at most five same-scope drafts."""

    __tablename__ = "profiling_review_batches"
    __table_args__ = (
        UniqueConstraint("id", "account_id", name="uq_profiling_review_batch_owner_pair"),
        UniqueConstraint(
            "id",
            "account_id",
            "session_id",
            "scope_key",
            name="uq_profiling_review_batch_scope_pair",
        ),
        ForeignKeyConstraint(
            ["session_id", "account_id"],
            ["profiling_sessions.id", "profiling_sessions.account_id"],
            name="fk_profiling_review_batch_owned_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["profile_id", "account_id"],
            ["career_profiles.id", "career_profiles.account_id"],
            name="fk_profiling_review_batch_owned_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('PREPARED', 'SUBMITTED', 'EXPIRED')",
            name="ck_profiling_review_batches_status",
        ),
        CheckConstraint("base_profile_version >= 0", name="ck_profiling_review_batches_version"),
        CheckConstraint("expires_at > created_at", name="ck_profiling_review_batches_expiry"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    base_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProfilingReviewItem(Base):
    """User decision is nullable until explicitly submitted; never default accept."""

    __tablename__ = "profiling_review_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "account_id", "session_id", "scope_key"],
            [
                "profiling_review_batches.id",
                "profiling_review_batches.account_id",
                "profiling_review_batches.session_id",
                "profiling_review_batches.scope_key",
            ],
            name="fk_profiling_review_item_owned_batch",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["draft_id", "account_id", "session_id", "scope_key"],
            [
                "profiling_drafts.id",
                "profiling_drafts.account_id",
                "profiling_drafts.session_id",
                "profiling_drafts.scope_key",
            ],
            name="fk_profiling_review_item_owned_draft",
            ondelete="CASCADE",
        ),
        UniqueConstraint("batch_id", "position", name="uq_profiling_review_item_position"),
        UniqueConstraint("batch_id", "draft_id", name="uq_profiling_review_item_draft"),
        CheckConstraint("position BETWEEN 1 AND 5", name="ck_profiling_review_items_position"),
        CheckConstraint(
            "decision IS NULL OR decision IN ('ACCEPT', 'EDIT', 'FOLLOW_UP', "
            "'EXCLUDE_NOT_TRUE', 'EXCLUDE_DO_NOT_USE')",
            name="ck_profiling_review_items_decision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_input_id: Mapped[str] = mapped_column(String(36), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(24))

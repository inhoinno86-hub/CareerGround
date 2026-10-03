"""Local synthetic product-MCP foundation; deliberately has no ASGI entrypoint.

This factory uses a distinct product scope and database-backed account gate. It
must not be pointed at real user data before provider and erasure gates pass.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, Resource, TextContent, ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.types import ASGIApp

from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import (
    AuthenticationRequired,
    ResourceNotFound,
    VerifiedIdentity,
    get_owned_profile,
    resolve_account_id,
)
from careerground.domain.browser_operations import (
    BrowserOperationRejected,
    BrowserOperationService,
    BrowserOperationUnavailable,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    ReviewIdempotencyConflict,
    ReviewStale,
    ReviewUnavailable,
)
from careerground.domain.contracts import ErrorResponse, SuccessResponse
from careerground.domain.contracts import ToolError as FunctionalToolError
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    DeletionTargetUnavailable,
)
from careerground.domain.graph_projection import (
    GraphUnavailable,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.jd_analysis import JDUnavailable, get_jd_analysis
from careerground.domain.jd_mapping import JDMappingRejected, get_jd_mapping
from careerground.domain.profile_export_selection import (
    ProfileSelectionRejected,
    VersionSelector,
    resolve_profile_version,
    selection_values,
)
from careerground.domain.profiling_draft_extraction import (
    DraftSpan,
    DraftSpanRejected,
    propose_source_span_drafts_once,
)
from careerground.domain.profiling_protocol_workspace import get_protocol_question_plan
from careerground.domain.profiling_workspace import (
    InputKind,
    ProfilingExpired,
    ProfilingIdempotencyConflict,
    ProfilingPaused,
    ProfilingUnavailable,
    ProfilingValidationError,
    ProfilingVersionConflict,
    append_explicit_profiling_input,
    pause_profiling_session,
    start_profiling_session,
)
from careerground.domain.profiling_workspace import (
    get_profiling_session as read_profiling_session,
)
from careerground.domain.project_scope_guard import deleted_project_scope_exists
from careerground.domain.request_limits import (
    DEFAULT_REQUEST_LIMITS,
    AccountRequestLimiter,
    RequestLimitExceeded,
    RequestLimitPolicy,
)
from careerground.domain.resume_draft import ResumeDraftUnavailable, get_resume_trace
from careerground.domain.safe_events import record_result
from careerground.mcp.account_access import ActiveAccountTokenVerifier
from careerground.mcp.confirmation_tools import (
    ACTION_SCOPES,
    ARTIFACT_WRITE_SCOPE,
    EXPORT_SCOPE,
    TOOL_SCOPES,
    register_confirmation_tools,
)
from careerground.mcp.local_ingress import LocalMCPIngress
from careerground.mcp.oauth_resource import (
    JwtTokenVerifier,
    LocalMetadataPathAlias,
    McpOAuthSettings,
    OAuthToolDeclarations,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import (
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingSession,
)

PROFILE_READ_SCOPE = "career.profile.read"
PROFILE_WRITE_SCOPE = "career.profile.write"
ARTIFACT_READ_SCOPE = "career.artifact.read"
DELETE_SCOPE = "career.delete"

_TOOL_ARGUMENTS = {
    "get_account_profile": frozenset(),
    "get_my_profile": frozenset(),
    "get_confirmation_status": frozenset({"request_id"}),
    "initialize_career_profile": frozenset({"policy_version"}),
    "propose_profiling_drafts": frozenset(
        {
            "profiling_session_id",
            "source_input_id",
            "base_profile_version",
            "experience_scope_id",
            "spans",
        }
    ),
    "get_owned_profile_metadata": frozenset({"profile_id"}),
    "get_profiling_session": frozenset({"profiling_session_id"}),
    "get_career_profile": frozenset({"profile_id", "profile_version"}),
    "get_claim_evidence": frozenset({"claim_id", "profile_version"}),
    "get_claim_review": frozenset({"review_batch_id"}),
    "get_jd_analysis": frozenset({"jd_id", "profile_version"}),
    "get_resume_trace": frozenset({"artifact_id"}),
    "start_profiling": frozenset({"profile_id", "goal", "policy_version", "idempotency_key"}),
    "add_profiling_input": frozenset(
        {
            "profiling_session_id",
            "base_profile_version",
            "content",
            "content_kind",
            "idempotency_key",
        }
    ),
    "pause_profiling": frozenset({"profiling_session_id"}),
    "prepare_claim_review": frozenset(
        {"profiling_session_id", "experience_scope_id", "base_profile_version", "idempotency_key"}
    ),
    "preview_data_deletion": frozenset({"scope", "target_ids"}),
    "analyze_jd": frozenset({"profile_id", "profile_version", "jd_text"}),
    "execute_data_deletion": frozenset(
        {"scope", "target_id", "profile_version", "idempotency_key", "approval_receipt"}
    ),
    "request_user_confirmation": frozenset(
        {"action", "target_id", "profile_version", "format", "idempotency_key"}
    ),
    "submit_claim_review": frozenset({"review_batch_id", "approval_receipt"}),
    "submit_resume_wording_review": frozenset({"artifact_id", "approval_receipt"}),
    "export_profile_data": frozenset(
        {"profile_id", "profile_version", "format", "approval_receipt"}
    ),
    "export_resume": frozenset({"artifact_id", "format", "approval_receipt"}),
    "get_deletion_status": frozenset({"erasure_request_id"}),
    "resolve_claim_conflict": frozenset({"claim_id", "approval_receipt"}),
    "review_boundary_change": frozenset({"claim_id", "approval_receipt"}),
    "record_selected_jd": frozenset({"profile_id", "profile_version", "approval_receipt"}),
    "link_jd_requirement": frozenset({"jd_id", "approval_receipt"}),
    "generate_resume_draft": frozenset({"jd_id", "profile_version", "approval_receipt"}),
}


class StrictProductMCPServer(MCPServer):
    """Reject surplus or missing tool fields before the SDK discards them."""

    guard_call: Callable[[str, dict[str, Any]], None]
    guard_invalid: Callable[[], None]
    list_private_export_resources: Callable[[], list[Resource]]

    async def list_resources(self) -> list[Resource]:
        resources = await super().list_resources()
        return resources + self.list_private_export_resources()

    def invalid_tool_call(self) -> CallToolResult:
        # Every authenticated malformed tool call reserves the shared read lane.
        # No write scope is inferred from untrusted or incomplete arguments.
        self.guard_invalid()
        return _functional_error("VALIDATION_FAILED")

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.input_schema["additionalProperties"] = False
            original = deepcopy(tool.output_schema)
            success = SuccessResponse.model_json_schema()
            success["required"] = ["status", "data", "next_actions", "user_message"]
            success["properties"]["data"] = original
            error = ErrorResponse.model_json_schema()
            error["required"] = ["status", "error"]
            definitions = {}
            for schema in (original, success, error):
                definitions.update(schema.pop("$defs", {}))
            tool.output_schema = {"type": "object", "oneOf": [success, error], "$defs": definitions}
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any], context=None):
        try:
            allowed = _TOOL_ARGUMENTS.get(name)
            optional = (
                {"inclusion"}
                if name in {"request_user_confirmation", "export_profile_data"}
                else set()
            )
            if (
                type(arguments) is not dict
                or allowed is None
                or not allowed <= set(arguments)
                or set(arguments) - allowed - optional
            ):
                return self.invalid_tool_call()
            # Reject SDK coercion and errors containing submitted values.
            for field, value in arguments.items():
                if field == "inclusion":
                    if (
                        name == "request_user_confirmation"
                        and arguments.get("action") != "PROFILE_EXPORT"
                    ):
                        return self.invalid_tool_call()
                    try:
                        selection_values(value)
                    except ProfileSelectionRejected:
                        return self.invalid_tool_call()
                    continue
                if (
                    field == "profile_version"
                    and value == "CURRENT"
                    and (
                        name in {"get_career_profile", "export_profile_data"}
                        or (
                            name == "request_user_confirmation"
                            and arguments.get("action") == "PROFILE_EXPORT"
                        )
                    )
                ):
                    continue
                if field == "spans":
                    if (
                        type(value) is not list
                        or not 1 <= len(value) <= 5
                        or any(
                            type(span) is not dict
                            or set(span) != {"start", "end"}
                            or any(type(v) is not int for v in span.values())
                            for span in value
                        )
                    ):
                        return self.invalid_tool_call()
                    continue
                if field == "target_ids":
                    if (
                        type(value) is not list
                        or len(value) != 1
                        or any(type(item) is not str or not item for item in value)
                    ):
                        return self.invalid_tool_call()
                    continue
                expected = int if field in {"profile_version", "base_profile_version"} else str
                if type(value) is not expected:
                    return self.invalid_tool_call()
            if name == "request_user_confirmation" and arguments["action"] not in ACTION_SCOPES:
                return self.invalid_tool_call()
            self.guard_call(name, arguments)
            result = await super().call_tool(name, arguments, context)
            data = result.structured_content
            if not isinstance(data, dict):
                raise TypeError("Missing structured tool output")
            if data.get("ok") is False:
                code = {
                    "IDEMPOTENCY_CONFLICT": "VALIDATION_FAILED",
                    "REVIEW_STALE": "VERSION_CONFLICT",
                }.get(data["error_code"], data["error_code"])
                return _functional_error(code)
            if data.get("found") is False:
                return _functional_error("NOT_FOUND")
            envelope = SuccessResponse(
                data=data, next_actions=[], user_message="요청이 처리됐습니다."
            )
            record_result("mcp", "OK")
            return _tool_result(envelope.model_dump(mode="json"))
        except RequestLimitExceeded as exc:
            return _functional_error("RATE_LIMITED", retry_after_seconds=exc.retry_after_seconds)
        except PermissionError:
            return _functional_error("FORBIDDEN")
        except BrowserOperationRejected:
            return _functional_error("REVIEW_REQUIRED")
        except ToolError as exc:
            if isinstance(exc.__cause__, BrowserOperationRejected):
                return _functional_error(
                    "NOT_FOUND"
                    if isinstance(exc.__cause__, BrowserOperationUnavailable)
                    else "REVIEW_REQUIRED"
                )
            return _functional_error(
                "INTERNAL_ERROR" if isinstance(exc, UnexpectedToolError) else "VALIDATION_FAILED"
            )
        except Exception:  # noqa: BLE001 - the public failure boundary must hide every SDK/DB crash
            # SDK error chains can contain SQL binds or submitted source values.
            # Return before SDK's exception logger serializes the exception chain.
            return _functional_error("INTERNAL_ERROR")


def _tool_result(payload: dict, *, error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
        is_error=error,
    )


def _functional_error(code: str, *, retry_after_seconds: int | None = None) -> CallToolResult:
    messages = {
        "FORBIDDEN": "이 요청을 수행할 권한이 없습니다.",
        "NOT_FOUND": "요청한 내용을 찾을 수 없습니다.",
        "VALIDATION_FAILED": "요청 형식을 확인해 주세요.",
        "VERSION_CONFLICT": "현재 버전을 확인하고 새 화면에서 다시 검토해 주세요.",
        "SESSION_PAUSED": "명시적으로 세션을 재개한 뒤 입력해 주세요.",
        "SESSION_EXPIRED": "세션이 만료됐습니다. 새 세션을 시작해 주세요.",
        "RATE_LIMITED": "잠시 후 다시 시도해 주세요.",
        "INTERNAL_ERROR": "처리 상태를 다시 확인해 주세요. 같은 작업을 바로 반복하지 마세요.",
        "REVIEW_REQUIRED": "현재 내용을 브라우저에서 직접 확인하고 유효한 완료 증명을 전달해 주세요.",
    }
    if code not in messages:
        code = "INTERNAL_ERROR"
    event = (
        code
        if code in {"FORBIDDEN", "NOT_FOUND", "VALIDATION_FAILED", "RATE_LIMITED", "INTERNAL_ERROR"}
        else "VALIDATION_FAILED"
    )
    record_result("mcp", event)
    payload = ErrorResponse(
        error=FunctionalToolError(
            code=code,
            message=messages[code],
            recoverable=code not in {"FORBIDDEN", "NOT_FOUND"},
            next_action="RETRY_AFTER" if code == "RATE_LIMITED" else "CHECK_CURRENT_STATE",
            retry_after_seconds=retry_after_seconds,
        )
    ).model_dump(mode="json")
    return _tool_result(payload, error=True)


class SourceSpanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class ProfilingDraftProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    error_code: str | None = None
    drafts: list[dict[str, str | int]] = Field(default_factory=list)
    canonical_saved: Literal[False] = False
    review_required: Literal[True] = True
    atomicity: Literal["UNVERIFIED"] = "UNVERIFIED"


class AccountProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)


class JDRequirementProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    exact_text: str
    source_start: int
    source_end: int
    requirement_type: Literal["UNCLASSIFIED"]
    gap_status: Literal["NOT_MAPPED"]


class JDProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    error_code: str | None = None
    profile_id: str | None = None
    profile_version: int | None = None
    mode: Literal["MOCK_ONLY"] = "MOCK_ONLY"
    source_hash: str | None = None
    source_length: int | None = None
    requirements: list[JDRequirementProposalOutput] = Field(default_factory=list)
    canonical_saved: Literal[False] = False
    analysis_kind: Literal["UNAPPROVED_MOCK_PROPOSAL"] = "UNAPPROVED_MOCK_PROPOSAL"
    review_required: Literal[True] = True


class LocalDeletionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    error_code: str | None = None
    mode: Literal["MOCK_ONLY"] = "MOCK_ONLY"
    status: Literal["WAITING", "DELETING"] | None = None
    request_id: str | None = None
    erasure_request_id: str | None = None
    confirmation_path: str | None = None
    expires_at: datetime | None = None
    user_message: str | None = None
    coverage: Literal["FOUNDATION_ONLY"] = "FOUNDATION_ONLY"
    completed_in_browser: bool = False
    ready_to_execute: Literal[False] = False


class DeletionPreviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["ACCOUNT", "PROFILE", "SESSION", "EVIDENCE", "PROJECT"]
    found: bool = True
    coverage: Literal["FOUNDATION_ONLY"] = "FOUNDATION_ONLY"
    ready_to_execute: Literal[False] = False
    counts: dict[str, int]


class ProfileMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    profile_id: str | None = Field(default=None, min_length=1)
    version: int | None = Field(default=None, ge=0)


class InitializationOutput(ProfileMetadata):
    ok: bool = True
    error_code: str | None = None


class PendingProfilingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiling_session_id: str
    base_profile_version: int
    experience_scope_ids: list[str]


class OwnedProfileDiscovery(ProfileMetadata):
    pending_profiling_sessions: list[PendingProfilingMetadata] = Field(default_factory=list)


class ProfilingSessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    session_id: str | None = None
    status: str | None = None
    base_profile_version: int | None = Field(default=None, ge=0)
    current_profile_version: int | None = Field(default=None, ge=0)
    last_activity_at: datetime | None = None
    retention_expires_at: datetime | None = None


class ProfilingStartOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    base_profile_version: int | None = None
    protocol_state: str | None = None
    retention_expires_at: datetime | None = None
    collection_scope: str | None = None


class ProfilingInputOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    input_id: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    protocol_cycle: int | None = None
    retention_expires_at: datetime | None = None


class ProfilingPauseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    profiling_session_id: str | None = None
    session_status: str | None = None
    retention_expires_at: datetime | None = None


class ClaimSummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: str
    exact_text: str
    scope_key: str
    knowledge_status: str
    consistency_status: str
    usage_policy: str


class CareerProfileOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    profile_id: str | None = None
    profile_version: int | None = None
    claims: list[ClaimSummaryOutput] = Field(default_factory=list)
    constraint_count: int | None = None


class EvidenceExcerptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    exact_excerpt: str
    source_id: str
    original_input_ref: str
    source_content_hash: str
    relation_type: str
    source_availability: str


class ClaimConstraintOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_type: str
    exact_text: str


class ClaimEvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    claim: ClaimSummaryOutput | None = None
    profile_version: int | None = None
    evidence: list[EvidenceExcerptOutput] = Field(default_factory=list)
    reviewed: bool | None = None
    constraints: list[ClaimConstraintOutput] = Field(default_factory=list)


class ClaimReviewItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    position: int
    exact_text: str
    claim_type: str
    scope_key: str
    source_input_id: str
    decision: str | None = None


class ClaimReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    review_batch_id: str | None = None
    profile_id: str | None = None
    base_profile_version: int | None = None
    current_profile_version: int | None = None
    base_version_compatible: bool | None = None
    review_digest: str | None = None
    expires_at: datetime | None = None
    scope_key: str | None = None
    items: list[ClaimReviewItemOutput] = Field(default_factory=list)


class ClaimReviewPrepareOutput(ClaimReviewOutput):
    ok: bool
    error_code: str | None = None


class JDRequirementOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    exact_text: str
    source_start: int
    source_end: int
    requirement_id: str
    linked_claim_ids: list[str] = Field(default_factory=list)
    gap_status: str


class JDAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    jd_id: str | None = None
    jd_version: int | None = None
    profile_version: int | None = None
    stale_relative_to_current_profile: bool | None = None
    source_hash: str | None = None
    source_length: int | None = None
    requirements: list[JDRequirementOutput] = Field(default_factory=list)


class ResumeUnitTraceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str
    exact_text: str
    claim_id: str
    evidence_ids: list[str]
    evidence_excerpts: list[str]
    original_input_refs: list[str]
    wording_level: str
    review_status: str
    source_unit_id: str | None = None


class ResumeTraceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    artifact_id: str | None = None
    artifact_version: int | None = None
    profile_version: int | None = None
    jd_id: str | None = None
    stale_relative_to_current_profile: bool | None = None
    units: list[ResumeUnitTraceOutput] = Field(default_factory=list)
    source_artifact_id: str | None = None


def build_product_foundation_app(
    settings: McpOAuthSettings,
    *,
    session_factory: Callable[[], Session],
    review_signing_secret: bytes,
    signing_key: Callable[[str], object] | None = None,
    request_limits: RequestLimitPolicy = DEFAULT_REQUEST_LIMITS,
    presentation_signing_secret: bytes | None = None,
    token_is_revoked: Callable[[str], bool] | None = None,
    local_deletion_adapter: Callable[..., dict] | None = None,
    enrollment_account_id: Callable[[VerifiedIdentity], str | None] | None = None,
    management_origin: str | None = None,
) -> ASGIApp:
    """Build isolated product auth/ownership checks for synthetic local tests."""

    review_preparation = ClaimReviewPreparation(review_signing_secret)
    limiter = AccountRequestLimiter(session_factory, review_signing_secret, policy=request_limits)
    operation_service = BrowserOperationService(
        review_signing_secret, presentation_signing_secret or review_signing_secret
    )
    verifier = ActiveAccountTokenVerifier(
        JwtTokenVerifier(
            settings,
            required_scope=frozenset(
                {
                    PROFILE_READ_SCOPE,
                    PROFILE_WRITE_SCOPE,
                    ARTIFACT_READ_SCOPE,
                    DELETE_SCOPE,
                    EXPORT_SCOPE,
                    ARTIFACT_WRITE_SCOPE,
                }
            ),
            signing_key=signing_key,
        ),
        issuer=settings.issuer,
        session_factory=session_factory,
        token_is_revoked=token_is_revoked,
        enrollment_account_id=enrollment_account_id,
    )
    server = StrictProductMCPServer(
        name="careerground-product-foundation",
        version="0.1.0",
        instructions=(
            "Synthetic-only CareerGround. Get get_my_profile before starting; initialize_career_profile only after an explicit request. Store only explicit task input; propose_profiling_drafts accepts exact source character ranges, never inferred facts. Prepare review, open confirmation_url in the authenticated management browser, then submit its receipt on this connection. Conversation yes is not approval."
        ),
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[],
            validate_token_resource=True,
        ),
    )

    def current_account_id(session: Session, required_scope: str = PROFILE_READ_SCOPE) -> str:
        access = get_access_token()
        if (
            access is None
            or not access.subject
            or (required_scope and required_scope not in access.scopes)
        ):
            raise PermissionError("Authentication required")
        try:
            return resolve_account_id(session, VerifiedIdentity(settings.issuer, access.subject))
        except AuthenticationRequired as exc:
            raise PermissionError("Authentication required") from exc

    def guard_call(name: str, arguments: dict[str, Any]) -> None:
        write = name in {
            "initialize_career_profile",
            "propose_profiling_drafts",
            "start_profiling",
            "add_profiling_input",
            "pause_profiling",
            "prepare_claim_review",
        } or (
            name in TOOL_SCOPES
            and name not in {"get_deletion_status", "get_confirmation_status", "analyze_jd"}
        )
        scope = (
            PROFILE_WRITE_SCOPE
            if write
            else DELETE_SCOPE
            if name == "preview_data_deletion"
            else ARTIFACT_READ_SCOPE
            if name in {"get_jd_analysis", "get_resume_trace"}
            else PROFILE_READ_SCOPE
        )
        if name in TOOL_SCOPES:
            scope = (
                ACTION_SCOPES[arguments["action"]]
                if name == "request_user_confirmation"
                else TOOL_SCOPES[name]
            )
        with session_factory() as session:
            try:
                account_id = current_account_id(session, scope)
            except PermissionError:
                access = get_access_token()
                if (
                    name not in {"initialize_career_profile", "get_my_profile"}
                    or access is None
                    or scope not in access.scopes
                ):
                    raise
                identity = VerifiedIdentity(settings.issuer, access.subject)
                account_id = enrollment_account_id(identity) if enrollment_account_id else None
                if not account_id:
                    raise PermissionError from None
        limiter.consume(account_id, "write" if write else "read")

    server.guard_call = guard_call

    def guard_invalid() -> None:
        with session_factory() as session:
            try:
                account_id = current_account_id(session, "")
            except PermissionError:
                access = get_access_token()
                identity = VerifiedIdentity(settings.issuer, access.subject) if access else None
                account_id = (
                    enrollment_account_id(identity) if identity and enrollment_account_id else None
                )
                if not account_id:
                    raise PermissionError from None
        limiter.consume(account_id, "read")

    server.guard_invalid = guard_invalid
    register_confirmation_tools(
        server,
        settings=settings,
        session_factory=session_factory,
        current_account_id=current_account_id,
        service=operation_service,
        limiter=limiter,
        management_origin=management_origin,
    )

    @server.tool(
        name="analyze_jd",
        title="Preview synthetic JD proposal",
        description="MOCK_ONLY explicit bullet span proposal. Read-only, not saved, no semantic classification or coverage. Store selected excerpts separately through browser JD_PASTE confirmation.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def analyze_jd(profile_id: str, profile_version: int, jd_text: str) -> JDProposalOutput:
        from careerground.domain.text_proposal_validation import (
            MockTextAnalyzer,
            TextProposalRejected,
            prepare_mock_jd_text_proposal,
        )

        with session_factory() as session:
            account_id = current_account_id(session, ARTIFACT_WRITE_SCOPE)
            try:
                proposal = prepare_mock_jd_text_proposal(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                    source_text=jd_text,
                    analyzer=MockTextAnalyzer(),
                )
            except TextProposalRejected:
                return JDProposalOutput(ok=False, error_code="VALIDATION_FAILED")
        return JDProposalOutput.model_validate(
            {
                "profile_id": proposal.profile_id,
                "profile_version": proposal.profile_version,
                "source_hash": proposal.source_hash,
                "source_length": len(jd_text),
                "requirements": [
                    JDRequirementProposalOutput(
                        ordinal=item.ordinal,
                        exact_text=item.exact_text,
                        source_start=item.source_start,
                        source_end=item.source_end,
                        requirement_type=item.requirement_type,
                        gap_status=item.gap_status,
                    )
                    for item in proposal.candidates
                ],
                "canonical_saved": False,
                "analysis_kind": "UNAPPROVED_MOCK_PROPOSAL",
                "review_required": True,
            }
        )

    @server.tool(
        name="execute_data_deletion",
        title="Approve and execute local synthetic deletion",
        description="MOCK_ONLY local adapter. Empty approval_receipt requests a bound browser confirmation; valid receipt from separate impact review/mock step-up/final approval executes only that same connection and exact scope/version. No production erasure guarantee. Account deletion revokes ordinary MCP access.",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, open_world_hint=False, idempotent_hint=True
        ),
        structured_output=True,
    )
    def execute_data_deletion(
        scope: Literal["ACCOUNT", "PROFILE", "SESSION", "EVIDENCE", "PROJECT"],
        target_id: str,
        profile_version: int,
        idempotency_key: str,
        approval_receipt: str,
    ) -> LocalDeletionOutput:
        if local_deletion_adapter is None:
            return LocalDeletionOutput(ok=False, error_code="REVIEW_REQUIRED")
        from careerground.domain.deletion_preview import DeletionTargetUnavailable
        from careerground.domain.local_deletion_connection import LocalDeletionConnectionRejected
        from careerground.domain.synthetic_deletion_journey import MockDeletionJourneyRejected

        with session_factory() as session:
            account_id = current_account_id(session, DELETE_SCOPE)
        access = get_access_token()
        connection = operation_service.connection_key(
            settings.issuer, access.subject, access.client_id, access.token
        )
        try:
            return LocalDeletionOutput.model_validate(
                local_deletion_adapter(
                    account_id=account_id,
                    connection=connection,
                    connection_expires_at=access.expires_at,
                    scope=scope,
                    target_id=target_id,
                    profile_version=profile_version,
                    idempotency_key=idempotency_key,
                    approval_receipt=approval_receipt,
                )
            )
        except (
            LocalDeletionConnectionRejected,
            MockDeletionJourneyRejected,
            DeletionTargetUnavailable,
        ):
            return LocalDeletionOutput(ok=False, error_code="REVIEW_REQUIRED")

    @server.tool(
        name="preview_data_deletion",
        title="Preview known local deletion counts",
        description="Synthetic known local impact counts for an exact owned scope. No digest or deletion execution; ready_to_execute=false.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def preview_data_deletion(
        scope: Literal["ACCOUNT", "PROFILE", "SESSION", "EVIDENCE", "PROJECT"],
        target_ids: list[str],
    ) -> DeletionPreviewOutput:
        with session_factory() as session:
            account_id = current_account_id(session, DELETE_SCOPE)
            try:
                view = DeletionPreviewService(review_signing_secret).preview(
                    session,
                    account_id=account_id,
                    scope=DeletionScope(scope),
                    target_id=target_ids[0],
                    now=datetime.now(UTC),
                )
            except DeletionTargetUnavailable:
                return DeletionPreviewOutput(scope=scope, found=False, counts={})
            return DeletionPreviewOutput(
                scope=scope, counts=dict(Counter(item.kind for item in view.items))
            )

    @server.tool(
        name="get_account_profile",
        title="Get linked CareerGround account",
        description="Return only a stable, opaque account ID for the authenticated connection.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        meta={"openai/profile": True},
        structured_output=True,
    )
    def get_account_profile() -> AccountProfile:
        with session_factory() as session:
            return AccountProfile(id=current_account_id(session))

    @server.tool(
        name="get_my_profile",
        description="Discover the active owned profile ID/version and up to 10 current unexpired profiling sessions with pending experience scopes. No source text, receipts or other account IDs are returned. Use these server IDs to resume an interrupted review; ask which experience if ambiguous.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_my_profile() -> OwnedProfileDiscovery:
        with session_factory() as session:
            try:
                account_id = current_account_id(session)
            except PermissionError:
                return OwnedProfileDiscovery(found=False)
            profile = session.scalar(
                select(CareerProfile).where(
                    CareerProfile.account_id == account_id, CareerProfile.status == "ACTIVE"
                )
            )
            pending = []
            now = datetime.now(UTC)
            if profile is not None:
                works = session.scalars(
                    select(ProfilingSession)
                    .where(
                        ProfilingSession.account_id == account_id,
                        ProfilingSession.profile_id == profile.id,
                        ProfilingSession.status == "ACTIVE",
                        ProfilingSession.base_profile_version == profile.version,
                        ProfilingSession.retention_expires_at > now,
                    )
                    .order_by(ProfilingSession.last_activity_at.desc(), ProfilingSession.id)
                    .limit(10)
                )
                for work in works:
                    scopes = session.scalars(
                        select(ProfilingDraft.scope_key)
                        .join(ProfilingInput, ProfilingInput.id == ProfilingDraft.source_input_id)
                        .where(
                            ProfilingDraft.account_id == account_id,
                            ProfilingDraft.session_id == work.id,
                            ProfilingDraft.status.in_(("DRAFT", "IN_REVIEW", "EDIT_REQUIRED")),
                            ProfilingDraft.expires_at > now,
                            ProfilingInput.account_id == account_id,
                            ProfilingInput.session_id == work.id,
                            ProfilingInput.protocol_cycle == work.protocol_cycle,
                        )
                        .distinct()
                        .order_by(ProfilingDraft.scope_key)
                        .limit(10)
                    )
                    pending.append(
                        PendingProfilingMetadata(
                            profiling_session_id=work.id,
                            base_profile_version=work.base_profile_version,
                            experience_scope_ids=[
                                scope
                                for scope in scopes
                                if not deleted_project_scope_exists(
                                    session,
                                    account_id=account_id,
                                    profile_id=profile.id,
                                    scope_key=scope,
                                )
                            ],
                        )
                    )
            return OwnedProfileDiscovery(
                found=profile is not None,
                profile_id=profile.id if profile else None,
                version=profile.version if profile else None,
                pending_profiling_sessions=pending,
            )

    @server.tool(
        name="initialize_career_profile",
        description="Explicit first-use initialization under product-policy-v0.1. Identity comes only from verified OAuth; enrollment requires a trusted server admission. Does not approve facts.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def initialize_career_profile(policy_version: str) -> InitializationOutput:
        if policy_version != "product-policy-v0.1":
            return InitializationOutput(found=False, ok=False, error_code="VALIDATION_FAILED")
        access = get_access_token()
        if access is None or not access.subject or PROFILE_WRITE_SCOPE not in access.scopes:
            raise PermissionError
        identity = VerifiedIdentity(settings.issuer, access.subject)
        with session_factory() as session:
            try:
                profile = initialize_account_profile(
                    session,
                    identity=identity,
                    enrollment_account_id=enrollment_account_id(identity)
                    if enrollment_account_id
                    else None,
                )
                output = InitializationOutput(
                    found=True, profile_id=profile.id, version=profile.version
                )
                session.commit()
                return output
            except AuthenticationRequired:
                return InitializationOutput(found=False, ok=False, error_code="FORBIDDEN")

    @server.tool(
        name="propose_profiling_drafts",
        description="Propose 1-5 nonoverlapping exact single-line source ranges (Python Unicode character offsets, end exclusive). Only unapproved CONTRIBUTION drafts are stored. No inferred wording, approval, metrics, owner or Claim type may be supplied. Requires owned current session/input/version.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def propose_profiling_drafts(
        profiling_session_id: str,
        source_input_id: str,
        base_profile_version: int,
        experience_scope_id: str,
        spans: list[SourceSpanInput],
    ) -> ProfilingDraftProposalOutput:
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
                if (
                    view.current_profile_version != base_profile_version
                    or view.base_profile_version != base_profile_version
                ):
                    return ProfilingDraftProposalOutput(ok=False, error_code="VERSION_CONFLICT")
                drafts = propose_source_span_drafts_once(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    source_input_id=source_input_id,
                    scope_key=experience_scope_id,
                    spans=tuple(DraftSpan(p.start, p.end) for p in spans),
                    now=datetime.now(UTC),
                )
                result = ProfilingDraftProposalOutput(
                    drafts=[
                        {
                            "draft_id": draft.id,
                            "source_input_id": draft.source_input_id,
                            "scope_key": draft.scope_key,
                            "claim_type": draft.claim_type,
                            "exact_text": draft.exact_text,
                            "status": draft.status,
                            "source_start": span.start,
                            "source_end": span.end,
                        }
                        for draft, span in zip(drafts, spans, strict=True)
                    ]
                )
                session.commit()
                return result
            except (ProfilingUnavailable, ReviewUnavailable):
                return ProfilingDraftProposalOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingDraftProposalOutput(ok=False, error_code="SESSION_EXPIRED")
            except ReviewStale:
                return ProfilingDraftProposalOutput(ok=False, error_code="VERSION_CONFLICT")
            except (DraftSpanRejected, ValueError):
                return ProfilingDraftProposalOutput(ok=False, error_code="VALIDATION_FAILED")

    @server.tool(
        name="get_owned_profile_metadata",
        title="Get owned profile metadata",
        description="Return only ID and version of an owned profile, or a NOT_FOUND error.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_owned_profile_metadata(profile_id: str) -> ProfileMetadata:
        with session_factory() as session:
            try:
                account_id = current_account_id(session)
                profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
            except ResourceNotFound:
                return ProfileMetadata(found=False)
            return ProfileMetadata(found=True, profile_id=profile.id, version=profile.version)

    @server.tool(
        name="get_profiling_session",
        title="Get owned profiling session metadata",
        description="Return only status, versions, and retention times for an owned session.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_profiling_session_tool(profiling_session_id: str) -> ProfilingSessionMetadata:
        with session_factory() as session:
            try:
                account_id = current_account_id(session)
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
            except (ProfilingUnavailable, ProfilingExpired):
                return ProfilingSessionMetadata(found=False)
            return ProfilingSessionMetadata(
                found=True,
                session_id=view.id,
                status=view.status,
                base_profile_version=view.base_profile_version,
                current_profile_version=view.current_profile_version,
                last_activity_at=view.last_activity_at,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="start_profiling",
        title="Start explicit CareerGround profiling",
        description="Create one temporary synthetic profiling session for an explicitly requested task.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def start_profiling_tool(
        profile_id: str, goal: str, policy_version: str, idempotency_key: str
    ) -> ProfilingStartOutput:
        if goal != "ADD_EXPERIENCE" or policy_version != "product-policy-v0.1":
            return ProfilingStartOutput(ok=False, error_code="VALIDATION_FAILED")
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                profile = get_owned_profile(session, account_id=account_id, profile_id=profile_id)
                work = start_profiling_session(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    base_profile_version=profile.version,
                    now=datetime.now(UTC),
                    idempotency_key=idempotency_key,
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                plan = get_protocol_question_plan(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except (ResourceNotFound, ProfilingUnavailable):
                return ProfilingStartOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingStartOutput(ok=False, error_code="SESSION_EXPIRED")
            except ProfilingVersionConflict:
                return ProfilingStartOutput(ok=False, error_code="VERSION_CONFLICT")
            except ProfilingIdempotencyConflict:
                return ProfilingStartOutput(ok=False, error_code="IDEMPOTENCY_CONFLICT")
            except ProfilingValidationError:
                return ProfilingStartOutput(ok=False, error_code="VALIDATION_FAILED")
            return ProfilingStartOutput(
                ok=True,
                profiling_session_id=view.id,
                session_status=view.status,
                base_profile_version=view.base_profile_version,
                protocol_state=plan.state.value,
                retention_expires_at=view.retention_expires_at,
                collection_scope="Only content explicitly sent to this CareerGround session",
            )

    @server.tool(
        name="add_profiling_input",
        title="Add explicit CareerGround task input",
        description="Store one bounded statement or correction in an owned temporary session.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def add_profiling_input_tool(
        profiling_session_id: str,
        base_profile_version: int,
        content: str,
        content_kind: str,
        idempotency_key: str,
    ) -> ProfilingInputOutput:
        if (
            type(base_profile_version) is not int
            or base_profile_version < 0
            or content_kind not in (InputKind.USER_STATEMENT, InputKind.CORRECTION)
        ):
            return ProfilingInputOutput(ok=False, error_code="VALIDATION_FAILED")
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                item = append_explicit_profiling_input(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    base_profile_version=base_profile_version,
                    content=content,
                    content_kind=InputKind(content_kind),
                    idempotency_key=idempotency_key,
                    now=datetime.now(UTC),
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except ProfilingUnavailable:
                return ProfilingInputOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingInputOutput(ok=False, error_code="SESSION_EXPIRED")
            except ProfilingPaused:
                return ProfilingInputOutput(ok=False, error_code="SESSION_PAUSED")
            except ProfilingVersionConflict:
                return ProfilingInputOutput(ok=False, error_code="VERSION_CONFLICT")
            except ProfilingIdempotencyConflict:
                return ProfilingInputOutput(ok=False, error_code="IDEMPOTENCY_CONFLICT")
            except ProfilingValidationError:
                return ProfilingInputOutput(ok=False, error_code="VALIDATION_FAILED")
            return ProfilingInputOutput(
                ok=True,
                input_id=item.id,
                profiling_session_id=view.id,
                session_status=view.status,
                protocol_cycle=view.protocol_cycle,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="pause_profiling",
        title="Pause explicit CareerGround profiling",
        description="Pause one owned temporary session without extending its retention.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def pause_profiling_tool(profiling_session_id: str) -> ProfilingPauseOutput:
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                work = pause_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    now=datetime.now(UTC),
                )
                session.flush()
                view = read_profiling_session(
                    session,
                    account_id=account_id,
                    profiling_session_id=work.id,
                    now=datetime.now(UTC),
                )
                session.commit()
            except ProfilingUnavailable:
                return ProfilingPauseOutput(ok=False, error_code="NOT_FOUND")
            except ProfilingExpired:
                return ProfilingPauseOutput(ok=False, error_code="SESSION_EXPIRED")
            return ProfilingPauseOutput(
                ok=True,
                profiling_session_id=view.id,
                session_status=view.status,
                retention_expires_at=view.retention_expires_at,
            )

    @server.tool(
        name="get_career_profile",
        title="Get exact career profile version",
        description="Return canonical Claim summaries only from an owned, stored profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_career_profile_tool(
        profile_id: str, profile_version: VersionSelector
    ) -> CareerProfileOutput:
        with session_factory() as session:
            account_id = current_account_id(session)
            try:
                profile_version = resolve_profile_version(
                    session, account_id=account_id, profile_id=profile_id, selector=profile_version
                )
                view = get_career_profile(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                )
            except (GraphUnavailable, ProfileSelectionRejected):
                return CareerProfileOutput(found=False)
            return CareerProfileOutput(
                found=True,
                profile_id=view.profile_id,
                profile_version=view.profile_version,
                claims=[ClaimSummaryOutput.model_validate(asdict(claim)) for claim in view.claims],
                constraint_count=view.constraint_count,
            )

    @server.tool(
        name="get_claim_evidence",
        title="Get exact Claim evidence",
        description="Return selected evidence excerpts and constraints from one owned, stored profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_claim_evidence_tool(claim_id: str, profile_version: int) -> ClaimEvidenceOutput:
        if isinstance(profile_version, bool) or profile_version < 0:
            return ClaimEvidenceOutput(found=False)
        with session_factory() as session:
            account_id = current_account_id(session)
            profile_id = session.scalar(
                select(Claim.profile_id).where(
                    Claim.id == claim_id,
                    Claim.account_id == account_id,
                )
            )
            if profile_id is None:
                return ClaimEvidenceOutput(found=False)
            try:
                view = get_claim_evidence(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                    claim_id=claim_id,
                )
            except GraphUnavailable:
                return ClaimEvidenceOutput(found=False)
            return ClaimEvidenceOutput(
                found=True,
                claim=ClaimSummaryOutput.model_validate(asdict(view.claim)),
                profile_version=view.profile_version,
                evidence=[
                    EvidenceExcerptOutput.model_validate(asdict(item)) for item in view.evidence
                ],
                reviewed=view.reviewed,
                constraints=[
                    ClaimConstraintOutput(constraint_type=kind, exact_text=text)
                    for kind, text in view.constraints
                ],
            )

    @server.tool(
        name="get_claim_review",
        title="Get exact pending Claim review",
        description="Return an owned, unexpired review snapshot without renewing its digest or expiry.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_claim_review_tool(review_batch_id: str) -> ClaimReviewOutput:
        with session_factory() as session:
            account_id = current_account_id(session)
            try:
                batch, items = review_preparation.get(
                    session,
                    account_id=account_id,
                    batch_id=review_batch_id,
                    now=datetime.now(UTC),
                )
                profile = get_owned_profile(
                    session, account_id=account_id, profile_id=batch.profile_id
                )
            except (ReviewUnavailable, ReviewStale, ResourceNotFound):
                return ClaimReviewOutput(found=False)
            return ClaimReviewOutput(
                found=True,
                review_batch_id=batch.id,
                profile_id=batch.profile_id,
                base_profile_version=batch.base_profile_version,
                current_profile_version=profile.version,
                base_version_compatible=profile.version == batch.base_profile_version,
                review_digest=batch.review_digest,
                expires_at=batch.expires_at,
                scope_key=batch.scope_key,
                items=[
                    ClaimReviewItemOutput(
                        review_item_id=item.id,
                        position=item.position,
                        exact_text=item.exact_text,
                        claim_type=item.claim_type,
                        scope_key=item.scope_key,
                        source_input_id=item.source_input_id,
                        decision=item.decision,
                    )
                    for item in items
                ],
            )

    @server.tool(
        name="prepare_claim_review",
        title="Prepare an exact temporary Claim review",
        description="Snapshot one owned experience scope of up to five existing drafts; never approves Claims.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=True,
    )
    def prepare_claim_review_tool(
        profiling_session_id: str,
        experience_scope_id: str,
        base_profile_version: int,
        idempotency_key: str,
    ) -> ClaimReviewPrepareOutput:
        with session_factory() as session:
            account_id = current_account_id(session, PROFILE_WRITE_SCOPE)
            try:
                batch = review_preparation.prepare_for_scope(
                    session,
                    account_id=account_id,
                    profiling_session_id=profiling_session_id,
                    scope_key=experience_scope_id,
                    base_profile_version=base_profile_version,
                    idempotency_key=idempotency_key,
                    now=datetime.now(UTC),
                )
                session.flush()
                batch, items = review_preparation.get(
                    session, account_id=account_id, batch_id=batch.id, now=datetime.now(UTC)
                )
                profile = get_owned_profile(
                    session, account_id=account_id, profile_id=batch.profile_id
                )
                session.commit()
            except (ReviewUnavailable, ResourceNotFound):
                return ClaimReviewPrepareOutput(ok=False, found=False, error_code="NOT_FOUND")
            except ReviewStale:
                return ClaimReviewPrepareOutput(ok=False, found=False, error_code="REVIEW_STALE")
            except ReviewIdempotencyConflict:
                return ClaimReviewPrepareOutput(
                    ok=False, found=False, error_code="IDEMPOTENCY_CONFLICT"
                )
            except ValueError:
                return ClaimReviewPrepareOutput(
                    ok=False, found=False, error_code="VALIDATION_FAILED"
                )
            return ClaimReviewPrepareOutput(
                ok=True,
                found=True,
                review_batch_id=batch.id,
                profile_id=batch.profile_id,
                base_profile_version=batch.base_profile_version,
                current_profile_version=profile.version,
                base_version_compatible=profile.version == batch.base_profile_version,
                review_digest=batch.review_digest,
                expires_at=batch.expires_at,
                scope_key=batch.scope_key,
                items=[
                    ClaimReviewItemOutput(
                        review_item_id=item.id,
                        position=item.position,
                        exact_text=item.exact_text,
                        claim_type=item.claim_type,
                        scope_key=item.scope_key,
                        source_input_id=item.source_input_id,
                        decision=item.decision,
                    )
                    for item in items
                ],
            )

    @server.tool(
        name="get_jd_analysis",
        title="Get owned JD excerpts",
        description="Return stored JD excerpts and recorded Claim links at one exact profile version.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_jd_analysis_tool(jd_id: str, profile_version: int) -> JDAnalysisOutput:
        if type(profile_version) is not int or profile_version < 0:
            return JDAnalysisOutput(found=False)
        with session_factory() as session:
            account_id = current_account_id(session, ARTIFACT_READ_SCOPE)
            try:
                view = get_jd_analysis(session, account_id=account_id, jd_id=jd_id)
                mapping = get_jd_mapping(
                    session,
                    account_id=account_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                )
            except (JDUnavailable, JDMappingRejected):
                return JDAnalysisOutput(found=False)
            if len(view.requirements) != len(mapping.requirements) or any(
                excerpt[1] != links.exact_text
                for excerpt, links in zip(view.requirements, mapping.requirements, strict=True)
            ):
                return JDAnalysisOutput(found=False)
            return JDAnalysisOutput(
                found=True,
                jd_id=view.jd_id,
                jd_version=view.jd_version,
                profile_version=mapping.profile_version,
                stale_relative_to_current_profile=mapping.stale_relative_to_current_profile,
                source_hash=view.source_hash,
                source_length=view.source_length,
                requirements=[
                    JDRequirementOutput(
                        ordinal=ordinal,
                        exact_text=exact_text,
                        source_start=start,
                        source_end=end,
                        requirement_id=links.requirement_id,
                        linked_claim_ids=list(links.linked_claim_ids),
                        gap_status=links.gap_status,
                    )
                    for (ordinal, exact_text, start, end), links in zip(
                        view.requirements, mapping.requirements, strict=True
                    )
                ],
            )

    @server.tool(
        name="get_resume_trace",
        title="Get owned R1/R2 resume trace",
        description="Return exact R1/R2 units, source lineage and eligible Claim and selected Evidence references.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def get_resume_trace_tool(artifact_id: str) -> ResumeTraceOutput:
        with session_factory() as session:
            account_id = current_account_id(session, ARTIFACT_READ_SCOPE)
            try:
                view = get_resume_trace(session, account_id=account_id, artifact_id=artifact_id)
            except ResumeDraftUnavailable:
                return ResumeTraceOutput(found=False)
            return ResumeTraceOutput(
                found=True,
                artifact_id=view.artifact_id,
                artifact_version=view.artifact_version,
                profile_version=view.profile_version,
                jd_id=view.jd_id,
                stale_relative_to_current_profile=view.stale_relative_to_current_profile,
                units=[ResumeUnitTraceOutput.model_validate(asdict(unit)) for unit in view.units],
                source_artifact_id=view.source_artifact_id,
            )

    hostname = urlsplit(settings.resource_url).netloc
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[hostname, "localhost:*", "127.0.0.1:*"],
            allowed_origins=["https://chatgpt.com"],
        ),
    )
    declarations = OAuthToolDeclarations(
        app,
        functional_headers=True,
        tool_scopes={
            "get_account_profile": PROFILE_READ_SCOPE,
            "get_my_profile": PROFILE_READ_SCOPE,
            "initialize_career_profile": PROFILE_WRITE_SCOPE,
            "propose_profiling_drafts": PROFILE_WRITE_SCOPE,
            "get_owned_profile_metadata": PROFILE_READ_SCOPE,
            "get_profiling_session": PROFILE_READ_SCOPE,
            "get_career_profile": PROFILE_READ_SCOPE,
            "get_claim_evidence": PROFILE_READ_SCOPE,
            "get_claim_review": PROFILE_READ_SCOPE,
            "get_jd_analysis": ARTIFACT_READ_SCOPE,
            "get_resume_trace": ARTIFACT_READ_SCOPE,
            "start_profiling": PROFILE_WRITE_SCOPE,
            "add_profiling_input": PROFILE_WRITE_SCOPE,
            "pause_profiling": PROFILE_WRITE_SCOPE,
            "prepare_claim_review": PROFILE_WRITE_SCOPE,
            "preview_data_deletion": DELETE_SCOPE,
            **TOOL_SCOPES,
        },
    )
    application = LocalMetadataPathAlias(declarations, urlsplit(settings.resource_url).path)
    return LocalMCPIngress(application)

"""Local browser-confirmed MCP commands and authenticated expiring export resources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ResourceError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, func, select

from careerground.domain.browser_operations import (
    BrowserOperationRejected,
    BrowserOperationService,
    BrowserOperationUnavailable,
)
from careerground.domain.request_limits import RequestLimitExceeded
from careerground.domain.safe_events import record_result
from careerground.storage.models import DeletionRequest, DeletionWorkItem

EXPORT_SCOPE = "career.export"
ARTIFACT_WRITE_SCOPE = "career.artifact.write"
ACTION_SCOPES = {
    "FACT_REVIEW": "career.profile.write",
    "CONFLICT_REVIEW": "career.profile.write",
    "BOUNDARY_REVIEW": "career.profile.write",
    "JD_PASTE": ARTIFACT_WRITE_SCOPE,
    "JD_LINK": ARTIFACT_WRITE_SCOPE,
    "R1_DRAFT": ARTIFACT_WRITE_SCOPE,
    "WORDING_REVIEW": ARTIFACT_WRITE_SCOPE,
    "PROFILE_EXPORT": EXPORT_SCOPE,
    "RESUME_EXPORT": EXPORT_SCOPE,
}
TOOL_SCOPES = {
    "request_user_confirmation": tuple(ACTION_SCOPES.values()),
    "submit_claim_review": "career.profile.write",
    "resolve_claim_conflict": "career.profile.write",
    "review_boundary_change": "career.profile.write",
    "record_selected_jd": ARTIFACT_WRITE_SCOPE,
    "link_jd_requirement": ARTIFACT_WRITE_SCOPE,
    "generate_resume_draft": ARTIFACT_WRITE_SCOPE,
    "submit_resume_wording_review": ARTIFACT_WRITE_SCOPE,
    "export_profile_data": EXPORT_SCOPE,
    "export_resume": EXPORT_SCOPE,
    "get_deletion_status": "career.delete",
}


class StrictOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfirmationRequestOutput(StrictOutput):
    request_id: str
    status: Literal["WAITING", "DONE", "CONSUMED"]
    confirmation_path: str
    expires_at: datetime
    user_message: str


class FactReceiptOutput(StrictOutput):
    review_batch_id: str
    profile_id: str
    version_after: int
    completed_in_browser: Literal[True]


class WordingReceiptOutput(StrictOutput):
    artifact_id: str
    review_id: str
    artifact_version: int
    profile_version: int
    completed_in_browser: Literal[True]


class PolicyReceiptOutput(StrictOutput):
    review_id: str
    claim_id: str
    profile_id: str
    version_after: int
    completed_in_browser: Literal[True]


class ExportReceiptOutput(StrictOutput):
    resource_uri: str
    format: Literal["JSON", "MARKDOWN"]
    profile_version: int
    content_hash: str
    content_bytes: int
    expires_at: datetime
    completed_in_browser: Literal[True]


class SelectedJDReceiptOutput(StrictOutput):
    jd_id: str
    jd_version: int
    profile_id: str
    profile_version: int
    requirement_count: int
    analysis_kind: Literal["SELECTED_EXCERPTS_ONLY"]
    completed_in_browser: Literal[True]


class JDLinkReceiptOutput(StrictOutput):
    link_id: str
    jd_id: str
    profile_version: int
    requirement_id: str
    claim_id: str
    mapping_kind: Literal["POTENTIAL"]
    completed_in_browser: Literal[True]


class R1ReceiptOutput(StrictOutput):
    artifact_id: str
    artifact_version: int
    profile_version: int
    wording_level: Literal["R1"]
    review_required: Literal[True]
    completed_in_browser: Literal[True]


class DeletionStatusOutput(StrictOutput):
    erasure_request_id: str
    coverage: Literal["FOUNDATION_ONLY"] = "FOUNDATION_ONLY"
    status: Literal["DELETING", "FAILED"]
    ready_to_execute: Literal[False] = False
    known_local_done: int
    pending_or_failed: int
    unverified: int


def register_confirmation_tools(
    server,
    *,
    settings,
    session_factory,
    current_account_id,
    service: BrowserOperationService,
    limiter,
):
    def principal(session, scope):
        account_id = current_account_id(session, scope)
        access = get_access_token()
        if access is None:
            raise PermissionError
        return (
            account_id,
            service.connection_key(settings.issuer, access.subject, access.client_id, access.token),
            access.client_id,
        )

    write = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

    @server.tool(
        name="request_user_confirmation",
        annotations=write,
        structured_output=True,
        description="Request exact browser confirmation for one synthetic operation. Creates no approval or canonical mutation. User must open confirmation_path and explicitly confirm. Requires the action-specific scope.",
    )
    def request_user_confirmation(
        action: Literal[
            "FACT_REVIEW",
            "WORDING_REVIEW",
            "PROFILE_EXPORT",
            "RESUME_EXPORT",
            "CONFLICT_REVIEW",
            "BOUNDARY_REVIEW",
            "JD_PASTE",
            "JD_LINK",
            "R1_DRAFT",
        ],
        target_id: str,
        profile_version: int,
        format: Literal["NONE", "JSON", "MARKDOWN"],
        idempotency_key: str,
    ) -> ConfirmationRequestOutput:
        with session_factory() as session:
            account, connection, client = principal(session, ACTION_SCOPES[action])
            row = service.request(
                session,
                account_id=account,
                connection_key=connection,
                client_id=client,
                action=action,
                target_id=target_id,
                profile_version=profile_version,
                format=format,
                idempotency_key=idempotency_key,
                now=datetime.now(UTC),
            )
            result = ConfirmationRequestOutput(
                request_id=row.id,
                status=row.status,
                confirmation_path="/mcp/confirm/" + row.id,
                expires_at=row.expires_at.replace(tzinfo=UTC)
                if row.expires_at.tzinfo is None
                else row.expires_at.astimezone(UTC),
                user_message="브라우저에서 연결 앱과 정확한 내용을 확인하고 직접 승인하세요.",
            )
            session.commit()
            return result

    def consume(scope, action, target, receipt, version=None, format=None):
        with session_factory() as session:
            account, connection, _ = principal(session, scope)
            result = service.consume(
                session,
                account_id=account,
                connection_key=connection,
                action=action,
                target_id=target,
                receipt=receipt,
                profile_version=version,
                format=format,
                now=datetime.now(UTC),
            )
            session.commit()
            return result

    @server.tool(
        name="submit_claim_review",
        annotations=write,
        structured_output=True,
        description="Return the exact fact-review result already completed by the trusted browser. Does not accept model-supplied approval, decisions or automatic use eligibility.",
    )
    def submit_claim_review(review_batch_id: str, approval_receipt: str) -> FactReceiptOutput:
        return FactReceiptOutput(
            **consume("career.profile.write", "FACT_REVIEW", review_batch_id, approval_receipt)
        )

    @server.tool(
        name="submit_resume_wording_review",
        annotations=write,
        structured_output=True,
        description="Return the exact R1 wording result completed by the trusted browser, using a short receipt bound to this OAuth connection.",
    )
    def submit_resume_wording_review(
        artifact_id: str, approval_receipt: str
    ) -> WordingReceiptOutput:
        return WordingReceiptOutput(
            **consume(ARTIFACT_WRITE_SCOPE, "WORDING_REVIEW", artifact_id, approval_receipt)
        )

    @server.tool(
        name="resolve_claim_conflict",
        annotations=write,
        structured_output=True,
        description="Acknowledge an exact conflict decision already completed by the browser. Opposing Evidence is retained; this never grants automatic publication.",
    )
    def resolve_claim_conflict(claim_id: str, approval_receipt: str) -> PolicyReceiptOutput:
        return PolicyReceiptOutput(
            **consume("career.profile.write", "CONFLICT_REVIEW", claim_id, approval_receipt)
        )

    @server.tool(
        name="review_boundary_change",
        annotations=write,
        structured_output=True,
        description="Acknowledge an exact boundary decision already completed by the browser. Model-supplied boundary changes or automatic use approval are not accepted.",
    )
    def review_boundary_change(claim_id: str, approval_receipt: str) -> PolicyReceiptOutput:
        return PolicyReceiptOutput(
            **consume("career.profile.write", "BOUNDARY_REVIEW", claim_id, approval_receipt)
        )

    @server.tool(
        name="record_selected_jd",
        annotations=write,
        structured_output=True,
        description="Acknowledge user-selected JD bullets recorded through exact browser confirmation. Selected excerpts only; no semantic AI analysis or model-supplied source text.",
    )
    def record_selected_jd(
        profile_id: str, profile_version: int, approval_receipt: str
    ) -> SelectedJDReceiptOutput:
        return SelectedJDReceiptOutput(
            **consume(
                ARTIFACT_WRITE_SCOPE,
                "JD_PASTE",
                profile_id,
                approval_receipt,
                version=profile_version,
            )
        )

    @server.tool(
        name="link_jd_requirement",
        annotations=write,
        structured_output=True,
        description="Acknowledge an exact browser-selected requirement and eligible Claim link. Records potential relevance only, without certifying coverage or creating new facts.",
    )
    def link_jd_requirement(jd_id: str, approval_receipt: str) -> JDLinkReceiptOutput:
        return JDLinkReceiptOutput(
            **consume(ARTIFACT_WRITE_SCOPE, "JD_LINK", jd_id, approval_receipt)
        )

    @server.tool(
        name="generate_resume_draft",
        annotations=write,
        structured_output=True,
        description="Acknowledge an exact browser-selected R1 draft copied from eligible Claims. No R2/R3 rewrite, automatic wording approval or export consent.",
    )
    def generate_resume_draft(
        jd_id: str, profile_version: int, approval_receipt: str
    ) -> R1ReceiptOutput:
        return R1ReceiptOutput(
            **consume(
                ARTIFACT_WRITE_SCOPE, "R1_DRAFT", jd_id, approval_receipt, version=profile_version
            )
        )

    @server.tool(
        name="export_profile_data",
        annotations=write,
        structured_output=True,
        description="Consume explicit browser JSON export consent and return a short authenticated canonical-only resource. No temporary draft or expired source restoration.",
    )
    def export_profile_data(
        profile_id: str, profile_version: int, format: Literal["JSON"], approval_receipt: str
    ) -> ExportReceiptOutput:
        return ExportReceiptOutput(
            **consume(
                EXPORT_SCOPE,
                "PROFILE_EXPORT",
                profile_id,
                approval_receipt,
                profile_version,
                format,
            )
        )

    @server.tool(
        name="export_resume",
        annotations=write,
        structured_output=True,
        description="Consume explicit browser R1 export consent and return a short authenticated resource; each read rechecks current owner, source eligibility and hash.",
    )
    def export_resume(
        artifact_id: str, format: Literal["JSON", "MARKDOWN"], approval_receipt: str
    ) -> ExportReceiptOutput:
        return ExportReceiptOutput(
            **consume(EXPORT_SCOPE, "RESUME_EXPORT", artifact_id, approval_receipt, format=format)
        )

    @server.tool(
        name="get_deletion_status",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
        description="Read known local deletion counts only, for an active account. External/provider/backup completion is unverified; no ledger secrets, target IDs or error details.",
    )
    def get_deletion_status(erasure_request_id: str) -> DeletionStatusOutput:
        with session_factory() as session:
            account = current_account_id(session, "career.delete")
            row = session.scalar(
                select(DeletionRequest).where(
                    DeletionRequest.id == erasure_request_id, DeletionRequest.account_id == account
                )
            )
            if row is None:
                raise BrowserOperationUnavailable
            done, pending, unverified = session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    (DeletionWorkItem.action == "ERASE")
                                    & (DeletionWorkItem.status == "DONE"),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((DeletionWorkItem.status != "DONE", 1), else_=0)), 0
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    (DeletionWorkItem.action == "VERIFY")
                                    & (DeletionWorkItem.status != "DONE"),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(DeletionWorkItem.request_id == row.id)
            ).one()
            # FOUNDATION_ONLY never certifies external/provider/backup completion.
            status = "DELETING" if row.status == "ERASED" else row.status
            return DeletionStatusOutput(
                erasure_request_id=row.id,
                status=status,
                known_local_done=done,
                pending_or_failed=pending,
                unverified=unverified,
            )

    @server.resource(
        "careerground://exports/{operation_id}",
        mime_type="text/plain",
        description="Short-lived private export. Requires career.export and the original OAuth account/client; erased or expired content is unavailable.",
    )
    def read_export(operation_id: str) -> str:
        try:
            with session_factory() as session:
                account, connection, _ = principal(session, EXPORT_SCOPE)
                limiter.consume(account, "read")
                content = service.read_export(
                    session,
                    account_id=account,
                    connection_key=connection,
                    operation_id=operation_id,
                    now=datetime.now(UTC),
                )
                record_result("mcp", "OK")
                return content
        except RequestLimitExceeded:
            record_result("mcp", "RATE_LIMITED")
            raise ResourceError("RATE_LIMITED") from None
        except PermissionError:
            record_result("mcp", "FORBIDDEN")
            raise ResourceError("Export unavailable") from None
        except BrowserOperationRejected:
            record_result("mcp", "NOT_FOUND")
            raise ResourceError("Export unavailable") from None
        except Exception:  # noqa: BLE001 - resources also have a payload-free failure boundary
            record_result("mcp", "INTERNAL_ERROR")
            raise ResourceError("Export unavailable") from None

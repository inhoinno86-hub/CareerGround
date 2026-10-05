"""Send untrusted ChatGPT JD/R2 suggestions to the authenticated management UI."""

import hashlib
from typing import Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from careerground.domain.chatgpt_proposal_review import ChatGPTProposalRejected
from careerground.domain.resume_r2_review import R2FactReviewRequired, R2ProposalRejected
from careerground.domain.text_proposal_validation import (
    MAX_SOURCE,
    TextProposalRejected,
    _owner,
    _source,
)
from careerground.mcp.management_navigation import validate_management_origin

CHATGPT_PROPOSAL_SCOPES = {
    "get_chatgpt_jd_source_context": "career.artifact.read",
    "prepare_chatgpt_jd_review": "career.artifact.write",
    "prepare_chatgpt_r2_review": "career.artifact.write",
    "get_chatgpt_proposal_status": "career.artifact.read",
}


class JDSourceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: int
    end: int
    exact_text: str


class JDSourceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    error_code: str | None = None
    source_hash: str | None = None
    source_length: int | None = None
    lines: list[JDSourceLine] = []
    canonical_saved: Literal[False] = False
    semantic_fit_verified: Literal[False] = False


class ChatGPTProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    error_code: str | None = None
    proposal_id: str | None = None
    kind: Literal["JD", "R2"] | None = None
    review_status: Literal["WAITING", "DONE", "FACT_REVIEW_REQUIRED"] = "WAITING"
    confirmation_path: str | None = None
    confirmation_url: str | None = None
    result_id: str | None = None
    profile_version: int | None = None
    canonical_saved: bool = False
    export_approved: Literal[False] = False
    semantic_fit_verified: Literal[False] = False


def register_chatgpt_proposal_tools(
    server, *, inbox, session_factory, current_account_id, management_origin
):
    origin = validate_management_origin(management_origin)

    def actor(scope):
        access = get_access_token()
        with session_factory() as session:
            account = current_account_id(session, scope)
        return account, inbox.connection(access.token)

    def waiting(row):
        path = "/chatgpt/proposals/" + row.id
        return ChatGPTProposalOutput(
            proposal_id=row.id,
            kind=row.kind,
            review_status=row.status,
            confirmation_path=path,
            confirmation_url=origin + path if origin else None,
            profile_version=row.version,
            canonical_saved=row.status == "DONE",
            result_id=row.result_id,
        )

    @server.tool(
        name="get_chatgpt_jd_source_context",
        title="Read exact JD source positions",
        description="Return SHA256 and Python Unicode line positions for explicit user JD text. Read-only; no model, storage, semantic analysis, mapping, approval or resume-use decision. Copy returned hash and positions into a separate untrusted review proposal; never invent a hash.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def jd_context(profile_id: str, profile_version: int, jd_text: str) -> JDSourceContext:
        account, _connection = actor("career.artifact.read")
        try:
            with session_factory() as session:
                _owner(session, account, profile_id, profile_version)
                _source(jd_text, limit=MAX_SOURCE)
            lines, offset = [], 0
            for line in jd_text.splitlines(keepends=True):
                exact = line.rstrip("\r\n")
                if exact.strip():
                    lines.append(
                        JDSourceLine(start=offset, end=offset + len(exact), exact_text=exact)
                    )
                offset += len(line)
            if len(lines) > 100:
                raise TextProposalRejected("INVALID_SOURCE")
            return JDSourceContext(
                source_hash=hashlib.sha256(jd_text.encode()).hexdigest(),
                source_length=len(jd_text),
                lines=lines,
            )
        except TextProposalRejected:
            return JDSourceContext(ok=False, error_code="VALIDATION_FAILED")

    @server.tool(
        name="prepare_chatgpt_jd_review",
        title="Review ChatGPT JD excerpts in CareerGround",
        description="Stage explicit user JD text and an untrusted ChatGPT JSON proposal for 3 minutes. proposal_json contains source_hash and 1-5 candidates with exact Python start/end, optional eligible claim_id and evidence_ids. No semantic score or automatic mapping. Only browser-selected exact excerpts are saved after explicit approval; chat yes is insufficient.",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def prepare_jd(
        profile_id: str,
        profile_version: int,
        jd_text: str,
        proposal_json: str,
        idempotency_key: str,
    ) -> ChatGPTProposalOutput:
        account, connection = actor("career.artifact.write")
        try:
            row = inbox.prepare_jd(
                account_id=account,
                connection=connection,
                profile_id=profile_id,
                profile_version=profile_version,
                jd_text=jd_text,
                proposal_json=proposal_json,
                key=idempotency_key,
            )
            return waiting(row)
        except (ChatGPTProposalRejected, TextProposalRejected):
            return ChatGPTProposalOutput(ok=False, error_code="VALIDATION_FAILED")

    @server.tool(
        name="prepare_chatgpt_r2_review",
        title="Review ChatGPT R2 wording in CareerGround",
        description="Stage 1-5 untrusted R2 proposals_json entries, one per source R1 unit, including unit_id/source_hash/proposed_text/fact_review/claim_id/evidence_ids. Conservative fact-preserving checks apply. Browser compares source and exact new wording and explicitly saves separate R2. No fact or export approval. R3 facts require a separate profiling review.",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def prepare_r2(
        artifact_id: str, proposals_json: str, idempotency_key: str
    ) -> ChatGPTProposalOutput:
        account, connection = actor("career.artifact.write")
        try:
            row = inbox.prepare_r2(
                account_id=account,
                connection=connection,
                artifact_id=artifact_id,
                proposals_json=proposals_json,
                key=idempotency_key,
            )
            return waiting(row)
        except R2FactReviewRequired:
            return ChatGPTProposalOutput(kind="R2", review_status="FACT_REVIEW_REQUIRED")
        except (ChatGPTProposalRejected, R2ProposalRejected, TextProposalRejected):
            return ChatGPTProposalOutput(ok=False, error_code="VALIDATION_FAILED")

    @server.tool(
        name="get_chatgpt_proposal_status",
        title="Read this connection's proposal review status",
        description="Read metadata only after returning from management review, using the same OAuth connection. DONE is a browser-completed JD/R2 write, never a fact/export/deletion approval. Expired, different connection, stale or removed sources are refused. Do not poll repeatedly.",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
        structured_output=True,
    )
    def status(proposal_id: str) -> ChatGPTProposalOutput:
        account, connection = actor("career.artifact.read")
        try:
            return ChatGPTProposalOutput(**inbox.status(proposal_id, account, connection))
        except (ChatGPTProposalRejected, R2ProposalRejected, TextProposalRejected):
            return ChatGPTProposalOutput(ok=False, error_code="VALIDATION_FAILED")

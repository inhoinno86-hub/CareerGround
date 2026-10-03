"""Explicit mock deletion controls, mounted solely in the disposable local demo."""

import time
from datetime import UTC, datetime
from html import escape

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from careerground.domain.browser_form_token import BrowserFormTokenRejected
from careerground.domain.deletion_preview import DeletionTargetUnavailable
from careerground.domain.local_deletion_connection import (
    LocalDeletionConnection,
    LocalDeletionConnectionRejected,
)
from careerground.domain.synthetic_deletion_journey import (
    MockDeletionJourney,
    MockDeletionJourneyRejected,
)
from careerground.local_demo import bounded_form, demo_page
from careerground.storage.graph_models import EvidenceItem
from careerground.storage.models import ProfilingSession, ProjectScope

_LABELS = {
    "ACCOUNT": "합성 계정",
    "AUTH_IDENTITY": "합성 로그인 연결",
    "CAREER_PROFILE": "경력 프로필",
    "PROFILING_SESSION": "경력 정리 세션",
    "PROFILING_INPUT": "임시 입력",
    "PROFILING_PROTOCOL_STEP": "질문 응답 단계",
    "PROFILING_DRAFT": "미승인 후보",
    "PROFILING_REVIEW_BATCH": "검토 묶음",
    "PROFILING_REVIEW_ITEM": "검토 항목",
    "BROWSER_OPERATION": "연결 승인 기록",
    "PROFILE_CHANGE_SET": "프로필 변경 기록",
    "PROFILE_ARCHIVE": "프로필 이전 버전",
    "CLAIM": "경력 주장",
    "EVIDENCE_SOURCE": "근거 출처",
    "EVIDENCE_ITEM": "근거 항목",
    "EVIDENCE_CLAIM_LINK": "근거 연결",
    "CLAIM_ASSESSMENT": "주장 평가",
    "CLAIM_REVIEW": "사실 검토",
    "CLAIM_BOUNDARY_REVIEW": "기여 범위 검토",
    "CLAIM_CONFLICT_REVIEW": "충돌 검토",
    "CLAIM_USE_REVIEW": "사용 적격 검토",
    "CLAIM_CONSTRAINT": "사용 제한",
    "JOB_DESCRIPTION": "JD 선택 발췌",
    "JD_REQUIREMENT": "JD 요구 문구",
    "REQUIREMENT_CLAIM_MAP": "요구 연결",
    "ARTIFACT": "이력서 초안",
    "ARTIFACT_UNIT": "이력서 문구",
    "ARTIFACT_WORDING_REVIEW": "이력서 문구 승인",
    "ARTIFACT_CLAIM_LINK": "이력서 근거 연결",
    "PRIVATE_OBJECT": "비공개 객체",
    "PRIVATE_OBJECT_VERSION": "비공개 객체 버전",
    "PROJECT_SCOPE": "등록된 프로젝트 범위",
    "PROFILE_VERSION": "프로필 버전 변경",
    "CLAIM_REASSESS": "사용 적격 재검토가 필요한 경력 주장",
}


def register_mock_deletion_routes(demo):
    journey = getattr(demo.runtime_store, "deletion_journey", None) or MockDeletionJourney(
        demo.presentation_secret, demo.review_secret, demo.review_secret
    )
    demo.deletion_connection = LocalDeletionConnection(demo, journey)

    def identity(state):
        return {
            "account_id": state["account_id"],
            "profile_id": state["profile_id"],
            "browser_session_id": state["session_id"],
        }

    def wrap_context(state, kind, inner_token, request_id=""):
        return demo.tokens.sign(
            {
                "purpose": "MOCK_DELETE_WEB_CONTEXT",
                "session_id": state["session_id"],
                "kind": kind,
                "inner_token": inner_token,
                "request_id": request_id,
                "expires_at": int(time.time()) + 180,
            }
        )

    def unwrap_context(state, kind, value):
        try:
            payload = demo.tokens.verify(
                value,
                expected_keys=frozenset(
                    {"purpose", "session_id", "kind", "inner_token", "request_id", "expires_at"}
                ),
            )
        except BrowserFormTokenRejected:
            raise HTTPException(409) from None
        if (
            payload["purpose"] != "MOCK_DELETE_WEB_CONTEXT"
            or payload["session_id"] != state["session_id"]
            or payload["kind"] != kind
            or type(payload["inner_token"]) is not str
            or type(payload["request_id"]) is not str
            or type(payload["expires_at"]) is not int
            or payload["expires_at"] <= time.time()
        ):
            raise HTTPException(409)
        return payload["inner_token"], payload["request_id"]

    @demo.web.get("/demo/deletion")
    async def show(request: Request):
        state = demo.browser(request)
        body = "<p>합성 데이터에만 적용되는 삭제 체험입니다. 실제 인증이나 운영 데이터 삭제 기능이 아닙니다. 삭제하면 이 체험의 해당 입력을 되돌릴 수 없습니다.</p><p>근거·프로젝트의 원본이 들어 있는 세션은 같은 입력의 다른 임시 항목까지 함께 삭제될 수 있습니다. 공유 근거는 다른 사실의 근거 연결에도 영향을 줄 수 있습니다. 다음 화면에서 정확한 영향 건수를 확인하세요.</p>"
        with demo.sessions() as session:
            choices = []
            for kind, model, statuses in (
                ("SESSION", ProfilingSession, ("ACTIVE", "PAUSED", "EXPIRED")),
                ("EVIDENCE", EvidenceItem, ("ACTIVE",)),
                ("PROJECT", ProjectScope, ("ACTIVE",)),
            ):
                rows = session.scalars(
                    select(model).where(
                        model.account_id == state["account_id"],
                        model.profile_id == state["profile_id"],
                        model.status.in_(statuses),
                    )
                )
                choices.extend((kind, row.id) for row in rows)
        options = "".join(
            f"<option value='{escape(kind + ':' + row_id, quote=True)}'>{escape(kind)} · {escape(row_id)}</option>"
            for kind, row_id in sorted(choices)
        )
        body += f"<form method='post' action='/demo/deletion/preview'><input type='hidden' name='form_token' value='{escape(demo.form_token('MOCK_DELETE_PREVIEW', state), quote=True)}'><label for='scope'>삭제할 범위</label><select id='scope' name='scope' required><option value='' selected>직접 선택</option><option value='PROFILE'>현재 합성 프로필</option><option value='ACCOUNT'>현재 합성 계정 전체</option><option value='SESSION'>경력 정리 세션</option><option value='EVIDENCE'>근거 항목</option><option value='PROJECT'>등록한 프로젝트 범위</option></select><label for='target_id'>부분 삭제 대상</label><select id='target_id' name='target_id'><option value=''>계정·프로필 삭제에는 선택하지 않음</option>{options}</select><button type='submit'>삭제 영향 확인</button></form>"
        return demo_page("합성 데이터 삭제 체험", body)

    @demo.web.post("/demo/deletion/preview")
    async def preview(request: Request):
        state = demo.browser(request)
        fields = await bounded_form(request)
        if set(fields) not in ({"form_token", "scope"}, {"form_token", "scope", "target_id"}):
            raise HTTPException(400)
        demo.verify_form(fields["form_token"], "MOCK_DELETE_PREVIEW", state)
        target = fields.get("target_id", "")
        if fields["scope"] in {"SESSION", "EVIDENCE", "PROJECT"}:
            if not target.startswith(fields["scope"] + ":"):
                raise HTTPException(409)
            target = target.split(":", 1)[1]
        elif target:
            raise HTTPException(409)
        return preview_page(state, fields["scope"], target_id=target or None)

    @demo.web.get("/demo/deletion/confirmation/{request_id}")
    async def connection_confirmation(request_id: str, request: Request):
        state = demo.browser(request)
        with demo.sessions() as session:
            try:
                row = demo.deletion_connection.bind_browser(session, request_id, state)
            except (LocalDeletionConnectionRejected, DeletionTargetUnavailable):
                raise HTTPException(409) from None
        return preview_page(state, row.scope, request_id, row.target_id)

    def preview_page(state, scope, request_id="", target_id=None):
        with demo.sessions() as session:
            try:
                view = journey.preview(
                    session,
                    **identity(state),
                    scope=scope,
                    target_id=target_id,
                    now=datetime.now(UTC),
                )
            except MockDeletionJourneyRejected:
                raise HTTPException(409) from None
        scope_label = {
            "ACCOUNT": "합성 계정 전체",
            "PROFILE": "현재 합성 프로필",
            "SESSION": "선택한 경력 정리 세션",
            "EVIDENCE": "선택한 근거 항목",
            "PROJECT": "등록한 프로젝트 범위",
        }[view.scope]
        phrase = "합성 계정 " + state["label"].upper()
        body = f"<p>선택 범위: {scope_label} · 대상 ID: {escape(view.target_id)}</p><p>아래는 현재 저장 항목의 수입니다. 원문은 표시하지 않습니다.</p><ul>"
        if request_id:
            body = (
                "<p>이 합성 MCP 연결이 요청한 삭제입니다. 이 화면의 모의 재인증과 최종 승인은 완료 증명을 발급하며, 같은 연결이 그 증명을 제출할 때 삭제가 실행됩니다.</p>"
                + body
            )
        for kind, count in view.impact_counts:
            body += f"<li>{escape(_LABELS.get(kind, '기타 로컬 항목'))}: {count}개</li>"
        context = wrap_context(state, "PREVIEW", view.preview_token, request_id)
        body += f"</ul><p>외부 서비스·백업은 검증하지 않으므로 전체 삭제 완료를 보증하지 않습니다.</p><h2>별도 모의 재인증 (MOCK_ONLY)</h2><p>실제 비밀번호를 입력하지 마세요. 아래에 <strong>{phrase}</strong>라고 입력해 합성 계정 선택을 다시 확인하세요.</p><form method='post' action='/demo/deletion/reauth'><input type='hidden' name='preview_token' value='{escape(context, quote=True)}'><label><input type='checkbox' name='acknowledged_impact' value='yes' required>표시한 삭제 범위와 영향을 확인했습니다.</label><label><input type='checkbox' name='mock_reauthenticated' value='yes' required>이 재인증은 로컬 체험용 모의 확인임을 이해했습니다.</label><label for='mock_phrase'>합성 계정 확인 문구</label><input id='mock_phrase' name='mock_phrase' maxlength='32' autocomplete='off' required><button type='submit'>모의 재인증 후 최종 확인</button></form>"
        return demo_page("삭제 영향 직접 확인", body)

    @demo.web.post("/demo/deletion/reauth")
    async def reauthenticate(request: Request):
        state = demo.browser(request)
        fields = await bounded_form(request)
        if set(fields) != {
            "preview_token",
            "acknowledged_impact",
            "mock_reauthenticated",
            "mock_phrase",
        }:
            raise HTTPException(400)
        if fields["mock_phrase"] != "합성 계정 " + state["label"].upper():
            raise HTTPException(409)
        preview_token, request_id = unwrap_context(state, "PREVIEW", fields["preview_token"])
        with demo.sessions() as session:
            try:
                token = journey.reauthenticate(
                    session,
                    **identity(state),
                    preview_token=preview_token,
                    acknowledged_impact=fields["acknowledged_impact"] == "yes",
                    mock_reauthenticated=fields["mock_reauthenticated"] == "yes",
                    now=datetime.now(UTC),
                )
                view = journey.describe_step(
                    session, **identity(state), step_up_token=token, now=datetime.now(UTC)
                )
            except MockDeletionJourneyRejected:
                raise HTTPException(409) from None
        scope_label = {
            "ACCOUNT": "합성 계정 전체",
            "PROFILE": "현재 합성 프로필",
            "SESSION": "선택한 경력 정리 세션",
            "EVIDENCE": "선택한 근거 항목",
            "PROJECT": "등록한 프로젝트 범위",
        }[view.scope]
        impact = (
            "<ul>"
            + "".join(
                f"<li>{escape(_LABELS.get(kind, '기타 로컬 항목'))}: {count}개</li>"
                for kind, count in view.impact_counts
            )
            + "</ul>"
        )
        context = wrap_context(state, "STEP", token, request_id)
        action_text = (
            "같은 합성 연결에 삭제 실행 증명을 발급합니다. 아직 삭제하지 않습니다."
            if request_id
            else "앞서 확인한 범위의 현재 합성 데이터를 삭제합니다."
        )
        body = f"<p>선택 범위: {scope_label} · 대상 ID: {escape(view.target_id)}</p>{impact}<p>모의 재인증을 확인했습니다. {action_text} 내용이나 버전이 바뀌었으면 실행이 거부됩니다.</p><p>외부 서비스·백업은 검증하지 않습니다. 전체 삭제 완료 상태는 발급하지 않습니다.</p><form method='post' action='/demo/deletion/execute'><input type='hidden' name='step_up_token' value='{escape(context, quote=True)}'><label><input type='checkbox' name='confirm' value='erase_local' required>확인한 범위의 로컬 합성 데이터 삭제를 최종 승인합니다.</label><button type='submit'>로컬 합성 데이터 삭제 실행</button></form>"
        return demo_page("모의 재인증 후 삭제 확인", body)

    @demo.web.post("/demo/deletion/execute")
    async def execute(request: Request):
        # An exact retry may still finish after ordinary account auth was blocked.
        # The journey separately checks its signed owner/session proof.
        state = demo.browser(request, active=False)
        fields = await bounded_form(request)
        if set(fields) != {"step_up_token", "confirm"}:
            raise HTTPException(400)
        step_up_token, request_id = unwrap_context(state, "STEP", fields["step_up_token"])
        with demo.sessions() as session:
            try:
                if request_id:
                    if fields["confirm"] != "erase_local":
                        raise HTTPException(409)
                    receipt = demo.deletion_connection.approve(
                        session, state, step_up_token, request_id
                    )
                    return demo_page(
                        "합성 연결 삭제 승인 증명",
                        "<p>현재 데이터는 아직 삭제하지 않았습니다. 같은 연결에서 동일 인자와 아래 증명을 제출해야 실행됩니다. 증명은 잠시 후 만료되며 다른 연결에서 사용할 수 없습니다.</p><pre id='approval-receipt'>"
                        + escape(receipt)
                        + "</pre><p><a href='/demo/mcp'>같은 합성 연결에서 삭제 실행</a></p>",
                    )
                result = journey.execute(
                    session,
                    **identity(state),
                    step_up_token=step_up_token,
                    confirmed=fields["confirm"] == "erase_local",
                    now=datetime.now(UTC),
                )
                demo.before_deletion_commit(session)
                session.commit()
                demo.after_deletion_commit()
            except (
                MockDeletionJourneyRejected,
                LocalDeletionConnectionRejected,
                DeletionTargetUnavailable,
            ):
                raise HTTPException(409) from None
        # Keep the minimal bearer capability server-side, never in a URL or HTML.
        state["deletion_capability"] = result.status_capability
        response = RedirectResponse("/demo/deletion/status", status_code=303)
        response.headers["cache-control"] = "no-store"
        return response

    @demo.web.get("/demo/deletion/status")
    async def status(request: Request):
        state = demo.browser(request, active=False)
        capability = state.get("deletion_capability")
        if capability is None:
            raise HTTPException(404)
        with demo.sessions() as session:
            try:
                view = journey.read_status(session, capability=capability, now=datetime.now(UTC))
            except MockDeletionJourneyRejected:
                raise HTTPException(409) from None
        body = f"<p>상태: {view.status} · {view.coverage}</p><dl><dt>로컬 삭제 확인 항목</dt><dd id='known-local-done'>{view.known_local_done}</dd><dt>대기 또는 실패 항목</dt><dd>{view.pending_or_failed}</dd><dt>검증하지 않은 외부·백업 항목</dt><dd id='unverified'>{view.unverified}</dd></dl><p>로컬 항목만 처리했습니다. 전체 삭제 완료를 보증하지 않습니다. 상태 조회는 실행 후 5분간 이 브라우저 세션에서만 가능합니다.</p><p><a href='/demo'>다른 합성 계정 선택</a></p>"
        return demo_page("합성 삭제 상태", body)

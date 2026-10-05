"""Isolated synthetic browser review UI; never mounted by the public web app."""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hmac import digest as hmac_digest
from html import escape
from inspect import isawaitable
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from careerground.domain.artifact_navigation import (
    JDList,
    ResumeArtifactList,
    list_jd_analyses,
    list_resume_artifacts,
)
from careerground.domain.artifact_operation_presentation import ARTIFACT_ACTIONS, ARTIFACT_FIELDS
from careerground.domain.browser_operations import BrowserOperationRejected, BrowserOperationService
from careerground.domain.claim_review_workspace import ClaimReviewPreparation
from careerground.domain.claim_use_review import (
    ClaimUseReviewPresentation,
    ClaimUseReviewRejected,
    ClaimUseReviewService,
)
from careerground.domain.deletion_preview import (
    DeletionPreview,
    DeletionPreviewService,
    DeletionScope,
    DeletionTargetUnavailable,
)
from careerground.domain.graph_projection import (
    ClaimEvidenceView,
    GraphUnavailable,
    ProfileView,
    get_career_profile,
    get_claim_evidence,
)
from careerground.domain.jd_analysis import JDAnalysisView, JDUnavailable, get_jd_analysis
from careerground.domain.jd_link_presentation import (
    JDLinkCandidate,
    JDLinkPresentation,
    JDLinkPresentationRejected,
    JDLinkPresentationService,
)
from careerground.domain.jd_mapping import JDMappingRejected, JDMappingView, get_jd_mapping
from careerground.domain.jd_paste_presentation import (
    JDPastePresentation,
    JDPastePresentationRejected,
    JDPastePresentationService,
)
from careerground.domain.policy_review_presentation import (
    BOUNDARY_FIELDS,
    CONFLICT_FIELDS,
    POLICY_ACTIONS,
)
from careerground.domain.profile_export_presentation import (
    ProfileExportPresentation,
    ProfileExportPresentationRejected,
    ProfileExportPresentationService,
)
from careerground.domain.profiling_bullet_presentation import (
    BulletPresentation,
    BulletPresentationRejected,
    BulletPresentationService,
)
from careerground.domain.profiling_draft_extraction import (
    DraftSpanRejected,
    extract_explicit_bullet_spans,
)
from careerground.domain.profiling_input_presentation import (
    ProfilingInputForm,
    ProfilingInputFormRejected,
    ProfilingInputFormService,
)
from careerground.domain.profiling_protocol_workspace import (
    ProtocolProgress,
    get_protocol_progress,
)
from careerground.domain.profiling_session_presentation import (
    ProfilingSessionActionForm,
    ProfilingSessionActionRejected,
    ProfilingSessionActionService,
)
from careerground.domain.profiling_start_presentation import (
    ProfilingStartRejected,
    ProfilingStartService,
    ProfilingStartView,
)
from careerground.domain.profiling_summary import (
    ProfilingDraftList,
    ProfilingWorkspaceSummary,
    get_profiling_workspace_summary,
    list_profiling_drafts_for_review,
)
from careerground.domain.profiling_workspace import (
    MAX_INPUT_CHARS,
    InputKind,
    ProfilingExpired,
    ProfilingUnavailable,
    ProfilingVersionConflict,
)
from careerground.domain.request_limits import (
    DEFAULT_REQUEST_LIMITS,
    AccountRequestLimiter,
    RequestLimitExceeded,
    RequestLimitPolicy,
    RequestLimitStoreUnavailable,
)
from careerground.domain.resume_draft import ResumeDraftUnavailable, ResumeTrace, get_resume_trace
from careerground.domain.resume_draft_presentation import (
    ResumeDraftPresentation,
    ResumeDraftPresentationRejected,
    ResumeDraftPresentationService,
)
from careerground.domain.resume_export_presentation import (
    ResumeExportPresentation,
    ResumeExportPresentationRejected,
    ResumeExportPresentationService,
)
from careerground.domain.resume_wording_presentation import (
    WordingPresentation,
    WordingPresentationRejected,
    WordingPresentationService,
)
from careerground.domain.resume_wording_review import WordingReviewService
from careerground.domain.review_prepare_presentation import (
    ReviewPreparePresentation,
    ReviewPreparePresentationRejected,
    ReviewPreparePresentationService,
)
from careerground.domain.review_presentation import (
    ReviewPresentation,
    ReviewPresentationRejected,
    ReviewPresentationService,
)
from careerground.domain.safe_events import record_result
from careerground.storage.jd_artifact_models import JobDescription
from careerground.storage.models import CareerProfile
from careerground.web.artifact_operation_forms import render_artifact_choices, render_artifact_exact
from careerground.web.policy_review_forms import render_policy_choices, render_policy_exact

_DECISION_LABELS = (
    ("ACCEPT", "사실 그대로 확인"),
    ("EDIT", "문구 수정 필요"),
    ("FOLLOW_UP", "추가 확인 필요"),
    ("EXCLUDE_NOT_TRUE", "사실이 아님"),
    ("EXCLUDE_DO_NOT_USE", "사용하지 않음"),
)


@dataclass(frozen=True)
class TrustedBrowserIdentity:
    """Verified account and a non-secret opaque session binding, never request text."""

    account_id: str
    session_id: str


def build_synthetic_review_app(
    *,
    session_factory: Callable[[], Session],
    authenticate_browser: Callable[
        [Request, Response],
        TrustedBrowserIdentity | None | Awaitable[TrustedBrowserIdentity | None],
    ],
    review_signing_secret: bytes,
    presentation_signing_secret: bytes,
    request_limits: RequestLimitPolicy = DEFAULT_REQUEST_LIMITS,
) -> FastAPI:
    """Legacy-named development factory with caller-supplied identity verification.

    Local fixtures and the opt-in Auth0 trial share these ownership/approval
    routes. This factory itself creates no login, provider or public server.
    """

    service = ReviewPresentationService(
        ClaimReviewPreparation(review_signing_secret), presentation_signing_secret
    )
    prepare_service = ReviewPreparePresentationService(
        ClaimReviewPreparation(review_signing_secret), presentation_signing_secret
    )
    start_service = ProfilingStartService(presentation_signing_secret)
    input_service = ProfilingInputFormService(presentation_signing_secret)
    bullet_service = BulletPresentationService(presentation_signing_secret)
    action_service = ProfilingSessionActionService(presentation_signing_secret)
    export_service = ProfileExportPresentationService(presentation_signing_secret)
    jd_paste_service = JDPastePresentationService(presentation_signing_secret)
    jd_link_service = JDLinkPresentationService(presentation_signing_secret)
    resume_draft_service = ResumeDraftPresentationService(presentation_signing_secret)
    use_review_service = ClaimUseReviewService(
        hmac_digest(review_signing_secret, b"synthetic-claim-r1-use-review-v1", "sha256"),
        presentation_signing_secret,
    )
    wording_domain = WordingReviewService(
        hmac_digest(review_signing_secret, b"synthetic-r1-wording-review-v1", "sha256")
    )
    wording_service = WordingPresentationService(wording_domain, presentation_signing_secret)
    resume_export_service = ResumeExportPresentationService(
        wording_domain, presentation_signing_secret
    )
    deletion_preview_service = DeletionPreviewService(
        hmac_digest(presentation_signing_secret, b"synthetic-deletion-preview-v1", "sha256")
    )
    app = FastAPI(title="CareerGround synthetic review", docs_url=None, redoc_url=None)
    limiter = AccountRequestLimiter(session_factory, review_signing_secret, policy=request_limits)
    operation_service = BrowserOperationService(review_signing_secret, presentation_signing_secret)

    @app.middleware("http")
    async def private_failure_boundary(request: Request, call_next):
        try:
            response = await call_next(request)
            if 200 <= response.status_code < 400:
                record_result("web", "OK")
            return response
        except Exception:  # noqa: BLE001 - sanitize before the ASGI server can log source/SQL values
            # Never log exc/traceback: database and SDK exceptions can contain input.
            record_result("web", "INTERNAL_ERROR")
            return _html_response(
                "<!doctype html><html lang='ko'><meta charset='utf-8'>"
                "<title>요청을 처리할 수 없습니다</title><main role='alert'>"
                "<h1>요청을 처리할 수 없습니다</h1>"
                "<p>처리 상태를 다시 확인해 주세요. 같은 작업을 바로 반복하지 마세요.</p>"
                "<p><a href='/profiling/start'>시작 화면에서 현재 상태 확인하기</a></p></main></html>",
                status_code=500,
            )

    @app.exception_handler(RequestValidationError)
    async def private_validation_error(request: Request, _exc: RequestValidationError):
        return await browser_error(request, StarletteHTTPException(400))

    @app.exception_handler(StarletteHTTPException)
    async def browser_error(_request: Request, exc: StarletteHTTPException) -> HTMLResponse:
        titles = {
            400: "제출 내용을 확인해 주세요",
            401: "로그인이 필요합니다",
            404: "요청한 내용을 찾을 수 없습니다",
            405: "지원하지 않는 요청입니다",
            409: "화면의 정보가 바뀌었습니다",
            413: "제출 내용이 너무 큽니다",
            415: "지원하지 않는 제출 형식입니다",
            429: "잠시 후 다시 시도해 주세요",
            503: "현재 요청을 처리할 수 없습니다",
        }
        title = titles.get(exc.status_code, "요청을 처리할 수 없습니다")
        recovery = (
            "<p><a href='/profiling/start'>경력 정리 시작 화면에서 다시 확인하기</a></p>"
            if exc.status_code in {400, 404, 409, 413, 415, 429, 503}
            else ""
        )
        retry = (exc.headers or {}).get("Retry-After")
        if exc.status_code == 429 and retry and retry.isdecimal():
            recovery = f"<p>{escape(retry)}초 뒤 현재 상태를 확인해 주세요.</p>" + recovery
        result = _html_response(
            "<!doctype html><html lang='ko'><meta charset='utf-8'>"
            f"<title>{title}</title><main role='alert'><h1>{title}</h1>"
            f"<p>이 요청은 저장되지 않았습니다.</p>{recovery}</main></html>",
            status_code=exc.status_code,
        )
        if exc.status_code == 429 and retry and retry.isdecimal():
            result.headers["Retry-After"] = retry
        record_result(
            "web",
            "RATE_LIMITED"
            if exc.status_code == 429
            else ("INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_FAILED"),
        )
        return result

    async def identity(request: Request, auth_response: Response) -> TrustedBrowserIdentity:
        principal = authenticate_browser(request, auth_response)
        if isawaitable(principal):
            principal = await principal
        if type(principal) is not TrustedBrowserIdentity:
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            limiter.consume(
                principal.account_id, "read" if request.method in {"GET", "HEAD"} else "write"
            )
        except RequestLimitExceeded as exc:
            raise HTTPException(
                429, headers={"Retry-After": str(exc.retry_after_seconds)}
            ) from None
        except RequestLimitStoreUnavailable:
            raise HTTPException(503) from None
        return principal

    from careerground.web.local_contract_extensions import attach_contract_extensions

    attach_contract_extensions(
        app,
        session_factory=session_factory,
        identity=identity,
        review_secret=review_signing_secret,
        presentation_secret=presentation_signing_secret,
    )

    @app.get("/profiling/start", response_class=HTMLResponse)
    async def show_profiling_start(request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                now = datetime.now(UTC)
                view = start_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    now=now,
                )
            except ProfilingStartRejected as exc:
                raise HTTPException(status_code=404, detail="Profile unavailable") from exc
            try:
                export_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profile_id=view.profile_id,
                    profile_version=view.profile_version,
                    now=now,
                )
            except ProfileExportPresentationRejected:
                export_available = False
            else:
                export_available = True
        return _with_auth_cookies(
            _html_response(_render_start(view, export_available=export_available)), auth_response
        )

    @app.post("/profiling/start")
    async def submit_profiling_start(request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"start_token", "confirm"}
            or values.get("confirm") != ["start"]
            or len(values["start_token"]) != 1
        ):
            raise HTTPException(status_code=400, detail="Explicit start required")
        with session_factory() as session:
            try:
                work = start_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    start_token=values["start_token"][0],
                    now=datetime.now(UTC),
                )
                work_id = work.id
                session.commit()
            except ProfilingStartRejected as exc:
                raise HTTPException(status_code=409, detail="Start unavailable or changed") from exc
        redirect = RedirectResponse("/profiling/" + quote(work_id, safe=""), status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/profiling/{session_id}", response_class=HTMLResponse)
    async def show_profiling_session(session_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_profiling_workspace_summary(
                    session,
                    account_id=principal.account_id,
                    profiling_session_id=session_id,
                    now=datetime.now(UTC),
                )
                try:
                    action_form = action_service.present(
                        session,
                        account_id=principal.account_id,
                        browser_session_id=principal.session_id,
                        profiling_session_id=session_id,
                        now=datetime.now(UTC),
                    )
                except ProfilingSessionActionRejected:
                    action_form = None
            except (ProfilingUnavailable, ProfilingExpired) as exc:
                raise HTTPException(status_code=404, detail="Session unavailable") from exc
        return _with_auth_cookies(_html_response(_render_session(view, action_form)), auth_response)

    @app.post("/profiling/{session_id}/action")
    async def submit_profiling_action(session_id: str, request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"action_token", "action", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["action"] not in (["pause"], ["resume"])
            or values["confirm"] != [values["action"][0]]
        ):
            raise HTTPException(status_code=400, detail="Explicit action required")
        with session_factory() as session:
            try:
                action_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    action=values["action"][0],
                    action_token=values["action_token"][0],
                    now=datetime.now(UTC),
                )
                session.commit()
            except ProfilingSessionActionRejected as exc:
                raise HTTPException(status_code=409, detail="Session action unavailable") from exc
        redirect = RedirectResponse("/profiling/" + quote(session_id, safe=""), status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/profiling/{session_id}/drafts", response_class=HTMLResponse)
    async def show_profiling_drafts(session_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = list_profiling_drafts_for_review(
                    session,
                    account_id=principal.account_id,
                    profiling_session_id=session_id,
                    now=datetime.now(UTC),
                )
            except (ProfilingUnavailable, ProfilingExpired) as exc:
                raise HTTPException(status_code=404, detail="Drafts unavailable") from exc
        return _with_auth_cookies(_html_response(_render_drafts(view)), auth_response)

    @app.get("/profiling/{session_id}/drafts/{scope_key}/prepare", response_class=HTMLResponse)
    async def show_review_prepare(
        session_id: str, scope_key: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = prepare_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    scope_key=scope_key,
                    now=datetime.now(UTC),
                )
            except ReviewPreparePresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Draft scope unavailable") from exc
        return _with_auth_cookies(_html_response(_render_review_prepare(view)), auth_response)

    @app.post("/profiling/{session_id}/drafts/{scope_key}/prepare")
    async def submit_review_prepare(session_id: str, scope_key: str, request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"prepare_token", "confirm"}
            or values.get("confirm") != ["prepare"]
            or len(values["prepare_token"]) != 1
        ):
            raise HTTPException(status_code=400, detail="Explicit preparation required")
        with session_factory() as session:
            try:
                batch = prepare_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    scope_key=scope_key,
                    prepare_token=values["prepare_token"][0],
                    now=datetime.now(UTC),
                )
                batch_id = batch.id
                session.commit()
            except ReviewPreparePresentationRejected as exc:
                raise HTTPException(status_code=409, detail="Draft scope changed") from exc
        redirect = RedirectResponse("/review/" + quote(batch_id, safe=""), status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/profiling/{session_id}/questions", response_class=HTMLResponse)
    async def show_profiling_questions(session_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_protocol_progress(
                    session,
                    account_id=principal.account_id,
                    profiling_session_id=session_id,
                    now=datetime.now(UTC),
                )
            except (ProfilingUnavailable, ProfilingExpired, ProfilingVersionConflict) as exc:
                raise HTTPException(status_code=404, detail="Questions unavailable") from exc
        return _with_auth_cookies(
            _html_response(_render_questions(session_id, view)), auth_response
        )

    async def show_task_input(
        session_id: str, request: Request, content_kind: InputKind
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = input_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    content_kind=content_kind,
                    now=datetime.now(UTC),
                )
            except ProfilingInputFormRejected as exc:
                raise HTTPException(status_code=404, detail="Input form unavailable") from exc
        return _with_auth_cookies(_html_response(_render_input_form(view)), auth_response)

    @app.get("/profiling/{session_id}/input", response_class=HTMLResponse)
    async def show_profiling_input(session_id: str, request: Request) -> HTMLResponse:
        return await show_task_input(session_id, request, InputKind.USER_STATEMENT)

    @app.get("/profiling/{session_id}/correction", response_class=HTMLResponse)
    async def show_profiling_correction(session_id: str, request: Request) -> HTMLResponse:
        return await show_task_input(session_id, request, InputKind.CORRECTION)

    async def submit_task_input(
        session_id: str, request: Request, content_kind: InputKind
    ) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 256_000:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"input_token", "content", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["submit"]
            or not values["content"][0].strip()
        ):
            raise HTTPException(status_code=400, detail="Explicit input required")
        with session_factory() as session:
            try:
                source = input_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    content_kind=content_kind,
                    input_token=values["input_token"][0],
                    content=values["content"][0],
                    now=datetime.now(UTC),
                )
                source_id = source.id
                session.commit()
            except ProfilingInputFormRejected as exc:
                raise HTTPException(status_code=409, detail="Input unavailable or changed") from exc
        target = "/profiling/" + quote(session_id, safe="")
        if content_kind == InputKind.USER_STATEMENT:
            try:
                extract_explicit_bullet_spans(values["content"][0])
            except DraftSpanRejected:
                pass
            else:
                target += "/input/" + quote(source_id, safe="") + "/drafts"
        redirect = RedirectResponse(target, status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.post("/profiling/{session_id}/input")
    async def submit_profiling_input(session_id: str, request: Request) -> Response:
        return await submit_task_input(session_id, request, InputKind.USER_STATEMENT)

    @app.post("/profiling/{session_id}/correction")
    async def submit_profiling_correction(session_id: str, request: Request) -> Response:
        return await submit_task_input(session_id, request, InputKind.CORRECTION)

    @app.get("/profiling/{session_id}/input/{source_input_id}/drafts", response_class=HTMLResponse)
    async def show_bullet_drafts(
        session_id: str, source_input_id: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = bullet_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    source_input_id=source_input_id,
                    now=datetime.now(UTC),
                )
            except BulletPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Bullets unavailable") from exc
        return _with_auth_cookies(_html_response(_render_bullet_drafts(view)), auth_response)

    @app.post("/profiling/{session_id}/input/{source_input_id}/drafts")
    async def submit_bullet_drafts(
        session_id: str, source_input_id: str, request: Request
    ) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"bullet_token", "scope_key", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["draft"]
        ):
            raise HTTPException(status_code=400, detail="Explicit draft choice required")
        with session_factory() as session:
            try:
                bullet_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profiling_session_id=session_id,
                    source_input_id=source_input_id,
                    scope_key=values["scope_key"][0],
                    bullet_token=values["bullet_token"][0],
                    now=datetime.now(UTC),
                )
                session.commit()
            except BulletPresentationRejected as exc:
                raise HTTPException(status_code=409, detail="Bullets changed") from exc
        redirect = RedirectResponse(
            "/profiling/" + quote(session_id, safe="") + "/drafts", status_code=303
        )
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/review/{batch_id}", response_class=HTMLResponse)
    async def show_review(batch_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    batch_id=batch_id,
                    now=datetime.now(UTC),
                )
            except ReviewPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Review unavailable") from exc
        return _with_auth_cookies(_html_response(_render_review(view)), auth_response)

    @app.get("/artifacts", response_class=HTMLResponse)
    async def show_artifacts(request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            view = list_resume_artifacts(session, account_id=principal.account_id)
        return _with_auth_cookies(_html_response(_render_artifacts(view)), auth_response)

    @app.get("/resume/{artifact_id}/wording", response_class=HTMLResponse)
    async def show_resume_wording(artifact_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = wording_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    artifact_id=artifact_id,
                    now=datetime.now(UTC),
                )
            except WordingPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Wording review unavailable") from exc
        return _with_auth_cookies(_html_response(_render_wording_review(view)), auth_response)

    @app.post("/resume/{artifact_id}/wording")
    async def submit_resume_wording(artifact_id: str, request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"approval_token", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["accept_r1"]
        ):
            raise HTTPException(status_code=400, detail="Explicit wording review required")
        with session_factory() as session:
            try:
                wording_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    artifact_id=artifact_id,
                    approval_token=values["approval_token"][0],
                    now=datetime.now(UTC),
                )
                session.commit()
            except WordingPresentationRejected as exc:
                raise HTTPException(status_code=409, detail="Wording review changed") from exc
        result = RedirectResponse(
            "/resume/" + quote(artifact_id, safe="") + "/trace", status_code=303
        )
        result.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(result, auth_response)

    @app.get("/resume/{artifact_id}/export/{format}", response_class=HTMLResponse)
    async def show_resume_export(artifact_id: str, format: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = resume_export_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    artifact_id=artifact_id,
                    format=format.upper(),
                    now=datetime.now(UTC),
                )
            except ResumeExportPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Resume export unavailable") from exc
        return _with_auth_cookies(_html_response(_render_resume_export_form(view)), auth_response)

    @app.post("/resume/{artifact_id}/export/{format}")
    async def submit_resume_export(artifact_id: str, format: str, request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"export_token", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["download"]
        ):
            raise HTTPException(status_code=400, detail="Explicit download required")
        with session_factory() as session:
            try:
                export = resume_export_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    artifact_id=artifact_id,
                    format=format.upper(),
                    export_token=values["export_token"][0],
                    now=datetime.now(UTC),
                )
            except ResumeExportPresentationRejected as exc:
                raise HTTPException(status_code=409, detail="Resume export changed") from exc
        media_type, filename = (
            ("application/json", "careerground-resume.json")
            if export.format == "JSON"
            else ("text/markdown; charset=utf-8", "careerground-resume.md")
        )
        result = Response(
            export.content_text,
            media_type=media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
        return _with_auth_cookies(result, auth_response)

    @app.get("/profile/{profile_id}/export/{profile_version}", response_class=HTMLResponse)
    async def show_profile_export(
        profile_id: str, profile_version: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        selector = (
            profile_version
            if profile_version == "CURRENT"
            else (
                int(profile_version)
                if profile_version.isascii()
                and profile_version.isdecimal()
                and len(profile_version) <= 10
                else None
            )
        )
        if selector is None:
            raise HTTPException(404)
        inclusion = None
        if request.query_params:
            names = {"claims", "evidence", "boundaries", "drafts", "unavailable_references"}
            if (
                set(request.query_params) - names - {"selection"}
                or request.query_params.get("selection") != "explicit"
                or any(
                    len(request.query_params.getlist(key)) != 1
                    or request.query_params[key] != "yes"
                    for key in set(request.query_params) - {"selection"}
                )
            ):
                raise HTTPException(400)
            inclusion = {key: request.query_params.get(key) == "yes" for key in names}
        with session_factory() as session:
            try:
                view = export_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profile_id=profile_id,
                    profile_version=selector,
                    inclusion=inclusion,
                    now=datetime.now(UTC),
                )
            except ProfileExportPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Export unavailable") from exc
        return _with_auth_cookies(_html_response(_render_export_form(view)), auth_response)

    @app.post("/profile/{profile_id}/export/{profile_version}")
    async def submit_profile_export(
        profile_id: str, profile_version: int, request: Request
    ) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"export_token", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["download"]
        ):
            raise HTTPException(status_code=400, detail="Explicit download required")
        with session_factory() as session:
            try:
                export = export_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                    export_token=values["export_token"][0],
                    now=datetime.now(UTC),
                )
            except ProfileExportPresentationRejected as exc:
                raise HTTPException(
                    status_code=409, detail="Export unavailable or changed"
                ) from exc
        result = Response(
            export.content_json,
            media_type="application/json",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": 'attachment; filename="careerground-profile.json"',
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            },
        )
        return _with_auth_cookies(result, auth_response)

    @app.get("/jd", response_class=HTMLResponse)
    async def show_jd_list(request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            view = list_jd_analyses(session, account_id=principal.account_id)
        return _with_auth_cookies(_html_response(_render_jd_list(view)), auth_response)

    @app.get("/jd/new", response_class=HTMLResponse)
    async def show_jd_paste(request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = jd_paste_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    now=datetime.now(UTC),
                )
            except JDPastePresentationRejected as exc:
                raise HTTPException(status_code=404, detail="Profile unavailable") from exc
        return _with_auth_cookies(_html_response(_render_jd_paste(view)), auth_response)

    @app.post("/jd/new")
    async def submit_jd_paste(request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 256_000:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"paste_token", "selected_text", "confirm"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm"] != ["store_excerpts"]
        ):
            raise HTTPException(status_code=400, detail="Explicit JD excerpt choice required")
        with session_factory() as session:
            try:
                jd = jd_paste_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    paste_token=values["paste_token"][0],
                    selected_text=values["selected_text"][0],
                    now=datetime.now(UTC),
                )
                jd_id = jd.id
                session.commit()
            except JDPastePresentationRejected as exc:
                raise HTTPException(status_code=409, detail="JD selection changed") from exc
        redirect = RedirectResponse("/jd/" + quote(jd_id, safe=""), status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/jd/{jd_id}", response_class=HTMLResponse)
    async def show_jd_analysis(jd_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_jd_analysis(session, account_id=principal.account_id, jd_id=jd_id)
                jd = session.get(JobDescription, jd_id)
                profile = session.get(CareerProfile, jd.profile_id)
            except JDUnavailable as exc:
                raise HTTPException(status_code=404, detail="JD unavailable") from exc
        return _with_auth_cookies(
            _html_response(_render_jd_analysis(view, profile_version=profile.version)),
            auth_response,
        )

    @app.get("/jd/{jd_id}/mapping/{profile_version}", response_class=HTMLResponse)
    async def show_jd_mapping(jd_id: str, profile_version: int, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_jd_mapping(
                    session,
                    account_id=principal.account_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                )
                candidates = jd_link_service.candidates(
                    session,
                    account_id=principal.account_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                )
            except (JDMappingRejected, JDLinkPresentationRejected) as exc:
                raise HTTPException(status_code=404, detail="JD mapping unavailable") from exc
        return _with_auth_cookies(
            _html_response(_render_jd_mapping(view, candidates)), auth_response
        )

    @app.get(
        "/jd/{jd_id}/mapping/{profile_version}/link/{requirement_id}/{claim_id}",
        response_class=HTMLResponse,
    )
    async def show_jd_link(
        jd_id: str, profile_version: int, requirement_id: str, claim_id: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = jd_link_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    jd_id=jd_id,
                    requirement_id=requirement_id,
                    claim_id=claim_id,
                    profile_version=profile_version,
                    now=datetime.now(UTC),
                )
            except JDLinkPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="JD link unavailable") from exc
        return _with_auth_cookies(_html_response(_render_jd_link(view)), auth_response)

    @app.post("/jd/{jd_id}/mapping/{profile_version}/link/{requirement_id}/{claim_id}")
    async def submit_jd_link(
        jd_id: str, profile_version: int, requirement_id: str, claim_id: str, request: Request
    ) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"link_token", "confirm"}
            or values.get("confirm") != ["link_potential"]
            or len(values["link_token"]) != 1
        ):
            raise HTTPException(status_code=400, detail="Explicit JD link choice required")
        with session_factory() as session:
            try:
                jd_link_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    jd_id=jd_id,
                    requirement_id=requirement_id,
                    claim_id=claim_id,
                    profile_version=profile_version,
                    link_token=values["link_token"][0],
                    now=datetime.now(UTC),
                )
                session.commit()
            except JDLinkPresentationRejected as exc:
                raise HTTPException(status_code=409, detail="JD link choice changed") from exc
        redirect = RedirectResponse(
            f"/jd/{quote(jd_id, safe='')}/mapping/{profile_version}", status_code=303
        )
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/jd/{jd_id}/draft/{profile_version}", response_class=HTMLResponse)
    async def show_r1_draft(jd_id: str, profile_version: int, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = resume_draft_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                    now=datetime.now(UTC),
                )
            except ResumeDraftPresentationRejected as exc:
                raise HTTPException(status_code=404, detail="R1 draft unavailable") from exc
        return _with_auth_cookies(_html_response(_render_r1_draft(view)), auth_response)

    @app.post("/jd/{jd_id}/draft/{profile_version}")
    async def submit_r1_draft(jd_id: str, profile_version: int, request: Request) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=7
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"draft_token", "claim_id", "confirm"}
            or len(values["draft_token"]) != 1
            or values["confirm"] != ["create_r1"]
            or not 1 <= len(values["claim_id"]) <= 5
        ):
            raise HTTPException(status_code=400, detail="Explicit R1 selection required")
        with session_factory() as session:
            try:
                artifact = resume_draft_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    jd_id=jd_id,
                    profile_version=profile_version,
                    claim_ids=tuple(values["claim_id"]),
                    draft_token=values["draft_token"][0],
                    now=datetime.now(UTC),
                )
                artifact_id = artifact.id
                session.commit()
            except ResumeDraftPresentationRejected as exc:
                raise HTTPException(status_code=409, detail="R1 draft selection changed") from exc
        redirect = RedirectResponse(f"/resume/{quote(artifact_id, safe='')}/trace", status_code=303)
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/profile/{profile_id}/{profile_version}", response_class=HTMLResponse)
    async def show_career_profile(
        profile_id: str, profile_version: int, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_career_profile(
                    session,
                    account_id=principal.account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                )
            except GraphUnavailable as exc:
                raise HTTPException(status_code=404, detail="Profile unavailable") from exc
        return _with_auth_cookies(_html_response(_render_career_profile(view)), auth_response)

    @app.get(
        "/profile/{profile_id}/{profile_version}/claim/{claim_id}",
        response_class=HTMLResponse,
    )
    async def show_claim_evidence(
        profile_id: str, profile_version: int, claim_id: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_claim_evidence(
                    session,
                    account_id=principal.account_id,
                    profile_id=profile_id,
                    profile_version=profile_version,
                    claim_id=claim_id,
                )
            except GraphUnavailable as exc:
                raise HTTPException(status_code=404, detail="Claim unavailable") from exc
        return _with_auth_cookies(
            _html_response(_render_claim_evidence(profile_id, view)), auth_response
        )

    @app.get(
        "/profile/{profile_id}/{profile_version}/claim/{claim_id}/use-review",
        response_class=HTMLResponse,
    )
    async def show_claim_use_review(
        profile_id: str, profile_version: int, claim_id: str, request: Request
    ) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = use_review_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profile_id=profile_id,
                    claim_id=claim_id,
                    now=datetime.now(UTC),
                )
                if view.base_profile_version != profile_version:
                    raise ClaimUseReviewRejected
            except ClaimUseReviewRejected as exc:
                raise HTTPException(status_code=404, detail="Use review unavailable") from exc
        return _with_auth_cookies(_html_response(_render_claim_use_review(view)), auth_response)

    @app.post("/profile/{profile_id}/{profile_version}/claim/{claim_id}/use-review")
    async def submit_claim_use_review(
        profile_id: str, profile_version: int, claim_id: str, request: Request
    ) -> Response:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 4096:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=3
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            set(values) != {"approval_token", "confirm_consistency", "confirm_use"}
            or any(len(item) != 1 for item in values.values())
            or values["confirm_consistency"] != ["yes"]
            or values["confirm_use"] != ["yes"]
        ):
            raise HTTPException(status_code=400, detail="Two explicit choices required")
        with session_factory() as session:
            try:
                review = use_review_service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    profile_id=profile_id,
                    claim_id=claim_id,
                    approval_token=values["approval_token"][0],
                    consistency_attested=True,
                    use_authorized=True,
                    now=datetime.now(UTC),
                )
                if review.base_profile_version != profile_version:
                    raise ClaimUseReviewRejected
                version_after = review.profile_version
                session.commit()
            except ClaimUseReviewRejected as exc:
                raise HTTPException(status_code=409, detail="Use review changed") from exc
        redirect = RedirectResponse(
            f"/profile/{quote(profile_id, safe='')}/{version_after}/claim/{quote(claim_id, safe='')}",
            status_code=303,
        )
        redirect.headers["Cache-Control"] = "no-store"
        return _with_auth_cookies(redirect, auth_response)

    @app.get("/deletion/preview/account", response_class=HTMLResponse)
    async def show_account_deletion_preview(request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = deletion_preview_service.preview(
                    session,
                    account_id=principal.account_id,
                    scope=DeletionScope.ACCOUNT,
                    target_id=principal.account_id,
                    now=datetime.now(UTC),
                )
            except DeletionTargetUnavailable as exc:
                raise HTTPException(status_code=404, detail="Preview unavailable") from exc
        return _with_auth_cookies(_html_response(_render_deletion_preview(view)), auth_response)

    @app.get("/deletion/preview/profile/{profile_id}", response_class=HTMLResponse)
    async def show_profile_deletion_preview(profile_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = deletion_preview_service.preview(
                    session,
                    account_id=principal.account_id,
                    scope=DeletionScope.PROFILE,
                    target_id=profile_id,
                    now=datetime.now(UTC),
                )
            except DeletionTargetUnavailable as exc:
                raise HTTPException(status_code=404, detail="Preview unavailable") from exc
        return _with_auth_cookies(_html_response(_render_deletion_preview(view)), auth_response)

    @app.get("/resume/{artifact_id}/trace", response_class=HTMLResponse)
    async def show_resume_trace(artifact_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                view = get_resume_trace(
                    session, account_id=principal.account_id, artifact_id=artifact_id
                )
            except ResumeDraftUnavailable as exc:
                raise HTTPException(status_code=404, detail="Trace unavailable") from exc
        return _with_auth_cookies(_html_response(_render_resume_trace(view)), auth_response)

    @app.post("/review/{batch_id}", response_class=HTMLResponse)
    async def submit_review(batch_id: str, request: Request) -> HTMLResponse:
        auth_response = Response()
        principal = await identity(request, auth_response)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/x-www-form-urlencoded"
        ):
            raise HTTPException(status_code=415, detail="Unsupported form")
        body = await request.body()
        if len(body) > 8192:
            raise HTTPException(status_code=413, detail="Form too large")
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=8
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid form") from exc
        if (
            any(len(value) != 1 for value in values.values())
            or values.get("confirm") != ["reviewed"]
            or "approval_token" not in values
        ):
            raise HTTPException(status_code=400, detail="Incomplete review")
        decision_keys = [key for key in values if key.startswith("decision_")]
        if set(values) != {"approval_token", "confirm", *decision_keys}:
            raise HTTPException(status_code=400, detail="Invalid form")
        decisions = tuple((key.removeprefix("decision_"), values[key][0]) for key in decision_keys)
        with session_factory() as session:
            try:
                change = service.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    batch_id=batch_id,
                    approval_token=values["approval_token"][0],
                    decisions=decisions,
                    now=datetime.now(UTC),
                )
                version_after = change.version_after if change is not None else None
                profile_id = change.profile_id if change is not None else None
                session.commit()
            except ReviewPresentationRejected as exc:
                raise HTTPException(
                    status_code=409, detail="Review unavailable or changed"
                ) from exc
        version_note = (
            f"<p>프로필 버전 {version_after}에 반영됐습니다.</p>"
            "<p>사실 확인은 외부 검증이나 R1 사용 허용을 뜻하지 않습니다. "
            "각 사실의 선택 근거 화면에서 별도로 사용 가능 여부를 검토하세요.</p>"
            f"<p><a href='/profile/{quote(profile_id, safe='')}/{version_after}'>"
            "반영된 사실과 선택 근거 확인하기</a></p>"
            if version_after is not None
            else "<p>추가 확인 또는 수정 대상으로 저장됐습니다.</p>"
        )
        return _with_auth_cookies(
            _html_response(
                "<!doctype html><html lang='ko'><meta charset='utf-8'>"
                "<title>검토 결과</title><main><h1>검토 결과 저장</h1>"
                f"{version_note}<p><a href='/profiling/start'>"
                "경력 정리 시작 화면으로 돌아가기</a></p></main></html>"
            ),
            auth_response,
        )

    @app.get("/mcp/confirm/{operation_id}", response_class=HTMLResponse)
    async def show_mcp_confirmation(operation_id: str, request: Request):
        auth_response = Response()
        principal = await identity(request, auth_response)
        with session_factory() as session:
            try:
                presentation = operation_service.present(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    operation_id=operation_id,
                    now=datetime.now(UTC),
                )
            except BrowserOperationRejected:
                raise HTTPException(404) from None
            row = presentation.operation
            if row.status != "WAITING":
                body = _render_operation_receipt(row, operation_service.receipt(row))
            else:
                if row.action in POLICY_ACTIONS | ARTIFACT_ACTIONS:
                    render_choices = (
                        render_policy_choices
                        if row.action in POLICY_ACTIONS
                        else render_artifact_choices
                    )
                    body = render_choices(presentation.view, row.id).replace(
                        "</h1>", "</h1>" + _operation_recipient(row), 1
                    )
                else:
                    render = {
                        "FACT_REVIEW": _render_review,
                        "WORDING_REVIEW": _render_wording_review,
                        "PROFILE_EXPORT": _render_export_form,
                        "RESUME_EXPORT": _render_resume_export_form,
                    }[row.action]
                    body = render(presentation.view)
                    body = re.sub(
                        r"<form method='post' action='[^']+'>",
                        f"<form method='post' action='/mcp/confirm/{escape(row.id, quote=True)}'>",
                        body,
                        count=1,
                    )
                    body = re.sub(
                        r"<input type='hidden' name='(?:approval_token|export_token)' value='[^']+'>",
                        f"<input type='hidden' name='confirmation_token' value='{escape(presentation.confirmation_token, quote=True)}'>",
                        body,
                        count=1,
                    )
                    body = body.replace("</h1>", "</h1>" + _operation_recipient(row), 1)
                    body = body.replace(
                        "<button type='submit'>",
                        "<label><input type='checkbox' name='allow_connection' value='yes' required>표시된 연결 앱이 이 작업의 결과를 받도록 허용합니다.</label><button type='submit'>",
                        1,
                    )
                    if row.action.endswith("EXPORT"):
                        body = body.replace(
                            "외부 전송이나 채용 결과를 뜻하지 않습니다.",
                            "받을 연결 앱과 내보낼 범위를 직접 확인하세요. 채용 결과를 뜻하지 않습니다.",
                        )
                        body = body.replace("다운로드합니다.", "표시된 연결 앱에 내보냅니다.")
                        body = body.replace(
                            "JSON 다운로드</button>", "JSON 내보내기 허용</button>"
                        ).replace("파일 다운로드</button>", "내보내기 허용</button>")
            return _with_auth_cookies(_html_response(body), auth_response)

    @app.post("/mcp/confirm/{operation_id}/prepare", response_class=HTMLResponse)
    async def prepare_mcp_policy(operation_id: str, request: Request):
        auth_response = Response()
        principal = await identity(request, auth_response)
        _require_confirmation_origin(request)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            raise HTTPException(415)
        body = await request.body()
        if len(body) > 65536:
            raise HTTPException(413)
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=16
            )
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400) from None
        if (
            any(
                not (1 <= len(value) <= 5 if key == "claim_ids" else len(value) == 1)
                for key, value in values.items()
            )
            or "choice_token" not in values
            or not set(values).issubset(
                {"choice_token", *CONFLICT_FIELDS, *BOUNDARY_FIELDS, *ARTIFACT_FIELDS}
            )
        ):
            raise HTTPException(400)
        with session_factory() as session:
            try:
                presentation = operation_service.prepare_policy(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    operation_id=operation_id,
                    choice_token=values["choice_token"][0],
                    fields={
                        key: value if key == "claim_ids" else value[0]
                        for key, value in values.items()
                        if key != "choice_token"
                    },
                    now=datetime.now(UTC),
                )
                render_exact = (
                    render_policy_exact
                    if presentation.operation.action in POLICY_ACTIONS
                    else render_artifact_exact
                )
                result = render_exact(presentation).replace(
                    "</h1>", "</h1>" + _operation_recipient(presentation.operation), 1
                )
            except BrowserOperationRejected:
                raise HTTPException(409) from None
        return _with_auth_cookies(_html_response(result), auth_response)

    @app.post("/mcp/confirm/{operation_id}", response_class=HTMLResponse)
    async def confirm_mcp_operation(operation_id: str, request: Request):
        auth_response = Response()
        principal = await identity(request, auth_response)
        _require_confirmation_origin(request)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            raise HTTPException(415)
        body = await request.body()
        if len(body) > 65536:
            raise HTTPException(413)
        try:
            values = parse_qs(
                body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=16
            )
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400) from None
        decision_keys = [key for key in values if key.startswith("decision_")]
        extra_keys = set(values) & (CONFLICT_FIELDS | BOUNDARY_FIELDS | ARTIFACT_FIELDS)
        if (
            any(
                not (1 <= len(value) <= 5 if key == "claim_ids" else len(value) == 1)
                for key, value in values.items()
            )
            or set(values)
            != {"confirmation_token", "confirm", "allow_connection", *decision_keys, *extra_keys}
            or values.get("allow_connection") != ["yes"]
        ):
            raise HTTPException(400)
        with session_factory() as session:
            try:
                row = operation_service.confirm(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    operation_id=operation_id,
                    confirmation_token=values["confirmation_token"][0],
                    confirm_value=values["confirm"][0],
                    decisions=tuple(
                        (key.removeprefix("decision_"), values[key][0]) for key in decision_keys
                    ),
                    submission_fields={
                        key: values[key] if key == "claim_ids" else values[key][0]
                        for key in extra_keys
                    },
                    now=datetime.now(UTC),
                )
                receipt = operation_service.receipt(row)
                result = _render_operation_receipt(row, receipt)
                session.commit()
            except BrowserOperationRejected:
                raise HTTPException(409) from None
        return _with_auth_cookies(_html_response(result), auth_response)

    return app


def _require_confirmation_origin(request):
    allowed_origins = {None, str(request.base_url).rstrip("/")}
    # A no-referrer HTTP form may send Origin: null. Permit it only on the
    # explicitly local synthetic route; the signed session token is still
    # mandatory. HTTPS deployments must send the matching origin.
    if request.url.scheme == "http" and request.url.hostname in {"127.0.0.1", "localhost"}:
        allowed_origins.add("null")
    if request.headers.get("origin") not in allowed_origins or request.headers.get(
        "sec-fetch-site"
    ) not in {None, "same-origin", "none"}:
        raise HTTPException(400)


def _operation_recipient(row) -> str:
    action_label = {
        "FACT_REVIEW": "경력 사실 검토",
        "CONFLICT_REVIEW": "모순 결정 검토",
        "BOUNDARY_REVIEW": "사용 경계 변경 검토",
        "JD_PASTE": "JD 선택 발췌 기록",
        "JD_LINK": "JD 요구와 경력의 잠재 연결",
        "R1_DRAFT": "정확한 R1 초안 생성",
        "WORDING_REVIEW": "R1 문구 검토",
        "PROFILE_EXPORT": "프로필 JSON 내보내기",
        "RESUME_EXPORT": "검토된 이력서 문구 내보내기",
    }[row.action]
    return (
        "<section aria-label='연결 앱 확인'><h2>이 결과를 받을 연결 앱</h2>"
        f"<p>연결 앱 식별자: {escape(row.client_id)} · 작업: {escape(action_label)}</p>"
        f"<p>유효 기한: {escape((row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at.astimezone(UTC)).isoformat())}</p>"
        "<p>이 요청을 시작한 연결 앱이 맞는지 확인하세요. 사실 확인은 별도 사용 허용을 뜻하지 않습니다.</p></section>"
    )


def _render_operation_receipt(row, receipt) -> str:
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>연결 작업 확인 결과</title><main><h1>연결 작업 확인 완료</h1>"
        + _operation_recipient(row)
        + "<p>표시한 내용을 직접 확인한 작업이 완료됐습니다. 아래 짧은 완료 증명은 요청을 시작한 연결 앱에서만 사용할 수 있습니다.</p>"
        + f"<p>완료 증명: <code id='approval-receipt'>{escape(receipt)}</code></p>"
        + "<p>작업을 시작한 ChatGPT 대화로 돌아가 ‘관리 화면에서 확인했어. 이어서 진행해줘’라고 알려주세요. 연결 앱이 이 확인 결과를 조회할 수 있으므로 증명을 직접 복사할 필요는 없습니다.</p>"
        + "<p>증명은 유효 기한 뒤 사용할 수 없습니다. 다른 앱이나 대화에 공유하지 마세요.</p>"
        + "<p><a href='/profiling/start'>시작 화면에서 현재 상태 확인하기</a></p></main></html>"
    )


def _render_review(view: ReviewPresentation) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 사실 검토</title><main>",
        "<h1>경력 사실 검토</h1>",
        "<p>아래 문구를 하나씩 확인해 주세요. 선택하지 않은 항목은 승인되지 않습니다.</p>",
        f"<p>경험 범위: {escape(view.scope_key)} · 기준 프로필 버전: {view.base_profile_version}</p>",
        f"<form method='post' action='/review/{escape(view.batch_id, quote=True)}'>",
        f"<input type='hidden' name='approval_token' value='{escape(view.approval_token, quote=True)}'>",
    ]
    for item in view.items:
        name = f"decision_{item.item_id}"
        parts.extend(
            [
                "<fieldset>",
                f"<legend>{item.position}. {escape(item.claim_type)} · {escape(item.scope_key)}</legend>",
                f"<blockquote>{escape(item.exact_text)}</blockquote>",
                f"<label for='{escape(name, quote=True)}'>이 문구에 대한 결정</label>",
                (
                    f"<select id='{escape(name, quote=True)}' name='{escape(name, quote=True)}' "
                    + "required><option value='' selected>결정 선택</option>"
                ),
            ]
        )
        parts.extend(f"<option value='{code}'>{label}</option>" for code, label in _DECISION_LABELS)
        parts.append("</select></fieldset>")
    parts.extend(
        [
            "<label><input type='checkbox' name='confirm' value='reviewed' required>",
            "위 문구와 각 결정을 직접 확인했습니다.</label>",
            "<button type='submit'>검토 결과 제출</button></form></main></html>",
        ]
    )
    return "".join(parts)


def _render_session(
    view: ProfilingWorkspaceSummary, action_form: ProfilingSessionActionForm | None
) -> str:
    work = view.session
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 프로파일링 상태</title><main>",
        "<h1>프로파일링 상태</h1>",
        "<p>명시적으로 제출한 이 세션의 입력만 처리합니다. 질문과 초안은 사실 확인 전 단계입니다.</p>",
        "<dl>",
        f"<dt>세션</dt><dd>{escape(work.id)}</dd>",
        f"<dt>상태</dt><dd>{escape(work.status)}</dd>",
        f"<dt>기준 프로필 버전</dt><dd>{work.base_profile_version}</dd>",
        f"<dt>현재 프로필 버전</dt><dd>{work.current_profile_version}</dd>",
        f"<dt>질문 단계</dt><dd>{escape(view.protocol_state or '재검토 필요')}</dd>",
        f"<dt>보관 만료</dt><dd>{escape(work.retention_expires_at.isoformat())}</dd>",
        "</dl>",
        "<h2>임시 초안 상태</h2><ul>",
    ]
    if view.draft_counts:
        parts.extend(f"<li>{escape(status)}: {count}</li>" for status, count in view.draft_counts)
    else:
        parts.append("<li>초안 없음</li>")
    parts.append(
        f"</ul><p><a href='/profiling/{escape(work.id, quote=True)}/drafts'>"
        "임시 초안 문구와 상태 보기</a></p>"
    )
    if work.base_profile_version == work.current_profile_version:
        parts.append(
            f"<p><a href='/profiling/{escape(work.id, quote=True)}/questions'>"
            "질문 단계별 진행 상태 보기</a></p>"
        )
    parts.append("<h2>검토 대기 묶음</h2><ul>")
    if view.pending_reviews:
        for batch in view.pending_reviews:
            parts.append(
                f"<li><a href='/review/{escape(batch.batch_id, quote=True)}'>"
                f"{escape(batch.scope_key)}</a> · 만료 {escape(batch.expires_at.isoformat())}</li>"
            )
    else:
        parts.append("<li>검토 대기 묶음 없음</li>")
    parts.append("</ul>")
    if work.status == "ACTIVE" and work.base_profile_version == work.current_profile_version:
        parts.extend(
            [
                (
                    f"<p><a href='/profiling/{escape(work.id, quote=True)}/input'>"
                    "이 세션에 경험 입력</a></p>"
                ),
                (
                    f"<p><a href='/profiling/{escape(work.id, quote=True)}/correction'>"
                    "이 세션의 내용 정정</a></p>"
                ),
            ]
        )
    if action_form is not None:
        label = "일시정지" if action_form.action == "pause" else "재개"
        parts.extend(
            [
                f"<form method='post' action='/profiling/{escape(work.id, quote=True)}/action'>",
                f"<input type='hidden' name='action_token' value='{escape(action_form.token, quote=True)}'>",
                f"<input type='hidden' name='action' value='{action_form.action}'>",
                f"<label><input type='checkbox' name='confirm' value='{action_form.action}' required>",
                f"이 세션을 직접 {label}합니다.</label>",
                f"<button type='submit'>세션 {label}</button></form>",
            ]
        )
    parts.append("<p>이 화면은 입력 원문이나 전체 대화 기록을 표시하지 않습니다.</p></main></html>")
    return "".join(parts)


def _render_drafts(view: ProfilingDraftList) -> str:
    work = view.session
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 임시 초안</title><main>",
        "<h1>임시 초안 문구</h1>",
        "<p>이 문구들은 제안된 임시 초안입니다. 사실 확인이나 사용 승인을 뜻하지 않습니다.</p>",
        (
            f"<p>세션: {escape(work.id)} · 보관 만료: "
            f"{escape(work.retention_expires_at.isoformat())}</p>"
        ),
        "<ol>",
    ]
    if view.items:
        for item in view.items:
            parts.extend(
                [
                    "<li>",
                    (
                        f"<p>범위: {escape(item.scope_key)} · 유형: {escape(item.claim_type)} "
                        f"· 상태: {escape(item.status)}</p>"
                    ),
                    f"<blockquote>{escape(item.exact_text)}</blockquote>",
                    "</li>",
                ]
            )
    else:
        parts.append("<li>현재 표시할 초안이 없습니다.</li>")
    parts.append("</ol>")
    counts: dict[str, int] = {}
    for item in view.items:
        if item.status == "DRAFT":
            counts[item.scope_key] = counts.get(item.scope_key, 0) + 1
    if not view.more_items:
        for scope_key, count in counts.items():
            if 1 <= count <= 5:
                parts.append(
                    f"<p><a href='/profiling/{escape(work.id, quote=True)}/drafts/"
                    f"{escape(quote(scope_key, safe=''), quote=True)}/prepare'>"
                    f"{escape(scope_key)} 범위의 {count}개 초안 검토 준비</a></p>"
                )
    if view.more_items:
        parts.append("<p>초안이 50개를 넘어 이 화면에는 처음 50개만 표시됩니다.</p>")
    parts.append(
        f"<p><a href='/profiling/{escape(work.id, quote=True)}'>"
        "세션 상태로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_review_prepare(view: ReviewPreparePresentation) -> str:
    session_id = escape(view.profiling_session_id, quote=True)
    scope_key = escape(quote(view.scope_key, safe=""), quote=True)
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 검토 준비</title><main><h1>임시 초안 검토 준비</h1>",
        "<p>아래 문구를 검토 화면에 묶습니다. 이 단계는 사실 승인이나 프로필 반영이 아닙니다.</p>",
        (
            f"<p>경험 범위: {escape(view.scope_key)} · 기준 프로필 버전: "
            f"{view.base_profile_version}</p><ol>"
        ),
    ]
    for draft in view.drafts:
        parts.append(
            f"<li><p>유형: {escape(draft.claim_type)}</p>"
            f"<blockquote>{escape(draft.exact_text)}</blockquote></li>"
        )
    parts.extend(
        [
            "</ol>",
            f"<form method='post' action='/profiling/{session_id}/drafts/{scope_key}/prepare'>",
            f"<input type='hidden' name='prepare_token' value='{escape(view.prepare_token, quote=True)}'>",
            "<label><input type='checkbox' name='confirm' value='prepare' required>",
            "표시된 문구를 검토 목록에 묶습니다.</label>",
            "<button type='submit'>검토 준비</button></form>",
            f"<p><a href='/profiling/{session_id}/drafts'>초안 목록으로 돌아가기</a></p>",
            "</main></html>",
        ]
    )
    return "".join(parts)


def _render_bullet_drafts(view: BulletPresentation) -> str:
    session_id = escape(view.profiling_session_id, quote=True)
    source_id = escape(view.source_input_id, quote=True)
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 글머리표 초안</title><main><h1>직접 작성한 글머리표</h1>",
        (
            "<p>입력에서 줄마다 '- ' 또는 '* '로 시작한 문구만 그대로 표시합니다. "
            "범위를 지정해 임시 초안으로 저장해도 사실 승인이나 프로필 반영은 아닙니다.</p>"
        ),
        "<ol>",
    ]
    parts.extend(f"<li><blockquote>{escape(text)}</blockquote></li>" for text in view.exact_bullets)
    parts.extend(
        [
            "</ol>",
            f"<form method='post' action='/profiling/{session_id}/input/{source_id}/drafts'>",
            f"<input type='hidden' name='bullet_token' value='{escape(view.bullet_token, quote=True)}'>",
            "<label for='scope_key'>경험 범위 식별자 (영문·숫자·_·-, 최대 64자)</label>",
            (
                "<input id='scope_key' name='scope_key' pattern='[A-Za-z0-9_-]{1,64}' "
                "maxlength='64' required>"
            ),
            "<p>이 문구들은 기여·수행 내용(CONTRIBUTION) 후보로 저장됩니다.</p>",
            "<label><input type='checkbox' name='confirm' value='draft' required>",
            "표시된 문구를 이 경험 범위의 임시 초안으로 저장합니다.</label>",
            "<button type='submit'>임시 초안 저장</button></form>",
            f"<p><a href='/profiling/{session_id}'>세션 상태로 돌아가기</a></p>",
            "</main></html>",
        ]
    )
    return "".join(parts)


def _render_questions(session_id: str, view: ProtocolProgress) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 질문 진행</title><main><h1>질문 단계별 진행 상태</h1>",
        (
            "<p>이 화면은 질문 횟수와 기록된 관찰 상태만 보여줍니다. "
            "답변의 의미나 사실 여부를 자동 판정하지 않습니다.</p>"
        ),
        (
            f"<p>현재 단계: {escape(view.current_state.value)} · "
            f"{'진행 차단' if view.blocked else '진행 중'}</p>"
        ),
        "<ol>",
    ]
    for step in view.steps:
        observation = step.observation_status.value if step.observation_status else "미기록"
        parts.append(
            f"<li>{escape(step.state.value)} · 질문 {step.asked_count}/2 · "
            f"관찰 {escape(observation)}</li>"
        )
    parts.append(
        f"</ol><p><a href='/profiling/{escape(session_id, quote=True)}'>"
        "세션 상태로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_artifacts(view: ResumeArtifactList) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 이력서 초안</title><main><h1>이력서 초안</h1>",
        "<p>초안 문구는 별도 검토가 필요하며 채용 결과를 보장하지 않습니다.</p><ul>",
    ]
    if view.items:
        for item in view.items:
            parts.append(
                f"<li><a href='/resume/{escape(item.artifact_id, quote=True)}/trace'>"
                f"초안 {item.artifact_version}</a> · 기준 프로필 버전 "
                f"{item.profile_version} · {escape(item.status)}</li>"
            )
            if item.status == "REVIEW_REQUIRED":
                parts.append(
                    f"<li><a href='/resume/{escape(item.artifact_id, quote=True)}/wording'>"
                    "R1 문구 직접 검토</a></li>"
                )
            if item.status == "WORDING_REVIEWED":
                parts.append(
                    f"<li><a href='/resume/{escape(item.artifact_id, quote=True)}/export/JSON'>"
                    "검토된 이력서 JSON 다운로드</a></li>"
                )
    else:
        parts.append("<li>표시할 이력서 초안이 없습니다.</li>")
    parts.append("</ul>")
    if view.more_items:
        parts.append("<p>초안이 20개를 넘어 이 화면에는 최근 20개만 표시됩니다.</p>")
    parts.append("</main></html>")
    return "".join(parts)


def _render_export_form(view: ProfileExportPresentation) -> str:
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>CareerGround 프로필 내보내기</title><main>"
        "<h1>보관된 프로필 버전 내보내기</h1>"
        "<p>선택한 본인용 데이터만 JSON으로 내보냅니다. 미확인 초안은 별도 상태로 표시하며 "
        "만료된 대화 원문과 삭제한 내용은 복원하지 않습니다.</p>"
        + (
            "<p>임시 초안과 만료된 전체 대화 원문은 포함되지 않습니다.</p>"
            if not view.inclusion["drafts"]
            else "<p>미승인 임시 초안은 확정한 경력 사실과 별도로 표시합니다.</p>"
        )
        + "<ul>"
        + "".join(
            f"<li>{escape({'claims': '경력 사실', 'evidence': '선택 근거 발췌', 'boundaries': '사용 경계', 'drafts': '미승인 임시 초안', 'unavailable_references': '불가 원문 참조 metadata'}[key])}: {'포함' if value else '제외'}</li>"
            for key, value in view.inclusion.items()
        )
        + "</ul>"
        f"<p>프로필 {escape(view.profile_id)} · 버전 {view.profile_version} · "
        f"크기 {view.content_bytes}바이트 · SHA-256 {escape(view.content_hash)}</p>"
        f"<form method='post' action='/profile/{escape(view.profile_id, quote=True)}"
        f"/export/{view.profile_version}'>"
        f"<input type='hidden' name='export_token' value='{escape(view.export_token, quote=True)}'>"
        "<label><input type='checkbox' name='confirm' value='download' required>"
        "이 범위의 JSON을 다운로드합니다.</label>"
        "<button type='submit'>JSON 다운로드</button></form></main></html>"
    )


def _render_resume_export_form(view: ResumeExportPresentation) -> str:
    artifact_id = escape(view.artifact_id, quote=True)
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        f"<title>CareerGround {view.wording_level} 이력서 내보내기</title><main>"
        f"<h1>검토한 {view.wording_level} 이력서 문구 내보내기</h1>"
        f"<p>현재 승인된 {view.wording_level} 문구와 기록된 근거만 내보냅니다. "
        "외부 전송이나 채용 결과를 뜻하지 않습니다.</p>"
        f"<p>초안 버전 {view.artifact_version} · 프로필 버전 {view.profile_version} "
        f"· 형식 {escape(view.format)} · 크기 {view.content_bytes}바이트 "
        f"· SHA-256 {escape(view.content_hash)}</p>"
        f"<form method='post' action='/resume/{artifact_id}/export/{view.format}'>"
        f"<input type='hidden' name='export_token' value='{escape(view.export_token, quote=True)}'>"
        "<label><input type='checkbox' name='confirm' value='download' required>"
        "이 범위의 파일을 다운로드합니다.</label>"
        "<button type='submit'>파일 다운로드</button></form>"
        f"<p><a href='/resume/{artifact_id}/trace'>근거 화면으로 돌아가기</a></p>"
        "</main></html>"
    )


def _render_jd_list(view: JDList) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround JD 발췌</title><main><h1>JD 발췌 목록</h1>",
        "<p>직접 선택해 저장한 발췌만 표시합니다. 적합성 판단은 포함되지 않습니다.</p>",
        "<p><a href='/jd/new'>선택한 JD 요건 글머리표 붙여넣기</a></p><ul>",
    ]
    if view.items:
        for item in view.items:
            label = " · ".join(
                part for part in (item.company_name, item.job_title) if part is not None
            )
            parts.append(
                f"<li><a href='/jd/{escape(item.jd_id, quote=True)}'>"
                f"JD 버전 {item.jd_version}</a> {escape(label)}</li>"
            )
    else:
        parts.append("<li>표시할 JD 발췌가 없습니다.</li>")
    parts.append("</ul>")
    if view.more_items:
        parts.append("<p>JD가 20개를 넘어 이 화면에는 최근 20개만 표시됩니다.</p>")
    parts.append("</main></html>")
    return "".join(parts)


def _render_jd_paste(view: JDPastePresentation) -> str:
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>CareerGround JD 발췌 저장</title><main><h1>선택한 JD 요건 저장</h1>"
        "<p>직접 선택한 요건을 줄마다 '- ' 또는 '* '로 시작해 1~5개 붙여넣으세요. "
        "각 줄의 내용만 저장하고, 나머지 JD 원문은 저장하지 않습니다. "
        "자동 분류·적합성 판단은 하지 않습니다.</p>"
        f"<p>프로필 {escape(view.profile_id)} · 기준 버전 {view.profile_version}</p>"
        "<form method='post' action='/jd/new'>"
        f"<input type='hidden' name='paste_token' value='{escape(view.paste_token, quote=True)}'>"
        "<label for='selected_text'>선택한 JD 요건 글머리표</label>"
        "<textarea id='selected_text' name='selected_text' maxlength='20000' required></textarea>"
        "<label><input type='checkbox' name='confirm' value='store_excerpts' required>"
        "표시한 줄만 JD 발췌로 저장합니다.</label>"
        "<button type='submit'>선택 발췌 저장</button></form>"
        "<p><a href='/jd'>JD 목록으로 돌아가기</a></p></main></html>"
    )


def _render_jd_analysis(view: JDAnalysisView, *, profile_version: int) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround JD 발췌</title><main><h1>선택한 JD 발췌</h1>",
        ("<p>저장된 위치의 원문 발췌만 보여줍니다. 자동 분류나 경력 적합성 판단이 아닙니다.</p>"),
        f"<p>JD 버전 {view.jd_version} · 원문 길이 {view.source_length}자</p><ol>",
    ]
    for ordinal, exact_text, start, end in view.requirements:
        parts.append(
            f"<li>{ordinal}. 원문 위치 {start}–{end}: "
            f"<blockquote>{escape(exact_text)}</blockquote></li>"
        )
    parts.append(
        f"</ol><p><a href='/jd/{escape(view.jd_id, quote=True)}/mapping/"
        f"{profile_version}'>현재 프로필 버전의 JD 연결 기록</a></p>"
        "<p><a href='/jd'>JD 목록으로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_jd_mapping(view: JDMappingView, candidates: tuple[JDLinkCandidate, ...]) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround JD 연결 기록</title><main><h1>JD와 경력 사실 연결 기록</h1>",
        (
            "<p>사용자가 기록한 잠재 연결만 표시합니다. 연결 없음은 역량 부족을 "
            "뜻하지 않으며, 적합성이나 채용 가능성 판단이 아닙니다.</p>"
        ),
        f"<p>JD 버전 {view.jd_version} · 보관 프로필 버전 {view.profile_version}</p>",
    ]
    if view.stale_relative_to_current_profile:
        parts.append("<p>현재 프로필보다 오래된 버전의 연결 기록입니다.</p>")
    parts.append("<ol>")
    for requirement in view.requirements:
        parts.extend(
            [
                f"<li><blockquote>{escape(requirement.exact_text)}</blockquote>",
                f"<p>연결 상태: {escape(requirement.gap_status)}</p>",
            ]
        )
        if requirement.linked_claim_ids:
            parts.append("<ul>")
            parts.extend(
                f"<li>Claim {escape(claim_id)}</li>" for claim_id in requirement.linked_claim_ids
            )
            parts.append("</ul>")
        if not view.stale_relative_to_current_profile and candidates:
            parts.append("<p>이 요건과 관련된 사실을 직접 선택해 기록할 수 있습니다.</p><ul>")
            for candidate in candidates:
                if candidate.claim_id in requirement.linked_claim_ids:
                    continue
                path = (
                    f"/jd/{escape(view.jd_id, quote=True)}/mapping/{view.profile_version}/link/"
                    f"{escape(requirement.requirement_id, quote=True)}/"
                    f"{escape(candidate.claim_id, quote=True)}"
                )
                parts.append(
                    f"<li><a href='{path}'>잠재 연결 검토: {escape(candidate.exact_text)}</a></li>"
                )
            parts.append("</ul>")
        parts.append("</li>")
    parts.append(
        f"</ol><p><a href='/jd/{escape(view.jd_id, quote=True)}/draft/"
        f"{view.profile_version}'>연결된 사실로 R1 초안 만들기</a></p>"
        f"<p><a href='/jd/{escape(view.jd_id, quote=True)}'>"
        "JD 발췌로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_jd_link(view: JDLinkPresentation) -> str:
    path = (
        f"/jd/{escape(view.jd_id, quote=True)}/mapping/{view.profile_version}/link/"
        f"{escape(view.requirement_id, quote=True)}/{escape(view.claim_id, quote=True)}"
    )
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround JD 잠재 연결</title><main><h1>JD와 사실 연결 검토</h1>",
        "<p>관련성은 직접 판단하세요. 연결은 잠재 관계만 기록하며 적합성이나 채용 가능성 판단이 아닙니다.</p>",
        f"<p>보관 프로필 버전 {view.profile_version}</p>",
        f"<h2>JD 요건</h2><blockquote>{escape(view.requirement_text)}</blockquote>",
        f"<h2>사용 허용된 사실</h2><blockquote>{escape(view.claim_text)}</blockquote>",
        "<h2>선택 근거</h2><ol>",
    ]
    for excerpt, source_ref in view.evidence:
        parts.append(
            f"<li><blockquote>{escape(excerpt)}</blockquote>원본 참조 {escape(source_ref)}</li>"
        )
    parts.extend(
        [
            "</ol>",
            f"<form method='post' action='{path}'>",
            f"<input type='hidden' name='link_token' value='{escape(view.link_token, quote=True)}'>",
            "<label><input type='checkbox' name='confirm' value='link_potential' required>",
            "두 문구와 근거를 확인했고 잠재 관련성을 기록합니다.</label>",
            "<button type='submit'>잠재 연결 저장</button></form>",
            (
                f"<p><a href='/jd/{escape(view.jd_id, quote=True)}/mapping/"
                f"{view.profile_version}'>연결 기록으로 돌아가기</a></p></main></html>"
            ),
        ]
    )
    return "".join(parts)


def _render_r1_draft(view: ResumeDraftPresentation) -> str:
    jd_id = escape(view.jd_id, quote=True)
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround R1 초안 선택</title><main><h1>R1 이력서 초안 선택</h1>",
        (
            "<p>JD와 잠재 연결로 기록한 사용 허용 사실 중 1~5개를 직접 고르세요. "
            "문구를 그대로 복사한 검토 전 초안이며 외부 검증·적합성·채용 가능성 판단이 아닙니다.</p>"
        ),
        f"<p>보관 프로필 버전 {view.profile_version}</p>",
    ]
    if not view.candidates:
        parts.append("<p>현재 선택 가능한 사실이 없습니다. 먼저 JD 잠재 연결을 기록하세요.</p>")
    else:
        parts.extend(
            [
                f"<form method='post' action='/jd/{jd_id}/draft/{view.profile_version}'>",
                f"<input type='hidden' name='draft_token' value='{escape(view.draft_token, quote=True)}'>",
                "<fieldset><legend>정확한 사실 문구 선택</legend>",
            ]
        )
        for candidate in view.candidates:
            parts.append(
                "<label><input type='checkbox' name='claim_id' "
                f"value='{escape(candidate.claim_id, quote=True)}'>"
                f"{escape(candidate.exact_text)}</label><ul>"
            )
            for excerpt, source_ref in candidate.evidence:
                parts.append(f"<li>{escape(excerpt)} · 원본 참조 {escape(source_ref)}</li>")
            parts.append("</ul>")
        parts.extend(
            [
                "</fieldset>",
                "<label><input type='checkbox' name='confirm' value='create_r1' required>",
                "선택한 정확한 문구로 검토 전 R1 초안을 만듭니다.</label>",
                "<button type='submit'>R1 초안 만들기</button></form>",
            ]
        )
    parts.append(
        f"<p><a href='/jd/{jd_id}/mapping/{view.profile_version}'>"
        "JD 연결 기록으로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_career_profile(view: ProfileView) -> str:
    profile_id = escape(view.profile_id, quote=True)
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 보관 프로필</title><main><h1>보관 프로필 사실</h1>",
        (
            f"<p>프로필 {escape(view.profile_id)} · 보관 버전 {view.profile_version} · "
            f"활성 경계 {view.constraint_count}개</p>"
        ),
        "<p>사용자가 확인한 사실도 외부 검증을 뜻하지 않습니다. 사용 정책과 일관성 상태를 확인하세요.</p>",
        "<ol>",
    ]
    if not view.claims:
        parts.append("<li>이 버전에는 활성 Claim이 없습니다.</li>")
    for claim in view.claims:
        parts.extend(
            [
                "<li>",
                f"<blockquote>{escape(claim.exact_text)}</blockquote>",
                (
                    f"<p>범위 {escape(claim.scope_key)} · 유형 {escape(claim.claim_type)} · "
                    f"확인 {escape(claim.knowledge_status)} · "
                    f"일관성 {escape(claim.consistency_status)} · "
                    f"사용 {escape(claim.usage_policy)}</p>"
                ),
                (
                    f"<a href='/profile/{profile_id}/{view.profile_version}/claim/"
                    f"{escape(claim.claim_id, quote=True)}'>선택 근거 보기</a></li>"
                ),
            ]
        )
    parts.extend(
        [
            "</ol>",
            "<p><a href='/jd/new'>JD 요건 직접 입력</a> · <a href='/jd'>저장한 JD 보기</a></p>",
            (
                f"<p><a href='/profile/{profile_id}/export/{view.profile_version}'>"
                "이 버전 JSON 내보내기</a></p>"
            ),
            "<p><a href='/profiling/start'>시작 화면으로 돌아가기</a></p></main></html>",
        ]
    )
    return "".join(parts)


def _render_claim_evidence(profile_id: str, view: ClaimEvidenceView) -> str:
    claim = view.claim
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround Claim 근거</title><main><h1>사실과 선택 근거</h1>",
        (
            f"<p>보관 프로필 버전 {view.profile_version} · 사실 검토 기록 "
            f"{'있음' if view.reviewed else '없음'}</p>"
        ),
        f"<blockquote>{escape(claim.exact_text)}</blockquote>",
        (
            f"<p>범위 {escape(claim.scope_key)} · 확인 {escape(claim.knowledge_status)} · "
            f"일관성 {escape(claim.consistency_status)} · 사용 {escape(claim.usage_policy)}</p>"
        ),
        "<h2>선택 근거 발췌</h2><ol>",
    ]
    if not view.evidence:
        parts.append("<li>기록된 선택 근거가 없습니다.</li>")
    for item in view.evidence:
        parts.append(
            f"<li><blockquote>{escape(item.exact_excerpt)}</blockquote>"
            f"관계 {escape(item.relation_type)} · 원본 참조 {escape(item.original_input_ref)} "
            f"· 원본 상태 {escape(item.source_availability)}</li>"
        )
    parts.append("</ol><h2>사용 경계</h2><ul>")
    if not view.constraints:
        parts.append("<li>이 보관 버전의 동일 범위에 기록된 경계가 없습니다.</li>")
    for kind, text in view.constraints:
        parts.append(f"<li>{escape(kind)}: <blockquote>{escape(text)}</blockquote></li>")
    parts.append(
        f"</ul><p><a href='/profile/{escape(profile_id, quote=True)}/"
        f"{view.profile_version}/claim/{escape(claim.claim_id, quote=True)}/use-review'>"
        "R1 사용 가능 여부 검토</a></p>"
    )
    parts.append(
        "<p><a href='/jd/new'>JD 요건 직접 입력</a> · <a href='/jd'>저장한 JD 보기</a></p>"
    )
    parts.append(
        f"<p><a href='/profile/{escape(profile_id, quote=True)}/"
        f"{view.profile_version}'>프로필 버전으로 돌아가기</a></p></main></html>"
    )
    return "".join(parts)


def _render_claim_use_review(view: ClaimUseReviewPresentation) -> str:
    trace = view.trace
    path = (
        f"/profile/{escape(view.profile_id, quote=True)}/{view.base_profile_version}/claim/"
        f"{escape(view.claim_id, quote=True)}"
    )
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround Claim R1 사용 검토</title><main><h1>별도 R1 사용 검토</h1>",
        (
            "<p>사실 확인과 이력서 사용 허용은 별개입니다. 사용자 확인은 외부 검증을 "
            "뜻하지 않습니다. 아래 문구·근거·경계를 직접 확인하세요.</p>"
        ),
        f"<p>보관 프로필 버전 {view.base_profile_version}</p>",
        f"<blockquote>{escape(trace.claim.exact_text)}</blockquote>",
        (
            f"<p>범위 {escape(trace.claim.scope_key)} · 유형 {escape(trace.claim.claim_type)} · "
            f"확인 {escape(trace.claim.knowledge_status)} · "
            f"일관성 {escape(trace.claim.consistency_status)} · "
            f"사용 {escape(trace.claim.usage_policy)}</p>"
        ),
        "<h2>선택 근거</h2><ol>",
    ]
    for item in trace.evidence:
        parts.append(
            f"<li><blockquote>{escape(item.exact_excerpt)}</blockquote>"
            f"관계 {escape(item.relation_type)} · 원본 참조 {escape(item.original_input_ref)}</li>"
        )
    parts.append("</ol><h2>동일 범위 사용 경계</h2><ul>")
    if not trace.constraints:
        parts.append("<li>기록된 활성 경계가 없습니다.</li>")
    for kind, text in trace.constraints:
        parts.append(f"<li>{escape(kind)}: <blockquote>{escape(text)}</blockquote></li>")
    parts.append("</ul>")
    if view.blockers:
        parts.append(
            "<p role='alert'>현재 사용 검토를 승인할 수 없습니다: "
            f"{escape(', '.join(view.blockers))}</p>"
        )
    else:
        parts.extend(
            [
                f"<form method='post' action='{path}/use-review'>",
                f"<input type='hidden' name='approval_token' value='{escape(view.approval_token, quote=True)}'>",
                "<label><input type='checkbox' name='confirm_consistency' value='yes' required>",
                "표시된 사실과 근거를 검토했고 이 경험에 대해 아는 상충 내용이 없습니다.</label>",
                "<label><input type='checkbox' name='confirm_use' value='yes' required>",
                "이 정확한 사실 문구를 R1 이력서에 사용하도록 허용합니다.</label>",
                "<button type='submit'>별도 사용 검토 저장</button></form>",
            ]
        )
    parts.append(f"<p><a href='{path}'>Claim 근거로 돌아가기</a></p></main></html>")
    return "".join(parts)


def _render_deletion_preview(view: DeletionPreview) -> str:
    counts: dict[str, int] = {}
    for item in view.items:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 합성 삭제 범위 미리보기</title><main>",
        "<h1>합성 삭제 범위 미리보기</h1>",
        (
            "<p>현재 구현된 로컬 저장소 일부만 집계합니다. 외부 제공자, 실제 파일 내용, "
            "백업 등은 이 목록으로 확인되지 않았습니다. 완전한 삭제 영향이나 삭제 완료를 "
            "뜻하지 않습니다.</p>"
        ),
        (
            f"<p>범위: {escape(view.scope.value)} · 대상: {escape(view.target_id)} "
            f"· 적용 가능: {'예' if view.ready_to_execute else '아니오'}</p>"
        ),
        "<h2>현재 확인 가능한 항목 수</h2><ul>",
    ]
    parts.extend(f"<li>{escape(kind)}: {count}</li>" for kind, count in sorted(counts.items()))
    parts.append("</ul><p>이 화면에서는 삭제 요청을 제출할 수 없습니다.</p></main></html>")
    return "".join(parts)


def _render_resume_trace(view: ResumeTrace) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 이력서 근거</title><main><h1>이력서 문구와 근거</h1>",
        (
            "<p>아래 문구는 기록된 사실과 근거에 연결된 초안입니다. "
            "외부 사실 검증이나 채용 성과를 뜻하지 않습니다.</p>"
        ),
        (
            f"<p>초안 버전 {view.artifact_version} · 프로필 버전 {view.profile_version} "
            f"· JD {escape(view.jd_id)}</p>"
        ),
        (
            f"<p><a href='/jd/{escape(view.jd_id, quote=True)}/mapping/"
            f"{view.profile_version}'>이 버전의 JD 연결 기록</a></p>"
        ),
    ]
    if view.stale_relative_to_current_profile:
        parts.append("<p>이 초안은 현재 프로필보다 오래된 버전을 기준으로 합니다.</p>")
    parts.append("<ol>")
    for unit in view.units:
        parts.extend(
            [
                "<li>",
                f"<blockquote>{escape(unit.exact_text)}</blockquote>",
                (
                    f"<p>문구 수준: {escape(unit.wording_level)} · 검토 상태: "
                    f"{escape(unit.review_status)}</p>"
                ),
                f"<p>Claim: {escape(unit.claim_id)}</p><ul>",
            ]
        )
        for evidence_id, excerpt, original_ref in zip(
            unit.evidence_ids,
            unit.evidence_excerpts,
            unit.original_input_refs,
            strict=True,
        ):
            parts.append(
                f"<li>근거 {escape(evidence_id)}: <blockquote>{escape(excerpt)}</blockquote>"
                f"원본 참조 {escape(original_ref)}</li>"
            )
        parts.append("</ul></li>")
    parts.append("</ol>")
    if not view.stale_relative_to_current_profile and all(
        unit.wording_level == "R1" and unit.review_status == "REVIEW_REQUIRED"
        for unit in view.units
    ):
        parts.append(
            f"<p><a href='/resume/{escape(view.artifact_id, quote=True)}/wording'>"
            "이 문구를 직접 검토</a></p>"
        )
    if not view.stale_relative_to_current_profile and all(
        unit.wording_level in {"R1", "R2"} and unit.review_status == "WORDING_REVIEWED"
        for unit in view.units
    ):
        artifact_id = escape(view.artifact_id, quote=True)
        parts.append(
            f"<p><a href='/resume/{artifact_id}/export/JSON'>JSON 다운로드</a> · "
            f"<a href='/resume/{artifact_id}/export/MARKDOWN'>Markdown 다운로드</a></p>"
        )
    if not view.stale_relative_to_current_profile and all(
        unit.wording_level == "R1" for unit in view.units
    ):
        parts.append(
            f"<p><a href='/resume/{escape(view.artifact_id, quote=True)}/r2'>R2 문구를 따로 제안하고 승인하기</a></p>"
        )
    parts.append("<p><a href='/artifacts'>초안 목록으로 돌아가기</a></p></main></html>")
    return "".join(parts)


def _render_wording_review(presentation: WordingPresentation) -> str:
    view = presentation.review
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround R1 이력서 문구 검토</title><main>",
        "<h1>R1 이력서 문구 직접 검토</h1>",
        (
            "<p>아래 문장은 확인된 Claim 문구 그대로입니다. 각 문장과 근거를 보고 "
            "전체 문구를 승인할 때만 제출하세요. 외부 사실 검증이나 채용 결과를 뜻하지 않습니다.</p>"
        ),
        f"<p>초안 버전 {view.artifact_version} · 프로필 버전 {view.profile_version}</p>",
        f"<form method='post' action='/resume/{escape(view.artifact_id, quote=True)}/wording'>",
        f"<input type='hidden' name='approval_token' value='{escape(presentation.approval_token, quote=True)}'>",
        "<ol>",
    ]
    for unit in view.trace_units:
        parts.extend(
            [
                f"<li><blockquote>{escape(unit.exact_text)}</blockquote>",
                f"<p>Claim {escape(unit.claim_id)} · 문구 수준 {escape(unit.wording_level)}</p>",
                "<ul>",
            ]
        )
        for evidence_id, excerpt, original_ref in zip(
            unit.evidence_ids,
            unit.evidence_excerpts,
            unit.original_input_refs,
            strict=True,
        ):
            parts.append(
                f"<li>근거 {escape(evidence_id)}: <blockquote>{escape(excerpt)}</blockquote>"
                f"원본 참조 {escape(original_ref)}</li>"
            )
        parts.append("</ul></li>")
    parts.extend(
        [
            "</ol><label><input type='checkbox' name='confirm' value='accept_r1' required>",
            "모든 R1 문구와 표시된 근거를 직접 확인하고 이 문구 그대로 사용하도록 승인합니다.</label>",
            "<button type='submit'>R1 문구 승인</button></form>",
            (
                f"<p><a href='/resume/{escape(view.artifact_id, quote=True)}/trace'>"
                "근거 화면으로 돌아가기</a></p></main></html>"
            ),
        ]
    )
    return "".join(parts)


def _render_start(view: ProfilingStartView, *, export_available: bool) -> str:
    parts = [
        "<!doctype html><html lang='ko'><meta charset='utf-8'>",
        "<title>CareerGround 경력 정리 시작</title><main>",
        "<h1>경력 정리 시작</h1>",
        "<p>경력 추가 작업을 명시적으로 시작합니다. 이 작업에 직접 제출한 내용만 수집합니다.</p>",
        (
            "<p>문서 없이 직접 입력할 수 있습니다. 사실 확인과 R1 사용 검토는 각각 필요하며, "
            "외부 검증이나 채용 결과를 보장하지 않습니다.</p>"
        ),
        "<p>임시 세션과 입력은 마지막 활동 후 최대 90일 동안 보관됩니다.</p>",
        f"<p>기준 프로필 버전: {view.profile_version}</p>",
        "<h2>기존 임시 세션</h2><ul>",
    ]
    if view.existing_sessions:
        for work in view.existing_sessions:
            parts.append(
                f"<li><a href='/profiling/{escape(work.session_id, quote=True)}'>"
                f"{escape(work.status)}</a> · 만료 {escape(work.retention_expires_at.isoformat())}</li>"
            )
    else:
        parts.append("<li>없음</li>")
    parts.extend(
        [
            "</ul><form method='post' action='/profiling/start'>",
            f"<input type='hidden' name='start_token' value='{escape(view.start_token, quote=True)}'>",
            "<label><input type='checkbox' name='confirm' value='start' required>",
            "수집 범위와 임시 보관 기간을 확인하고 새 세션을 시작합니다.</label>",
            "<button type='submit'>새 경력 정리 시작</button></form>",
            (
                "<p><a href='/jd/new'>JD 요건 직접 입력</a> · "
                "<a href='/jd'>저장한 JD 보기</a> · "
                "<a href='/artifacts'>이력서 초안과 근거 보기</a></p>"
            ),
            (
                "<p>합성 테스트 저장소의 일부 삭제 영향만 확인할 수 있습니다. "
                "이 화면에서는 삭제 요청을 제출할 수 없습니다.</p>"
            ),
            (
                f"<p><a href='/deletion/preview/profile/{escape(view.profile_id, quote=True)}'>"
                "프로필 삭제 범위 미리보기</a> · "
                "<a href='/deletion/preview/account'>계정 삭제 범위 미리보기</a></p>"
            ),
            "</main></html>",
        ]
    )
    if export_available:
        parts.insert(
            -1,
            f"<p><a href='/profile/{escape(view.profile_id, quote=True)}/"
            f"{view.profile_version}'>현재 보관 프로필 보기</a></p>",
        )
        parts.insert(
            -1,
            f"<p><a href='/profile/{escape(view.profile_id, quote=True)}/export/"
            f"{view.profile_version}'>현재 보관 프로필 JSON 내보내기</a></p>",
        )
    return "".join(parts)


def _render_input_form(view: ProfilingInputForm) -> str:
    session_id = escape(view.profiling_session_id, quote=True)
    correction = view.content_kind is InputKind.CORRECTION
    suffix = "correction" if correction else "input"
    title = "경험 정정" if correction else "경험 입력"
    notice = (
        "직접 정정한 내용 한 건만 저장합니다. 현재 질문 회차와 미제출 검토 묶음은 무효화되고 "
        "기존 초안은 다시 검토해야 합니다."
        if correction
        else "여기에 직접 작성한 내용 한 건만 이 CareerGround 세션에 저장합니다. "
        "전체 채팅이나 관련 없는 내용을 붙여넣지 마세요. 줄마다 '- ' 또는 '* '로 "
        "시작하는 1~5개 글머리표를 적으면 다음 화면에서 임시 초안으로 선택할 수 있습니다."
    )
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        f"<title>CareerGround {title}</title><main>"
        f"<h1>이 세션에 {title}</h1>"
        f"<p>{notice}</p>"
        f"<p>기준 프로필 버전: {view.base_profile_version} · "
        f"보관 만료: {escape(view.retention_expires_at.isoformat())}</p>"
        f"<form method='post' action='/profiling/{session_id}/{suffix}'>"
        f"<input type='hidden' name='input_token' value='{escape(view.input_token, quote=True)}'>"
        f"<label for='content'>직접 작성한 {title}</label>"
        f"<textarea id='content' name='content' maxlength='{MAX_INPUT_CHARS}' required></textarea>"
        "<label><input type='checkbox' name='confirm' value='submit' required>"
        "이 세션에 이 내용 한 건을 제출합니다.</label>"
        f"<button type='submit'>{title} 저장</button></form>"
        f"<p><a href='/profiling/{session_id}'>세션 상태로 돌아가기</a></p></main></html>"
    )


_REVIEW_CSS = """html{font-family:system-ui,sans-serif;line-height:1.6;color:#172033;background:#fff}
body{margin:1rem}main{max-width:64rem;margin:auto;overflow-wrap:anywhere}
a{color:#0645ad}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,
textarea:focus-visible,main:focus-visible{outline:3px solid #0645ad;outline-offset:3px}
textarea,input[type=text],select{box-sizing:border-box;max-width:100%;font:inherit}
textarea{width:100%}button{font:inherit;max-width:100%;white-space:normal;margin:.5rem 0}
label{display:block;margin:.5rem 0}fieldset{min-width:0}blockquote{margin:1rem}
table{display:block;max-width:100%;overflow-x:auto}pre{white-space:pre-wrap}
"""
_REVIEW_CSS_HASH = base64.b64encode(hashlib.sha256(_REVIEW_CSS.encode()).digest()).decode()


def _html_response(body: str, *, status_code: int = 200) -> HTMLResponse:
    body = body.replace(
        "<meta charset='utf-8'>",
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{_REVIEW_CSS}</style>",
        1,
    )
    focus = " autofocus" if status_code >= 400 else ""
    body = body.replace(
        "<main",
        "<a href='#main-content'>본문으로 바로가기</a>"
        f"<main id='main-content' tabindex='-1'{focus}",
        1,
    )
    return HTMLResponse(
        body,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; "
                f"style-src 'sha256-{_REVIEW_CSS_HASH}'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


def _with_auth_cookies(result: Response, auth_response: Response) -> Response:
    for name, value in auth_response.raw_headers:
        if name.lower() == b"set-cookie":
            result.raw_headers.append((name, value))
    return result

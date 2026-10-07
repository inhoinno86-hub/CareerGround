"""Local browser-only R2 approval and explicit owned project registration."""

from datetime import UTC, datetime, timedelta
from hmac import digest
from html import escape
from urllib.parse import parse_qs, quote
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from careerground.domain.authorization import ResourceNotFound, get_owned_profile
from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.resume_draft import ResumeDraftUnavailable, get_resume_trace
from careerground.domain.resume_r2_review import (
    R2FactReviewRequired,
    R2ProposalRejected,
    R2ProposalService,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import Account, ProjectScope
from careerground.web.resume_r2_forms import render_r2_exact, render_r2_input


def attach_contract_extensions(
    app, *, session_factory, identity, review_secret, presentation_secret
):
    from careerground.web.review_foundation import (
        _html_response,
        _require_confirmation_origin,
        _with_auth_cookies,
    )

    tokens = BrowserFormTokenCodec(presentation_secret)
    r2 = R2ProposalService(digest(review_secret, b"synthetic-r1-wording-review-v1", "sha256"))
    keys = frozenset(
        {"purpose", "account_id", "browser_session_id", "target_id", "version", "expires_at"}
    )

    def sign(principal, purpose, target, version):
        return tokens.sign(
            {
                "purpose": purpose,
                "account_id": principal.account_id,
                "browser_session_id": principal.session_id,
                "target_id": target,
                "version": version,
                "expires_at": int((datetime.now(UTC) + timedelta(minutes=3)).timestamp()),
            }
        )

    def verify(value, principal, purpose, target, version):
        try:
            payload = tokens.verify(value, expected_keys=keys)
            if (
                (
                    payload["purpose"],
                    payload["account_id"],
                    payload["browser_session_id"],
                    payload["target_id"],
                    payload["version"],
                )
                != (purpose, principal.account_id, principal.session_id, target, version)
                or type(payload["version"]) is not int
                or type(payload["expires_at"]) is not int
                or payload["expires_at"] <= datetime.now(UTC).timestamp()
            ):
                raise HTTPException(409)
        except (BrowserFormTokenRejected, ValueError, TypeError):
            raise HTTPException(409) from None

    async def form(request):
        _require_confirmation_origin(request)
        if (
            request.headers.get("content-type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            raise HTTPException(415)
        body = await request.body()
        if len(body) > 65536:
            raise HTTPException(413)
        try:
            return parse_qs(
                body.decode(), keep_blank_values=True, strict_parsing=True, max_num_fields=64
            )
        except (UnicodeError, ValueError):
            raise HTTPException(400) from None

    def fact_review_page():
        return _html_response(
            "<!doctype html><html lang='ko'><meta charset='utf-8'><main><h1>별도 경력 사실 검토가 필요합니다</h1><p>역할·성과·기간·새 근거의 변화는 문구 승인으로 저장하지 않습니다. 기존 후보는 저장되지 않았습니다.</p><p><a href='/profiling/start'>새 경력 사실을 직접 입력하고 검토하기</a></p></main></html>",
            status_code=409,
        )

    @app.get("/profile/{profile_id}/export-options/{selector}")
    async def export_options(profile_id: str, selector: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        if selector != "CURRENT" and (
            not selector.isascii() or not selector.isdecimal() or len(selector) > 10
        ):
            raise HTTPException(404)
        with session_factory() as session:
            try:
                get_owned_profile(session, account_id=principal.account_id, profile_id=profile_id)
            except ResourceNotFound:
                raise HTTPException(404) from None
        labels = {
            "claims": "canonical 경력 사실",
            "evidence": "선택 근거 발췌",
            "boundaries": "사용 경계",
            "drafts": "미승인 임시 초안 (사실 승인과 구분)",
            "unavailable_references": "만료·불가 원문의 참조 metadata만",
        }
        body = "<!doctype html><html lang='ko'><meta charset='utf-8'><main><h1>프로필 내보내기 범위 선택</h1><p>선택한 내용은 다음 화면의 정확한 버전과 함께 승인합니다. 만료 원문·삭제한 자료는 복원하지 않습니다.</p>"
        body += f"<form method='get' action='/profile/{escape(profile_id, quote=True)}/export/{escape(selector, quote=True)}'><input type='hidden' name='selection' value='explicit'>"
        body += "".join(
            f"<label><input type='checkbox' name='{key}' value='yes' {'checked' if key != 'drafts' else ''}>{label}</label>"
            for key, label in labels.items()
        )
        body += "<button type='submit'>선택한 범위와 버전 확인</button></form></main></html>"
        return _with_auth_cookies(_html_response(body), auth)

    @app.get("/resume/{artifact_id}/r2")
    async def r2_input(artifact_id: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        with session_factory() as session:
            try:
                source = get_resume_trace(
                    session, account_id=principal.account_id, artifact_id=artifact_id
                )
                if (
                    source.stale_relative_to_current_profile
                    or not 1 <= len(source.units) <= 5
                    or any(unit.wording_level != "R1" for unit in source.units)
                ):
                    raise ResumeDraftUnavailable
            except ResumeDraftUnavailable:
                raise HTTPException(404) from None
            return _with_auth_cookies(
                _html_response(
                    render_r2_input(
                        source, sign(principal, "R2_INPUT", artifact_id, source.artifact_version)
                    )
                ),
                auth,
            )

    @app.post("/resume/{artifact_id}/r2/prepare")
    async def r2_prepare(artifact_id: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        fields = await form(request)
        with session_factory() as session:
            try:
                source = get_resume_trace(
                    session, account_id=principal.account_id, artifact_id=artifact_id
                )
                verify(
                    fields.get("input_token", [""])[0],
                    principal,
                    "R2_INPUT",
                    artifact_id,
                    source.artifact_version,
                )
                expected = {"input_token"} | {
                    f"{key}_{index}"
                    for index in range(len(source.units))
                    for key in (
                        "unit_id",
                        "source_hash",
                        "claim_id",
                        "evidence_id",
                        "proposed_text",
                        "fact_review",
                    )
                }
                if set(fields) != expected or any(
                    len(value) != 1
                    for key, value in fields.items()
                    if not key.startswith("evidence_id_")
                ):
                    raise HTTPException(400)
                proposals = tuple(
                    {
                        "unit_id": fields[f"unit_id_{i}"][0],
                        "source_hash": fields[f"source_hash_{i}"][0],
                        "claim_id": fields[f"claim_id_{i}"][0],
                        "evidence_ids": fields[f"evidence_id_{i}"],
                        "proposed_text": fields[f"proposed_text_{i}"][0],
                        "fact_review": fields[f"fact_review_{i}"][0],
                    }
                    for i in range(len(source.units))
                )
                view = r2.prepare(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    source_artifact_id=artifact_id,
                    proposals=proposals,
                    now=datetime.now(UTC),
                )
            except R2FactReviewRequired:
                return _with_auth_cookies(fact_review_page(), auth)
            except (R2ProposalRejected, ResumeDraftUnavailable):
                return _with_auth_cookies(fact_review_page(), auth)
        return _with_auth_cookies(_html_response(render_r2_exact(view)), auth)

    @app.post("/resume/{artifact_id}/r2/approve")
    async def r2_approve(artifact_id: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        fields = await form(request)
        if (
            set(fields) != {"approval_token", "confirm"}
            or any(len(v) != 1 for v in fields.values())
            or fields["confirm"] != ["approve_r2"]
        ):
            raise HTTPException(400)
        with session_factory() as session:
            try:
                artifact = r2.submit(
                    session,
                    account_id=principal.account_id,
                    browser_session_id=principal.session_id,
                    approval_token=fields["approval_token"][0],
                    now=datetime.now(UTC),
                )
                if artifact.source_artifact_id != artifact_id:
                    raise R2ProposalRejected
                target = artifact.id
                session.commit()
            except R2ProposalRejected:
                raise HTTPException(409) from None
        return _with_auth_cookies(
            RedirectResponse("/resume/" + quote(target, safe="") + "/trace", status_code=303), auth
        )

    @app.get("/profile/{profile_id}/projects")
    async def project_choices(profile_id: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        with session_factory() as session:
            try:
                profile = get_owned_profile(
                    session, account_id=principal.account_id, profile_id=profile_id
                )
            except ResourceNotFound:
                raise HTTPException(404) from None
            scopes = sorted(
                set(
                    session.scalars(
                        select(Claim.scope_key).where(
                            Claim.account_id == principal.account_id,
                            Claim.profile_id == profile_id,
                            Claim.status == "ACTIVE",
                        )
                    )
                )
            )
            if len(scopes) > 100:
                raise HTTPException(413)
            projects = session.scalars(
                select(ProjectScope)
                .where(
                    ProjectScope.account_id == principal.account_id,
                    ProjectScope.profile_id == profile_id,
                )
                .order_by(ProjectScope.id)
            ).all()
            token = sign(principal, "PROJECT_REGISTER", profile_id, profile.version)
            body = "<!doctype html><html lang='ko'><meta charset='utf-8'><main><h1>합성 프로젝트 범위 등록</h1><p>경력 범위를 직접 프로젝트로 지정합니다. 등록은 사실 변경이나 삭제 승인이 아닙니다.</p><ul>"
            body += "".join(
                f"<li>{escape(p.scope_key)} · {escape(p.status)} · 프로젝트 ID: {escape(p.id)}</li>"
                for p in projects
            )
            body += f"</ul><form method='post'><input type='hidden' name='registration_token' value='{escape(token, quote=True)}'><label for='scope_key'>프로젝트로 지정할 경력 범위</label><select id='scope_key' name='scope_key' required><option value='' selected>직접 선택</option>"
            body += "".join(
                f"<option value='{escape(key, quote=True)}'>{escape(key)}</option>"
                for key in scopes
            )
            body += "</select><label><input type='checkbox' name='confirm' value='register_project' required>선택한 경력 범위를 프로젝트로 등록합니다.</label><button type='submit'>프로젝트 범위 등록</button></form></main></html>"
            return _with_auth_cookies(_html_response(body), auth)

    @app.post("/profile/{profile_id}/projects")
    async def register_project(profile_id: str, request: Request):
        auth = Response()
        principal = await identity(request, auth)
        fields = await form(request)
        if (
            set(fields) != {"registration_token", "scope_key", "confirm"}
            or any(len(v) != 1 for v in fields.values())
            or fields["confirm"] != ["register_project"]
        ):
            raise HTTPException(400)
        with session_factory() as session:
            try:
                account = session.scalar(
                    select(Account)
                    .where(Account.id == principal.account_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if account is None or account.status != "ACTIVE":
                    raise ResourceNotFound
                profile = get_owned_profile(
                    session, account_id=principal.account_id, profile_id=profile_id
                )
                # Serialize registrations and partial erasure on the same owner.
                profile = session.scalar(
                    select(type(profile))
                    .where(
                        type(profile).id == profile_id,
                        type(profile).account_id == principal.account_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if profile is None or profile.status != "ACTIVE":
                    raise ResourceNotFound
                verify(
                    fields["registration_token"][0],
                    principal,
                    "PROJECT_REGISTER",
                    profile_id,
                    profile.version,
                )
                key = fields["scope_key"][0]
                exists = session.scalar(
                    select(Claim.id)
                    .where(
                        Claim.account_id == principal.account_id,
                        Claim.profile_id == profile_id,
                        Claim.scope_key == key,
                        Claim.status == "ACTIVE",
                    )
                    .limit(1)
                )
                if exists is None:
                    raise HTTPException(409)
                current = session.scalar(
                    select(ProjectScope).where(
                        ProjectScope.account_id == principal.account_id,
                        ProjectScope.profile_id == profile_id,
                        ProjectScope.scope_key == key,
                    )
                )
                if current is None:
                    session.add(
                        ProjectScope(
                            id=str(uuid4()),
                            account_id=principal.account_id,
                            profile_id=profile_id,
                            scope_key=key,
                            status="ACTIVE",
                            created_at=datetime.now(UTC),
                        )
                    )
                elif current.status != "ACTIVE":
                    raise HTTPException(409)
                session.commit()
            except ResourceNotFound:
                raise HTTPException(404) from None
        return _with_auth_cookies(
            RedirectResponse(
                "/profile/" + quote(profile_id, safe="") + "/projects", status_code=303
            ),
            auth,
        )

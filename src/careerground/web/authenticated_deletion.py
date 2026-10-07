"""Opt-in local PROFILE erasure after fresh signed OIDC authentication.

Only the isolated authenticated development store may mount these routes. This
does not delete a provider account, assert upstream credential entry/MFA, expose
a production erasure API, or turn a browser cookie into an MCP approval receipt.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from threading import RLock

from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from careerground.domain.authorization import resolve_account_id
from careerground.domain.deletion_execution import apply_deletion_work, execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.providers.oidc_identity import (
    FRESH_AUTHENTICATION_MAX_AGE_SECONDS,
    REAUTHENTICATION_TRANSACTION_TTL_SECONDS,
)
from careerground.storage.models import Account, CareerProfile, DeletionWorkItem

REAUTH_COOKIE = "__Host-careerground-delete-reauth"
_ORDER = {
    "PROFILING_INPUT": 0,
    "PROFILING_PROTOCOL_STEP": 1,
    "PROFILING_DRAFT": 2,
    "PROFILING_REVIEW_ITEM": 3,
    "PROFILING_REVIEW_BATCH": 4,
    "PROFILING_SESSION": 5,
    "PROFILE_LOCAL_DATA": 6,
    "CAREER_PROFILE": 8,
}
_LABELS = {
    "CAREER_PROFILE": "경력 프로필",
    "PROFILING_SESSION": "경력 정리 세션",
    "PROFILING_INPUT": "임시 입력",
    "PROFILING_PROTOCOL_STEP": "질문 응답 단계",
    "PROFILING_DRAFT": "미승인 후보",
    "PROFILING_REVIEW_BATCH": "사실 검토 묶음",
    "PROFILING_REVIEW_ITEM": "사실 검토 항목",
    "BROWSER_OPERATION": "연결 승인 기록",
    "PROFILE_CHANGE_SET": "프로필 변경 기록",
    "PROFILE_ARCHIVE": "프로필 이전 버전",
    "CLAIM": "경력 사실",
    "EVIDENCE_SOURCE": "근거 출처",
    "EVIDENCE_ITEM": "근거 문구",
    "EVIDENCE_CLAIM_LINK": "근거 연결",
    "CLAIM_ASSESSMENT": "경력 사실 평가",
    "CLAIM_REVIEW": "사실 승인 기록",
    "CLAIM_BOUNDARY_REVIEW": "사용 경계 검토",
    "CLAIM_CONFLICT_REVIEW": "상충 내용 검토",
    "CLAIM_USE_REVIEW": "사용 가능 여부 검토",
    "CLAIM_CONSTRAINT": "사용 제한",
    "JOB_DESCRIPTION": "선택한 채용공고 내용",
    "JD_REQUIREMENT": "채용 요구사항",
    "REQUIREMENT_CLAIM_MAP": "요구사항과 근거 연결",
    "ARTIFACT": "이력서 초안",
    "ARTIFACT_UNIT": "이력서 문구",
    "ARTIFACT_WORDING_REVIEW": "문구 검토 기록",
    "ARTIFACT_CLAIM_LINK": "이력서 근거 연결",
    "PROJECT_SCOPE": "프로젝트 범위",
    "PRIVATE_OBJECT": "비공개 첨부 자료",
    "PRIVATE_OBJECT_VERSION": "첨부 자료의 이전 버전",
}


@dataclass(repr=False)
class _Pending:
    id: str
    account_id: str
    session_id: str
    profile_id: str
    version: int
    issued_at: datetime
    expires_at: datetime
    digest: str
    counts: tuple[tuple[str, int], ...]
    stage: str = "PREVIEW"
    authenticated_at: int | None = None
    passkey_challenge: bytes | None = None
    passkey_verified: bool = False


class AuthenticatedProfileDeletion:
    """Bounded, process-local approval, using an independent durable checkpoint."""

    def __init__(self, management, store):
        self.management, self.store = management, store
        # Allow review and interactive provider login, then shorten approval to
        # the verified authentication's remaining three-minute lifetime.
        self.previews = DeletionPreviewService(store.presentation_secret, ttl_seconds=900)
        self.pending: dict[str, _Pending] = {}
        self.lock = RLock()
        self.unavailable = False

    def _now(self):
        return datetime.fromtimestamp(self.management._clock(), UTC)

    def _prune(self):
        self.pending = {
            key: row for key, row in self.pending.items() if row.expires_at > self._now()
        }

    def _row(self, request_id, principal, *, stage):
        self._prune()
        row = self.pending.get(request_id)
        if (
            row is None
            or row.account_id != principal.account_id
            or row.session_id != principal.session_id
            or row.stage != stage
        ):
            raise HTTPException(409)
        return row

    def _unchanged(self, session, row):
        profile = session.get(CareerProfile, row.profile_id, populate_existing=True)
        view = self.previews.preview(
            session,
            account_id=row.account_id,
            scope=DeletionScope.PROFILE,
            target_id=row.profile_id,
            now=row.issued_at,
        )
        if (
            profile is None
            or profile.status != "ACTIVE"
            or profile.version != row.version
            or view.deletion_digest != row.digest
        ):
            raise HTTPException(409)

    def _token(self, row, purpose):
        return self.management._form_token(purpose=purpose, binding=row.id + ":" + row.session_id)

    def _check(self, token, row, purpose):
        self.management._check_token(token, purpose=purpose, binding=row.id + ":" + row.session_id)

    def _render(self, row, *, ready=False):
        from careerground.web.authenticated_management import _page

        body = "<p>현재 개발 프로필의 로컬 저장 자료만 삭제합니다. 기존 다른 시험 DB와 제공자 계정은 삭제하지 않습니다.</p>"
        body += f"<p>대상 프로필: {escape(row.profile_id)} · 버전: {row.version}</p><ul>"
        body += "".join(
            f"<li>{escape(_LABELS.get(kind, '기타 로컬 항목'))}: {count}개</li>"
            for kind, count in row.counts
        )
        body += "</ul><p>외부 사본·백업의 전체 삭제를 보증하지 않습니다.</p>"
        body += (
            "<p>최근 같은 계정 로그인과 등록된 패스키의 기기 확인을 모두 요구합니다. OTP MFA는 사용하지 않습니다.</p>"
            if self.management.deletion_passkeys is not None
            else "<p>서명된 인증 시각과 비밀번호 또는 MFA 인증 수단이 확인되지 않으면 삭제를 거부합니다. 소셜 제공자의 비밀번호 재입력까지 보장하지는 않습니다.</p>"
        )
        if ready:
            body += "<p>제공자가 서명한 이번 인증 교환 시각과 동일 계정을 확인했습니다. 아직 삭제하지 않았습니다.</p>"
            action, purpose = "execute", "development-delete-execute"
            control = "<label><input type='checkbox' name='confirm' value='erase_local_profile' required>위 프로필의 로컬 합성 자료 삭제를 최종 승인합니다.</label>"
            button = "로컬 프로필 삭제 실행"
        else:
            action, purpose = "reauth", "development-delete-reauth"
            control = "<label><input type='checkbox' name='confirm' value='reviewed_impact' required>표시한 삭제 범위와 영향을 확인했습니다.</label>"
            button = "같은 계정으로 다시 인증"
        body += (
            f"<form method='post' action='/deletion/development/{action}'>"
            f"<input type='hidden' name='request_id' value='{escape(row.id)}'>"
            f"<input type='hidden' name='token' value='{escape(self._token(row, purpose))}'>"
            f"{control}<button type='submit'>{button}</button></form>"
        )
        return _page("로컬 프로필 삭제 최종 확인" if ready else "로컬 프로필 삭제 영향", body)

    async def callback(self, request):
        from careerground.web.authenticated_management import _clear, _cookie, _page

        checks = {"freshness": False, "owner": False, "method": False}
        try:
            principal = await self.management.browser(request, Response())
            if principal is None:
                raise HTTPException(401)
            binding = _cookie(request, REAUTH_COOKIE)
            with self.lock:
                row = self._row(binding, principal, stage="AUTHENTICATING")
                # Failed/duplicate callbacks cannot retry this one-use transaction.
                row.stage = "VERIFYING"
            query = request.query_params
            if (
                not {"code", "state"} <= set(query) <= {"code", "state", "iss"}
                or any(len(query.getlist(key)) != 1 for key in query)
                or ("iss" in query and query["iss"] != self.management.login.settings.issuer)
            ):
                raise HTTPException(400)
            proof = await asyncio.to_thread(
                self.management.login.finish_reauthentication,
                state=query["state"],
                code=query["code"],
                browser_binding=binding,
            )
            checks["freshness"] = True
            with self.lock, self.management.sessions() as session:
                self._row(binding, principal, stage="VERIFYING")
                current = await self.management.browser(request, Response())
                if (
                    current != principal
                    or resolve_account_id(session, proof.identity) != row.account_id
                    or proof.authenticated_at < int(row.issued_at.timestamp())
                ):
                    raise HTTPException(409)
                checks["owner"] = True
                # Fresh social-provider exchange alone is insufficient. Never
                # infer credential entry or MFA from iat/auth_time or a checkbox.
                allowed_methods = (
                    {"mfa"} if self.management.require_deletion_mfa else {"pwd", "mfa"}
                )
                if self.management.deletion_passkeys is None and not allowed_methods.intersection(
                    proof.authentication_methods
                ):
                    row.stage = "REJECTED"
                    raise HTTPException(409)
                checks["method"] = self.management.deletion_passkeys is None
                self._unchanged(session, row)
                row.authenticated_at = proof.authenticated_at
                row.expires_at = min(
                    row.expires_at,
                    datetime.fromtimestamp(proof.authenticated_at, UTC)
                    + timedelta(seconds=FRESH_AUTHENTICATION_MAX_AGE_SECONDS),
                )
                row.stage = (
                    "PASSKEY_REQUIRED" if self.management.deletion_passkeys is not None else "READY"
                )
                if self.management.deletion_passkeys is not None:
                    from careerground.web.development_passkeys import ceremony_page

                    row.passkey_challenge = secrets.token_bytes(32)
                    options = self.management.deletion_passkeys.authentication_options(
                        row.account_id, row.passkey_challenge
                    )
                    result = ceremony_page(
                        self.management,
                        title="삭제 전 기기 확인",
                        body="<p>최근 로그인과 같은 계정을 확인했습니다. 등록된 패스키로 확인한 뒤 최종 삭제 승인 화면으로 이동합니다. 아직 삭제하지 않았습니다.</p>",
                        options=options,
                        action="/deletion/development/passkey",
                        request_id=row.id,
                        purpose="development-delete-passkey",
                        binding=row.id + ":" + row.session_id,
                        register=False,
                    )
                else:
                    result = RedirectResponse(
                        "/deletion/development/final/" + row.id, status_code=303
                    )
        except Exception:  # noqa: BLE001 - provider responses/codes never escape
            logging.getLogger(__name__).warning(
                "development_deletion_authentication rejected freshness=%s owner=%s method=%s",
                checks["freshness"],
                checks["owner"],
                checks["method"],
            )
            if checks["freshness"] and checks["owner"] and not checks["method"]:
                result = _page(
                    "삭제에 필요한 추가 인증을 확인할 수 없습니다",
                    "<p>최근 로그인과 동일 계정은 확인했습니다.</p>"
                    "<p>현재 로그인 연결에서 삭제에 필요한 추가 인증을 확인할 수 없어 자료를 보존했습니다.</p>"
                    "<p>추가 인증 설정을 확인한 뒤 삭제 검토를 다시 시작하세요. 현재 방식의 로그인을 반복할 필요는 없습니다.</p>"
                    "<p>삭제는 실행하지 않았습니다.</p>"
                    "<p><a href='/account'>관리 화면으로 돌아가기</a></p>",
                    status=409,
                )
            else:
                result = _page(
                    "삭제 재인증을 완료할 수 없습니다",
                    "<p>삭제는 실행하지 않았습니다. 관리 화면에서 새 검토를 시작하세요.</p>"
                    "<p><a href='/account'>관리 화면으로 돌아가기</a></p>",
                    status=409,
                )
        _clear(result, REAUTH_COOKIE)
        return result

    def mount(self):
        from careerground.web.authenticated_management import _form, _page

        app = self.management.web

        async def principal(request):
            identity = await self.management.browser(request, Response())
            if identity is None:
                raise HTTPException(401)
            return identity

        @app.get("/deletion/development/profile/{profile_id}", include_in_schema=False)
        async def preview(profile_id: str, request: Request):
            owner = await principal(request)
            try:
                with self.lock, self.management.sessions() as session:
                    self._prune()
                    if len(self.pending) >= 128:
                        raise HTTPException(429)
                    now = self._now()
                    view = self.previews.preview(
                        session,
                        account_id=owner.account_id,
                        scope=DeletionScope.PROFILE,
                        target_id=profile_id,
                        now=now,
                    )
                    profile = session.get(CareerProfile, profile_id)
                    row = _Pending(
                        secrets.token_urlsafe(32),
                        owner.account_id,
                        owner.session_id,
                        profile_id,
                        profile.version,
                        now,
                        view.expires_at,
                        view.deletion_digest,
                        tuple(sorted(Counter(x.kind for x in view.items).items())),
                    )
                    self.pending[row.id] = row
                    return self._render(row)
            except HTTPException:
                raise
            except Exception:  # noqa: BLE001 - no ownership/SQL disclosures
                raise HTTPException(404) from None

        @app.post("/deletion/development/reauth", include_in_schema=False)
        async def reauthenticate(request: Request):
            owner = await principal(request)
            fields = await _form(request)
            if await principal(request) != owner:
                raise HTTPException(401)
            if (
                set(fields) != {"request_id", "token", "confirm"}
                or fields["confirm"] != "reviewed_impact"
            ):
                raise HTTPException(400)
            with self.lock, self.management.sessions() as session:
                row = self._row(fields["request_id"], owner, stage="PREVIEW")
                self._check(fields["token"], row, "development-delete-reauth")
                try:
                    self._unchanged(session, row)
                    if (
                        self.management.deletion_passkeys is not None
                        and not self.management.deletion_passkeys.has_credential(row.account_id)
                    ):
                        return _page(
                            "삭제 확인용 패스키 등록이 필요합니다",
                            "<p>아직 삭제하지 않았습니다. 먼저 같은 계정에 패스키를 등록하세요.</p>"
                            "<a href='/security/development/passkey'>패스키 등록 검토</a>",
                            status=409,
                        )
                    url = self.management.login.begin_reauthentication(
                        row.id, require_mfa=self.management.require_deletion_mfa
                    )
                except Exception:  # noqa: BLE001
                    raise HTTPException(409) from None
                row.stage = "AUTHENTICATING"
            # form-action 'self' correctly blocks a form's external redirect in
            # Chromium. Finish the local POST, then use an explicit navigation
            # link; never weaken CSP or submit credentials through our form.
            response = _page(
                "제공자에서 다시 인증",
                "<p>표시된 삭제 영향만 확인했습니다. 아직 삭제하지 않았습니다.</p>"
                "<p>10분 안에 같은 제공자 계정으로 인증을 완료하세요. 인증 완료 후 3분 안에 최종 확인해야 합니다.</p>"
                f"<p><a href='{escape(url, quote=True)}'>인증 제공자에서 계속</a></p>",
            )
            response.set_cookie(
                REAUTH_COOKIE,
                row.id,
                max_age=REAUTHENTICATION_TRANSACTION_TTL_SECONDS,
                path="/",
                secure=True,
                httponly=True,
                samesite="lax",
            )
            response.headers["cache-control"] = "no-store"
            from careerground.web.authenticated_management import _clear
            from careerground.web.development_passkeys import PASSKEY_ENROLLMENT_COOKIE

            _clear(response, PASSKEY_ENROLLMENT_COOKIE)
            return response

        @app.get("/deletion/development/final/{request_id}", include_in_schema=False)
        async def final(request_id: str, request: Request):
            owner = await principal(request)
            with self.lock, self.management.sessions() as session:
                row = self._row(request_id, owner, stage="READY")
                try:
                    self._unchanged(session, row)
                except Exception:  # noqa: BLE001
                    raise HTTPException(409) from None
                return self._render(row, ready=True)

        @app.post("/deletion/development/passkey", include_in_schema=False)
        async def passkey(request: Request):
            owner = await principal(request)
            fields = await _form(request)
            if (
                self.management.deletion_passkeys is None
                or set(fields) != {"request_id", "token", "credential", "confirm"}
                or fields["confirm"] != "verified_device"
            ):
                raise HTTPException(400)
            with self.lock, self.management.sessions() as session:
                row = self._row(fields["request_id"], owner, stage="PASSKEY_REQUIRED")
                self._check(fields["token"], row, "development-delete-passkey")
                row.stage = "VERIFYING_PASSKEY"
                try:
                    if await principal(request) != owner:
                        raise HTTPException(401)
                    self._unchanged(session, row)
                    self.management.deletion_passkeys.verify(
                        row.account_id, row.passkey_challenge, fields["credential"]
                    )
                    row.passkey_verified = True
                    row.stage = "READY"
                except Exception:  # noqa: BLE001 - credential data never escape
                    row.stage = "REJECTED"
                    raise HTTPException(409) from None
            return RedirectResponse("/deletion/development/final/" + row.id, status_code=303)

        @app.post("/deletion/development/execute", include_in_schema=False)
        async def execute(request: Request):
            owner = await principal(request)
            fields = await _form(request)
            if await principal(request) != owner:
                raise HTTPException(401)
            if (
                set(fields) != {"request_id", "token", "confirm"}
                or fields["confirm"] != "erase_local_profile"
            ):
                raise HTTPException(400)
            with self.lock:
                row = self._row(fields["request_id"], owner, stage="READY")
                self._check(fields["token"], row, "development-delete-execute")
                row.stage = "CONSUMING"
                checkpoint_started = False
                try:
                    with self.management.sessions() as session:
                        session.execute(
                            update(Account)
                            .where(Account.id == row.account_id)
                            .values(status=Account.status)
                        )
                        self._unchanged(session, row)
                        if self.management.deletion_passkeys is not None and (
                            not row.passkey_verified
                            or not self.management.deletion_passkeys.has_credential(row.account_id)
                        ):
                            raise HTTPException(409)
                        if (
                            row.authenticated_at is None
                            or self._now().timestamp() - row.authenticated_at
                            > FRESH_AUTHENTICATION_MAX_AGE_SECONDS
                        ):
                            raise HTTPException(409)
                        approval = VerifiedDeletionApproval(
                            row.account_id, DeletionScope.PROFILE, row.profile_id, row.expires_at
                        )
                        deletion = execute_synthetic_deletion(
                            session,
                            preview_service=self.previews,
                            ledger_secret=self.store.ledger_secret,
                            account_id=row.account_id,
                            scope=DeletionScope.PROFILE,
                            target_id=row.profile_id,
                            deletion_digest=row.digest,
                            acknowledged_impact=True,
                            step_up=approval,
                            now=self._now(),
                        )
                        session.flush()
                        work = tuple(
                            session.scalars(
                                select(DeletionWorkItem).where(
                                    DeletionWorkItem.request_id == deletion.id,
                                    DeletionWorkItem.action == "ERASE",
                                )
                            )
                        )
                        for item in sorted(
                            work, key=lambda item: (_ORDER.get(item.kind, 20), item.target_id)
                        ):
                            apply_deletion_work(session, item.id)
                        session.flush()
                        checkpoint_started = True
                        self.store.before_deletion_commit(session)
                        session.commit()
                    row.stage = "DONE"
                except Exception:  # noqa: BLE001 - fail closed; checkpoint may require quarantine
                    row.stage = "REJECTED"
                    self.unavailable = checkpoint_started
                    raise HTTPException(409) from None
            result = _page(
                "로컬 프로필 삭제 처리 결과",
                "<p>선택한 개발 프로필의 알려진 로컬 자료 삭제를 처리했습니다.</p>"
                "<p>coverage: FOUNDATION_ONLY · 외부 사본·백업을 포함한 전체 삭제 완료는 아닙니다.</p>"
                "<p>MCP 삭제 승인 증명이나 제공자 계정 삭제를 발급·실행하지 않았습니다.</p>",
            )
            self.management.browser.revoke(request, result)
            return result

"""Explicit, opt-in deletion passkey enrollment after fresh same-owner OIDC.

Initial enrollment trusts the existing identity-provider account. No replacement
or recovery route is offered; losing the key leaves deletion blocked. This is an
isolated development proposal, never a public sign-in or model-facing endpoint.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from html import escape
from threading import RLock

from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from careerground.domain.authorization import resolve_account_id

PASSKEY_ENROLLMENT_COOKIE = "__Host-careerground-passkey-enrollment"


def _restart_registration():
    from careerground.web.authenticated_management import _page

    return _page(
        "패스키 등록 검토를 다시 시작하세요",
        "<p>화면의 유효시간이 지났거나 등록 상태가 바뀌었습니다. 이 요청으로 패스키를 저장하지 않았습니다.</p>"
        "<p>휴대전화와 Bluetooth를 먼저 준비한 뒤 새 검토 화면에서 진행하세요. 검토 화면은 3분 동안 유효합니다.</p>"
        "<a href='/security/development/passkey'>새 등록 검토 열기</a>",
        status=409,
    )


_SCRIPT = """'use strict';
const form = document.querySelector('form[data-passkey]');
const button = form.querySelector('button');
const status = document.getElementById('passkey-status');
const decode = value => Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/') + '='.repeat((4-value.length%4)%4)), c => c.charCodeAt(0));
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
button.addEventListener('click', async () => {
  if (!form.reportValidity()) return;
  button.disabled = true;
  try {
    const options = JSON.parse(form.dataset.options);
    options.challenge = decode(options.challenge);
    if (options.user) options.user.id = decode(options.user.id);
    for (const name of ['allowCredentials','excludeCredentials'])
      for (const item of options[name] || []) item.id = decode(item.id);
    const credential = await navigator.credentials[form.dataset.passkey]({publicKey: options});
    const response = {};
    for (const name of ['attestationObject','clientDataJSON','authenticatorData','signature','userHandle'])
      if (credential.response[name] != null) response[name] = encode(credential.response[name]);
    form.querySelector('[name=credential]').value = JSON.stringify({
      id: credential.id, rawId: encode(credential.rawId), type: credential.type,
      response, clientExtensionResults: credential.getClientExtensionResults()
    });
    form.submit();
  } catch (error) {
    status.textContent = '기기 인증을 완료하지 못했습니다. 등록·삭제는 실행하지 않았습니다.';
    button.disabled = false;
  }
});
"""


def ceremony_page(
    management, *, title, body, options, action, request_id, purpose, binding, register
):
    from careerground.web.authenticated_management import _page

    result = _page(
        title,
        body
        + f"<form method='post' action='{escape(action)}' data-passkey='{'create' if register else 'get'}'"
        + f" data-options='{escape(json.dumps(options), quote=True)}'>"
        + f"<input type='hidden' name='request_id' value='{escape(request_id)}'>"
        + f"<input type='hidden' name='token' value='{escape(management._form_token(purpose=purpose, binding=binding))}'>"
        + "<input type='hidden' name='credential' value=''>"
        + (
            "<label><input type='checkbox' name='confirm' value='register_device' required>"
            "이 기기의 패스키를 삭제 확인용으로 등록합니다</label>"
            if register
            else "<input type='hidden' name='confirm' value='verified_device'>"
        )
        + f"<button type='button'>{'패스키 등록' if register else '기기 패스키로 확인'}</button></form>"
        + "<p id='passkey-status' role='status'></p><p><a href='/account'>관리 화면으로 돌아가기</a></p>"
        + "<script src='/security/development/passkey.js' defer></script>",
    )
    result.headers["content-security-policy"] += "; script-src 'self'; object-src 'none'"
    return result


@dataclass(repr=False)
class _Enrollment:
    id: str
    account_id: str
    session_id: str
    issued_at: int
    expires_at: float
    stage: str = "AUTHENTICATING"
    challenge: bytes | None = None


class DevelopmentPasskeyEnrollment:
    def __init__(self, management, registry, *, allow_enrollment=False):
        self.management, self.registry = management, registry
        self.allow_enrollment = allow_enrollment
        self.pending = {}
        self.lock = RLock()

    def _row(self, request_id, owner, *, stage):
        row = self.pending.get(request_id)
        if (
            row is None
            or row.expires_at <= self.management._clock()
            or row.account_id != owner.account_id
            or row.session_id != owner.session_id
            or row.stage != stage
        ):
            raise HTTPException(409)
        return row

    async def callback(self, request):
        from careerground.web.authenticated_management import _clear, _cookie, _page

        try:
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            binding = _cookie(request, PASSKEY_ENROLLMENT_COOKIE)
            with self.lock:
                row = self._row(binding, owner, stage="AUTHENTICATING")
                row.stage = "VERIFYING"
            query = request.query_params
            if (
                not {"code", "state"} <= set(query) <= {"code", "state", "iss"}
                or any(len(query.getlist(k)) != 1 for k in query)
                or ("iss" in query and query["iss"] != self.management.login.settings.issuer)
            ):
                raise HTTPException(400)
            proof = await asyncio.to_thread(
                self.management.login.finish_reauthentication,
                state=query["state"],
                code=query["code"],
                browser_binding=binding,
            )
            with self.lock, self.management.sessions() as session:
                self._row(binding, owner, stage="VERIFYING")
                if (
                    not self.allow_enrollment
                    or await self.management.browser(request, Response()) != owner
                    or resolve_account_id(session, proof.identity) != row.account_id
                    or proof.authenticated_at < row.issued_at
                ):
                    raise HTTPException(409)
                row.challenge = secrets.token_bytes(32)
                row.expires_at = min(row.expires_at, proof.authenticated_at + 180)
                row.stage = "REGISTERING"
                options = self.registry.registration_options(row.account_id, row.challenge)
                result = ceremony_page(
                    self.management,
                    title="삭제 확인용 패스키 등록",
                    body="<p>최근 로그인과 같은 계정을 확인했습니다. 기기 PIN·생체 확인 후 공개키만 저장합니다.</p>"
                    "<p>로그인 확인 시점부터 3분 안에 기기 확인을 마치세요. 시간이 지나면 새 등록 검토를 시작해야 합니다.</p>"
                    "<p>현재 개발 경로에는 패스키 교체·분실 복구가 없습니다. 등록은 자료 삭제가 아닙니다.</p>",
                    options=options,
                    action="/security/development/passkey/register",
                    request_id=row.id,
                    purpose="development-passkey-register",
                    binding=row.id + ":" + row.session_id,
                    register=True,
                )
        except Exception:  # noqa: BLE001 - suppress provider/credential details
            result = _page(
                "패스키 등록을 시작할 수 없습니다",
                "<p>등록·삭제는 실행하지 않았습니다.</p><a href='/account'>관리 화면</a>",
                status=409,
            )
        _clear(result, PASSKEY_ENROLLMENT_COOKIE)
        return result

    def mount(self):
        from careerground.web.authenticated_management import _form, _page

        app = self.management.web

        @app.get("/security/development/passkey.js", include_in_schema=False)
        async def script():
            return Response(
                _SCRIPT,
                media_type="application/javascript",
                headers={"cache-control": "no-store", "x-content-type-options": "nosniff"},
            )

        @app.get("/security/development/passkey", include_in_schema=False)
        async def review(request: Request):
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            if self.registry.has_credential(owner.account_id):
                return _page(
                    "삭제 확인용 패스키",
                    "<p>패스키가 등록돼 있습니다. 삭제 검토에서 기기로 확인합니다.</p><a href='/account'>관리 화면</a>",
                )
            if not self.allow_enrollment:
                raise HTTPException(403)
            return _page(
                "삭제 확인용 패스키 등록 검토",
                "<p>이 계정에 기기 공개키 하나를 등록합니다. Auth0 MFA 설정·다른 계정 연결은 변경하지 않습니다.</p>"
                "<p>분실·교체 복구가 준비되지 않아 패스키를 잃으면 삭제가 차단됩니다. 일반 로그인은 유지됩니다.</p>"
                "<p>이 검토 화면은 3분 동안 유효합니다. 휴대전화·Bluetooth를 먼저 준비하고, 로그인에서 돌아온 뒤에도 3분 안에 기기 확인을 마치세요.</p>"
                "<form method='post' action='/security/development/passkey/reauth'>"
                f"<input type='hidden' name='token' value='{escape(self.management._form_token(purpose='development-passkey-enroll', binding=owner.session_id))}'>"
                "<label><input type='checkbox' name='confirm' value='reviewed_enrollment' required>등록 범위와 분실 시 제한을 확인했습니다</label>"
                "<button type='submit'>같은 계정으로 다시 인증</button></form>",
            )

        @app.post("/security/development/passkey/reauth", include_in_schema=False)
        async def start(request: Request):
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            fields = await _form(request)
            if not self.allow_enrollment:
                raise HTTPException(403)
            if set(fields) != {"token", "confirm"} or fields["confirm"] != "reviewed_enrollment":
                raise HTTPException(400)
            try:
                self.management._check_token(
                    fields["token"], purpose="development-passkey-enroll", binding=owner.session_id
                )
            except HTTPException as error:
                if error.status_code != 409:
                    raise
                return _restart_registration()
            if await self.management.browser(request, Response()) != owner:
                raise HTTPException(401)
            with self.lock:
                self.pending = {
                    k: r for k, r in self.pending.items() if r.expires_at > self.management._clock()
                }
                if len(self.pending) >= 128:
                    raise HTTPException(429)
                if self.registry.has_credential(owner.account_id):
                    raise HTTPException(409)
                row = _Enrollment(
                    secrets.token_urlsafe(32),
                    owner.account_id,
                    owner.session_id,
                    int(self.management._clock()),
                    self.management._clock() + 600,
                )
                url = self.management.login.begin_reauthentication(row.id)
                self.pending[row.id] = row
            result = _page(
                "패스키 등록 전 로그인 확인",
                f"<p>10분 안에 같은 계정으로 로그인하세요. 아직 등록하지 않았습니다.</p><a href='{escape(url, quote=True)}'>인증 제공자에서 계속</a>",
            )
            result.set_cookie(
                PASSKEY_ENROLLMENT_COOKIE,
                row.id,
                max_age=600,
                secure=True,
                httponly=True,
                samesite="lax",
                path="/",
            )
            from careerground.web.authenticated_deletion import REAUTH_COOKIE
            from careerground.web.authenticated_management import _clear

            _clear(result, REAUTH_COOKIE)
            return result

        @app.post("/security/development/passkey/register", include_in_schema=False)
        async def register(request: Request):
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            fields = await _form(request)
            if not self.allow_enrollment:
                raise HTTPException(403)
            if (
                set(fields) != {"request_id", "token", "credential", "confirm"}
                or fields["confirm"] != "register_device"
            ):
                raise HTTPException(400)
            with self.lock:
                try:
                    row = self._row(fields["request_id"], owner, stage="REGISTERING")
                    self.management._check_token(
                        fields["token"],
                        purpose="development-passkey-register",
                        binding=row.id + ":" + row.session_id,
                    )
                except HTTPException as error:
                    if error.status_code != 409:
                        raise
                    return _restart_registration()
                row.stage = "CONSUMED"
                try:
                    if await self.management.browser(request, Response()) != owner:
                        raise HTTPException(401)
                    self.registry.register(row.account_id, row.challenge, fields["credential"])
                except Exception:  # noqa: BLE001
                    raise HTTPException(409) from None
            return RedirectResponse("/security/development/passkey", status_code=303)

"""Explicit Auth0 development assembly; imports do not connect to a provider.

Identity verification and account admission are injected. Web cookies never
become MCP tokens: the resource server independently verifies each bearer JWT.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from threading import Lock
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from mcp.server.auth.provider import AccessToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from careerground.domain.account_initialization import initialize_account_profile
from careerground.domain.authorization import (
    AuthenticationRequired,
    VerifiedIdentity,
    resolve_account_id,
)
from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.domain.chatgpt_proposal_review import ChatGPTProposalInbox
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.providers.oidc_identity import IdentityLoginRejected, IdentityOnlyLogin
from careerground.storage.models import CareerProfile
from careerground.web.chatgpt_proposal_routes import attach_chatgpt_proposal_routes
from careerground.web.review_foundation import _html_response, build_synthetic_review_app
from careerground.web.verified_browser_sessions import VerifiedBrowserSessions

LOGIN_COOKIE = "__Host-careerground-login"
SETUP_COOKIE = "__Host-careerground-setup"
POLICY = "product-policy-v0.1"


@dataclass(frozen=True, repr=False)
class _PendingSetup:
    identity: VerifiedIdentity
    nonce: str
    expires_at: float


def _cookie(request: Request, name: str) -> str:
    occurrences = sum(
        value.count((name + "=").encode())
        for key, value in request.headers.raw
        if key.lower() == b"cookie"
    )
    value = request.cookies.get(name, "")
    return value if occurrences == 1 and 32 <= len(value) <= 128 else ""


def _clear(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/", secure=True, httponly=True, samesite="lax")


def _page(title: str, body: str, *, status: int = 200):
    return _html_response(
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><main><h1>{escape(title)}</h1>{body}</main></html>",
        status_code=status,
    )


async def _form(request: Request) -> dict[str, str]:
    if request.headers.get("content-type", "").split(";", 1)[0] != (
        "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            raise HTTPException(413)
    try:
        values = parse_qs(
            body.decode(), keep_blank_values=True, strict_parsing=True, max_num_fields=4
        )
    except (ValueError, UnicodeError):
        raise HTTPException(400) from None
    if any(len(value) != 1 for value in values.values()):
        raise HTTPException(400)
    return {key: value[0] for key, value in values.items()}


class AuthenticatedManagement:
    """One-process development Web/MCP assembly with revocable browser sessions."""

    def __init__(
        self,
        *,
        login: IdentityOnlyLogin,
        origin: str,
        session_factory: Callable[[], Session],
        account_admission: Callable[[VerifiedIdentity], str | None],
        review_secret: bytes,
        presentation_secret: bytes,
        mcp_settings: McpOAuthSettings,
        signing_key: Callable[[str], object] | None = None,
        deletion_store=None,
        require_deletion_mfa: bool = False,
        connection_is_revoked: Callable[[AccessToken], bool] | None = None,
        deletion_passkeys=None,
        allow_passkey_enrollment: bool = False,
        connection_registry=None,
        connection_client_id: str | None = None,
        clock=time.time,
    ):
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"})
            or login.settings.redirect_uri != origin + "/auth/callback"
            or login.settings.issuer != mcp_settings.issuer
        ):
            raise ValueError("Invalid authenticated management configuration")
        if deletion_store is not None and deletion_store.sessions is not session_factory:
            raise ValueError("Deletion checkpoint and management must share the same store")
        if type(require_deletion_mfa) is not bool or (
            require_deletion_mfa and deletion_store is None
        ):
            raise ValueError("MFA deletion policy requires the isolated deletion store")
        if type(allow_passkey_enrollment) is not bool or (
            allow_passkey_enrollment and deletion_passkeys is None
        ):
            raise ValueError("Passkey enrollment requires an explicitly supplied registry")
        if deletion_passkeys is not None and (
            deletion_store is None
            or require_deletion_mfa
            or deletion_passkeys.origin != origin
            or deletion_passkeys.binding["store"]
            != hashlib.sha256(
                deletion_store.admission_secret + deletion_store.binding_digest.encode()
            ).hexdigest()
        ):
            raise ValueError(
                "Passkeys require the same isolated store/origin and separate MFA mode"
            )
        self.origin, self.login, self.sessions = origin, login, session_factory
        self.require_deletion_mfa = require_deletion_mfa
        self.deletion_passkeys = deletion_passkeys
        self.passkeys = None
        self.connections = None
        if connection_registry is not None:
            if connection_is_revoked is not None:
                raise ValueError("Only one connection denial policy may be supplied")
            from careerground.web.development_connections import DevelopmentConnectionControls

            self.connections = DevelopmentConnectionControls(
                self, connection_registry, connection_client_id
            )
            connection_is_revoked = connection_registry.is_revoked
        elif connection_client_id is not None:
            raise ValueError("Connection client requires an explicit denial registry")
        self._admission, self._clock = account_admission, clock
        self._pending: dict[str, _PendingSetup] = {}
        self._lock = Lock()
        self.browser = VerifiedBrowserSessions(session_factory, clock=clock)
        self.forms = BrowserFormTokenCodec(presentation_secret)
        self.proposals = ChatGPTProposalInbox(
            session_factory, review_secret, presentation_secret, clock=clock
        )
        self.web = build_synthetic_review_app(
            session_factory=session_factory,
            authenticate_browser=self.browser,
            review_signing_secret=review_secret,
            presentation_signing_secret=presentation_secret,
        )
        self.web.title = "CareerGround authenticated development"
        self.mcp = build_product_foundation_app(
            mcp_settings,
            session_factory=session_factory,
            review_signing_secret=review_secret,
            presentation_signing_secret=presentation_secret,
            signing_key=signing_key,
            connection_is_revoked=connection_is_revoked,
            management_origin=origin,
            # First use requires the authenticated browser's explicit setup.
            enrollment_account_id=None,
            chatgpt_proposal_inbox=self.proposals,
        )
        self._routes()
        if self.connections is not None:
            self.connections.mount()
        attach_chatgpt_proposal_routes(self.web, inbox=self.proposals, authenticate=self.browser)
        self.deletion = None
        if deletion_store is not None:
            from careerground.web.authenticated_deletion import AuthenticatedProfileDeletion

            self.deletion = AuthenticatedProfileDeletion(self, deletion_store)
            self.deletion.mount()
        if deletion_passkeys is not None:
            from careerground.web.development_passkeys import DevelopmentPasskeyEnrollment

            self.passkeys = DevelopmentPasskeyEnrollment(
                self, deletion_passkeys, allow_enrollment=allow_passkey_enrollment
            )
            self.passkeys.mount()

    def _pending_get(self, request: Request, *, consume: bool = False):
        cookie = _cookie(request, SETUP_COOKIE)
        if not cookie:
            return None
        key = hashlib.sha256(cookie.encode()).hexdigest()
        with self._lock:
            row = self._pending.pop(key, None) if consume else self._pending.get(key)
            if row is None or row.expires_at <= self._clock():
                self._pending.pop(key, None)
                return None
            return row

    def _setup_issue(self, identity: VerifiedIdentity, response: Response):
        cookie = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock:
            self._pending = {key: row for key, row in self._pending.items() if row.expires_at > now}
            if len(self._pending) >= 128:
                raise IdentityLoginRejected
            self._pending[hashlib.sha256(cookie.encode()).hexdigest()] = _PendingSetup(
                identity, secrets.token_urlsafe(32), now + 180
            )
        response.set_cookie(
            SETUP_COOKIE, cookie, max_age=180, path="/", secure=True, httponly=True, samesite="lax"
        )

    def _active(self, identity):
        with self.sessions() as session:
            try:
                return resolve_account_id(session, identity)
            except AuthenticationRequired:
                return None

    def _initialize(self, identity):
        with self.sessions() as session:
            profile = initialize_account_profile(
                session, identity=identity, enrollment_account_id=self._admission(identity)
            )
            session.commit()
            return profile.account_id

    def _form_token(self, *, purpose: str, binding: str):
        return self.forms.sign(
            {"purpose": purpose, "binding": binding, "expires_at": int(self._clock()) + 180}
        )

    def _check_token(self, token, *, purpose, binding):
        try:
            payload = self.forms.verify(
                token, expected_keys=frozenset({"purpose", "binding", "expires_at"})
            )
            if (
                payload["purpose"] != purpose
                or type(payload["binding"]) is not str
                or not hmac.compare_digest(payload["binding"], binding)
                or type(payload["expires_at"]) is not int
                or payload["expires_at"] <= self._clock()
            ):
                raise BrowserFormTokenRejected
        except BrowserFormTokenRejected:
            raise HTTPException(409) from None

    def _routes(self):
        @self.web.middleware("http")
        async def web_origin(request, call_next):
            if self.deletion is not None and self.deletion.unavailable:
                return _page("저장 상태 확인이 필요합니다", "", status=503)
            if request.headers.get("host") != urlsplit(self.origin).netloc:
                return _page("허용되지 않은 주소입니다", "", status=403)
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin")
                native = origin == "null" and request.headers.get("sec-fetch-site") == "same-origin"
                if origin != self.origin and not native:
                    return _page("허용되지 않은 요청입니다", "", status=403)
            response = await call_next(request)
            if response.status_code == 401:
                return _page(
                    "로그인이 필요합니다",
                    "<p>로그인 상태와 계정 접근 권한을 확인할 수 없습니다.</p>"
                    "<p><a href='/auth/login'>CareerGround 로그인</a></p>",
                    status=401,
                )
            return response

        @self.web.get("/", include_in_schema=False)
        async def home(request: Request):
            if await self.browser(request, Response()) is not None:
                return RedirectResponse("/account", status_code=303)
            return _page(
                "CareerGround",
                "<p>ChatGPT에서 경력 대화를 진행하고 여기에서 자료를 확인·승인합니다.</p>"
                "<p><a href='/auth/login'>CareerGround 로그인</a></p>"
                "<p>현재는 개발 시험 화면입니다. 실제 경력 자료를 입력하지 마세요.</p>",
            )

        @self.web.get("/auth/login", include_in_schema=False)
        async def start_login():
            from careerground.web.authenticated_deletion import REAUTH_COOKIE
            from careerground.web.development_passkeys import PASSKEY_ENROLLMENT_COOKIE

            response = RedirectResponse("/", status_code=303)
            _clear(response, REAUTH_COOKIE)
            _clear(response, PASSKEY_ENROLLMENT_COOKIE)
            try:
                binding = secrets.token_urlsafe(32)
                response.headers["location"] = self.login.begin(binding)
                response.set_cookie(
                    LOGIN_COOKIE,
                    binding,
                    max_age=180,
                    path="/",
                    secure=True,
                    httponly=True,
                    samesite="lax",
                )
            except IdentityLoginRejected:
                return _page("로그인을 시작할 수 없습니다", "<a href='/'>다시 시작</a>", status=503)
            response.headers["cache-control"] = "no-store"
            return response

        @self.web.get("/auth/callback", include_in_schema=False)
        async def callback(request: Request):
            from careerground.web.authenticated_deletion import REAUTH_COOKIE
            from careerground.web.development_passkeys import PASSKEY_ENROLLMENT_COOKIE

            if self.passkeys is not None and PASSKEY_ENROLLMENT_COOKIE in request.cookies:
                return await self.passkeys.callback(request)
            if self.deletion is not None and REAUTH_COOKIE in request.cookies:
                return await self.deletion.callback(request)
            response = RedirectResponse("/account/setup", status_code=303)
            _clear(response, LOGIN_COOKIE)
            try:
                if (
                    not {"code", "state"} <= set(request.query_params)
                    or not set(request.query_params) <= {"code", "state", "iss"}
                    or (
                        "iss" in request.query_params
                        and request.query_params.getlist("iss") != [self.login.settings.issuer]
                    )
                    or any(len(request.query_params.getlist(key)) != 1 for key in ("code", "state"))
                ):
                    raise IdentityLoginRejected
                identity = await asyncio.to_thread(
                    self.login.finish,
                    state=request.query_params["state"],
                    code=request.query_params["code"],
                    browser_binding=_cookie(request, LOGIN_COOKIE),
                )
                self.browser.revoke(request, response)
                self._pending_get(request, consume=True)
                _clear(response, SETUP_COOKIE)
                if await asyncio.to_thread(self._active, identity) is not None:
                    await asyncio.to_thread(self.browser.issue, identity, response)
                    response.headers["location"] = "/account"
                else:
                    if self._admission(identity) is None:
                        raise IdentityLoginRejected
                    self._setup_issue(identity, response)
            except Exception:  # noqa: BLE001 - provider payloads/codes are private
                result = _page(
                    "로그인을 완료할 수 없습니다", "<a href='/'>다시 시작</a>", status=400
                )
                _clear(result, LOGIN_COOKIE)
                return result
            response.headers["cache-control"] = "no-store"
            return response

        @self.web.get("/account/setup", include_in_schema=False)
        async def setup(request: Request):
            row = self._pending_get(request)
            if row is None:
                raise HTTPException(401)
            token = self._form_token(purpose="setup", binding=row.nonce)
            return _page(
                "CareerGround 계정 시작",
                "<p>로그인이 확인되었습니다. 아직 경력 프로필을 만들지 않았습니다.</p>"
                "<p>3분 안에 확인해 주세요. 만료되면 시작 화면에서 다시 로그인하세요.</p>"
                "<p>ChatGPT 연결도 같은 로그인 제공자·계정을 선택해야 같은 자료를 확인합니다.</p>"
                f"<p>적용 정책: {POLICY}. 자료의 최종 반영에는 별도 확인·승인이 필요합니다.</p>"
                "<form method='post' action='/account/setup'>"
                f"<input type='hidden' name='token' value='{escape(token)}'>"
                f"<input type='hidden' name='policy_version' value='{POLICY}'>"
                "<label><input type='checkbox' name='confirm' value='reviewed' required>"
                "시험용 빈 프로필 생성을 요청합니다</label>"
                "<button type='submit'>프로필 만들기</button></form>",
            )

        @self.web.post("/account/setup", include_in_schema=False)
        async def complete_setup(request: Request):
            row = self._pending_get(request)
            if row is None:
                raise HTTPException(401)
            form = await _form(request)
            if set(form) != {"token", "policy_version", "confirm"} or (
                form["confirm"] != "reviewed" or form["policy_version"] != POLICY
            ):
                raise HTTPException(400)
            self._check_token(form["token"], purpose="setup", binding=row.nonce)
            if self._pending_get(request, consume=True) is not row:
                raise HTTPException(409)
            try:
                await asyncio.to_thread(self._initialize, row.identity)
                response = RedirectResponse("/account", status_code=303)
                await asyncio.to_thread(self.browser.issue, row.identity, response)
            except AuthenticationRequired:
                raise HTTPException(401) from None
            _clear(response, SETUP_COOKIE)
            response.headers["cache-control"] = "no-store"
            return response

        @self.web.get("/account", include_in_schema=False)
        async def account(request: Request):
            principal = await self.browser(request, Response())
            if principal is None:
                raise HTTPException(401)
            with self.sessions() as session:
                profile = session.scalar(
                    select(CareerProfile).where(
                        CareerProfile.account_id == principal.account_id,
                        CareerProfile.status == "ACTIVE",
                    )
                )
                if profile is None:
                    raise HTTPException(401)
                profile_id, version = profile.id, profile.version
            token = self._form_token(purpose="logout", binding=principal.session_id)
            return _page(
                "CareerGround 관리",
                "<p>CareerGround 계정으로 로그인했습니다.</p>"
                f"<p><a href='/profile/{escape(profile_id)}/{version}'>내 경력 자료 확인</a></p>"
                "<p><a href='/profiling/start'>경력 정리 시작</a></p>"
                "<p>ChatGPT에서 준비한 승인 링크도 이 로그인 상태에서 확인합니다.</p>"
                + (
                    f"<p><a href='/deletion/development/profile/{escape(profile_id)}'>"
                    "개발 프로필의 로컬 자료 삭제 검토</a></p>"
                    if self.deletion is not None
                    else ""
                )
                + (
                    "<p><a href='/security/development/passkey'>삭제 확인용 패스키</a></p>"
                    if self.passkeys is not None
                    else ""
                )
                + (
                    "<p><a href='/connections/development'>ChatGPT 연결 접근 차단 검토</a></p>"
                    if self.connections is not None
                    else ""
                )
                + "<form method='post' action='/auth/logout'>"
                f"<input type='hidden' name='token' value='{escape(token)}'>"
                "<button type='submit'>로그아웃</button></form>",
            )

        @self.web.post("/auth/logout", include_in_schema=False)
        async def logout(request: Request):
            from careerground.web.authenticated_deletion import REAUTH_COOKIE
            from careerground.web.development_passkeys import PASSKEY_ENROLLMENT_COOKIE

            principal = await self.browser(request, Response())
            if principal is None:
                raise HTTPException(401)
            form = await _form(request)
            if set(form) != {"token"}:
                raise HTTPException(400)
            self._check_token(form["token"], purpose="logout", binding=principal.session_id)
            url = (
                self.login.settings.issuer
                + "v2/logout?"
                + urlencode(
                    {
                        "client_id": self.login.settings.client_id,
                        "returnTo": self.origin,
                    }
                )
            )
            response = RedirectResponse(url, status_code=303)
            self.browser.revoke(request, response)
            self._pending_get(request, consume=True)
            _clear(response, SETUP_COOKIE)
            _clear(response, LOGIN_COOKIE)
            _clear(response, REAUTH_COOKIE)
            _clear(response, PASSKEY_ENROLLMENT_COOKIE)
            return response

        @self.web.get("/health/live", include_in_schema=False)
        async def live():
            return {"status": "live", "mode": "authenticated-development"}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.deletion is not None and self.deletion.unavailable:
            await _page(
                "저장 상태 확인이 필요합니다",
                "<p>삭제 저장 검증을 완료할 수 없어 접근을 중지했습니다.</p>",
                status=503,
            )(scope, receive, send)
            return
        if scope["type"] == "lifespan" or (
            scope["type"] == "http"
            and (
                scope.get("path") == "/mcp"
                or scope.get("path", "").startswith("/.well-known/oauth-protected-resource")
            )
        ):
            await self.mcp(scope, receive, send)
        else:
            await self.web(scope, receive, send)

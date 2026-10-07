"""First-party opt-in local denial; never revokes an Auth0 grant automatically."""

from html import escape

from fastapi import HTTPException, Request, Response
from sqlalchemy import select

from careerground.domain.authorization import VerifiedIdentity, resolve_account_id
from careerground.storage.models import AuthIdentity


class DevelopmentConnectionControls:
    def __init__(self, management, registry, client_id):
        if (
            registry.issuer != management.login.settings.issuer
            or type(client_id) is not str
            or not 1 <= len(client_id) <= 255
        ):
            raise ValueError("Explicit same-issuer development connection client required")
        self.management, self.registry, self.client_id = management, registry, client_id

    def _identity(self, owner):
        with self.management.sessions() as session:
            row = session.scalar(
                select(AuthIdentity).where(
                    AuthIdentity.account_id == owner.account_id,
                    AuthIdentity.issuer == self.registry.issuer,
                )
            )
            if row is None:
                raise HTTPException(401)
            identity = VerifiedIdentity(row.issuer, row.subject)
            if resolve_account_id(session, identity) != owner.account_id:
                raise HTTPException(401)
            return identity

    def mount(self):
        from careerground.web.authenticated_management import _form, _page

        app = self.management.web

        @app.get("/connections/development", include_in_schema=False)
        async def review(request: Request):
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            # Reading the signed registry here also fails closed on corruption.
            identity = self._identity(owner)
            try:
                blocked = self.registry.is_blocked(identity, self.client_id)
            except Exception:  # noqa: BLE001 - signed registry failures are private
                raise HTTPException(503) from None
            body = (
                "<p>이 계정의 CareerGround 개발 ChatGPT 연결에 대한 서버 접근을 차단합니다.</p>"
                "<p>같은 client를 사용하는 Dev OAuth PoC와 Phase A Dev 두 연결 모두 영향을 받습니다.</p>"
                "<p>Web 로그인·경력 자료는 유지됩니다. Auth0 grant 자체나 이미 진행 중인 요청을 취소하지 않습니다.</p>"
                "<p>새 토큰·서버 재시작으로 풀리지 않습니다. 현재 관리 화면에는 차단 해제 기능이 없습니다.</p>"
            )
            if blocked:
                return _page(
                    "ChatGPT 연결 접근 차단",
                    body + "<p>현재 차단돼 있습니다.</p><a href='/account'>관리 화면</a>",
                )
            token = self.management._form_token(
                purpose="development-connection-block", binding=owner.session_id
            )
            return _page(
                "ChatGPT 연결 접근 차단 검토",
                body
                + "<form method='post' action='/connections/development/block'>"
                + f"<input type='hidden' name='token' value='{escape(token)}'>"
                + "<label><input type='checkbox' name='confirm' value='block_shared_client' required>이 계정의 두 개발 연결 차단과 해제 제한을 확인했습니다</label>"
                + "<button type='submit'>두 개발 연결의 접근 차단</button></form><a href='/account'>관리 화면</a>",
            )

        @app.post("/connections/development/block", include_in_schema=False)
        async def block(request: Request):
            owner = await self.management.browser(request, Response())
            if owner is None:
                raise HTTPException(401)
            fields = await _form(request)
            if set(fields) != {"token", "confirm"} or fields["confirm"] != "block_shared_client":
                raise HTTPException(400)
            self.management._check_token(
                fields["token"], purpose="development-connection-block", binding=owner.session_id
            )
            if await self.management.browser(request, Response()) != owner:
                raise HTTPException(401)
            try:
                self.registry.block(self._identity(owner), self.client_id)
            except Exception:  # noqa: BLE001 - no private account/storage details
                raise HTTPException(503) from None
            return _page(
                "ChatGPT 연결 접근 차단",
                "<p>이 계정의 두 개발 연결에 대한 다음 요청부터 차단했습니다. Web 자료는 삭제하지 않았습니다.</p><a href='/account'>관리 화면</a>",
            )

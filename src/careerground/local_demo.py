"""Disposable loopback demo. No public entrypoint, provider or configured DB use."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import secrets
import socket
import tempfile
import time
from html import escape
from pathlib import Path
from urllib.parse import parse_qs

import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from starlette.responses import Response

from careerground.domain.browser_form_token import BrowserFormTokenCodec, BrowserFormTokenRejected
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.storage.models import Account, AuthIdentity, Base, CareerProfile
from careerground.web.review_foundation import (
    TrustedBrowserIdentity,
    _html_response,
    build_synthetic_review_app,
)

ISSUER = "https://auth.local-demo.synthetic.example/"
RESOURCE = "https://mcp.local-demo.synthetic.example/mcp"
SCOPES = "career.profile.read career.profile.write career.artifact.read career.artifact.write career.export career.delete"
COOKIE = "cg_local_demo"
ACCOUNTS = {"a": ("demo-account-a", "demo-profile-a"), "b": ("demo-account-b", "demo-profile-b")}


async def bounded_form(request, *, limit=16384, fields=8):
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413)
    try:
        parsed = parse_qs(
            body.decode(), keep_blank_values=True, strict_parsing=True, max_num_fields=fields
        )
    except (ValueError, UnicodeError):
        raise HTTPException(400) from None
    if any(len(values) != 1 for values in parsed.values()):
        raise HTTPException(400)
    return {key: values[0] for key, values in parsed.items()}


def demo_page(title, body):
    return _html_response(
        f"<!doctype html><html lang='ko'><meta charset='utf-8'><title>{escape(title)}</title><main><h1>{escape(title)}</h1>{body}</main></html>"
    )


class LocalDemo:
    """Two synthetic accounts, in-memory keys and owner-only temporary SQLite."""

    def __init__(self, port=8008):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid local port")
        self.port = port
        self.origin = f"http://127.0.0.1:{port}"
        self.closed = False
        self.folder = tempfile.TemporaryDirectory(prefix="careerground-local-demo-")
        self.database_path = Path(self.folder.name) / "synthetic.sqlite"
        self.database_path.touch(mode=0o600)
        self.engine = create_engine(
            "sqlite+pysqlite:///" + str(self.database_path), hide_parameters=True
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.review_secret = secrets.token_bytes(32)
        self.presentation_secret = secrets.token_bytes(32)
        self.tokens = BrowserFormTokenCodec(self.presentation_secret)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.browsers = {}
        with self.sessions() as session:
            for label, (account, profile) in ACCOUNTS.items():
                session.add(Account(id=account))
                session.flush()
                session.add(
                    AuthIdentity(
                        id="demo-identity-" + label,
                        account_id=account,
                        issuer=ISSUER,
                        subject="demo-subject-" + label,
                    )
                )
                session.add(CareerProfile(id=profile, account_id=account, version=0))
            session.commit()
        self.web = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=self.authenticate,
            review_signing_secret=self.review_secret,
            presentation_signing_secret=self.presentation_secret,
        )
        self.mcp = build_product_foundation_app(
            McpOAuthSettings(ISSUER, RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=self.review_secret,
            presentation_signing_secret=self.presentation_secret,
            signing_key=lambda _token: self.key.public_key(),
        )
        self._register_routes()
        from careerground.web.local_demo_deletion import register_mock_deletion_routes
        from careerground.web.local_demo_jd import register_mock_jd_routes

        register_mock_jd_routes(self)
        register_mock_deletion_routes(self)

        @self.web.middleware("http")
        async def demo_navigation(request, call_next):
            response = await call_next(request)
            if "text/html" not in response.headers.get("content-type", ""):
                return response
            content = b"".join([part async for part in response.body_iterator]).decode("utf-8")
            nav = "<p><strong>로컬 합성 체험 · 실제 개인정보 입력 금지</strong></p><nav aria-label='로컬 체험 탐색'><a href='/demo'>체험 홈·계정 선택</a> · <a href='/profiling/start'>경력 정리</a> · <a href='/jd'>JD</a> · <a href='/demo/jd-analysis'>JD 모의 분석</a> · <a href='/resume'>R1</a> · <a href='/demo/mcp'>MCP 시험</a> · <a href='/demo/deletion'>합성 삭제</a></nav>"
            state = self.browsers.get(request.cookies.get(COOKIE, ""))
            if state and state.get("deletion_capability"):
                nav += "<p><a href='/demo/deletion/status'>합성 삭제 상태 조회</a></p>"
            content = re.sub(
                r"(<main\b[^>]*>)", lambda match: match.group(1) + nav, content, count=1
            ).encode()
            result = Response(content, status_code=response.status_code)
            result.raw_headers = [
                (name, value)
                for name, value in response.raw_headers
                if name.lower() != b"content-length"
            ] + [(b"content-length", str(len(content)).encode())]
            return result

    def browser(self, request, *, active=True):
        state = self.browsers.get(request.cookies.get(COOKIE, ""))
        if state is None:
            raise HTTPException(401)
        if active:
            with self.sessions() as session:
                account = session.get(Account, state["account_id"])
                if account is None or account.status != "ACTIVE":
                    raise HTTPException(401)
        return state

    def authenticate(self, request, _response):
        try:
            state = self.browser(request)
        except HTTPException:
            return None
        return TrustedBrowserIdentity(state["account_id"], state["session_id"])

    def form_token(self, purpose, state=None):
        return self.tokens.sign(
            {
                "purpose": purpose,
                "session_id": state["session_id"] if state else "SELECT_SYNTHETIC_ACCOUNT",
                "expires_at": int(time.time()) + 300,
            }
        )

    def verify_form(self, value, purpose, state=None):
        try:
            payload = self.tokens.verify(
                value, expected_keys=frozenset({"purpose", "session_id", "expires_at"})
            )
        except BrowserFormTokenRejected:
            raise HTTPException(409) from None
        if (
            payload["purpose"] != purpose
            or payload["session_id"]
            != (state["session_id"] if state else "SELECT_SYNTHETIC_ACCOUNT")
            or type(payload["expires_at"]) is not int
            or payload["expires_at"] <= time.time()
        ):
            raise HTTPException(409)

    def _access_token(self, state):
        now = int(time.time())
        if state.get("access_expiry", 0) <= now:
            state["access_expiry"] = now + 300
            state["access_token"] = jwt.encode(
                {
                    "iss": ISSUER,
                    "aud": RESOURCE,
                    "sub": "demo-subject-" + state["label"],
                    "azp": "local-demo-" + state["session_id"],
                    "scope": SCOPES,
                    "iat": now,
                    "exp": now + 300,
                    "jti": secrets.token_urlsafe(16),
                },
                self.key,
                algorithm="RS256",
                headers={"kid": "ephemeral-local-demo"},
            )
        return state["access_token"]

    async def rpc(self, state, method, params):
        """Call the real authenticated MCP ASGI app without an external HTTP client."""
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, ensure_ascii=False
        ).encode()
        headers = [
            (b"host", f"127.0.0.1:{self.port}".encode()),
            (b"authorization", ("Bearer " + self._access_token(state)).encode()),
            (b"content-type", b"application/json"),
            (b"accept", b"application/json, text/event-stream"),
            (b"content-length", str(len(body)).encode()),
        ]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "server": ("127.0.0.1", self.port),
            "client": ("127.0.0.1", 0),
        }
        sent = False
        done = asyncio.Event()
        parts = []
        status = 500

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await done.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    done.set()

        await self.mcp(scope, receive, send)
        try:
            return status, json.loads(b"".join(parts))
        except (ValueError, UnicodeError):
            raise HTTPException(503) from None

    def _register_routes(self):
        @self.web.get("/")
        @self.web.get("/demo")
        async def home(request: Request):
            token = self.form_token("DEMO_SELECT")
            body = "<p>실제 경력·계정 정보는 입력하지 마세요. 종료하면 이 체험의 입력과 임시 계정이 사라집니다.</p>"
            state = self.browsers.get(request.cookies.get(COOKIE, ""))
            if state:
                body += f"<p>선택된 합성 계정: {escape(state['label'].upper())}</p><p><a href='/profiling/start'>경력 정리 시작</a> · <a href='/jd'>JD 목록</a> · <a href='/demo/jd-analysis'>JD 모의 분석</a> · <a href='/resume'>R1 목록</a> · <a href='/demo/mcp'>합성 MCP 연결 시험</a> · <a href='/demo/deletion'>합성 삭제 체험</a></p>"
            body += f"<form method='post' action='/demo/account'><input type='hidden' name='form_token' value='{escape(token, quote=True)}'><label for='account'>체험할 합성 계정</label><select id='account' name='account' required><option value='' selected>직접 선택</option><option value='a'>합성 계정 A</option><option value='b'>합성 계정 B</option></select><button type='submit'>합성 계정으로 시작</button></form>"
            return demo_page("CareerGround 로컬 체험", body)

        @self.web.post("/demo/account")
        async def choose_account(request: Request):
            fields = await bounded_form(request)
            if set(fields) != {"account", "form_token"} or fields["account"] not in ACCOUNTS:
                raise HTTPException(400)
            self.verify_form(fields["form_token"], "DEMO_SELECT")
            label = fields["account"]
            with self.sessions() as session:
                if session.get(Account, ACCOUNTS[label][0]).status != "ACTIVE":
                    raise HTTPException(409)
            self.browsers.pop(request.cookies.get(COOKIE, ""), None)
            # This disposable process serves bounded local sessions only.
            if len(self.browsers) >= 128:
                raise HTTPException(429)
            cookie = secrets.token_urlsafe(32)
            self.browsers[cookie] = {
                "label": label,
                "account_id": ACCOUNTS[label][0],
                "profile_id": ACCOUNTS[label][1],
                "session_id": secrets.token_urlsafe(32),
            }
            response = RedirectResponse("/demo", status_code=303)
            response.set_cookie(COOKIE, cookie, httponly=True, samesite="strict", path="/")
            response.headers["cache-control"] = "no-store"
            return response

        async def console(request, result=None):
            state = self.browser(request)
            _, listing = await self.rpc(state, "tools/list", {})
            tools = listing.get("result", {}).get("tools", [])
            options = "".join(
                f"<option value='{escape(item['name'], quote=True)}'>{escape(item['name'])}</option>"
                for item in tools
            )
            body = "<p>합성 연결 앱의 도구 호출을 시험합니다. 모델이 승인하지 않습니다. 확인 경로를 열어 직접 승인한 뒤 완료 증명을 제출하세요. 인증 토큰은 화면에 표시하지 않습니다.</p>"
            body += f"<form method='post' action='/demo/mcp'><input type='hidden' name='form_token' value='{escape(self.form_token('DEMO_MCP', state), quote=True)}'><label for='tool'>시험할 도구</label><select id='tool' name='tool' required>{options}</select><label for='arguments'>도구 인자 JSON (합성 값만)</label><textarea id='arguments' name='arguments' required>{{}}</textarea><button type='submit'>합성 도구 호출</button></form>"
            if result is not None:
                body += (
                    "<h2>도구 응답</h2><pre id='mcp-result'>"
                    + escape(json.dumps(result, ensure_ascii=False, indent=2))
                    + "</pre>"
                )
                path = (
                    result.get("result", {})
                    .get("structuredContent", {})
                    .get("data", {})
                    .get("confirmation_path", "")
                )
                if re.fullmatch(r"/mcp/confirm/[0-9a-f-]{36}", path):
                    body += f"<p><a href='{path}'>정확한 내용을 직접 확인하고 승인</a></p>"
            return demo_page("합성 MCP 연결 시험", body)

        @self.web.get("/demo/mcp")
        async def show_console(request: Request):
            return await console(request)

        @self.web.post("/demo/mcp")
        async def call_console(request: Request):
            state = self.browser(request)
            fields = await bounded_form(request, limit=65536)
            if set(fields) != {"tool", "arguments", "form_token"}:
                raise HTTPException(400)
            self.verify_form(fields["form_token"], "DEMO_MCP", state)
            try:
                arguments = json.loads(fields["arguments"])
            except ValueError:
                raise HTTPException(400) from None
            if type(arguments) is not dict:
                raise HTTPException(400)
            _, result = await self.rpc(
                state, "tools/call", {"name": fields["tool"], "arguments": arguments}
            )
            return await console(request, result)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.mcp(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        headers = dict(scope.get("headers", []))
        expected = f"127.0.0.1:{self.port}".encode()
        # no-referrer makes native browser form POSTs send a null Origin.
        # Permit it only with the browser-controlled same-origin fetch marker;
        # foreign or opaque-origin documents still fail before form processing.
        origin = headers.get(b"origin")
        native_same_origin = origin == b"null" and headers.get(b"sec-fetch-site") == b"same-origin"
        if (
            self.closed
            or scope.get("client", ("", 0))[0] not in {"127.0.0.1", "::1"}
            or headers.get(b"host") != expected
            or (origin not in {None, self.origin.encode()} and not native_same_origin)
            or headers.get(b"sec-fetch-site") not in {None, b"same-origin", b"none"}
        ):
            response = demo_page(
                "체험 요청을 확인해 주세요", "<p>로컬 체험 주소에서 다시 시작해 주세요.</p>"
            )
            response.status_code = 403
            await response(scope, receive, send)
            return
        if scope["path"] == "/mcp" or scope["path"].startswith("/.well-known/"):
            await self.mcp(scope, receive, send)
        else:
            await self.web(scope, receive, send)

    def close(self):
        self.closed = True
        self.browsers.clear()
        self.key = None
        self.tokens = None
        self.review_secret = None
        self.presentation_secret = None
        self.web = None
        self.mcp = None
        self.engine.dispose()
        self.folder.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def main():
    parser = argparse.ArgumentParser(
        description="Disposable synthetic CareerGround on 127.0.0.1 only"
    )
    parser.add_argument("--port", type=int, default=8008)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0..65535")
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", args.port))
        with LocalDemo(sock.getsockname()[1]) as demo:

            class ReadyServer(uvicorn.Server):
                async def startup(self, sockets=None):
                    await super().startup(sockets=sockets)
                    if self.started:
                        print(
                            f"합성 데이터 전용 체험: {demo.origin}/demo (종료: Ctrl+C)", flush=True
                        )

            server = ReadyServer(
                uvicorn.Config(demo, log_level="warning", access_log=False, proxy_headers=False)
            )
            server.run(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    main()

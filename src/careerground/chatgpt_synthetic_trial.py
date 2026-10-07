"""Disposable ChatGPT tool-selection trial over a private development tunnel.

The tunnel endpoint intentionally uses one server-assigned SYNTHETIC identity.
It does not verify a ChatGPT user's identity or test production OAuth. The real
product MCP behind it still checks its minted synthetic JWT, scope and account.
Never use this adapter for real data or expose it through a public forwarder.
"""

from __future__ import annotations

import argparse
import json
import secrets
import socket
from html import escape
from uuid import uuid4

import uvicorn
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from starlette.responses import JSONResponse, Response

from careerground.local_demo import COOKIE, ISSUER, RESOURCE, LocalDemo, bounded_form, demo_page
from careerground.mcp.local_ingress import MAX_MCP_BODY_BYTES
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import build_product_foundation_app
from careerground.storage.models import CareerProfile


class SyntheticChatGPTTrial(LocalDemo):
    """A fresh isolated dataset, enrollment ID and fixed trial connection."""

    def __init__(self, port=8044):
        super().__init__(port)
        self.trial_account_id = str(uuid4())
        self.trial_state = {
            "label": "chatgpt-trial",
            "account_id": self.trial_account_id,
            "session_id": secrets.token_urlsafe(32),
        }
        self.mcp = build_product_foundation_app(
            McpOAuthSettings(ISSUER, RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=self.review_secret,
            presentation_signing_secret=self.presentation_secret,
            signing_key=lambda _token: self.key.public_key(),
            token_is_revoked=self.token_is_revoked,
            enrollment_account_id=lambda identity: (
                self.trial_account_id
                if identity.issuer == ISSUER and identity.subject == "demo-subject-chatgpt-trial"
                else None
            ),
            management_origin=self.origin,
        )
        self._register_trial_routes()

    def _register_trial_routes(self):
        @self.web.post("/chatgpt/mcp")
        async def trial_mcp(request: Request):
            if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                raise HTTPException(415)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_MCP_BODY_BYTES:
                    raise HTTPException(413)
            try:
                message = json.loads(body)
            except (ValueError, UnicodeError):
                raise HTTPException(400) from None
            if (
                type(message) is not dict
                or message.get("jsonrpc") != "2.0"
                or set(message) - {"jsonrpc", "id", "method", "params"}
                or type(message.get("params", {})) is not dict
            ):
                raise HTTPException(400)
            method = message.get("method")
            if (
                method in {"notifications/initialized", "notifications/cancelled"}
                and "id" not in message
            ):
                return Response(status_code=202)
            if type(message.get("id")) not in {str, int}:
                raise HTTPException(400)
            if method not in {
                "initialize",
                "ping",
                "tools/list",
                "tools/call",
                "resources/list",
                "resources/read",
                "resources/templates/list",
                "prompts/list",
            }:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {"code": -32601, "message": "Unsupported trial method"},
                    }
                )
            status, result = await self.rpc(self.trial_state, method, message.get("params", {}))
            if status != 200 or type(result) is not dict:
                raise HTTPException(503)
            result["id"] = message["id"]
            if method == "initialize" and "result" in result:
                result["result"]["serverInfo"]["name"] = "careerground-synthetic-chatgpt-trial"
                result["result"]["instructions"] = (
                    "SYNTHETIC TRIAL ONLY; the private tunnel uses one synthetic account, "
                    "not your real identity. Use get_my_profile, then initialize_career_profile "
                    "only on explicit first-use request. Store only synthetic user input; "
                    "propose_profiling_drafts takes exact Python character ranges. Prepare "
                    "FACT_REVIEW and open confirmation_url; wait for the management browser. "
                    "When the user returns, get_confirmation_status once, then submit the "
                    "receipt on this connection. No chat approval, real data, or production deletion."
                )
            if method == "tools/list" and "result" in result:
                for tool in result["result"]["tools"]:
                    tool["securitySchemes"] = [{"type": "noauth"}]
                    tool.setdefault("_meta", {})["securitySchemes"] = [{"type": "noauth"}]
                    tool["description"] = "SYNTHETIC PRIVATE TRIAL: " + tool.get("description", "")
            return JSONResponse(result, headers={"cache-control": "no-store"})

        @self.web.get("/chatgpt")
        async def trial_browser(request: Request):
            with self.sessions() as session:
                profile = session.scalar(
                    select(CareerProfile).where(
                        CareerProfile.account_id == self.trial_account_id,
                        CareerProfile.status == "ACTIVE",
                    )
                )
                if profile is None:
                    return demo_page(
                        "ChatGPT 합성 시험",
                        "<p>ChatGPT에서 명시적으로 시작을 요청하고 프로필을 초기화한 뒤 이 화면을 여세요.</p>",
                    )
                profile_id = profile.id
            token = self.form_token("TRIAL_BROWSER")
            return demo_page(
                "ChatGPT 합성 시험 계정 선택",
                "<p>이 일회용 시험에서 ChatGPT에 할당된 합성 계정으로 관리 화면을 엽니다. 실제 사용자 로그인 검증이 아닙니다.</p>"
                + f"<form method='post' action='/chatgpt/account'><input type='hidden' name='form_token' value='{escape(token, quote=True)}'>"
                + "<button type='submit'>ChatGPT 시험 계정으로 관리 화면 열기</button></form>"
                + f"<p>합성 프로필: {escape(profile_id)}</p>",
            )

        @self.web.post("/chatgpt/account")
        async def select_trial_account(request: Request):
            fields = await bounded_form(request)
            if set(fields) != {"form_token"}:
                raise HTTPException(400)
            self.verify_form(fields["form_token"], "TRIAL_BROWSER")
            with self.sessions() as session:
                profile = session.scalar(
                    select(CareerProfile).where(
                        CareerProfile.account_id == self.trial_account_id,
                        CareerProfile.status == "ACTIVE",
                    )
                )
                if profile is None:
                    raise HTTPException(409)
                profile_id = profile.id
            if len(self.browsers) >= 128:
                raise HTTPException(429)
            self.revoke_browser(request.cookies.get(COOKIE, ""))
            cookie = secrets.token_urlsafe(32)
            self.browsers[cookie] = {
                "label": self.trial_state["label"],
                "account_id": self.trial_account_id,
                "profile_id": profile_id,
                "session_id": secrets.token_urlsafe(32),
            }
            response = RedirectResponse("/profiling/start", status_code=303)
            response.set_cookie(COOKIE, cookie, httponly=True, samesite="strict", path="/")
            response.headers["cache-control"] = "no-store"
            return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8044)
    parser.add_argument("--allow-synthetic-chatgpt-tunnel", action="store_true", required=True)
    args = parser.parse_args()
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", args.port))
    with SyntheticChatGPTTrial(args.port) as trial:
        uvicorn.run(trial, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()

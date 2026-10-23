"""Local native API with explicitly separate synthetic and OIDC authentication."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .session import (
    MAX_ATTACHMENT,
    MAX_ENVELOPE,
    MAX_JSON,
    MAX_SESSION,
    Rejected,
    Sessions,
    decode,
    exact,
    parse,
)


def create_app(*, credentials: dict[str, str] | None = None, oidc_verifier=None, sessions=None):
    if (credentials is None) == (oidc_verifier is None):
        raise ValueError("Choose exactly one authentication mode")
    if credentials is not None and (
        not credentials or any(not token or not owner for token, owner in credentials.items())
    ):
        raise ValueError("Explicit development credentials required")
    auth_mode = "oidc" if oidc_verifier is not None else "synthetic_dev"
    store = sessions if sessions is not None else Sessions(auth_mode=auth_mode)
    if store.auth_mode != auth_mode:
        raise ValueError("Session store authentication mode must match API mode")
    revoked: dict[str, int] = {}

    @asynccontextmanager
    async def lifespan(app):
        async def purge():
            while True:
                await asyncio.sleep(15)
                store._purge()

        task = asyncio.create_task(purge())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            store._items.clear()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def boundary(request, call_next):
        def failure(code, status):
            return JSONResponse(
                {"errors": [code]}, status_code=status, headers={"Cache-Control": "no-store"}
            )

        # Browser cross-origin calls are not part of the native local interface.
        if request.headers.get("origin") is not None:
            return failure("ORIGIN_FORBIDDEN", 403)
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return failure("UNAUTHENTICATED", 401)
        if oidc_verifier is not None:
            try:
                principal = await asyncio.to_thread(oidc_verifier.verify, supplied)
            except Rejected as error:
                return failure(error.codes[0], error.status)
            now = time.time()
            for key in list(revoked):
                if revoked[key] <= now:
                    del revoked[key]
            digest = hashlib.sha256(supplied.encode()).hexdigest()
            if digest in revoked:
                return failure("UNAUTHENTICATED", 401)
            owner = principal.owner_binding
            request.state.token_digest = digest
            request.state.expires_at = principal.expires_at
        else:
            owner = next(
                (
                    v
                    for k, v in credentials.items()
                    if secrets.compare_digest(supplied.encode("utf-8"), k.encode("utf-8"))
                ),
                None,
            )
        if owner is None:
            return failure("UNAUTHENTICATED", 401)
        request.state.owner = owner
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Rejected)
    async def rejected(request, error):
        return JSONResponse({"errors": error.codes}, status_code=error.status)

    async def body(request):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise Rejected("CONTENT_TYPE", status=415)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_ENVELOPE:
                raise Rejected("SIZE_LIMIT", status=413)
        return parse(bytes(raw), MAX_ENVELOPE)

    def attachments(data):
        if not isinstance(data, dict) or len(data) > 500:
            raise Rejected("REQUEST_SCHEMA")
        return {name: decode(value, MAX_ATTACHMENT) for name, value in data.items()}

    @app.get("/v1/status")
    async def status(request: Request):
        return {
            "auth_mode": "oidc" if oidc_verifier is not None else "synthetic_dev",
            "owner": request.state.owner,
            "ai_status": ("AVAILABLE_ACTUAL" if store.provider.actual else "MOCK_ONLY")
            if hasattr(store, "provider")
            else "NOT_IMPLEMENTED",
            "step": "03" if hasattr(store, "provider") else "02",
            "autosave": False,
            "expires_at": getattr(request.state, "expires_at", None),
        }

    @app.post("/v1/import")
    async def import_handoff(request: Request):
        data = await body(request)
        exact(data, {"handoff_base64", "attachments"})
        return store.create(
            request.state.owner,
            decode(data["handoff_base64"], MAX_JSON),
            attachments(data["attachments"]),
        )

    @app.post("/v1/restore")
    async def restore(request: Request):
        data = await body(request)
        exact(data, {"session_base64", "attachments"})
        return store.restore(
            request.state.owner,
            decode(data["session_base64"], MAX_SESSION),
            attachments(data["attachments"]),
        )

    @app.get("/v1/sessions/{sid}")
    async def get_session(sid: str, request: Request):
        return store.view(sid, request.state.owner)

    @app.post("/v1/sessions/{sid}/review")
    async def review(sid: str, request: Request):
        data = await body(request)
        exact(data, {"canonical_digest", "record", "mode"})
        return store.review(
            sid, request.state.owner, data["canonical_digest"], data["record"], data["mode"]
        )

    @app.post("/v1/sessions/{sid}/transition")
    async def transition(sid: str, request: Request):
        data = await body(request)
        exact(data, {"action"})
        if not isinstance(data["action"], str):
            raise Rejected("REQUEST_SCHEMA")
        return store.transition(sid, request.state.owner, data["action"])

    @app.get("/v1/sessions/{sid}/export")
    async def export(sid: str, request: Request):
        return Response(
            store.export(sid, request.state.owner),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="session.json"'},
        )

    if hasattr(store, "provider"):

        @app.post("/v1/sessions/{sid}/questions")
        async def questions(sid: str, request: Request):
            return await asyncio.to_thread(store.questions, sid, request.state.owner)

        @app.post("/v1/sessions/{sid}/answer")
        async def answer(sid: str, request: Request):
            data = await body(request)
            exact(data, {"question_id", "text", "input_kind", "request_id", "confirmed"})
            if data["confirmed"] is not True:
                raise Rejected("ANSWER_CONFIRMATION_REQUIRED")
            return store.answer(
                sid,
                request.state.owner,
                data["question_id"],
                data["text"],
                data["input_kind"],
                data["request_id"],
            )

        @app.post("/v1/sessions/{sid}/evaluate")
        async def evaluate(sid: str, request: Request):
            data = await body(request)
            exact(data, {"answer_id"})
            if not isinstance(data["answer_id"], str):
                raise Rejected("REQUEST_SCHEMA")
            return await asyncio.to_thread(
                store.evaluate, sid, request.state.owner, data["answer_id"]
            )

        @app.post("/v1/sessions/{sid}/skip")
        async def skip(sid: str, request: Request):
            data = await body(request)
            exact(data, {"question_id"})
            return store.skip(sid, request.state.owner, data["question_id"])

        @app.post("/v1/sessions/{sid}/finish")
        async def finish(sid: str, request: Request):
            return await asyncio.to_thread(store.finish, sid, request.state.owner)

        @app.get("/v1/sessions/{sid}/result")
        async def result(sid: str, request: Request):
            return Response(
                store.result(sid, request.state.owner),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="result.json"'},
            )

    @app.delete("/v1/sessions/{sid}", status_code=204)
    async def delete(sid: str, request: Request):
        store.delete(sid, request.state.owner)

    @app.post("/v1/logout", status_code=204)
    async def logout(request: Request):
        store.clear_owner(request.state.owner)
        if oidc_verifier is not None:
            if len(revoked) >= 10000:
                raise Rejected("REVOCATION_CAPACITY", status=503)
            revoked[request.state.token_digest] = request.state.expires_at

    return app

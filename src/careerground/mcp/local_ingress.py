"""Small request-body boundary for the isolated local MCP ASGI factory.

This limits bytes accepted before OAuth and SDK parsing. It is not an Internet
rate limiter or a public deployment entrypoint.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_MCP_BODY_BYTES = 128 * 1024
MAX_BODY_FRAMES = 1024
_REJECTED_BODY = b'{"error":"REQUEST_REJECTED"}'


class LocalMCPIngress:
    """Buffer at most 128 KiB for one MCP POST, then replay it unchanged."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        path: str = "/mcp",
        max_body_bytes: int = MAX_MCP_BODY_BYTES,
    ) -> None:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise ValueError("invalid MCP path")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= MAX_MCP_BODY_BYTES:
            raise ValueError("invalid MCP body limit")
        self.app = app
        self.path = path
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("path") != self.path
            or scope.get("method") != "POST"
        ):
            await self.app(scope, receive, send)
            return

        declared = self._content_length(scope)
        if declared is False or (declared is not None and declared > self.max_body_bytes):
            await self._reject(send)
            return

        body = bytearray()
        for _ in range(MAX_BODY_FRAMES):
            message = await receive()
            if message["type"] != "http.request":
                await self._reject(send)
                return
            chunk = message.get("body", b"")
            if type(chunk) is not bytes or len(body) + len(chunk) > self.max_body_bytes:
                await self._reject(send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        else:
            await self._reject(send)
            return
        if declared is not None and declared != len(body):
            await self._reject(send)
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None | bool:
        lengths = [
            value for name, value in scope.get("headers", []) if name.lower() == b"content-length"
        ]
        chunked = any(
            name.lower() == b"transfer-encoding" and b"chunked" in value.lower()
            for name, value in scope.get("headers", [])
        )
        if len(lengths) > 1 or (chunked and lengths):
            return False
        if not lengths:
            return None
        value = lengths[0]
        if not value or len(value) > 10 or any(char < 48 or char > 57 for char in value):
            return False
        return int(value)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_REJECTED_BODY)).encode()),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _REJECTED_BODY})

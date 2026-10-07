"""Byte and frame bounds before the local MCP OAuth/SDK stack."""

from __future__ import annotations

import unittest

from careerground.mcp.local_ingress import MAX_MCP_BODY_BYTES, LocalMCPIngress


class RecordingApp:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, scope, receive, send) -> None:
        message = await receive()
        self.calls.append((scope, message))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"accepted"})


class LocalIngressTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, ingress, body_frames, *, headers=(), path="/mcp", method="POST"):
        messages = list(body_frames)
        receives = 0
        sent = []
        scope = {
            "type": "http",
            "path": path,
            "method": method,
            "headers": list(headers),
        }

        async def receive():
            nonlocal receives
            receives += 1
            return messages.pop(0) if messages else {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        await ingress(scope, receive, send)
        return sent, receives

    @staticmethod
    def body(value: bytes, *, more=False):
        return {"type": "http.request", "body": value, "more_body": more}

    def assert_rejected(self, sent, private=b"synthetic-private-source"):
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(dict(sent[0]["headers"])[b"cache-control"], b"no-store")
        self.assertNotIn(private, sent[1]["body"])
        self.assertNotIn(b"Authorization", sent[1]["body"])

    async def test_exact_limit_replays_identical_body_and_headers(self) -> None:
        app = RecordingApp()
        ingress = LocalMCPIngress(app)
        body = b"x" * MAX_MCP_BODY_BYTES
        sent, received = await self.invoke(
            ingress,
            [self.body(body[:16], more=True), self.body(body[16:])],
            headers=[
                (b"content-length", str(len(body)).encode()),
                (b"authorization", b"Bearer synthetic-private-token"),
            ],
        )
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(received, 2)
        self.assertEqual(len(app.calls), 1)
        self.assertEqual(app.calls[0][1]["body"], body)
        self.assertEqual(
            dict(app.calls[0][0]["headers"])[b"authorization"],
            b"Bearer synthetic-private-token",
        )

    async def test_oversized_declared_or_streamed_body_never_reaches_sdk(self) -> None:
        app = RecordingApp()
        ingress = LocalMCPIngress(app)
        private = b"synthetic-private-source"
        sent, received = await self.invoke(
            ingress,
            [self.body(private)],
            headers=[(b"content-length", str(MAX_MCP_BODY_BYTES + 1).encode())],
        )
        self.assert_rejected(sent, private)
        self.assertEqual(received, 0)

        sent, received = await self.invoke(
            ingress,
            [self.body(b"x" * MAX_MCP_BODY_BYTES, more=True), self.body(private)],
            headers=[(b"transfer-encoding", b"chunked")],
        )
        self.assert_rejected(sent, private)
        self.assertEqual(received, 2)
        self.assertEqual(app.calls, [])

    async def test_false_duplicate_or_invalid_content_length_fails_closed(self) -> None:
        app = RecordingApp()
        ingress = LocalMCPIngress(app, max_body_bytes=128)
        for headers, content in (
            ([(b"content-length", b"3")], b"abcd"),
            ([(b"content-length", b"10")], b"abc"),
            ([(b"content-length", b"abc")], b"abc"),
            ([(b"content-length", b"9" * 100)], b"abc"),
            ([(b"content-length", b"-1")], b"abc"),
            ([(b"content-length", b"3"), (b"content-length", b"3")], b"abc"),
            ([(b"content-length", b"3"), (b"transfer-encoding", b"chunked")], b"abc"),
        ):
            with self.subTest(headers=headers):
                sent, _ = await self.invoke(ingress, [self.body(content)], headers=headers)
                self.assert_rejected(sent)
        self.assertEqual(app.calls, [])

    async def test_chunked_and_other_paths_keep_supported_transport_flow(self) -> None:
        app = RecordingApp()
        ingress = LocalMCPIngress(app, max_body_bytes=16)
        sent, _ = await self.invoke(
            ingress,
            [self.body(b"{", more=True), self.body(b"}")],
            headers=[(b"transfer-encoding", b"chunked")],
        )
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(app.calls[-1][1]["body"], b"{}")
        sent, _ = await self.invoke(ingress, [self.body(b"x" * 50)], method="GET")
        self.assertEqual(sent[0]["status"], 200)
        self.assertEqual(app.calls[-1][1]["body"], b"x" * 50)
        sent, _ = await self.invoke(ingress, [self.body(b"x" * 50)], path="/other")
        self.assertEqual(sent[0]["status"], 200)

    async def test_frame_and_disconnect_limits_are_bounded(self) -> None:
        app = RecordingApp()
        ingress = LocalMCPIngress(app)
        sent, count = await self.invoke(ingress, [self.body(b"", more=True)] * 1025)
        self.assert_rejected(sent)
        self.assertEqual(count, 1024)
        sent, _ = await self.invoke(ingress, [{"type": "http.disconnect"}])
        self.assert_rejected(sent)
        self.assertEqual(app.calls, [])

    def test_constructor_rejects_invalid_budget(self) -> None:
        for limit in (0, False, MAX_MCP_BODY_BYTES + 1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                LocalMCPIngress(RecordingApp(), max_body_bytes=limit)

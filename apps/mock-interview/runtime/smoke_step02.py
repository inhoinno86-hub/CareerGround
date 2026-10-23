"""Actual loopback HTTP + synthetic manual file roundtrip, not an Android test."""

import argparse
import base64
import hashlib
import json
import secrets
import socket
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import uvicorn
from cg_mock.api import create_app
from cg_mock.session import ROOT, Sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite prior evidence")
    token = secrets.token_urlsafe(32)
    store = Sessions()
    app = create_app(credentials={token: "synthetic-smoke-owner"}, sessions=store)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("Runtime failed to start")
            time.sleep(0.025)
        if not server.started:
            raise RuntimeError("Runtime startup timed out")
        checks = []
        raw = (ROOT / "fixtures/portable/handoff-v1.json").read_bytes()
        with httpx.Client(
            base_url=f"http://127.0.0.1:{sock.getsockname()[1]}",
            headers={"Authorization": f"Bearer {token}"},
            trust_env=False,
        ) as client:
            view = (
                client.post(
                    "/v1/import",
                    json={
                        "handoff_base64": base64.b64encode(raw).decode(),
                        "attachments": {},
                    },
                )
                .raise_for_status()
                .json()
            )
            sid = view["session_id"]
            assert view["state"] == "REVIEW_REQUIRED"
            checks.append("actual_http_import")
            assert (
                client.post(f"/v1/sessions/{sid}/transition", json={"action": "start"}).status_code
                == 409
            )
            checks.append("start_before_review_rejected")
            ready = (
                client.post(
                    f"/v1/sessions/{sid}/review",
                    json={
                        "canonical_digest": view["canonical_digest"],
                        "record": "synthetic smoke review",
                        "mode": "coaching",
                    },
                )
                .raise_for_status()
                .json()
            )
            assert ready["state"] == "READY"
            client.post(
                f"/v1/sessions/{sid}/transition", json={"action": "start"}
            ).raise_for_status()
            client.post(
                f"/v1/sessions/{sid}/transition", json={"action": "pause"}
            ).raise_for_status()
            checks.append("review_start_pause")
            response = client.get(f"/v1/sessions/{sid}/export").raise_for_status()
            with tempfile.TemporaryDirectory(prefix="cg-smoke-") as folder:
                path = Path(folder) / "manual-session.json"
                path.write_bytes(response.content)
                actual_file = path.read_bytes()
                resumed = (
                    client.post(
                        "/v1/restore",
                        json={
                            "session_base64": base64.b64encode(actual_file).decode(),
                            "attachments": {},
                        },
                    )
                    .raise_for_status()
                    .json()
                )
                assert token.encode() not in actual_file
                assert resumed["canonical_digest"] == view["canonical_digest"]
                assert resumed["raw_sha256"] == hashlib.sha256(raw).hexdigest()
                assert resumed["state"] == "REVIEW_REQUIRED"
                checks.append("actual_manual_file_write_read_restore")
                file_sha = hashlib.sha256(actual_file).hexdigest()
            client.post("/v1/logout").raise_for_status()
            assert not store._items
            checks.append("logout_memory_cleared")
        evidence = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "step": "02",
            "scope": "actual_loopback_http_and_synthetic_manual_file_only",
            "verdict": "PASS",
            "auth": "synthetic_dev",
            "ai_calls": 0,
            "checks": checks,
            "handoff_raw_sha256": view["raw_sha256"],
            "handoff_canonical_digest": view["canonical_digest"],
            "session_file_sha256": file_sha,
            "temporary_session_file_removed": True,
            "android_build": "NOT_RUN",
            "android_saf_roundtrip": "NOT_RUN",
            "actual_oidc": "NOT_RUN",
            "actual_voice": "NOT_RUN",
            "actual_codex": "NOT_RUN",
            "chatgpt_review": "NOT_RUN",
            "package_complete": False,
        }
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"verdict": "PASS", "checks": len(checks), "evidence": str(args.output)}))
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("Runtime did not terminate")


if __name__ == "__main__":
    main()

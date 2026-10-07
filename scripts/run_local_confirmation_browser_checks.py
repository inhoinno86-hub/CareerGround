"""Real keyboard confirmation -> MCP receipts/resources, on disposable synthetic data.

Reuses the integration-test fixture deliberately; this is a repository validation
tool, never a product entrypoint. No existing profile, account or host is accessed.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_browser_mcp_confirmation import (
    PHRASE,
    RESOURCE,
    BrowserMCPConfirmationTests,
)


def run(output: Path, browser_name: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    fixture = BrowserMCPConfirmationTests()
    fixture.setUpClass()
    checks = []
    external = []
    server = None
    thread = None
    sock = socket.socket()
    try:
        fixture.setUp()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(uvicorn.Config(fixture.web, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline or not thread.is_alive():
                raise RuntimeError("synthetic confirmation server did not start")
            time.sleep(0.02)

        def check(condition, label):
            if not condition:
                raise AssertionError(label)
            checks.append(label)

        with (
            TestClient(fixture.web) as setup_browser,
            TestClient(fixture.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
            sync_playwright() as playwright,
        ):
            executable = (
                shutil.which("google-chrome") or shutil.which("chromium")
                if browser_name == "chromium"
                else None
            )
            browser = getattr(playwright, browser_name).launch(
                headless=True, executable_path=executable
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})

            def local_only(route):
                if urlsplit(route.request.url).netloc == f"127.0.0.1:{port}":
                    route.continue_()
                else:
                    external.append("blocked")
                    route.abort()

            context.route("**/*", local_only)
            page = context.new_page()

            def tab_to(selector):
                for _ in range(30):
                    page.keyboard.press("Tab")
                    if page.locator(selector).evaluate(
                        "element => element === document.activeElement"
                    ):
                        check(True, selector + ": keyboard focus")
                        return
                raise AssertionError("keyboard target unreachable: " + selector)

            def confirm(request, label):
                page.goto(origin + request["confirmation_path"])
                check(page.locator("h1").count() == 1, label + ": heading")
                check(page.locator("main#main-content").count() == 1, label + ": main landmark")
                check(page.locator("html").get_attribute("lang") == "ko", label + ": language")
                check(
                    "client-a" in page.locator("section[aria-label='연결 앱 확인']").inner_text(),
                    label + ": recipient",
                )
                snapshot = page.locator("body").aria_snapshot()
                check(
                    'checkbox "표시된 연결 앱이' in snapshot, label + ": named connection consent"
                )
                for index in range(page.locator("select").count()):
                    selector = (
                        "select[name='"
                        + page.locator("select").nth(index).get_attribute("name")
                        + "']"
                    )
                    tab_to(selector)
                    page.keyboard.press("ArrowDown")
                    check(page.locator(selector).input_value() == "ACCEPT", label + ": fact choice")
                tab_to("input[name='confirm']")
                page.keyboard.press("Space")
                check(
                    page.locator("input[name='confirm']").is_checked(),
                    label + ": explicit domain confirmation",
                )
                tab_to("input[name='allow_connection']")
                page.keyboard.press("Space")
                check(
                    page.locator("input[name='allow_connection']").is_checked(),
                    label + ": explicit connection confirmation",
                )
                # Capture the visible synthetic form, before any receipt is issued.
                page.screenshot(path=str(output / (label + ".png")), full_page=True)
                tab_to("button[type='submit']")
                with page.expect_navigation() as navigation:
                    page.keyboard.press("Enter")
                response = navigation.value
                if response.status != 200:
                    request = response.request
                    raise AssertionError(
                        str(
                            {
                                "status": response.status,
                                "fields": sorted(parse_qs(request.post_data or "")),
                                "origin": request.headers.get("origin"),
                                "site": request.headers.get("sec-fetch-site"),
                            }
                        )
                    )
                page.locator("#approval-receipt").wait_for()
                check(
                    page.locator("h1").inner_text() == "연결 작업 확인 완료",
                    label + ": completed in browser",
                )
                return page.locator("#approval-receipt").inner_text()

            batch = fixture.review_batch(setup_browser)
            intent = fixture.request(mcp, "FACT_REVIEW", batch, 0)
            receipt = confirm(intent, "fact")
            result = fixture.call(
                mcp, "submit_claim_review", {"review_batch_id": batch, "approval_receipt": receipt}
            )
            check(result["data"]["completed_in_browser"], "fact: MCP acknowledges browser result")
            artifact = fixture.artifact_after_fact(setup_browser)
            intent = fixture.request(
                mcp, "WORDING_REVIEW", artifact, 2, key="browser_wording_confirmation_0001"
            )
            receipt = confirm(intent, "wording")
            result = fixture.call(
                mcp,
                "submit_resume_wording_review",
                {"artifact_id": artifact, "approval_receipt": receipt},
            )
            check(
                result["data"]["completed_in_browser"], "wording: MCP acknowledges browser result"
            )
            for action, target, fmt, tool, args in (
                (
                    "RESUME_EXPORT",
                    artifact,
                    "MARKDOWN",
                    "export_resume",
                    {"artifact_id": artifact, "format": "MARKDOWN"},
                ),
                (
                    "PROFILE_EXPORT",
                    "profile-a",
                    "JSON",
                    "export_profile_data",
                    {"profile_id": "profile-a", "profile_version": 2, "format": "JSON"},
                ),
            ):
                intent = fixture.request(
                    mcp, action, target, 2, fmt, key="browser_export_confirmation_" + action
                )
                receipt = confirm(intent, action.lower())
                result = fixture.call(mcp, tool, {**args, "approval_receipt": receipt})
                check(result["status"] == "ok", action + ": MCP export receipt")
                resource = fixture.rpc(
                    mcp, "resources/read", {"uri": result["data"]["resource_uri"]}
                ).json()["result"]["contents"][0]["text"]
                text = (
                    json.dumps(json.loads(resource), ensure_ascii=False)
                    if fmt == "JSON"
                    else re.sub(r"\\(.)", r"\1", resource)
                )
                check(PHRASE in text, action + ": authenticated synthetic resource")
            browser.close()
        check(not external, "no external browser requests")
        report = {
            "browser": browser_name,
            "checks": checks,
            "check_count": len(checks),
            "external_requests": len(external),
            "synthetic_only": True,
        }
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return report
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        sock.close()
        fixture.doCleanups()
        fixture.tearDownClass()


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=("chromium", "firefox"), default="chromium")
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    result = run(options.output_dir, options.browser)
    print(
        json.dumps(
            {
                "browser": result["browser"],
                "checks": result["check_count"],
                "external_requests": result["external_requests"],
            }
        )
    )

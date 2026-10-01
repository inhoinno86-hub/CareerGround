"""Exercise exact policy approval in Chrome and Firefox using synthetic data.

Run: uv run python scripts/run_local_policy_browser_checks.py --output-dir /tmp/cg-policy-browser
Each case uses a new file SQLite database, local HTTP server and browser context.
The report never stores confirmation tokens, OAuth tokens or approval receipts.
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
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from sqlalchemy import func, select

from careerground.storage.graph_models import (
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    EvidenceItem,
)
from careerground.storage.models import CareerProfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_browser_mcp_confirmation import RESOURCE
from test_policy_browser_confirmation import PolicyBrowserTests


@dataclass(frozen=True)
class Case:
    action: str
    decision: str

    @property
    def slug(self) -> str:
        return (self.action + "-" + self.decision).lower().replace("_", "-")


CASES = (
    Case("CONFLICT_REVIEW", "KEEP_EXISTING"),
    Case("CONFLICT_REVIEW", "ACCEPT_CORRECTION"),
    Case("CONFLICT_REVIEW", "KEEP_BOTH_SCOPED"),
    Case("CONFLICT_REVIEW", "REMAIN_UNCERTAIN"),
    Case("BOUNDARY_REVIEW", "ADD"),
    Case("BOUNDARY_REVIEW", "REVOKE"),
)


def _case(browser, browser_name: str, case: Case, output: Path) -> dict:
    fixture = PolicyBrowserTests()
    fixture.setUp()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(
        uvicorn.Config(fixture.fixture.web, log_level="error", access_log=False)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    context = None
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline or not thread.is_alive():
                raise RuntimeError("local policy browser server did not start")
            time.sleep(0.02)
        with TestClient(fixture.fixture.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp:
            request = fixture.fixture.request(
                mcp, case.action, "claim-a", 1, key="synthetic_" + case.slug
            )
            with fixture.sessions() as session:
                original_sources = {
                    item.id: item.content_text for item in session.scalars(select(EvidenceItem))
                }
                unaffected_before = session.scalar(
                    select(func.count())
                    .select_from(ClaimAssessment)
                    .where(ClaimAssessment.claim_id == "claim-unaffected")
                )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            external = []

            def local_only(route):
                if urlsplit(route.request.url).netloc == f"127.0.0.1:{port}":
                    route.continue_()
                else:
                    external.append(route.request.url)
                    route.abort()

            context.route("**/*", local_only)
            page = context.new_page()
            checks = []

            def check(condition, name):
                if not condition:
                    raise AssertionError(f"{browser_name} {case.slug}: {name}")
                checks.append(name)

            def audit(label):
                check(page.locator("html").get_attribute("lang") == "ko", label + " language")
                check(page.locator("h1").count() == 1, label + " heading")
                check(page.locator("main#main-content").count() == 1, label + " main")
                check(
                    page.get_by_role("region", name="연결 앱 확인").count() == 1,
                    label + " app recipient region",
                )
                check("client-a" in page.locator("main").inner_text(), label + " app identity")
                snapshot = page.locator("body").aria_snapshot()
                check("- main:" in snapshot, label + " accessible main")
                controls = re.findall(
                    r'^\s*- (?:button|checkbox|textbox|combobox)(?: "([^"]*)")?',
                    snapshot,
                    re.MULTILINE,
                )
                check(all(controls), label + " named controls")
                check(
                    page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                    label + " no horizontal overflow",
                )

            def tab_to(locator):
                check(locator.count() == 1, "unique keyboard target")
                for _ in range(80):
                    if locator.evaluate("el => el === document.activeElement"):
                        check(
                            locator.evaluate("el => getComputedStyle(el).outlineStyle !== 'none'"),
                            "visible keyboard focus",
                        )
                        return
                    page.keyboard.press("Tab")
                raise AssertionError(f"{browser_name} {case.slug}: keyboard target unreachable")

            def choose(name, expected):
                locator = page.locator(f'select[name="{name}"]')
                tab_to(locator)
                for _ in range(12):
                    if locator.input_value() == expected:
                        break
                    page.keyboard.press("ArrowDown")
                check(locator.input_value() == expected, "keyboard select " + name)

            def type_text(name, value):
                locator = page.locator(f'textarea[name="{name}"]')
                tab_to(locator)
                page.keyboard.insert_text(value)
                check(locator.input_value() == value, "keyboard text " + name)

            page.goto(origin + request["confirmation_path"])
            audit("choices")
            check("기준 프로필 버전: 1" in page.locator("main").inner_text(), "version shown")
            check(
                all(
                    item in page.locator("main").inner_text() for item in original_sources.values()
                ),
                "source text shown",
            )
            page.keyboard.press("Tab")
            check(
                page.locator('a[href="#main-content"]').evaluate(
                    "el => el === document.activeElement"
                ),
                "skip link first Tab",
            )
            page.keyboard.press("Enter")
            check(
                page.locator("main").evaluate("el => el === document.activeElement"),
                "skip link focuses main",
            )
            choice_url = page.url
            tab_to(page.locator('button[type="submit"]'))
            page.keyboard.press("Enter")
            check(page.url == choice_url, "native required fields block empty choice")
            if case.action == "CONFLICT_REVIEW":
                choose("conflict_link_id", "contradiction-link")
                choose("resolution", case.decision)
                type_text("explanation", "합성 모순의 양쪽 근거를 보존한다. " + case.decision)
            else:
                choose(
                    "evidence_id",
                    "contradiction-a" if case.decision == "ADD" else "support-a",
                )
                choose("action", case.decision)
                if case.decision == "REVOKE":
                    choose("constraint_id", "old-boundary")
                    check(
                        page.locator('textarea[name="proposed_boundary_text"]').input_value() == "",
                        "revoke leaves proposed boundary blank",
                    )
                else:
                    check(
                        page.locator('select[name="constraint_id"]').input_value() == "",
                        "add leaves old boundary blank",
                    )
                    type_text("proposed_boundary_text", "관리 권한을 주장하지 않는다.")
                type_text("allowed_wording", "기능을 구현했다.")
                type_text("remaining_prohibited_expansion", "단독 리더십과 수치 확대는 금지한다.")
            page.screenshot(path=str(output / f"{browser_name}-{case.slug}-choices.png"))
            tab_to(page.locator('button[type="submit"]'))
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.keyboard.press("Enter")
            audit("exact review")
            check(
                page.locator("h1").inner_text().endswith("직접 확인"),
                "exact review distinct heading",
            )
            exact_text = page.locator("main").inner_text()
            check("직접 입력한 변경 내용" in exact_text, "exact changes shown")
            check(
                all(item in exact_text for item in original_sources.values()),
                "original source text retained on exact review",
            )
            if case.action == "CONFLICT_REVIEW":
                check(case.decision in page.content(), "chosen conflict decision retained")
            elif case.decision == "ADD":
                check("관리 권한을 주장하지 않는다." in exact_text, "added boundary exact text")
                check("기능을 구현했다." in exact_text, "allowed wording exact text")
            else:
                check("Do not claim sole leadership" in exact_text, "revoked old boundary shown")
                check("해당 없음" in exact_text, "no proposed boundary on revoke")
            with fixture.sessions() as session:
                check(session.get(CareerProfile, "profile-a").version == 1, "prepare has no write")
                review_table = (
                    ClaimConflictReview if case.action == "CONFLICT_REVIEW" else ClaimBoundaryReview
                )
                check(
                    session.scalar(select(func.count()).select_from(review_table)) == 0,
                    "prepare has no review journal",
                )
            exact_url = page.url
            tab_to(page.locator('button[type="submit"]'))
            page.keyboard.press("Enter")
            check(page.url == exact_url, "native required approval prevents submit")
            for name in ("confirm", "allow_connection"):
                locator = page.locator(f'input[type="checkbox"][name="{name}"]')
                tab_to(locator)
                page.keyboard.press("Space")
                check(locator.is_checked(), "keyboard explicit checkbox " + name)
            page.screenshot(path=str(output / f"{browser_name}-{case.slug}-exact.png"))
            tab_to(page.locator('button[type="submit"]'))
            with page.expect_navigation(wait_until="domcontentloaded"):
                page.keyboard.press("Enter")
            check(page.locator("h1").inner_text() == "연결 작업 확인 완료", "receipt screen")
            receipt = page.locator("#approval-receipt").inner_text()
            check(bool(receipt), "browser issued approval receipt")
            tool = (
                "resolve_claim_conflict"
                if case.action == "CONFLICT_REVIEW"
                else "review_boundary_change"
            )
            result = fixture.fixture.call(
                mcp, tool, {"claim_id": "claim-a", "approval_receipt": receipt}
            )
            check(result["status"] == "ok", "MCP envelope success")
            check(result["data"]["version_after"] == 2, "MCP result version 2")
            check(result["data"]["completed_in_browser"] is True, "MCP browser proof")
            check(
                fixture.fixture.call(
                    mcp, tool, {"claim_id": "claim-a", "approval_receipt": receipt}
                )
                == result,
                "MCP exact retry stable",
            )
            with fixture.sessions() as session:
                check(session.get(CareerProfile, "profile-a").version == 2, "profile version 2")
                latest = session.scalar(
                    select(ClaimAssessment)
                    .where(ClaimAssessment.claim_id == "claim-a")
                    .order_by(ClaimAssessment.profile_version.desc())
                )
                expected_usage = (
                    "DO_NOT_CLAIM"
                    if case.action == "CONFLICT_REVIEW" and case.decision == "ACCEPT_CORRECTION"
                    else "REVIEW_REQUIRED"
                )
                check(latest.usage_policy == expected_usage, "no automatic use approval")
                check(
                    {item.id: item.content_text for item in session.scalars(select(EvidenceItem))}
                    == original_sources,
                    "all original source text preserved",
                )
                check(
                    session.scalar(
                        select(func.count())
                        .select_from(ClaimAssessment)
                        .where(ClaimAssessment.claim_id == "claim-unaffected")
                    )
                    == unaffected_before,
                    "unaffected claim preserved",
                )
                check(
                    session.scalar(select(func.count()).select_from(review_table)) == 1,
                    "one review journal",
                )
            check(not external, "no external browser requests")
            return {
                "browser": browser_name,
                "browser_version": browser.version,
                "case": case.slug,
                "passed": len(checks),
                "checks": checks,
            }
    finally:
        if context is not None:
            context.close()
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        fixture.doCleanups()
        if thread.is_alive():
            raise RuntimeError("local policy browser server did not stop")


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        for name in ("chromium", "firefox"):
            executable = shutil.which("google-chrome") if name == "chromium" else None
            browser = getattr(playwright, name).launch(headless=True, executable_path=executable)
            try:
                for case in CASES:
                    results.append(_case(browser, name, case, output))
            finally:
                browser.close()
    report = {
        "browsers": {
            name: next(item["browser_version"] for item in results if item["browser"] == name)
            for name in sorted({item["browser"] for item in results})
        },
        "scenarios": len(results),
        "passed": sum(item["passed"] for item in results),
        "results": results,
        "limits": [
            "Synthetic SQLite and local HTTP only; no public account or real connection",
            "Browser keyboard and accessibility tree checks, not a human spoken screen reader audit",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> None:
    logging.disable(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output_dir)
    print(
        json.dumps(
            {"scenarios": report["scenarios"], "passed": report["passed"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Exercise synthetic JD→R1→wording→export approval in Chrome and Firefox.

Run: uv run python scripts/run_local_artifact_browser_checks.py --output-dir /tmp/cg-artifact-browser
Each browser uses a new SQLite database and local HTTP server. Reports omit
OAuth tokens, browser confirmation tokens, receipts and resource URIs.
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
from urllib.parse import urlsplit

import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from sqlalchemy import func, select

from careerground.storage.graph_models import Claim
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactUnit,
    ArtifactWordingReview,
    JDRequirement,
    JobDescription,
    RequirementClaimMap,
)
from careerground.storage.models import BrowserOperation, CareerProfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_browser_mcp_confirmation import PHRASE, RESOURCE, BrowserMCPConfirmationTests

JD_LINES = (
    "테스트 자동화 경험",
    "서버 API 구현 경험",
    "오류 처리 경험",
    "기술 문서 작성 경험",
    "협업 경험",
)


def _browser_journey(playwright, browser_name: str, bullet_count: int, output: Path) -> dict:
    selected_lines = JD_LINES[:bullet_count]
    screenshot_prefix = f"{browser_name}-{bullet_count}-bullets"
    fixture = BrowserMCPConfirmationTests()
    fixture.setUpClass()
    fixture.setUp()
    browser = None
    context = None
    sock = None
    server = None
    thread = None
    try:
        with (
            TestClient(fixture.web) as seed_web,
            TestClient(fixture.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            fixture.fact(seed_web, mcp)
            with fixture.sessions() as session:
                claim_id = session.scalar(select(Claim)).id
            use_path = f"/profile/profile-a/1/claim/{claim_id}/use-review"
            use_page = seed_web.get(use_path)
            if use_page.status_code != 200:
                raise AssertionError("synthetic use review unavailable")
            use_result = seed_web.post(
                use_path,
                data={
                    "approval_token": fixture.hidden(use_page.text, "approval_token"),
                    "confirm_consistency": "yes",
                    "confirm_use": "yes",
                },
                follow_redirects=False,
            )
            if use_result.status_code != 303:
                raise AssertionError("synthetic Claim use prerequisite failed")
            with fixture.sessions() as session:
                if session.get(CareerProfile, "profile-a").version != 2:
                    raise AssertionError("synthetic Claim use did not reach profile version 2")
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            server = uvicorn.Server(
                uvicorn.Config(fixture.web, log_level="error", access_log=False)
            )
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()
            deadline = time.monotonic() + 10
            while not server.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("local artifact browser server did not start")
                time.sleep(0.02)
            executable = shutil.which("google-chrome") if browser_name == "chromium" else None
            browser = getattr(playwright, browser_name).launch(
                headless=True, executable_path=executable
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
                    raise AssertionError(f"{browser_name}: {name}")
                checks.append(name)

            def audit(label):
                check(page.locator("html").get_attribute("lang") == "ko", label + " language")
                check(page.locator("h1").count() == 1, label + " heading")
                check(page.locator("main#main-content").count() == 1, label + " main")
                check(
                    page.get_by_role("region", name="연결 앱 확인").count() == 1,
                    label + " recipient region",
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
                raise AssertionError("keyboard target unreachable")

            def choose(name, expected):
                locator = page.locator(f'select[name="{name}"]')
                tab_to(locator)
                for _ in range(12):
                    if locator.input_value() == expected:
                        break
                    page.keyboard.press("ArrowDown")
                check(locator.input_value() == expected, "keyboard select " + name)

            def confirm_checkboxes():
                tab_to(page.locator('button[type="submit"]'))
                before = page.url
                page.keyboard.press("Enter")
                check(page.url == before, "native required approval blocks unchecked submit")
                for name in ("confirm", "allow_connection"):
                    locator = page.locator(f'input[type="checkbox"][name="{name}"]')
                    tab_to(locator)
                    page.keyboard.press("Space")
                    check(locator.is_checked(), "keyboard checkbox " + name)

            def submit():
                tab_to(page.locator('button[type="submit"]'))
                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.keyboard.press("Enter")

            def open_request(action, target, *, format="NONE"):
                requested = fixture.request(
                    mcp,
                    action,
                    target,
                    2,
                    format,
                    key="synthetic_artifact_browser_" + action.lower(),
                )
                page.goto(origin + requested["confirmation_path"])
                audit(action + " choices")
                check(
                    "기준 프로필 버전: 2" in page.locator("main").inner_text(),
                    action + " version shown",
                )
                page.keyboard.press("Tab")
                check(
                    page.locator('a[href="#main-content"]').evaluate(
                        "el => el === document.activeElement"
                    ),
                    action + " skip link first Tab",
                )
                page.keyboard.press("Enter")
                check(
                    page.locator("main").evaluate("el => el === document.activeElement"),
                    action + " skip link focuses main",
                )
                return requested

            def exact_approval(
                action, before_count, count_table, *, expected_texts=(), expected_order=()
            ):
                submit()
                audit(action + " exact")
                check(
                    page.locator("h1").inner_text().endswith("직접 확인"),
                    action + " distinct exact heading",
                )
                check(
                    "이번 작업의 정확한 내용" in page.locator("main").inner_text(),
                    action + " exact review",
                )
                exact_text = page.locator("main").inner_text()
                check(
                    all(item in exact_text for item in expected_texts),
                    action + " selected source shown before approval",
                )
                if expected_order:
                    check(
                        page.locator("main > ol > li").all_inner_texts() == list(expected_order),
                        action + " exact selected order before approval",
                    )
                with fixture.sessions() as session:
                    check(
                        session.scalar(select(func.count()).select_from(count_table))
                        == before_count,
                        action + " prepare has no product write",
                    )
                page.screenshot(
                    path=str(output / f"{screenshot_prefix}-{action.lower()}-exact.png")
                )
                confirm_checkboxes()
                submit()
                check(page.locator("h1").inner_text() == "연결 작업 확인 완료", action + " receipt")
                receipt = page.locator("#approval-receipt").inner_text()
                check(bool(receipt), action + " browser receipt issued")
                return receipt

            def check_operation_private(request, selected_text):
                with fixture.sessions() as session:
                    row = session.get(BrowserOperation, request["request_id"])
                    check(row.status in {"DONE", "CONSUMED"}, "operation completed")
                    check(
                        all(fragment not in (row.result_json or "") for fragment in selected_text),
                        "pending operation stores no selected source text",
                    )

            # JD selection: each supported explicit bullet count from one to five.
            with fixture.sessions() as session:
                check(
                    session.scalar(select(func.count()).select_from(JobDescription)) == 0,
                    "no initial JD",
                )
            request = open_request("JD_PASTE", "profile-a")
            tab_to(page.locator('button[type="submit"]'))
            page.keyboard.press("Enter")
            check(
                urlsplit(page.url).path == request["confirmation_path"],
                "JD native required text blocks empty submit",
            )
            selected_text = "\n".join("- " + line for line in selected_lines)
            tab_to(page.locator('textarea[name="selected_text"]'))
            page.keyboard.insert_text(selected_text)
            check(
                page.locator('textarea[name="selected_text"]').input_value() == selected_text,
                "JD bullets typed verbatim",
            )
            page.screenshot(path=str(output / f"{screenshot_prefix}-jd-paste-choices.png"))
            receipt = exact_approval(
                "JD_PASTE",
                0,
                JobDescription,
                expected_texts=selected_lines,
                expected_order=selected_lines,
            )
            check(
                page.locator("#approval-receipt").count() == 1,
                "JD browser receipt visible only after approval",
            )
            result = fixture.call(
                mcp,
                "record_selected_jd",
                {"profile_id": "profile-a", "profile_version": 2, "approval_receipt": receipt},
            )
            check(result["status"] == "ok", "JD MCP envelope")
            jd = result["data"]
            check(jd["requirement_count"] == bullet_count, "JD requirement count recorded")
            check(jd["analysis_kind"] == "SELECTED_EXCERPTS_ONLY", "JD no AI analysis")
            jd_id = jd["jd_id"]
            with fixture.sessions() as session:
                requirements = session.scalars(
                    select(JDRequirement)
                    .where(JDRequirement.jd_id == jd_id)
                    .order_by(JDRequirement.ordinal)
                ).all()
                check(
                    [item.exact_text for item in requirements] == list(selected_lines),
                    "JD exact chosen order persisted",
                )
            check_operation_private(request, selected_lines)

            # Potential link: direct requirement and eligible Claim, no coverage claim.
            request = open_request("JD_LINK", jd_id)
            choose("requirement_id", requirements[0].id)
            choose("claim_id", claim_id)
            page.screenshot(path=str(output / f"{screenshot_prefix}-jd-link-choices.png"))
            receipt = exact_approval(
                "JD_LINK", 0, RequirementClaimMap, expected_texts=(selected_lines[0], PHRASE)
            )
            exact_text = page.locator("main").inner_text()
            check("연결 작업 확인 완료" in exact_text, "JD link confirmation complete")
            linked = fixture.call(
                mcp, "link_jd_requirement", {"jd_id": jd_id, "approval_receipt": receipt}
            )
            check(linked["status"] == "ok", "link MCP envelope")
            check(linked["data"]["mapping_kind"] == "POTENTIAL", "link remains potential")
            check(linked["data"]["claim_id"] == claim_id, "selected Claim linked")
            check_operation_private(request, (PHRASE, selected_lines[0]))

            # R1: one eligible Claim copied exactly, with no automatic wording consent.
            request = open_request("R1_DRAFT", jd_id)
            candidate = page.locator('input[type="checkbox"][name="claim_ids"]')
            tab_to(candidate)
            page.keyboard.press("Space")
            check(candidate.is_checked(), "R1 Claim selected with keyboard")
            page.screenshot(path=str(output / f"{screenshot_prefix}-r1-draft-choices.png"))
            receipt = exact_approval("R1_DRAFT", 0, Artifact, expected_texts=(PHRASE,))
            drafted = fixture.call(
                mcp,
                "generate_resume_draft",
                {"jd_id": jd_id, "profile_version": 2, "approval_receipt": receipt},
            )
            check(drafted["status"] == "ok", "R1 MCP envelope")
            draft = drafted["data"]
            check(
                draft["wording_level"] == "R1" and draft["review_required"] is True,
                "R1 wording remains unreviewed",
            )
            artifact_id = draft["artifact_id"]
            with fixture.sessions() as session:
                units = session.scalars(
                    select(ArtifactUnit)
                    .where(ArtifactUnit.artifact_id == artifact_id)
                    .order_by(ArtifactUnit.ordinal)
                ).all()
                check(len(units) == 1, "one exact R1 unit")
                check(units[0].exact_text == PHRASE, "R1 copies Claim wording exactly")
                check(units[0].review_status == "REVIEW_REQUIRED", "no automatic wording review")
                check(
                    session.scalar(select(func.count()).select_from(ArtifactWordingReview)) == 0,
                    "no preconsent wording journal",
                )
            check_operation_private(request, (PHRASE, *selected_lines))

            # Later, separate browser wording and export approvals.
            def approve_single(action, target, *, format="NONE"):
                requested = fixture.request(
                    mcp,
                    action,
                    target,
                    2,
                    format,
                    key="synthetic_artifact_browser_" + action.lower(),
                )
                page.goto(origin + requested["confirmation_path"])
                audit(action + " review")
                review_text = page.locator("main").inner_text()
                if action == "WORDING_REVIEW":
                    check(PHRASE in review_text, "wording exact R1 shown")
                else:
                    check(
                        "형식 MARKDOWN" in review_text and "SHA-256" in review_text,
                        "export format and hash shown",
                    )
                page.screenshot(
                    path=str(output / f"{screenshot_prefix}-{action.lower()}-review.png")
                )
                confirm_checkboxes()
                submit()
                check(page.locator("h1").inner_text() == "연결 작업 확인 완료", action + " receipt")
                receipt = page.locator("#approval-receipt").inner_text()
                check(bool(receipt), action + " browser receipt issued")
                return receipt

            receipt = approve_single("WORDING_REVIEW", artifact_id)
            wording = fixture.call(
                mcp,
                "submit_resume_wording_review",
                {"artifact_id": artifact_id, "approval_receipt": receipt},
            )
            check(wording["status"] == "ok", "wording MCP envelope")
            with fixture.sessions() as session:
                check(
                    session.scalar(select(func.count()).select_from(ArtifactWordingReview)) == 1,
                    "separate wording journal",
                )
            receipt = approve_single("RESUME_EXPORT", artifact_id, format="MARKDOWN")
            exported = fixture.call(
                mcp,
                "export_resume",
                {"artifact_id": artifact_id, "format": "MARKDOWN", "approval_receipt": receipt},
            )
            check(exported["status"] == "ok", "export MCP envelope")
            check(exported["data"]["format"] == "MARKDOWN", "approved export format")
            resource = fixture.rpc(mcp, "resources/read", {"uri": exported["data"]["resource_uri"]})
            check(resource.status_code == 200, "private Markdown resource readable")
            content = resource.json()["result"]["contents"][0]["text"]
            check(
                re.sub(r"\\(.)", r"\1", content) == "- " + PHRASE + "\n",
                "export matches reviewed R1 only",
            )
            check(not external, "no external browser requests")
            return {
                "browser": browser_name,
                "version": browser.version,
                "jd_bullets": bullet_count,
                "passed": len(checks),
                "checks": checks,
            }
    finally:
        if context is not None:
            context.close()
        if browser is not None:
            browser.close()
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        if sock is not None:
            sock.close()
        fixture.doCleanups()
        if thread is not None and thread.is_alive():
            raise RuntimeError("local artifact browser server did not stop")


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        results = [
            _browser_journey(playwright, name, count, output)
            for name in ("chromium", "firefox")
            for count in range(1, 6)
        ]
    report = {
        "browsers": {item["browser"]: item["version"] for item in results},
        "journeys": len(results),
        "passed": sum(item["passed"] for item in results),
        "results": results,
        "limits": [
            "Synthetic SQLite and loopback browser traffic only; no public account or real connector",
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
    print(json.dumps({"journeys": report["journeys"], "passed": report["passed"]}))


if __name__ == "__main__":
    main()

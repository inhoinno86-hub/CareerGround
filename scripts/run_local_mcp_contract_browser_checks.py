"""Focused native-zoom browser checks for new local MCP approval and logout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from run_local_demo_release_checks import (
    _audit,
    _check,
    _focus,
    _native_zoom,
    _new_demo,
    _select,
    _stop_demo,
    _submit,
    _toggle,
)


def _fill(page, selector, value, checks):
    _focus(page, selector, checks)
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(value)
    _check(page.locator(selector).input_value() == value, "synthetic input entered", checks)


def _call(page, tool, args, checks):
    _focus(page, "#tool", checks)
    page.keyboard.press("Home")
    for _ in range(40):
        if page.locator("#tool").input_value() == tool:
            break
        page.keyboard.press("ArrowDown")
    _check(page.locator("#tool").input_value() == tool, "MCP tool keyboard selected", checks)
    _fill(page, "#arguments", json.dumps(args, ensure_ascii=False), checks)
    _submit(page, "합성 도구 호출", checks)


def _case(playwright, browser_name, scope):
    checks, external = [], []
    with tempfile.TemporaryDirectory(prefix="cg-contract-browser-") as private:
        folder = Path(private)
        process, port = _new_demo(folder)
        browser = None
        try:
            browser_type = getattr(playwright, browser_name)
            executable = browser_type.executable_path
            if browser_name == "chromium":
                executable = shutil.which("google-chrome") or shutil.which("chromium") or executable
            elif not Path(executable).is_file():
                cache = Path(
                    os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright")
                )
                candidates = sorted(cache.glob("firefox-*/firefox/firefox"), reverse=True)
                if candidates:
                    executable = str(candidates[0])
            browser = browser_type.launch(
                headless=False,
                executable_path=executable,
                args=["--ozone-platform=x11", "--disable-background-networking"]
                if browser_name == "chromium"
                else [],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900}, reduced_motion="reduce"
            )

            def local_only(route):
                if urlsplit(route.request.url).netloc == f"127.0.0.1:{port}":
                    route.continue_()
                else:
                    external.append(1)
                    route.abort()

            context.route("**/*", local_only)
            page = context.new_page()
            origin = f"http://127.0.0.1:{port}"
            page.goto(origin + "/demo")
            zoom = _native_zoom(page, browser_name, checks)
            _select(page, "#account", "a", checks)
            _submit(page, "합성 계정으로 시작", checks)
            page.goto(origin + "/demo/mcp")
            _call(
                page,
                "analyze_jd",
                {
                    "profile_id": "demo-profile-a",
                    "profile_version": 0,
                    "jd_text": "- 합성 테스트 경험",
                },
                checks,
            )
            result = json.loads(page.locator("#mcp-result").inner_text())["result"][
                "structuredContent"
            ]
            _check(result["data"]["canonical_saved"] is False, "JD candidate not saved", checks)
            args = {
                "scope": scope,
                "target_id": "demo-account-a" if scope == "ACCOUNT" else "demo-profile-a",
                "profile_version": 0,
                "idempotency_key": "synthetic_browser_delete_0001",
                "approval_receipt": "",
            }
            _call(page, "execute_data_deletion", args, checks)
            result = json.loads(page.locator("#mcp-result").inner_text())["result"][
                "structuredContent"
            ]
            _check(result["data"]["status"] == "WAITING", "model request not approval", checks)
            path = result["data"]["confirmation_path"]
            _focus(page, "p a[href='" + path + "']", checks)
            page.keyboard.press("Enter")
            page.wait_for_url(origin + path)
            _check(
                page.locator("h1").inner_text() == "삭제 영향 직접 확인",
                "confirmation page title: " + page.locator("h1").inner_text(),
                checks,
            )
            _audit(page, "삭제 영향 직접 확인", checks)
            _toggle(page, "input[name=acknowledged_impact]", checks)
            _toggle(page, "input[name=mock_reauthenticated]", checks)
            _fill(page, "#mock_phrase", "합성 계정 A", checks)
            _submit(page, "모의 재인증 후 최종 확인", checks)
            _audit(page, "모의 재인증 후 삭제 확인", checks)
            _toggle(page, "input[name=confirm]", checks)
            _submit(page, "로컬 합성 데이터 삭제 실행", checks)
            _audit(page, "합성 연결 삭제 승인 증명", checks)
            _check(
                "아직 삭제하지 않았습니다" in page.locator("main").inner_text(),
                "browser issues proof only",
                checks,
            )
            receipt = page.locator("#approval-receipt").inner_text()
            page.goto(origin + "/demo/mcp")
            _call(page, "execute_data_deletion", {**args, "approval_receipt": receipt}, checks)
            if scope == "ACCOUNT":
                _audit(page, "합성 삭제 실행 접수", checks)
                _check(
                    page.goto(origin + "/profiling/start").status == 401,
                    "deleted account Web denied",
                    checks,
                )
            else:
                _check(
                    page.locator("#mcp-result").count() == 1,
                    "MCP result rendered: " + page.locator("h1").inner_text(),
                    checks,
                )
                result = json.loads(page.locator("#mcp-result").inner_text())["result"][
                    "structuredContent"
                ]
                _check(result["data"]["status"] == "DELETING", "profile erasure staged", checks)
            _check(
                page.goto(origin + "/demo/deletion/status").status == 200,
                "minimal status after erasure",
                checks,
            )
            page.goto(origin + "/demo")
            _submit(page, "합성 연결 로그아웃·토큰 철회", checks)
            _check(
                page.goto(origin + "/demo/deletion/status").status == 401,
                "logout loses status proof",
                checks,
            )
            page.goto(origin + "/demo")
            _select(page, "#account", "b", checks)
            _submit(page, "합성 계정으로 시작", checks)
            _check(
                page.goto(origin + "/profiling/start").status == 200, "other account usable", checks
            )
            _check(not external, "localhost page requests only", checks)
            version = browser.version
            context.close()
        finally:
            if browser:
                browser.close()
            _stop_demo(process)
        _check(
            not list(folder.glob("careerground-local-demo-*")),
            "owned temporary data removed",
            checks,
        )
    return {
        "browser": browser_name,
        "browser_version": version,
        "scope": scope,
        "passed": len(checks),
        "checks": checks,
        "native_zoom": zoom,
        "external_request_count": len(external),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--inside-private-display", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.inside_private_display:
        env = os.environ.copy()
        env.pop("WAYLAND_DISPLAY", None)
        env.update({"GDK_BACKEND": "x11", "XDG_SESSION_TYPE": "x11"})
        return subprocess.call(
            [
                "xvfb-run",
                "-a",
                sys.executable,
                str(Path(__file__).resolve()),
                "--output-dir",
                str(output),
                "--inside-private-display",
            ],
            env=env,
        )
    with sync_playwright() as playwright:
        results = []
        for browser in ("chromium", "firefox"):
            for scope in ("PROFILE", "ACCOUNT"):
                result = _case(playwright, browser, scope)
                results.append(result)
                print(
                    json.dumps({"browser": browser, "scope": scope, "passed": result["passed"]}),
                    flush=True,
                )
    report = {"cases": results, "passed": sum(item["passed"] for item in results)}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": len(results),
                "passed": report["passed"],
                "report": str(output / "report.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

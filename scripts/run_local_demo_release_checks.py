"""Real Chrome/Firefox checks of the disposable localhost demo.

Run: uv run python scripts/run_local_demo_release_checks.py --output-dir /tmp/cg-demo-release
The script starts only fresh localhost CLI processes and a private Xvfb display.
Its JSON report excludes source text, form proofs, account cookies and identifiers.
"""

from __future__ import annotations

import argparse
import ctypes
import http.client
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

SOURCE = "- 합성 테스트 경험\n- 합성 문서 작성"
SCRIPT_SOURCE = "- <script>window.__cg_demo_executed = true</script>"


def _check(value, name, checks):
    if not value:
        raise AssertionError(name)
    checks.append(name)


def _new_demo(folder):
    env = os.environ.copy()
    env["TMPDIR"] = str(folder)
    process = subprocess.Popen(
        [sys.executable, "-m", "careerground.local_demo", "--port", "0"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 20
        line = ""
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("local demo CLI exited before readiness")
            ready, _, _ = select.select([process.stdout], [], [], 0.2)
            if ready:
                line = process.stdout.readline()
                break
        match = re.search(r"http://127\.0\.0\.1:(\d+)/demo", line)
        if match is None:
            raise RuntimeError("local demo CLI did not announce localhost readiness")
        port = int(match.group(1))
        for _ in range(50):
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                connection.request("GET", "/demo")
                response = connection.getresponse()
                response.read()
                connection.close()
                if response.status == 200:
                    return process, port
            except (ConnectionError, OSError):
                pass
            time.sleep(0.05)
        raise RuntimeError("local demo CLI did not accept localhost requests")
    except BaseException:
        _stop_demo(process)
        raise


def _stop_demo(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
    for stream in (process.stdout, process.stderr):
        if stream:
            stream.close()


def _focus(page, selector, checks):
    target = page.locator(selector)
    _check(target.count() == 1 and target.is_visible(), f"visible {selector}", checks)
    # The main landmark has tabindex=-1; start at it, then use real Tab keys.
    page.locator("main").focus()
    for _ in range(90):
        if target.evaluate("el => document.activeElement === el"):
            _check(True, f"keyboard focus {selector}", checks)
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"Tab cannot reach {selector}")


def _select(page, selector, value, checks):
    _focus(page, selector, checks)
    for _ in range(8):
        if page.locator(selector).input_value() == value:
            return
        page.keyboard.press("ArrowDown")
    raise AssertionError(f"keyboard select cannot reach {value}")


def _type(page, selector, value, checks):
    _focus(page, selector, checks)
    page.keyboard.insert_text(value)
    _check(page.locator(selector).input_value() == value, f"typed {selector}", checks)


def _toggle(page, selector, checks):
    _focus(page, selector, checks)
    page.keyboard.press("Space")
    _check(page.locator(selector).is_checked(), f"keyboard checked {selector}", checks)


def _submit(page, text, checks):
    button = page.get_by_role("button", name=text)
    _check(button.count() == 1, f"named button {text}", checks)
    _focus(page, f"button:has-text('{text}')", checks)
    # Locator.press waits for the navigation initiated by the real Enter key.
    # Invalid forms remain on the current document without a fixed sleep.
    button.press("Enter", no_wait_after=False)
    page.wait_for_load_state("load")


def _audit(page, title, checks):
    _check(page.locator("html").get_attribute("lang") == "ko", f"{title} language", checks)
    _check(page.get_by_role("main").count() == 1, f"{title} main landmark", checks)
    _check(page.get_by_role("heading", name=title, level=1).count() == 1, f"{title} h1", checks)
    _check(
        page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
        f"{title} no horizontal overflow",
        checks,
    )
    _check("main" in page.locator("body").aria_snapshot(), f"{title} accessibility tree", checks)


def _native_zoom(page, browser_name, checks):
    if not shutil.which("xwininfo"):
        raise RuntimeError("xwininfo needed for private native zoom")
    windows = subprocess.run(
        ["xwininfo", "-root", "-tree"], check=True, capture_output=True, text=True
    ).stdout
    pattern = (
        r'^\s*(0x[0-9a-f]+) "[^"]* - (?:Google Chrome|Chromium)"'
        if browser_name == "chromium"
        else r'^\s*(0x[0-9a-f]+) "[^"]+": \("Navigator"'
    )
    match = re.search(pattern, windows, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"private {browser_name} X11 browser window not found")
    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("private X11 display unavailable")
    try:
        x11.XSetInputFocus(display, int(match.group(1), 16), 1, 0)
        x11.XFlush(display)
        time.sleep(0.2)
        before = page.evaluate("({width: innerWidth, dpr: devicePixelRatio})")
        control = x11.XKeysymToKeycode(display, 0xFFE3)
        equal = x11.XKeysymToKeycode(display, ord("="))
        for _ in range(12):
            for key, pressed in ((control, 1), (equal, 1), (equal, 0), (control, 0)):
                xtst.XTestFakeKeyEvent(display, key, pressed, 0)
            x11.XFlush(display)
            time.sleep(0.16)
            if page.evaluate("innerWidth") <= before["width"] / 2:
                break
        page.wait_for_timeout(250)
        after = page.evaluate("({width: innerWidth, dpr: devicePixelRatio})")
        width_ratio = before["width"] / after["width"]
        dpr_ratio = after["dpr"] / before["dpr"]
        _check(
            before["width"] >= 1200
            and 1.99 <= width_ratio <= 2.01
            and (browser_name == "firefox" or 1.99 <= dpr_ratio <= 2.01),
            f"{browser_name} native 200 percent browser zoom",
            checks,
        )
        _check(
            page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
            f"{browser_name} native zoom no horizontal overflow",
            checks,
        )
        return {
            "before": before,
            "after": after,
            "width_ratio": width_ratio,
            "dpr_ratio": dpr_ratio,
        }
    finally:
        x11.XCloseDisplay(display)


def _case(playwright, browser_name, scope):
    checks = []
    external = []
    with tempfile.TemporaryDirectory(prefix="cg-demo-release-") as private:
        folder = Path(private)
        process, port = _new_demo(folder)
        browser = None
        try:
            browser_type = getattr(playwright, browser_name)
            args = (
                ["--ozone-platform=x11", "--disable-background-networking"]
                if browser_name == "chromium"
                else []
            )
            executable = (
                shutil.which("google-chrome")
                or shutil.which("chromium")
                or browser_type.executable_path
                if browser_name == "chromium"
                else browser_type.executable_path
            )
            if browser_name == "firefox" and not Path(executable).is_file():
                # An older cached Playwright Firefox is usable in local checkouts.
                cache = Path(
                    os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright")
                )
                candidates = sorted(cache.glob("firefox-*/firefox/firefox"), reverse=True)
                if candidates:
                    executable = str(candidates[0])
            browser = browser_type.launch(headless=False, args=args, executable_path=executable)
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
            _audit(page, "CareerGround 로컬 체험", checks)
            zoom = _native_zoom(page, browser_name, checks)
            _audit(page, "CareerGround 로컬 체험", checks)
            _check(page.get_by_label("체험할 합성 계정").count() == 1, "account label", checks)
            _select(page, "#account", "a", checks)
            _submit(page, "합성 계정으로 시작", checks)
            _check(
                "선택된 합성 계정: A" in page.locator("main").inner_text(),
                "selected account A",
                checks,
            )

            # Server error recovery remains keyboard reachable.
            response = page.goto(origin + "/profile/not-an-id/1")
            _check(response.status == 404, "missing profile returns 404", checks)
            _check(page.get_by_role("alert").count() == 1, "error alert", checks)
            # Browser autofocus can finish after the navigation load event.
            expect(page.locator("main")).to_be_focused(timeout=10000)
            checks.append("error focuses main")
            _focus(page, "p a[href='/profiling/start']", checks)
            page.keyboard.press("Enter")
            page.wait_for_url("**/profiling/start", timeout=10000)
            _check(page.url.endswith("/profiling/start"), "error recovery link", checks)

            page.goto(origin + "/demo/jd-analysis")
            _audit(page, "JD 모의 분석", checks)
            _check(
                page.get_by_label(re.compile("합성 JD 요구 문구")).count() == 1,
                "JD textarea label",
                checks,
            )
            _type(page, "#source_text", SCRIPT_SOURCE, checks)
            _submit(page, "모의 요구와 원문 위치 확인", checks)
            _audit(page, "모의 JD 요구 직접 확인", checks)
            _check(
                page.evaluate("window.__cg_demo_executed === undefined"),
                "JD script not executed",
                checks,
            )
            _check(
                "<script>" in page.locator("blockquote").first.inner_text(),
                "JD script text escaped",
                checks,
            )
            page.goto(origin + "/demo/jd-analysis")
            _type(page, "#source_text", SOURCE, checks)
            _submit(page, "모의 요구와 원문 위치 확인", checks)
            _audit(page, "모의 JD 요구 직접 확인", checks)
            blocks = page.locator("blockquote").all_inner_texts()
            _check(blocks == ["합성 테스트 경험", "합성 문서 작성"], "exact JD order", checks)
            _check(
                page.locator("li").filter(has_text="원문 위치:").count() == 2,
                "JD source positions",
                checks,
            )
            _check(
                page.get_by_label(re.compile("표시한 정확한 문구")).count() == 1,
                "JD consent label",
                checks,
            )
            _submit(page, "선택 발췌 저장 승인", checks)
            _check(
                page.get_by_role("heading", name="모의 JD 요구 직접 확인").count() == 1,
                "JD unchecked blocked",
                checks,
            )
            _toggle(page, "input[name='confirm']", checks)
            _submit(page, "선택 발췌 저장 승인", checks)
            _check(
                re.fullmatch(r"/jd/[0-9a-f-]{36}", urlsplit(page.url).path) is not None,
                "JD stored after explicit consent",
                checks,
            )

            page.goto(origin + "/demo/deletion")
            _audit(page, "합성 데이터 삭제 체험", checks)
            _check(page.get_by_label("삭제할 범위").count() == 1, "deletion scope label", checks)
            _select(page, "#scope", scope, checks)
            _submit(page, "삭제 영향 확인", checks)
            _audit(page, "삭제 영향 직접 확인", checks)
            _check(
                "JD 선택 발췌" in page.locator("main").inner_text(),
                "JD deletion impact count",
                checks,
            )
            _check(
                SOURCE not in page.locator("main").inner_text(),
                "impact excludes source text",
                checks,
            )
            _check(
                page.get_by_label("합성 계정 확인 문구").count() == 1, "mock phrase label", checks
            )
            _submit(page, "모의 재인증 후 최종 확인", checks)
            _check(
                page.get_by_role("heading", name="삭제 영향 직접 확인").count() == 1,
                "unchecked deletion preview blocked",
                checks,
            )
            _toggle(page, "input[name='acknowledged_impact']", checks)
            _toggle(page, "input[name='mock_reauthenticated']", checks)
            _type(page, "#mock_phrase", "합성 계정 A", checks)
            _submit(page, "모의 재인증 후 최종 확인", checks)
            _audit(page, "모의 재인증 후 삭제 확인", checks)
            _submit(page, "로컬 합성 데이터 삭제 실행", checks)
            _check(
                page.get_by_role("heading", name="모의 재인증 후 삭제 확인").count() == 1,
                "final unchecked deletion blocked",
                checks,
            )
            _toggle(page, "input[name='confirm']", checks)
            _submit(page, "로컬 합성 데이터 삭제 실행", checks)
            _audit(page, "합성 삭제 상태", checks)
            status = page.locator("main").inner_text()
            _check(
                "FOUNDATION_ONLY" in status and "DELETING" in status,
                "honest deletion status",
                checks,
            )
            _check("ERASED" not in status, "no erased claim", checks)
            _check(
                page.locator("#known-local-done").count() == 1
                and page.locator("#unverified").count() == 1,
                "bounded status aggregates",
                checks,
            )
            _check(SOURCE not in status, "status excludes source text", checks)
            if scope == "ACCOUNT":
                response = page.goto(origin + "/profiling/start")
                _check(response.status == 401, "deleted account A blocked", checks)
                page.goto(origin + "/demo")
                _select(page, "#account", "b", checks)
                _submit(page, "합성 계정으로 시작", checks)
                _check(
                    "선택된 합성 계정: B" in page.locator("main").inner_text(),
                    "account B selectable",
                    checks,
                )
                response = page.goto(origin + "/profiling/start")
                _check(response.status == 200, "account B remains usable", checks)
            _check(not external, "only localhost browser requests", checks)
            version = browser.version
            context.close()
            browser.close()
            browser = None
        finally:
            if browser:
                browser.close()
            _stop_demo(process)
        _check(
            not list(folder.glob("careerground-local-demo-*")),
            "CLI temporary data removed on SIGINT",
            checks,
        )
    return {
        "browser": browser_name,
        "browser_version": version,
        "scope": scope,
        "checks": checks,
        "passed": len(checks),
        "external_request_count": len(external),
        "native_zoom": zoom,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--inside-private-display", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.inside_private_display:
        if not shutil.which("xvfb-run"):
            parser.error("xvfb-run required for isolated native zoom")
        env = os.environ.copy()
        env.pop("WAYLAND_DISPLAY", None)
        env.update({"GDK_BACKEND": "x11", "XDG_SESSION_TYPE": "x11"})
        command = [
            "xvfb-run",
            "-a",
            sys.executable,
            str(Path(__file__).resolve()),
            "--output-dir",
            str(output),
            "--inside-private-display",
        ]
        return subprocess.call(command, env=env)
    results = []
    with sync_playwright() as playwright:
        for browser in ("chromium", "firefox"):
            for scope in ("PROFILE", "ACCOUNT"):
                results.append(_case(playwright, browser, scope))
    report = {"cases": results, "passed": sum(item["passed"] for item in results)}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": len(results),
                "passed": report["passed"],
                "report": str(output / "report.json"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

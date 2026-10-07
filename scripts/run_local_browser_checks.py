"""Exercise synthetic UI with keyboard input in a fresh local browser context.

Run: uv run python scripts/run_local_browser_checks.py --output-dir /tmp/cg-browser-checks
Firefox: uv run python scripts/run_local_browser_checks.py --browser firefox --output-dir /tmp/cg-firefox
Native Chrome zoom: env -u WAYLAND_DISPLAY XDG_SESSION_TYPE=x11 xvfb-run -a \
    uv run python scripts/run_local_browser_checks.py --native-zoom --output-dir /tmp/cg-zoom
No application credentials, external hosts or existing browser profile are used.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from ctypes import CDLL, c_char_p, c_int, c_uint, c_ulong, c_void_p
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from careerground.storage.graph_models import ClaimAssessment, ClaimUseReview
from careerground.storage.models import Account, Base, CareerProfile
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app


def _native_chrome_zoom(page) -> dict:
    """Send browser chrome zoom keys on a private Xvfb display, then measure it."""
    if not shutil.which("xwininfo"):
        raise RuntimeError("native zoom check needs xwininfo on a private X11 display")
    windows = subprocess.run(
        ["xwininfo", "-root", "-tree"], capture_output=True, text=True, check=True
    ).stdout
    match = re.search(r'^\s*(0x[0-9a-f]+) "[^"]* - Google Chrome"', windows, re.MULTILINE)
    if match is None:
        raise RuntimeError("private Chrome window not found; run under Xvfb with Wayland unset")
    x11 = CDLL("libX11.so.6")
    xtst = CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XOpenDisplay.restype = c_void_p
    x11.XKeysymToKeycode.argtypes = [c_void_p, c_ulong]
    x11.XKeysymToKeycode.restype = c_uint
    x11.XSetInputFocus.argtypes = [c_void_p, c_ulong, c_int, c_ulong]
    x11.XFlush.argtypes = [c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [c_void_p, c_uint, c_int, c_ulong]
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("private X11 display unavailable")
    try:
        x11.XSetInputFocus(display, int(match.group(1), 16), 1, 0)
        x11.XFlush(display)
        time.sleep(0.2)
        before = page.evaluate("({dpr: devicePixelRatio, width: innerWidth})")
        control = x11.XKeysymToKeycode(display, 0xFFE3)
        equal = x11.XKeysymToKeycode(display, ord("="))
        for _ in range(8):
            for key, pressed in ((control, 1), (equal, 1), (equal, 0), (control, 0)):
                xtst.XTestFakeKeyEvent(display, key, pressed, 0)
            x11.XFlush(display)
            time.sleep(0.15)
            if page.evaluate("devicePixelRatio") >= 2:
                break
        page.wait_for_timeout(300)
        after = page.evaluate("({dpr: devicePixelRatio, width: innerWidth})")
        return {"before": before, "after": after}
    finally:
        x11.XCloseDisplay.argtypes = [c_void_p]
        x11.XCloseDisplay(display)


def run(output: Path, *, browser_name: str = "chromium", native_zoom: bool = False) -> dict:
    if native_zoom and browser_name != "chromium":
        raise ValueError("native browser zoom check currently supports Chrome only")
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    external = []
    with tempfile.TemporaryDirectory(prefix="careerground-browser-") as directory:
        engine = create_engine(
            "sqlite+pysqlite:///" + str(Path(directory) / "synthetic.sqlite"), hide_parameters=True
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as session:
            session.add(Account(id="synthetic-browser-account"))
            session.flush()
            session.add(
                CareerProfile(
                    id="synthetic-browser-profile",
                    account_id="synthetic-browser-account",
                    version=0,
                )
            )
            session.commit()
        secret = b"browser-only-synthetic-signing-secret-32-bytes"
        app = build_synthetic_review_app(
            session_factory=sessions,
            authenticate_browser=lambda _request, _response: TrustedBrowserIdentity(
                "synthetic-browser-account", "synthetic-browser-session"
            ),
            review_signing_secret=secret,
            presentation_signing_secret=secret,
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if time.monotonic() > deadline or not thread.is_alive():
                    raise RuntimeError("local browser server did not start")
                time.sleep(0.02)
            with sync_playwright() as playwright:
                executable = (
                    shutil.which("google-chrome") or shutil.which("chromium")
                    if browser_name == "chromium"
                    else None
                )
                browser = getattr(playwright, browser_name).launch(
                    headless=not native_zoom,
                    executable_path=executable,
                    args=["--ozone-platform=x11"] if native_zoom else [],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900}, accept_downloads=True
                )

                def local_only(route):
                    if urlsplit(route.request.url).netloc == f"127.0.0.1:{port}":
                        route.continue_()
                    else:
                        external.append(route.request.url)
                        route.abort()

                context.route("**/*", local_only)
                page = context.new_page()
                cdp = context.new_cdp_session(page) if browser_name == "chromium" else None

                def check(condition, name):
                    if not condition:
                        raise AssertionError(name)
                    checks.append(name)

                def audit(name):
                    check(page.locator("h1").count() == 1, name + ": heading")
                    check(page.locator("main#main-content").count() == 1, name + ": landmark")
                    check(page.locator("html").get_attribute("lang") == "ko", name + ": language")
                    if cdp is not None:
                        tree = cdp.send("Accessibility.getFullAXTree")
                        nodes = [node for node in tree["nodes"] if not node.get("ignored")]
                        check(
                            any(node.get("role", {}).get("value") == "main" for node in nodes),
                            name + ": accessibility main",
                        )
                        controls = [
                            node
                            for node in nodes
                            if node.get("role", {}).get("value")
                            in {"button", "checkbox", "textbox", "combobox"}
                        ]
                        check(
                            all(node.get("name", {}).get("value") for node in controls),
                            name + ": accessible control names",
                        )
                    else:
                        snapshot = page.locator("body").aria_snapshot()
                        check("- main:" in snapshot, name + ": accessibility main")
                        controls = re.findall(
                            r'^\s*- (?:button|checkbox|textbox|combobox)(?: "([^"]*)")?',
                            snapshot,
                            re.MULTILINE,
                        )
                        visible_controls = page.locator(
                            "button, input:not([type=hidden]), select, textarea"
                        ).evaluate_all(
                            "els => els.filter(el => !!(el.offsetWidth || el.offsetHeight)).length"
                        )
                        check(
                            len(controls) >= visible_controls,
                            name + ": accessibility controls represented",
                        )
                        check(all(controls), name + ": accessible control names")
                    check(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                        name + ": no horizontal page overflow",
                    )
                    viewport = page.viewport_size
                    original_font = page.evaluate("document.documentElement.style.fontSize")
                    for width, height, label in ((320, 800, "320px"), (640, 450, "200% reflow")):
                        page.set_viewport_size({"width": width, "height": height})
                        check(
                            page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                            name + ": " + label,
                        )
                    page.evaluate("document.documentElement.style.fontSize = '200%'")
                    check(
                        page.locator("html").evaluate("el => getComputedStyle(el).fontSize")
                        == "32px",
                        name + ": enlarged text",
                    )
                    check(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                        name + ": 200% text reflow",
                    )
                    page.evaluate(
                        "value => document.documentElement.style.fontSize = value", original_font
                    )
                    page.set_viewport_size(viewport)

                def tab_to(locator):
                    check(locator.count() == 1, "unique keyboard target")
                    for _ in range(80):
                        if locator.evaluate("el => el === document.activeElement"):
                            check(
                                locator.evaluate(
                                    "el => getComputedStyle(el).outlineStyle !== 'none'"
                                ),
                                "visible keyboard focus",
                            )
                            return
                        page.keyboard.press("Tab")
                    raise AssertionError("keyboard target unreachable")

                def activate(locator, *, navigation=True):
                    tab_to(locator)
                    if navigation:
                        with page.expect_navigation(wait_until="domcontentloaded"):
                            page.keyboard.press("Enter")
                    else:
                        page.keyboard.press("Enter")

                def link(pattern):
                    hrefs = page.locator("a[href]").evaluate_all(
                        "els => els.map(el => el.getAttribute('href'))"
                    )
                    matches = [href for href in hrefs if re.fullmatch(pattern, href)]
                    check(len(matches) == 1, "unique journey link: " + pattern)
                    activate(page.locator(f'a[href="{matches[0]}"]'))

                def type_field(name, value):
                    locator = page.locator(f'[name="{name}"]')
                    tab_to(locator)
                    page.keyboard.insert_text(value)

                def confirm(name="confirm"):
                    locator = page.locator(f'input[type="checkbox"][name="{name}"]')
                    tab_to(locator)
                    page.keyboard.press("Space")
                    check(locator.is_checked(), "keyboard checkbox: " + name)

                def submit():
                    activate(page.locator('button[type="submit"]'))

                page.goto(origin + "/profiling/start")
                audit("start desktop")
                page.keyboard.press("Tab")
                check(
                    page.locator('a[href="#main-content"]').evaluate(
                        "el => el === document.activeElement"
                    ),
                    "skip link is first Tab",
                )
                page.keyboard.press("Enter")
                check(
                    page.locator("main").evaluate("el => el === document.activeElement"),
                    "skip link focuses main",
                )
                before = page.url
                activate(page.locator('button[type="submit"]'), navigation=False)
                check(
                    page.url == before
                    and not page.locator('input[name="confirm"]').evaluate(
                        "el => el.validity.valid"
                    ),
                    "unchecked confirmation prevents submission",
                )
                confirm()
                submit()
                audit("workspace")
                link(r"/profiling/[^/]+/input")
                audit("input")
                type_field("content", "- 합성 기능의 테스트를 작성했다.")
                confirm()
                submit()
                audit("bullet draft")
                type_field("scope_key", "synthetic-feature")
                confirm()
                submit()
                link(r"/profiling/.+/prepare")
                audit("prepare")
                confirm()
                submit()
                audit("fact review")
                select_box = page.locator("select")
                tab_to(select_box)
                # Native selection through keyboard, with no Playwright select_option shortcut.
                for _ in range(6):
                    if select_box.input_value() == "ACCEPT":
                        break
                    page.keyboard.press("ArrowDown")
                check(select_box.input_value() == "ACCEPT", "keyboard fact decision")
                confirm()
                submit()
                audit("fact result")
                with sessions() as session:
                    assessment = session.scalar(select(ClaimAssessment))
                    check(
                        assessment.knowledge_status == "USER_CONFIRMED"
                        and assessment.usage_policy == "REVIEW_REQUIRED",
                        "fact approval preserves separate use requirement",
                    )
                link(r"/profile/[^/]+/1")
                audit("profile")
                link(r"/profile/[^/]+/1/claim/[^/]+")
                audit("evidence")
                link(r"/profile/.+/use-review")
                audit("use review")
                confirm("confirm_consistency")
                confirm("confirm_use")
                submit()
                audit("use result")
                link(r"/jd/new")
                audit("JD paste")
                type_field("selected_text", "- 테스트 작성 경험")
                confirm()
                submit()
                audit("JD analysis")
                link(r"/jd/[^/]+/mapping/2")
                audit("mapping")
                link(r"/jd/.+/link/.+")
                audit("potential link")
                confirm()
                submit()
                link(r"/jd/[^/]+/draft/2")
                audit("R1 selection")
                confirm("claim_id")
                confirm()
                submit()
                trace_url = page.url
                audit("trace")
                link(r"/resume/[^/]+/wording")
                audit("wording")
                confirm()
                submit()
                page.goto(trace_url)
                audit("reviewed trace")
                page.screenshot(path=str(output / "trace-desktop.png"), full_page=True)
                link(r"/resume/[^/]+/export/MARKDOWN")
                audit("export")
                confirm()
                tab_to(page.locator('button[type="submit"]'))
                with page.expect_download() as download_info:
                    page.keyboard.press("Enter")
                download = download_info.value
                download.save_as(str(output / "synthetic-resume.md"))
                content = Path(download.path()).read_text()
                check(
                    re.sub(r"\\(.)", r"\1", content) == "- 합성 기능의 테스트를 작성했다.\n",
                    "exact approved Markdown download",
                )
                with sessions() as session:
                    check(
                        session.get(CareerProfile, "synthetic-browser-profile").version == 2,
                        "profile version 2",
                    )
                    check(
                        session.scalar(select(ClaimUseReview)) is not None,
                        "separate use journal exists",
                    )
                page.goto(trace_url)
                page.set_viewport_size({"width": 320, "height": 800})
                audit("trace 320 CSS pixels")
                page.screenshot(path=str(output / "trace-mobile.png"), full_page=True)
                # Equivalent layout viewport for 200% browser zoom on a 1280px window.
                page.set_viewport_size({"width": 640, "height": 450})
                audit("trace 200 percent reflow equivalent")
                # Also enlarge actual text to 200%; temporary automation style property only.
                page.evaluate("document.documentElement.style.fontSize = '200%'")
                check(
                    page.locator("html").evaluate("el => getComputedStyle(el).fontSize") == "32px",
                    "text is actually 200 percent",
                )
                audit("trace 200 percent text")
                page.screenshot(path=str(output / "trace-large-text.png"), full_page=True)
                zoom_metrics = None
                if native_zoom:
                    page.goto(trace_url)
                    page.set_viewport_size({"width": 1280, "height": 900})
                    zoom_metrics = _native_chrome_zoom(page)
                    check(
                        zoom_metrics["before"]["dpr"] == 1
                        and zoom_metrics["after"]["dpr"] >= 1.9
                        and zoom_metrics["after"]["width"] <= 640,
                        "native Chrome zoom reaches at least 200 percent",
                    )
                    check(
                        page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                        "native Chrome 200 percent no horizontal page overflow",
                    )
                    page.screenshot(path=str(output / "trace-native-zoom.png"), full_page=True)
                page.goto(origin + "/profile/synthetic-browser-profile/not-an-integer")
                check(page.locator('[role="alert"]').count() == 1, "error alert present")
                check(
                    page.locator("main").evaluate("el => el === document.activeElement"),
                    "error focuses main",
                )
                link(r"/profiling/start")
                audit("error recovery")
                check(not external, "no external requests")
                version = browser.version
                browser.close()
            report = {
                "browser_name": browser_name,
                "browser": version,
                "checks": checks,
                "passed": len(checks),
                "external_requests": external,
                "native_zoom": zoom_metrics,
                "limits": [
                    "Browser accessibility tree and keyboard checks; no spoken screen reader audit",
                    (
                        "Native Chrome zoom checked in private Xvfb display"
                        if native_zoom
                        else "640px layout tests equivalent 200% reflow; native browser chrome zoom untested"
                    ),
                    "Synthetic SQLite app only; no public endpoint or real identity provider",
                ],
            }
            (output / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            return report
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            engine.dispose()
            if thread.is_alive():
                raise RuntimeError("local browser server did not stop")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--browser", choices=("chromium", "firefox"), default="chromium")
    parser.add_argument("--native-zoom", action="store_true")
    args = parser.parse_args()
    report = run(args.output_dir, browser_name=args.browser, native_zoom=args.native_zoom)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "browser": report["browser"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

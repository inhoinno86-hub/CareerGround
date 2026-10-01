"""Check Orca speech requests on the synthetic CareerGround UI in private Xvfb.

Run: uv run python scripts/run_local_screenreader_checks.py --output-dir /tmp/cg-orca
Creates a temporary D-Bus, AT-SPI bus, X11 display, configuration, browser
profile, and silent Speech Dispatcher socket. No existing desktop audio or
browser profile is used. This checks speech requests, not heard audio quality.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from careerground.storage.models import Account, Base, CareerProfile
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app


def _prepare_private_services(directory: Path) -> dict[str, str]:
    config = directory / "config"
    speech_config = config / "speech-dispatcher"
    (speech_config / "modules").mkdir(parents=True)
    (directory / "cache").mkdir()
    (directory / "data").mkdir()
    (directory / "logs").mkdir()
    socket_path = directory / "runtime" / "speech-dispatcher" / "speechd.sock"
    socket_path.parent.mkdir(parents=True)
    (speech_config / "modules" / "dummy.conf").write_text("")
    (speech_config / "speechd.conf").write_text(
        'CommunicationMethod "unix_socket"\n'
        f'SocketPath "{socket_path}"\n'
        "LogLevel 3\n"
        f'LogDir "{directory / "logs"}"\n'
        f'CustomLogFile "protocol" "{directory / "protocol.log"}"\n'
        'AddModule "dummy" "/usr/lib/speech-dispatcher-modules/sd_dummy" "dummy.conf"\n'
        "DefaultModule dummy\n"
    )
    env = os.environ.copy()
    env.update(
        {
            "XDG_RUNTIME_DIR": str(directory / "runtime"),
            "XDG_CONFIG_HOME": str(config),
            "XDG_CACHE_HOME": str(directory / "cache"),
            "XDG_DATA_HOME": str(directory / "data"),
            "GDK_BACKEND": "x11",
            "XDG_SESSION_TYPE": "x11",
            "SPEECHD_SOCKET": str(socket_path),
            "PULSE_SERVER": "unix:" + str(directory / "absent-pulse.sock"),
        }
    )
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("AT_SPI_BUS_ADDRESS", None)
    return env


def _utterances(protocol_path: Path) -> list[str]:
    if not protocol_path.exists():
        return []
    utterances = []
    for line in protocol_path.read_text(errors="replace").splitlines():
        match = re.search(r"DATA:\|(<speak>.*</speak>)", line)
        if match is None:
            continue
        try:
            utterances.append("".join(ET.fromstring(match.group(1)).itertext()).strip())
        except ET.ParseError:
            continue
    return utterances


def _inside(output: Path) -> dict:
    directory = Path(os.environ["XDG_RUNTIME_DIR"]).parent
    socket_path = directory / "runtime" / "speech-dispatcher" / "speechd.sock"
    speech_config = directory / "config" / "speech-dispatcher"
    speech = subprocess.Popen(
        ["speech-dispatcher", "-s", "-C", str(speech_config), "-S", str(socket_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    orca = None
    try:
        for _ in range(50):
            if socket_path.exists():
                break
            if speech.poll() is not None:
                raise RuntimeError("private Speech Dispatcher exited during startup")
            time.sleep(0.1)
        if not socket_path.exists():
            raise RuntimeError("private Speech Dispatcher socket unavailable")
        database = create_engine(
            "sqlite+pysqlite:///" + str(directory / "synthetic.sqlite"), hide_parameters=True
        )
        Base.metadata.create_all(database)
        sessions = sessionmaker(bind=database)
        with sessions() as session:
            session.add(Account(id="synthetic-orca-account"))
            session.flush()
            session.add(
                CareerProfile(
                    id="synthetic-orca-profile", account_id="synthetic-orca-account", version=0
                )
            )
            session.commit()
        secret = b"browser-only-synthetic-signing-secret-32-bytes"
        app = build_synthetic_review_app(
            session_factory=sessions,
            authenticate_browser=lambda _request, _response: TrustedBrowserIdentity(
                "synthetic-orca-account", "synthetic-orca-session"
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
                    raise RuntimeError("synthetic browser server did not start")
                time.sleep(0.02)
            orca = subprocess.Popen(["orca"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.8)
            if orca.poll() is not None:
                raise RuntimeError("Orca exited before private browser startup")
            external = []
            checks = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=False,
                    executable_path=shutil.which("google-chrome"),
                    args=[
                        "--ozone-platform=x11",
                        "--force-renderer-accessibility",
                        "--disable-translate",
                        "--lang=ko-KR",
                        "--disable-background-networking",
                    ],
                )
                context = browser.new_context(
                    viewport={"width": 1024, "height": 768}, locale="ko-KR"
                )

                def local_only(route):
                    if urlsplit(route.request.url).netloc == f"127.0.0.1:{port}":
                        route.continue_()
                    else:
                        external.append(route.request.url)
                        route.abort()

                context.route("**/*", local_only)
                page = context.new_page()

                def await_speech(phrase, *, timeout=4.0):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if any(phrase in item for item in _utterances(directory / "protocol.log")):
                            checks.append(f"Orca speech request: {phrase}")
                            return
                        if orca.poll() is not None:
                            raise RuntimeError("Orca exited before expected speech request")
                        time.sleep(0.1)
                    raise AssertionError(f"Orca did not send speech request for {phrase!r}")

                def tab_to(locator):
                    for _ in range(40):
                        if locator.evaluate("el => el === document.activeElement"):
                            return
                        page.keyboard.press("Tab")
                    raise AssertionError("Orca keyboard target unreachable")

                try:
                    page.goto(origin + "/profiling/start")
                    await_speech("경력 정리 시작")
                    page.keyboard.press("Tab")
                    assert page.locator('a[href="#main-content"]').evaluate(
                        "el => el === document.activeElement"
                    )
                    checks.append("skip link focused by keyboard")
                    await_speech("본문으로 바로가기")
                    tab_to(page.locator('input[name="confirm"]'))
                    page.keyboard.press("Space")
                    tab_to(page.locator('button[type="submit"]'))
                    await_speech("새 경력 정리 시작")
                    with page.expect_navigation(wait_until="domcontentloaded"):
                        page.keyboard.press("Enter")
                    assert page.locator("h1").inner_text() == "프로파일링 상태"
                    checks.append("session started by keyboard with Orca active")
                    await_speech("CareerGround 프로파일링 상태")
                    if orca.poll() is not None:
                        raise RuntimeError("Orca exited before error recovery check")
                    page.goto(origin + "/profile/synthetic-orca-profile/not-an-integer")
                    assert page.locator("main").evaluate("el => el === document.activeElement")
                    checks.append("error recovery focus in Orca browser")
                    await_speech(page.locator("h1").inner_text())
                    recovery = page.locator('a[href="/profiling/start"]')
                    tab_to(recovery)
                    await_speech(recovery.inner_text())
                    with page.expect_navigation(wait_until="domcontentloaded"):
                        page.keyboard.press("Enter")
                    assert page.locator("h1").inner_text() == "경력 정리 시작"
                    checks.append("error recovery link activated by keyboard")
                    browser_version = browser.version
                finally:
                    browser.close()
            assert not external, "unexpected external browser request"
            checks.append("browser requests stayed on loopback")
            utterances = _utterances(directory / "protocol.log")
            orca_version = subprocess.run(
                ["orca", "--version"], capture_output=True, text=True, check=True
            ).stdout.strip()
            speech_version = subprocess.run(
                ["speech-dispatcher", "--version"], capture_output=True, text=True, check=True
            ).stdout.strip()
            report = {
                "browser": browser_version,
                "orca": orca_version,
                "speech_dispatcher": speech_version,
                "passed": len(checks),
                "checks": checks,
                "speech_requests": utterances,
                "external_requests": external,
                "limits": [
                    "Orca speech requests were observed through AT-SPI and a private silent Speech Dispatcher; no audible voice quality or human comprehension assessment",
                    "Synthetic SQLite UI and temporary Xvfb display only",
                ],
            }
            output.mkdir(parents=True, exist_ok=True)
            (output / "screenreader-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            return report
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            database.dispose()
            if thread.is_alive():
                raise RuntimeError("synthetic browser server did not stop")
    finally:
        if orca is not None:
            orca.terminate()
            try:
                orca.wait(timeout=2)
            except subprocess.TimeoutExpired:
                orca.kill()
                orca.wait(timeout=3)
        speech.terminate()
        speech.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--inside-private-display", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside_private_display:
        report = _inside(args.output_dir)
        print(json.dumps({"passed": report["passed"], "browser": report["browser"]}))
        return
    for command in ("dbus-run-session", "xvfb-run", "speech-dispatcher", "orca"):
        if not shutil.which(command):
            raise RuntimeError(f"local Orca check needs {command}")
    with tempfile.TemporaryDirectory(prefix="careerground-screenreader-") as private:
        environment = _prepare_private_services(Path(private))
        process = subprocess.run(
            [
                "dbus-run-session",
                "--",
                "xvfb-run",
                "-a",
                sys.executable,
                str(Path(__file__).resolve()),
                "--inside-private-display",
                "--output-dir",
                str(args.output_dir),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(
                "private Orca check failed: " + (process.stderr[-1800:] or process.stdout[-1800:])
            )
        print(process.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    main()

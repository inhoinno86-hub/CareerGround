"""Exercise a private synthetic runtime through the real BrowserOS MCP server.

BrowserOS must already be running. This script opens only its own tabs, uses
accessibility references for inputs, and never invokes an AI provider. Reports
contain aggregate checks; approval proofs and authentication values stay in RAM.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import signal
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class BrowserOSSession(ClientSession):
    async def validate_tool_result(self, name, result):
        # 0.0.162 adds its session metadata to run's otherwise strict output.
        # Validate the advertised payload after removing only that known field.
        if name == "run" and result.structured_content is not None:
            content = dict(result.structured_content)
            if "session" in content:
                if not isinstance(content.pop("session"), str):
                    raise RuntimeError("invalid BrowserOS session metadata")
                result = result.model_copy(update={"structured_content": content})
        await super().validate_tool_result(name, result)


def start_runtime(store: Path, port: int, log):
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "careerground.development_runtime",
            "--state-dir",
            str(store),
            "--port",
            str(port),
        ],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError("synthetic runtime failed to start")
        try:
            with urlopen(f"http://127.0.0.1:{port}/demo", timeout=0.2) as response:
                if response.status == 200:
                    return process
        except OSError:
            time.sleep(0.05)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("synthetic runtime readiness timed out")


def stop_runtime(process):
    if process is not None and process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            raise RuntimeError("synthetic runtime required forced termination") from None
        if process.returncode != 0:
            raise RuntimeError("synthetic runtime did not exit cleanly")


class BrowserChecks:
    def __init__(self, session, output):
        self.session, self.output = session, output
        self.checks = []
        self.tabs = []
        self.settings_page = None

    def check(self, condition, label):
        if not condition:
            raise AssertionError(label)
        self.checks.append(label)

    async def call(self, name, **arguments):
        result = await self.session.call_tool(name, arguments)
        if result.is_error:
            raise RuntimeError(f"BrowserOS tool failed: {name}")
        return result

    @staticmethod
    def text(result):
        text = "\n".join(item.text for item in result.content if item.type == "text")
        if "[UNTRUSTED_PAGE_CONTENT" in text:
            text = text.split("\n", 1)[1].rsplit("\n[END_UNTRUSTED_PAGE_CONTENT", 1)[0]
        return text

    async def evaluate(self, page, code):
        # MCP renders primitive strings as plain text; an object envelope keeps
        # the boundary consistently JSON without guessing text types.
        code = "return {value:await (async()=>{" + code + "})()};"
        return json.loads(self.text(await self.call("evaluate", page=page, code=code)))["value"]

    async def new(self, url):
        text = self.text(await self.call("tabs", action="new", url=url, background=False))
        page = int(re.search(r"opened page (\d+)", text).group(1))
        self.tabs.append(page)
        return page

    async def ref(self, page, pattern):
        text = self.text(await self.call("snapshot", page=page))
        matches = [line for line in text.splitlines() if re.search(pattern, line)]
        if len(matches) != 1:
            raise AssertionError(f"expected one accessibility target: {pattern}")
        return re.search(r"\[ref=(e\d+)\]", matches[0]).group(1)

    async def act(self, page, kind, pattern, **kwargs):
        # BrowserOS 0.0.162's DOM.focus needs a document initialized in the CDP
        # session. Keep this inside BrowserOS MCP; do not substitute Playwright.
        if kind == "focus":
            params = json.dumps(json.dumps({"depth": 0}))
            await self.call(
                "run",
                code=f'await browser.cdpJsonForPage({page}, "DOM.getDocument", {params}); return true;',
            )
        await self.call("act", page=page, kind=kind, ref=await self.ref(page, pattern), **kwargs)

    async def goto(self, page, origin, path):
        await self.call("navigate", page=page, url=origin + path)

    async def submit(self, page, label, selector):
        # Tab activation alone can leave another BrowserOS window in front.
        # Focus the private window through its extension API before native keys.
        origin = await self.evaluate(page, "return location.origin;")
        await self.evaluate(
            self.settings_page,
            f"""
const tabs=await chrome.tabs.query({{url:{json.dumps(origin + "/*")}}});
if(tabs.length!==1) throw new Error('Expected one private synthetic tab');
await chrome.tabs.update(tabs[0].id,{{active:true}});
await chrome.windows.update(tabs[0].windowId,{{focused:true}});
return true;
""",
        )
        await self.call(
            "run",
            code=f'await browser.cdpJsonForPage({page}, "Page.bringToFront", "{{}}"); return true;',
        )
        await self.act(page, "focus", r'button "' + re.escape(label) + r'"')
        focused = await self.evaluate(page, "return document.activeElement?.tagName;")
        self.check(focused == "BUTTON", "keyboard submit focus: " + label)
        marker = str(time.time_ns())
        await self.evaluate(
            page, "globalThis.__cgBrowserOSNavigation=" + json.dumps(marker) + "; return true;"
        )
        # Send a complete native Enter event through BrowserOS's page-scoped
        # CDP tool, including the key codes used for form default activation.
        down = json.dumps(
            json.dumps(
                {
                    "type": "keyDown",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13,
                    "nativeVirtualKeyCode": 13,
                    "text": "\r",
                    "unmodifiedText": "\r",
                }
            )
        )
        up = json.dumps(
            json.dumps(
                {
                    "type": "keyUp",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13,
                    "nativeVirtualKeyCode": 13,
                }
            )
        )
        await self.call(
            "run",
            code=f'await browser.cdpJsonForPage({page}, "Input.dispatchKeyEvent", {down}); await browser.cdpJsonForPage({page}, "Input.dispatchKeyEvent", {up}); return true;',
        )
        for _ in range(100):
            current = await self.evaluate(page, "return globalThis.__cgBrowserOSNavigation??null;")
            if current != marker:
                break
            await asyncio.sleep(0.05)
        else:
            state = await self.evaluate(
                page,
                "return {focused:document.hasFocus(),active:document.activeElement?.tagName,valid:document.activeElement?.form?.checkValidity()};",
            )
            raise AssertionError(f"keyboard form submission did not navigate: {state}")
        await self.call(
            "wait", page=page, **{"for": "selector", "value": selector, "timeout": 10000}
        )

    async def login(self, page, origin, account):
        await self.goto(page, origin, "/demo")
        # Use a private BrowserOS profile when running this script: browser
        # cookies are scoped to a host, and ports do not isolate cookies.
        has_logout = await self.evaluate(
            page,
            "return [...document.querySelectorAll('button')].some(x=>x.innerText.includes('토큰 철회'));",
        )
        if has_logout:
            await self.submit(page, "합성 연결 로그아웃·토큰 철회", "#account")
        await self.act(page, "select", r'combobox "체험할 합성 계정"', value=account)
        await self.submit(page, "합성 계정으로 시작", "nav")
        await self.goto(page, origin, "/demo/mcp")
        result = await self.mcp(page, "get_account_profile", {})
        self.check(
            result.get("id") == "demo-account-" + account, "synthetic account selected: " + account
        )

    async def mcp(self, page, name, arguments, *, allow_error=False):
        await self.act(page, "select", r'combobox "시험할 도구"', value=name)
        await self.act(
            page,
            "fill",
            r'textbox "도구 인자 JSON',
            value=json.dumps(arguments, ensure_ascii=False),
        )
        await self.submit(page, "합성 도구 호출", "#mcp-result, h1")
        for _ in range(50):
            data = await self.evaluate(
                page,
                "return {result:document.querySelector('#mcp-result')?.innerText||null,title:document.querySelector('h1')?.innerText};",
            )
            if data["result"]:
                payload = json.loads(data["result"])["result"]["structuredContent"]
                if "data" not in payload:
                    if allow_error and "error" in payload:
                        return {"error": payload["error"]}
                    raise AssertionError("CareerGround MCP returned a functional error: " + name)
                return payload["data"]
            if data["title"] == "합성 삭제 실행 접수":
                return {"account_erasure_received": True}
            await asyncio.sleep(0.1)
        raise AssertionError("MCP form response did not arrive")

    async def audit(self, page, label):
        data = await self.evaluate(
            page,
            """
return {main:document.querySelectorAll('main').length,h1:document.querySelectorAll('h1').length,
 overflow:document.documentElement.scrollWidth>innerWidth+1,dpr:devicePixelRatio,
 unlabeled:[...document.querySelectorAll('input:not([type=hidden]),textarea,select')]
 .filter(x=>!x.labels?.length&&!x.getAttribute('aria-label')).length,
 nonlocalResources:performance.getEntriesByType('resource').filter(x=>!x.name.startsWith(location.origin+'/')).length};
""",
        )
        self.check(data["main"] == 1 and data["h1"] == 1, label + ": main and heading")
        self.check(not data["overflow"], label + ": no horizontal overflow")
        self.check(data["unlabeled"] == 0, label + ": controls labeled")
        self.check(data["dpr"] == 2, label + ": native 200% zoom")
        self.check(data["nonlocalResources"] == 0, label + ": observed resources local")

    async def http_status(self, page, url):
        # A real top-level navigation sends the tab's cookies without weakening
        # the app's connect-src CSP. Navigation timing exposes its HTTP status.
        await self.call("navigate", page=page, url=url)
        return await self.evaluate(
            page,
            "return performance.getEntriesByType('navigation')[0]?.responseStatus;",
        )

    async def screenshot(self, page, filename):
        # BrowserOS 0.0.162's screenshot tool clips CSS dimensions as DIP at
        # native zoom 2. Capture the full DIP content through its own MCP/CDP
        # tool so the evidence includes the whole rendered page.
        result = await self.call(
            "run",
            code=f"""
const decode=x=>typeof x==='string'?JSON.parse(x):x;
const metrics=decode(await browser.cdpJsonForPage({page},'Page.getLayoutMetrics','{{}}'));
const clip={{...metrics.contentSize,scale:1}};
const params=JSON.stringify({{format:'png',captureBeyondViewport:true,clip}});
const capture=decode(await browser.cdpJsonForPage({page},'Page.captureScreenshot',params));
return {{width:clip.width,height:clip.height,data:capture.data}};
""",
        )
        content = result.structured_content
        if not content or content.get("ok") is not True:
            raise RuntimeError("BrowserOS full-page capture failed")
        value = content["value"]
        if "[UNTRUSTED_PAGE_CONTENT" in value:
            value = value.split("\n", 1)[1].rsplit("\n[END_UNTRUSTED_PAGE_CONTENT", 1)[0]
        capture = json.loads(value)
        png = base64.b64decode(capture["data"], validate=True)
        self.check(
            png[:8] == b"\x89PNG\r\n\x1a\n"
            and struct.unpack(">II", png[16:24]) == (capture["width"], capture["height"]),
            filename + ": full rendered DIP dimensions captured",
        )
        (self.output / filename).write_bytes(png)

    async def case(self, scope):
        before = len(self.checks)
        with tempfile.TemporaryDirectory(prefix="cg-browseros-") as private:
            folder = Path(private)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            process = None
            page = settings = None
            with (folder / "runtime.log").open("wb") as log:
                try:
                    process = await asyncio.to_thread(start_runtime, folder / "store", port, log)
                    page = await self.new(origin + "/demo")
                    settings = await self.new("chrome://browseros/settings")
                    self.settings_page = settings
                    zoom = await self.evaluate(
                        settings,
                        f"""
const tabs=await chrome.tabs.query({{url:{json.dumps(origin + "/*")}}});
for (const tab of tabs) {{await chrome.tabs.setZoomSettings(tab.id,{{mode:'automatic',scope:'per-origin'}}); await chrome.tabs.setZoom(tab.id,2);}}
return {{count:tabs.length,zooms:await Promise.all(tabs.map(tab=>chrome.tabs.getZoom(tab.id)))}};
""",
                    )
                    self.check(
                        zoom["count"] == 1, scope + ": zoom selects one private synthetic tab"
                    )
                    self.check(zoom["zooms"] == [2], scope + ": BrowserOS reports zoom factor 2")
                    await self.login(page, origin, "a")
                    await self.audit(page, scope + " MCP console")
                    metadata = await self.mcp(
                        page, "get_owned_profile_metadata", {"profile_id": "demo-profile-a"}
                    )
                    version = metadata["version"]
                    foreign = await self.mcp(
                        page,
                        "get_owned_profile_metadata",
                        {"profile_id": "demo-profile-b"},
                        allow_error=True,
                    )
                    self.check(
                        foreign.get("found") is False
                        or foreign.get("error", {}).get("code") == "NOT_FOUND",
                        scope + ": A cannot read B profile",
                    )
                    proposal = await self.mcp(
                        page,
                        "analyze_jd",
                        {
                            "profile_id": "demo-profile-a",
                            "profile_version": version,
                            "jd_text": "- 합성 테스트 경험\n- 합성 문서 작성 경험",
                        },
                    )
                    self.check(
                        proposal["canonical_saved"] is False,
                        scope + ": candidate not canonical saved",
                    )
                    after = await self.mcp(
                        page, "get_owned_profile_metadata", {"profile_id": "demo-profile-a"}
                    )
                    self.check(
                        after["version"] == version, scope + ": analysis leaves version unchanged"
                    )
                    database = folder / "store" / "synthetic.sqlite"

                    def rows(sql):
                        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                            return db.execute(sql).fetchall()

                    self.check(
                        rows("SELECT COUNT(*) FROM job_descriptions")[0][0] == 0,
                        scope + ": no JD stored by MCP analysis",
                    )
                    if scope == "PROFILE":
                        await self.goto(page, origin, "/demo/jd-analysis")
                        await self.act(
                            page,
                            "fill",
                            r'textbox "합성 JD 요구 문구',
                            value="- 합성 테스트 경험\n- 합성 문서 작성 경험",
                        )
                        await self.submit(page, "모의 요구와 원문 위치 확인", "blockquote")
                        await self.audit(page, "JD proposal review")
                        await self.screenshot(page, "jd-proposal-native-200.png")
                        text = await self.evaluate(
                            page, "return document.querySelector('main').innerText;"
                        )
                        self.check(
                            "미승인" in text and "NOT_MAPPED" in text,
                            "JD candidate explicitly unapproved and unmapped",
                        )
                        await self.act(page, "check", r'checkbox "표시한 정확한 문구')
                        await self.submit(page, "선택 발췌 저장 승인", "h1")
                        await self.goto(page, origin, "/demo/mcp")
                        metadata = await self.mcp(
                            page, "get_owned_profile_metadata", {"profile_id": "demo-profile-a"}
                        )
                        self.check(
                            metadata["version"] == version, "JD save preserves career fact version"
                        )
                        version = metadata["version"]
                        saved = rows("SELECT source_hash, source_length FROM job_descriptions")
                        self.check(len(saved) == 1, "explicit JD save creates one stored JD")
                        stop_runtime(process)
                        process = await asyncio.to_thread(
                            start_runtime, folder / "store", port, log
                        )
                        await self.login(page, origin, "a")
                        restored = await self.mcp(
                            page, "get_owned_profile_metadata", {"profile_id": "demo-profile-a"}
                        )
                        self.check(
                            restored["version"] == version,
                            "saved JD version persists through process restart",
                        )
                        self.check(
                            rows("SELECT source_hash, source_length FROM job_descriptions")
                            == saved,
                            "saved JD content fingerprint persists through restart",
                        )
                    args = {
                        "scope": scope,
                        "target_id": "demo-account-a" if scope == "ACCOUNT" else "demo-profile-a",
                        "profile_version": version,
                        "idempotency_key": "synthetic_browseros_delete_0001",
                        "approval_receipt": "",
                    }
                    request = await self.mcp(page, "execute_data_deletion", args)
                    self.check(
                        request["status"] == "WAITING",
                        scope + ": model request does not delete",
                    )
                    await self.goto(page, origin, request["confirmation_path"])
                    await self.audit(page, scope + " deletion impact")
                    await self.act(page, "check", r'checkbox "표시한 삭제 범위')
                    await self.act(page, "check", r'checkbox "이 재인증은')
                    await self.act(
                        page, "fill", r'textbox "합성 계정 확인 문구"', value="합성 계정 A"
                    )
                    await self.submit(page, "모의 재인증 후 최종 확인", "input[name=confirm]")
                    await self.audit(page, scope + " final deletion review")
                    await self.act(page, "check", r'checkbox "확인한 범위의')
                    await self.submit(page, "로컬 합성 데이터 삭제 실행", "#approval-receipt")
                    data = await self.evaluate(
                        page,
                        "return {text:document.querySelector('main').innerText,receipt:document.querySelector('#approval-receipt').innerText};",
                    )
                    self.check(
                        "아직 삭제하지 않았습니다" in data["text"],
                        scope + ": browser approval alone does not delete",
                    )
                    self.check(
                        rows("SELECT COUNT(*) FROM deletion_requests")[0][0] == 0,
                        scope + ": browser proof has not created a deletion request",
                    )
                    receipt = data["receipt"]
                    await self.goto(page, origin, "/demo/mcp")
                    result = await self.mcp(
                        page, "execute_data_deletion", {**args, "approval_receipt": receipt}
                    )
                    self.check(
                        result.get("account_erasure_received")
                        if scope == "ACCOUNT"
                        else result["status"] == "DELETING",
                        scope + ": same connection consumes approval",
                    )
                    receipt = ""
                    self.check(
                        rows("SELECT scope,target_id,status FROM deletion_requests")
                        == [(scope, args["target_id"], "DELETING")],
                        scope + ": exact local deletion request is recorded",
                    )
                    self.check(
                        rows("SELECT COUNT(*) FROM job_descriptions")[0][0] == 0,
                        scope + ": local JD data erased",
                    )
                    if scope == "PROFILE":
                        erased = await self.mcp(
                            page,
                            "get_owned_profile_metadata",
                            {"profile_id": "demo-profile-a"},
                            allow_error=True,
                        )
                        self.check(
                            erased.get("found") is False
                            or erased.get("error", {}).get("code") == "NOT_FOUND",
                            "erased profile cannot be read",
                        )
                    await self.goto(page, origin, "/demo/deletion/status")
                    await self.audit(page, scope + " minimal deletion status")
                    await self.screenshot(page, scope.lower() + "-status-native-200.png")
                    status_text = await self.evaluate(
                        page, "return document.querySelector('main').innerText;"
                    )
                    self.check(
                        "FOUNDATION_ONLY" in status_text,
                        scope + ": status does not claim full deletion completion",
                    )
                    if scope == "ACCOUNT":
                        denied = await self.http_status(page, origin + "/profiling/start")
                        self.check(denied == 401, "deleted account ordinary Web access denied")
                    await self.goto(page, origin, "/demo")
                    await self.submit(page, "합성 연결 로그아웃·토큰 철회", "#account")
                    denied = await self.http_status(page, origin + "/demo/deletion/status")
                    self.check(denied == 401, scope + ": logout revokes deletion status access")
                    await self.login(page, origin, "b")
                    metadata = await self.mcp(
                        page, "get_owned_profile_metadata", {"profile_id": "demo-profile-b"}
                    )
                    self.check(
                        metadata["found"] and metadata["version"] == 0,
                        scope + ": B preserved and usable",
                    )
                    await self.goto(page, origin, "/demo")
                    await self.submit(page, "합성 연결 로그아웃·토큰 철회", "#account")
                finally:
                    errors = []
                    try:
                        for tab in [page, settings]:
                            if tab is not None:
                                try:
                                    await self.call("tabs", action="close", page=tab)
                                    self.tabs.remove(tab)
                                except Exception as error:  # noqa: BLE001 - re-raised after cleanup
                                    errors.append(error)
                    finally:
                        self.settings_page = None
                        stop_runtime(process)
                    if errors:
                        raise ExceptionGroup("BrowserOS tab cleanup failed", errors)
        self.check(not folder.exists(), scope + ": private test store removed")
        return {"scope": scope, "passed": len(self.checks) - before}


async def main(args):
    profile = args.private_browser_profile.resolve()
    if not profile.is_dir() or profile.stat().st_mode & 0o077:
        raise RuntimeError("private BrowserOS profile must exist with owner-only permissions")
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    async with (
        streamable_http_client(args.mcp_url) as (read, write),
        BrowserOSSession(read, write) as session,
    ):
        server = await session.initialize()
        tools = await session.list_tools()
        checks = BrowserChecks(session, args.output_dir)
        expected = json.dumps("--user-data-dir=" + str(profile))
        guard = await checks.call(
            "run",
            code=f"const info=await browser.cdp('Browser.getBrowserCommandLine'); return info.arguments.includes({expected});",
        )
        if not guard.structured_content or guard.structured_content.get("ok") is not True:
            raise RuntimeError("BrowserOS private profile could not be verified")
        value = guard.structured_content.get("value", "")
        if "[UNTRUSTED_PAGE_CONTENT" in value:
            value = value.split("\n", 1)[1].rsplit("\n[END_UNTRUSTED_PAGE_CONTENT", 1)[0]
        checks.check(value.strip() == "true", "private BrowserOS profile verified")
        cases = []
        try:
            for scope in ["PROFILE", "ACCOUNT"]:
                cases.append(await checks.case(scope))
                print(scope, "PASS", flush=True)
            report = {
                "server_version": server.server_info.version,
                "tool_count": len(tools.tools),
                "transport": "BrowserOS native MCP",
                "script_ai_calls": 0,
                "cases": cases,
                "passed": len(checks.checks),
                "checks": checks.checks,
            }
            (args.output_dir / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2)
            )
            print("checks", len(checks.checks), "PASS", flush=True)
        finally:
            for tab in checks.tabs[:]:
                await checks.call("tabs", action="close", page=tab)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument(
        "--private-browser-profile",
        required=True,
        type=Path,
        help="Exact owner-only profile of BrowserOS started with --enable-automation",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    asyncio.run(main(parser.parse_args()))

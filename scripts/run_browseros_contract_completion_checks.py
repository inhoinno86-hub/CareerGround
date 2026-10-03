"""Native BrowserOS checks of CURRENT/options, R2/R3 and three partial scopes.

Only prerequisite approved facts/R1 are synthetic fixtures. Every new approval,
registration, export receipt and deletion is performed through BrowserOS MCP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mcp.client.streamable_http import streamable_http_client
from run_browseros_local_contract_checks import (
    BrowserChecks,
    BrowserOSSession,
    start_runtime,
    stop_runtime,
)
from sqlalchemy import select

from careerground.development_runtime import DevelopmentRuntime
from careerground.domain.claim_review_submission import (
    VerifiedReviewApproval,
    submit_synthetic_review,
)
from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.jd_mapping import link_jd_requirement_to_claim
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.domain.profiling_workspace import (
    append_explicit_profiling_input,
    start_profiling_session,
)
from careerground.domain.resume_draft import generate_resume_draft
from careerground.storage.graph_models import Claim, ClaimAssessment, EvidenceItem
from careerground.storage.jd_artifact_models import JDRequirement


def seed(store, port):
    now = datetime.now(UTC)
    with DevelopmentRuntime(port, store) as runtime, runtime.sessions() as session:
        account, profile = "demo-account-a", "demo-profile-a"
        work = start_profiling_session(
            session, account_id=account, profile_id=profile, base_profile_version=0, now=now
        )
        session.flush()
        source = append_explicit_profiling_input(
            session,
            account_id=account,
            profiling_session_id=work.id,
            base_profile_version=0,
            content="I implemented a feature",
            content_kind="USER_STATEMENT",
            idempotency_key="synthetic_browseros_input_0001",
            now=now,
        )
        session.flush()
        draft = propose_verbatim_draft(
            session,
            account_id=account,
            profiling_session_id=work.id,
            source_input_id=source.id,
            scope_key="synthetic-project",
            claim_type="CONTRIBUTION",
            exact_text=source.body,
            now=now,
        )
        session.flush()
        preparation = ClaimReviewPreparation(runtime.review_secret)
        batch = preparation.prepare(
            session,
            account_id=account,
            profiling_session_id=work.id,
            draft_ids=(draft.id,),
            now=now,
        )
        session.flush()
        from careerground.storage.models import ProfilingReviewItem

        item = session.scalar(
            select(ProfilingReviewItem).where(ProfilingReviewItem.batch_id == batch.id)
        )
        submit_synthetic_review(
            session,
            preparation=preparation,
            approval=VerifiedReviewApproval(
                account,
                batch.id,
                batch.review_digest,
                ((item.id, "ACCEPT"),),
                now + timedelta(minutes=2),
            ),
            now=now,
        )
        session.flush()
        claim = session.scalar(select(Claim).where(Claim.account_id == account))
        assessment = session.scalar(
            select(ClaimAssessment).where(ClaimAssessment.claim_id == claim.id)
        )
        assessment.consistency_status = "CONSISTENT"
        assessment.usage_policy = "ALLOWED"
        session.add(
            Claim(
                id="unrelated-a",
                account_id=account,
                profile_id=profile,
                scope_key="other",
                claim_type="CONTRIBUTION",
                canonical_text="Independent synthetic A fact",
                created_in_version=1,
                status="ACTIVE",
                created_at=now,
            )
        )
        session.flush()
        # Replace fixture archive after setting its explicit eligible assessment.
        from sqlalchemy import delete

        from careerground.storage.graph_models import ProfileArchive

        session.execute(delete(ProfileArchive).where(ProfileArchive.profile_id == profile))
        ensure_profile_archive(
            session, account_id=account, profile_id=profile, profile_version=1, now=now
        )
        jd = record_pasted_jd_analysis(
            session,
            account_id=account,
            profile_id=profile,
            source_text="feature",
            excerpts=(JDExcerpt(0, 7),),
            now=now,
        )
        requirement = session.scalar(select(JDRequirement).where(JDRequirement.jd_id == jd.id))
        link_jd_requirement_to_claim(
            session,
            account_id=account,
            jd_id=jd.id,
            requirement_id=requirement.id,
            claim_id=claim.id,
            profile_version=1,
            now=now,
        )
        artifact = generate_resume_draft(
            session,
            account_id=account,
            profile_id=profile,
            profile_version=1,
            jd_id=jd.id,
            claim_ids=(claim.id,),
            now=now,
        )
        pending = start_profiling_session(
            session, account_id=account, profile_id=profile, base_profile_version=1, now=now
        )
        session.flush()
        pending_input = append_explicit_profiling_input(
            session,
            account_id=account,
            profiling_session_id=pending.id,
            base_profile_version=1,
            content="Unapproved synthetic draft",
            content_kind="USER_STATEMENT",
            idempotency_key="synthetic_pending_draft_0001",
            now=now,
        )
        session.flush()
        propose_verbatim_draft(
            session,
            account_id=account,
            profiling_session_id=pending.id,
            source_input_id=pending_input.id,
            scope_key="pending",
            claim_type="CONTRIBUTION",
            exact_text=pending_input.body,
            now=now,
        )
        session.flush()
        evidence = session.scalar(select(EvidenceItem).where(EvidenceItem.account_id == account))
        result = {
            "artifact": artifact.id,
            "session": work.id,
            "evidence": evidence.id,
            "claim": claim.id,
        }
        session.commit()
        return result


class CompletionChecks(BrowserChecks):
    async def case(self, scope):
        before = len(self.checks)
        with tempfile.TemporaryDirectory(prefix="cg-browseros-completion-") as private:
            folder = Path(private)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            fixture = await asyncio.to_thread(seed, folder / "store", port)
            database = folder / "store" / "synthetic.sqlite"

            def rows(sql):
                with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
                    return db.execute(sql).fetchall()

            process = None
            with (folder / "runtime.log").open("wb") as log:
                try:
                    process = await asyncio.to_thread(start_runtime, folder / "store", port, log)
                    page = await self.new(origin + "/demo")
                    settings = await self.new("chrome://browseros/settings")
                    self.settings_page = settings
                    await self.evaluate(
                        settings,
                        f"const tabs=await chrome.tabs.query({{url:{json.dumps(origin + '/*')}}}); for(const tab of tabs) await chrome.tabs.setZoom(tab.id,2); return true;",
                    )
                    await self.login(page, origin, "a")
                    if scope == "SESSION":
                        current = await self.mcp(
                            page,
                            "get_career_profile",
                            {"profile_id": "demo-profile-a", "profile_version": "CURRENT"},
                        )
                        self.check(
                            current["profile_version"] == 1, "CURRENT reads exact owned version 1"
                        )
                        choices = {
                            "claims": True,
                            "evidence": False,
                            "boundaries": True,
                            "drafts": True,
                            "unavailable_references": False,
                        }
                        request = await self.mcp(
                            page,
                            "request_user_confirmation",
                            {
                                "action": "PROFILE_EXPORT",
                                "target_id": "demo-profile-a",
                                "profile_version": "CURRENT",
                                "format": "JSON",
                                "idempotency_key": "browseros_current_export_0001",
                                "inclusion": choices,
                            },
                        )
                        await self.goto(page, origin, request["confirmation_path"])
                        await self.audit(page, "CURRENT selected export approval")
                        await self.screenshot(page, "current-options-native-200.png")
                        await self.act(page, "check", r'checkbox "이 범위의 JSON')
                        await self.act(page, "check", r'checkbox "표시된 연결 앱')
                        await self.submit(page, "JSON 내보내기 허용", "#approval-receipt")
                        receipt = await self.evaluate(
                            page, "return document.querySelector('#approval-receipt').innerText;"
                        )
                        await self.goto(page, origin, "/demo/mcp")
                        exported = await self.mcp(
                            page,
                            "export_profile_data",
                            {
                                "profile_id": "demo-profile-a",
                                "profile_version": "CURRENT",
                                "format": "JSON",
                                "approval_receipt": receipt,
                                "inclusion": choices,
                            },
                        )
                        self.check(
                            exported["profile_version"] == 1 and exported["inclusion"] == choices,
                            "CURRENT receipt binds exact number and inclusion",
                        )
                        await self.goto(page, origin, f"/resume/{fixture['artifact']}/r2")
                        await self.act(
                            page,
                            "fill",
                            r'textbox "제안 R2 문구 1"',
                            value="I implemented a feature.",
                        )
                        await self.submit(page, "변경 전후 직접 확인", "input[name=approval_token]")
                        await self.audit(page, "R2 exact wording approval")
                        await self.screenshot(page, "r2-exact-native-200.png")
                        self.check(
                            rows("SELECT COUNT(*) FROM artifacts") == [(1,)],
                            "R2 preview does not save artifact",
                        )
                        await self.act(page, "check", r'checkbox "변경 전후 문구와 근거')
                        await self.submit(page, "R2 문구 승인 및 저장", "h1")
                        r2 = await self.evaluate(page, "return location.pathname.split('/')[2];")
                        self.check(
                            r2 != fixture["artifact"]
                            and rows("SELECT COUNT(*) FROM artifacts") == [(2,)],
                            "exact approval saves separate R2 and preserves R1",
                        )
                        await self.goto(page, origin, "/demo/mcp")
                        request = await self.mcp(
                            page,
                            "request_user_confirmation",
                            {
                                "action": "RESUME_EXPORT",
                                "target_id": r2,
                                "profile_version": 1,
                                "format": "JSON",
                                "idempotency_key": "browseros_r2_export_0001",
                            },
                        )
                        await self.goto(page, origin, request["confirmation_path"])
                        await self.act(page, "check", r'checkbox "이 범위의 파일')
                        await self.act(page, "check", r'checkbox "표시된 연결 앱')
                        await self.submit(page, "내보내기 허용", "#approval-receipt")
                        receipt = await self.evaluate(
                            page, "return document.querySelector('#approval-receipt').innerText;"
                        )
                        await self.goto(page, origin, "/demo/mcp")
                        exported = await self.mcp(
                            page,
                            "export_resume",
                            {"artifact_id": r2, "format": "JSON", "approval_receipt": receipt},
                        )
                        self.check(
                            exported["profile_version"] == 1
                            and exported["resource_uri"].endswith(request["request_id"])
                            and len(exported["content_hash"]) == 64,
                            "R2 export requires separate exact browser receipt",
                        )
                        await self.goto(page, origin, f"/resume/{fixture['artifact']}/r2")
                        await self.act(
                            page,
                            "fill",
                            r'textbox "제안 R2 문구 1"',
                            value="I led an entire new team.",
                        )
                        await self.act(
                            page,
                            "select",
                            r'combobox "새 사실 포함 여부 1"',
                            value="R3_NEEDS_FACT_REVIEW",
                        )
                        await self.submit(page, "변경 전후 직접 확인", "h1")
                        await self.audit(page, "R3 separate fact review")
                        self.check(
                            await self.evaluate(
                                page,
                                "return !!document.querySelector('a[href=\"/profiling/start\"]');",
                            ),
                            "R3 routes to explicit fact review",
                        )
                        self.check(
                            rows("SELECT COUNT(*) FROM artifacts") == [(2,)]
                            and rows(
                                "SELECT version FROM career_profiles WHERE id='demo-profile-a'"
                            )
                            == [(1,)],
                            "R3 neither saves wording nor promotes facts",
                        )
                    target = (
                        fixture["session" if scope == "SESSION" else "evidence"]
                        if scope != "PROJECT"
                        else None
                    )
                    if scope == "PROJECT":
                        await self.goto(page, origin, "/profile/demo-profile-a/projects")
                        await self.act(
                            page,
                            "select",
                            r'combobox "프로젝트로 지정할 경력 범위"',
                            value="synthetic-project",
                        )
                        await self.act(page, "check", r'checkbox "선택한 경력 범위를')
                        await self.submit(page, "프로젝트 범위 등록", "h1")
                        target = rows("SELECT id FROM project_scopes")[0][0]
                        self.check(
                            rows("SELECT status FROM project_scopes") == [("ACTIVE",)],
                            "PROJECT scope explicitly registered through browser",
                        )
                    await self.goto(page, origin, "/demo/mcp")
                    args = {
                        "scope": scope,
                        "target_id": target,
                        "profile_version": 1,
                        "idempotency_key": "browseros_partial_delete_0001",
                        "approval_receipt": "",
                    }
                    request = await self.mcp(page, "execute_data_deletion", args)
                    self.check(
                        request["status"] == "WAITING",
                        scope + ": unapproved request does not delete",
                    )
                    await self.goto(page, origin, request["confirmation_path"])
                    await self.audit(page, scope + " exact deletion impact")
                    await self.act(page, "check", r'checkbox "표시한 삭제 범위')
                    await self.act(page, "check", r'checkbox "이 재인증은')
                    await self.act(
                        page, "fill", r'textbox "합성 계정 확인 문구"', value="합성 계정 A"
                    )
                    await self.submit(page, "모의 재인증 후 최종 확인", "input[name=confirm]")
                    await self.act(page, "check", r'checkbox "확인한 범위의')
                    await self.submit(page, "로컬 합성 데이터 삭제 실행", "#approval-receipt")
                    receipt = await self.evaluate(
                        page, "return document.querySelector('#approval-receipt').innerText;"
                    )
                    self.check(
                        rows("SELECT COUNT(*) FROM deletion_requests") == [(0,)],
                        scope + ": browser approval alone leaves data intact",
                    )
                    await self.goto(page, origin, "/demo/mcp")
                    result = await self.mcp(
                        page, "execute_data_deletion", {**args, "approval_receipt": receipt}
                    )
                    self.check(
                        result["status"] == "DELETING",
                        scope + ": same connection executes approved partial erasure",
                    )
                    self.check(
                        rows("SELECT version,status FROM career_profiles WHERE id='demo-profile-a'")
                        == [(2, "ACTIVE")],
                        scope + ": A profile remains active at new version",
                    )
                    self.check(
                        rows("SELECT canonical_text FROM claims WHERE id='unrelated-a'")
                        == [("Independent synthetic A fact",)],
                        scope + ": independent A canonical fact preserved",
                    )
                    self.check(
                        rows(
                            "SELECT COUNT(*) FROM profiling_inputs WHERE body='I implemented a feature'"
                        )
                        == [(0,)],
                        scope + ": related original raw input erased",
                    )
                    self.check(
                        rows("SELECT COUNT(*) FROM artifacts") == [(0,)],
                        scope + ": old R1/R2 artifacts removed",
                    )
                    await self.goto(page, origin, "/demo/deletion/status")
                    await self.audit(page, scope + " minimal status")
                    await self.screenshot(page, scope.lower() + "-partial-status-native-200.png")
                    self.check(
                        "FOUNDATION_ONLY"
                        in await self.evaluate(
                            page, "return document.querySelector('main').innerText;"
                        ),
                        scope + ": honest limited deletion status",
                    )
                    stop_runtime(process)
                    process = await asyncio.to_thread(start_runtime, folder / "store", port, log)
                    await self.login(page, origin, "a")
                    metadata = await self.mcp(
                        page, "get_owned_profile_metadata", {"profile_id": "demo-profile-a"}
                    )
                    self.check(
                        metadata["version"] == 2,
                        scope + ": erasure ledger and profile persist through restart",
                    )
                    await self.login(page, origin, "b")
                    metadata = await self.mcp(
                        page, "get_owned_profile_metadata", {"profile_id": "demo-profile-b"}
                    )
                    self.check(
                        metadata["version"] == 0 and metadata["found"], scope + ": B remains usable"
                    )
                finally:
                    for tab in self.tabs[:]:
                        await self.call("tabs", action="close", page=tab)
                        self.tabs.remove(tab)
                    self.settings_page = None
                    stop_runtime(process)
        self.check(not folder.exists(), scope + ": temporary runtime removed")
        return {"scope": scope, "passed": len(self.checks) - before}


async def main(args):
    profile = args.private_browser_profile.resolve()
    if not profile.is_dir() or profile.stat().st_mode & 0o077:
        raise RuntimeError("private BrowserOS profile required")
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    async with (
        streamable_http_client(args.mcp_url) as (read, write),
        BrowserOSSession(read, write) as session,
    ):
        server = await session.initialize()
        checks = CompletionChecks(session, args.output_dir)
        guard = await checks.call(
            "run",
            code=f"const info=await browser.cdp('Browser.getBrowserCommandLine'); return info.arguments.includes({json.dumps('--user-data-dir=' + str(profile))});",
        )
        if "true" not in checks.text(guard):
            raise RuntimeError("private BrowserOS profile mismatch")
        checks.check(True, "private BrowserOS profile verified")
        cases = []
        for scope in ("SESSION", "EVIDENCE", "PROJECT"):
            cases.append(await checks.case(scope))
            print(scope, "PASS", flush=True)
        report = {
            "transport": "BrowserOS native MCP",
            "server_version": server.server_info.version,
            "script_ai_calls": 0,
            "prerequisites": "synthetic approved fact/R1 fixtures",
            "passed": len(checks.checks),
            "cases": cases,
            "checks": checks.checks,
        }
        (args.output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print("checks", len(checks.checks), "PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--private-browser-profile", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    asyncio.run(main(parser.parse_args()))

"""Real HTTP two-stage policy choices, exact browser approval and MCP receipts."""

from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import test_boundary_review as boundary_fixtures
import test_browser_mcp_confirmation as confirmation_fixtures
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from careerground.domain.browser_operations import BrowserOperationRejected
from careerground.storage.graph_models import (
    ClaimAssessment,
    ClaimBoundaryReview,
    ClaimConflictReview,
    EvidenceItem,
    ProfileChangeSet,
)
from careerground.storage.models import Base, BrowserOperation, CareerProfile

RESOURCE = confirmation_fixtures.RESOURCE


class PolicyBrowserTests(unittest.TestCase):
    fixture_type = confirmation_fixtures.BrowserMCPConfirmationTests

    def setUp(self):
        self.fixture = self.fixture_type()
        self.fixture.setUpClass()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.sessions = self.fixture.sessions
        source = boundary_fixtures.BoundaryReviewTests()
        source.setUp()
        self.addCleanup(source.tearDown)
        with source.engine.connect() as read, self.fixture.engine.begin() as write:
            write.execute(
                CareerProfile.__table__.update()
                .where(CareerProfile.id == "profile-a")
                .values(version=1)
            )
            for table in Base.metadata.sorted_tables:
                if table.name in {"accounts", "career_profiles", "auth_identities"}:
                    continue
                rows = [
                    {
                        key: value.replace(tzinfo=UTC)
                        if isinstance(value, datetime) and value.tzinfo is None
                        else value
                        for key, value in row._mapping.items()
                    }
                    for row in read.execute(select(table))
                ]
                if rows:
                    write.execute(table.insert(), rows)

    def prepare(self, browser, path, mode, **override):
        page = browser.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        fields = (
            {
                "conflict_link_id": "contradiction-link",
                "resolution": "REMAIN_UNCERTAIN",
                "explanation": "합성 모순의 양쪽 근거를 보존한다.",
            }
            if mode == "CONFLICT_REVIEW"
            else {
                "evidence_id": "contradiction-a",
                "action": "ADD",
                "constraint_id": "",
                "proposed_boundary_text": "관리 권한을 주장하지 않는다.",
                "allowed_wording": "기능을 구현했다.",
                "remaining_prohibited_expansion": "단독 리더십과 수치 확대는 금지한다.",
            }
        )
        fields.update(override)
        exact = browser.post(
            path + "/prepare",
            data={"choice_token": self.fixture.hidden(page.text, "choice_token"), **fields},
        )
        self.assertEqual(exact.status_code, 200, exact.text)
        return {
            "confirmation_token": self.fixture.hidden(exact.text, "confirmation_token"),
            "confirm": "confirm_policy",
            "allow_connection": "yes",
            **fields,
        }, exact

    def test_conflict_stages_do_not_auto_approve_and_exact_receipt_preserves_sources(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            request = f.request(mcp, "CONFLICT_REVIEW", "claim-a", 1)
            form, exact = self.prepare(browser, request["confirmation_path"], "CONFLICT_REVIEW")
            self.assertIn("합성 모순의 양쪽 근거를 보존한다.", exact.text)
            self.assertRegex(
                exact.text,
                r"이 결정에 선택한 근거</dt><dd>연결 contradiction-link · 근거 contradiction-a · CONTRADICTS",
            )
            with self.sessions() as session:
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ClaimConflictReview)), 0
                )
            forged = f.call(
                mcp,
                "resolve_claim_conflict",
                {"claim_id": "claim-a", "approval_receipt": request["request_id"] + "." + "0" * 64},
            )
            self.assertEqual(forged["error"]["code"], "REVIEW_REQUIRED")
            self.assertEqual(
                browser.post(
                    request["confirmation_path"], data={**form, "explanation": "내용 변조"}
                ).status_code,
                409,
            )
            browser.cookies.set("cg_session", "other-session")
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
            browser.cookies.set("cg_session", "owner")
            receipt = f.confirm(browser, request["confirmation_path"], form)
            result = f.call(
                mcp, "resolve_claim_conflict", {"claim_id": "claim-a", "approval_receipt": receipt}
            )
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual(result["data"]["version_after"], 2)
            self.assertEqual(receipt, f.confirm(browser, request["confirmation_path"], form))
            self.assertEqual(
                result,
                f.call(
                    mcp,
                    "resolve_claim_conflict",
                    {"claim_id": "claim-a", "approval_receipt": receipt},
                ),
            )
        with self.sessions() as session:
            self.assertIsNotNone(session.get(EvidenceItem, "contradiction-a"))
            latest = session.scalar(
                select(ClaimAssessment)
                .where(ClaimAssessment.claim_id == "claim-a")
                .order_by(ClaimAssessment.profile_version.desc())
            )
            self.assertEqual(
                (latest.consistency_status, latest.usage_policy), ("DISPUTED", "REVIEW_REQUIRED")
            )
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(ClaimAssessment)
                    .where(ClaimAssessment.claim_id == "claim-unaffected")
                ),
                1,
            )
            self.assertNotIn(
                "양쪽", session.get(BrowserOperation, request["request_id"]).result_json
            )

    def test_boundary_add_exact_decision_and_current_source_change_rejection(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            request = f.request(mcp, "BOUNDARY_REVIEW", "claim-a", 1)
            form, exact = self.prepare(browser, request["confirmation_path"], "BOUNDARY_REVIEW")
            self.assertIn("관리 권한을 주장하지 않는다.", exact.text)
            self.assertRegex(
                exact.text,
                r"이 결정에 선택한 근거</dt><dd>연결 contradiction-link · 근거 contradiction-a · CONTRADICTS",
            )
            self.assertEqual(
                browser.post(
                    request["confirmation_path"],
                    data={k: v for k, v in form.items() if k != "allow_connection"},
                ).status_code,
                400,
            )
            receipt = f.confirm(browser, request["confirmation_path"], form)
            response = f.call(
                mcp, "review_boundary_change", {"claim_id": "claim-a", "approval_receipt": receipt}
            )
            self.assertEqual(response["status"], "ok", response)
            self.assertEqual(
                f.call(
                    mcp,
                    "resolve_claim_conflict",
                    {"claim_id": "claim-a", "approval_receipt": receipt},
                )["status"],
                "error",
            )
            self.assertEqual(
                f.call(
                    mcp,
                    "review_boundary_change",
                    {"claim_id": "claim-a", "approval_receipt": receipt},
                    client_id="foreign-client",
                )["status"],
                "error",
            )
        with self.sessions() as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimBoundaryReview)), 1
            )
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(ClaimAssessment)
                    .where(ClaimAssessment.claim_id == "claim-unaffected")
                ),
                1,
            )

    def test_boundary_revoke_requires_new_support_and_stays_review_required(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            request = f.request(mcp, "BOUNDARY_REVIEW", "claim-a", 1)
            form, exact = self.prepare(
                browser,
                request["confirmation_path"],
                "BOUNDARY_REVIEW",
                evidence_id="support-a",
                action="REVOKE",
                constraint_id="old-boundary",
                proposed_boundary_text="",
            )
            self.assertIn("Do not claim sole leadership", exact.text)
            f.confirm(browser, request["confirmation_path"], form)
        with self.sessions() as session:
            latest = session.scalar(
                select(ClaimAssessment)
                .where(ClaimAssessment.claim_id == "claim-a")
                .order_by(ClaimAssessment.profile_version.desc())
            )
            self.assertEqual(latest.usage_policy, "REVIEW_REQUIRED")

    def test_distinct_concurrent_conflict_operations_share_one_current_version(self):
        f = self.fixture
        prepared = []
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            for index in range(2):
                request = f.request(
                    mcp,
                    "CONFLICT_REVIEW",
                    "claim-a",
                    1,
                    key=f"synthetic_distinct_policy_{index:04}",
                )
                form, _ = self.prepare(browser, request["confirmation_path"], "CONFLICT_REVIEW")
                prepared.append((request, form))

        def approve(pair):
            request, form = pair
            with self.sessions() as session:
                try:
                    f.service.confirm(
                        session,
                        account_id="acct-a",
                        browser_session_id="synthetic-browser-session-a",
                        operation_id=request["request_id"],
                        confirmation_token=form["confirmation_token"],
                        confirm_value="confirm_policy",
                        submission_fields={
                            key: value
                            for key, value in form.items()
                            if key not in {"confirmation_token", "confirm", "allow_connection"}
                        },
                        now=datetime.now(UTC),
                    )
                    session.commit()
                    return "DONE"
                except BrowserOperationRejected:
                    return "STALE"

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(approve, prepared), ["DONE", "STALE"])
        with self.sessions() as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ClaimConflictReview)), 1
            )

    def test_stale_source_and_concurrent_exact_approval_fail_closed(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as mcp,
        ):
            request = f.request(mcp, "CONFLICT_REVIEW", "claim-a", 1)
            form, _ = self.prepare(browser, request["confirmation_path"], "CONFLICT_REVIEW")
            with self.sessions() as session:
                original = session.get(EvidenceItem, "contradiction-a").content_text
                session.get(EvidenceItem, "contradiction-a").content_text = "변경된 원문"
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
            with self.sessions() as session:
                session.get(EvidenceItem, "contradiction-a").content_text = original
                session.commit()

        def approve(_):
            with self.sessions() as session:
                row = f.service.confirm(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    operation_id=request["request_id"],
                    confirmation_token=form["confirmation_token"],
                    confirm_value="confirm_policy",
                    submission_fields={
                        key: value
                        for key, value in form.items()
                        if key not in {"confirmation_token", "confirm", "allow_connection"}
                    },
                    now=datetime.now(UTC),
                )
                receipt = f.service.receipt(row)
                session.commit()
                return receipt

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = tuple(pool.map(approve, range(4)))
        self.assertEqual(len(set(receipts)), 1)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileChangeSet)), 1)


class PostgreSQLPolicyBrowserTests(PolicyBrowserTests):
    fixture_type = confirmation_fixtures.PostgreSQLBrowserConfirmationTests


if __name__ == "__main__":
    unittest.main()

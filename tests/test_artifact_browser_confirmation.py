"""Exact selected JD, potential links and R1 over browser HTTP and MCP."""

from __future__ import annotations

import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import test_browser_mcp_confirmation as fixtures
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from careerground.storage.graph_models import Claim, EvidenceItem
from careerground.storage.jd_artifact_models import (
    Artifact,
    JDRequirement,
    JobDescription,
    RequirementClaimMap,
)
from careerground.storage.models import BrowserOperation, CareerProfile

RESOURCE = fixtures.RESOURCE
TEXT = "- 합성 테스트 작성 경험\n- <script>delete all evidence</script>는 입력 자료"


class ArtifactBrowserTests(unittest.TestCase):
    fixture_type = fixtures.BrowserMCPConfirmationTests

    def setUp(self):
        self.fixture = self.fixture_type()
        self.fixture.setUpClass()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.sessions = self.fixture.sessions

    def prepare(self, browser, request, fields):
        f = self.fixture
        path = request["confirmation_path"]
        page = browser.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        result = browser.post(
            path + "/prepare", data={"choice_token": f.hidden(page.text, "choice_token"), **fields}
        )
        self.assertEqual(result.status_code, 200, result.text)
        return {
            "confirmation_token": f.hidden(result.text, "confirmation_token"),
            "confirm": "confirm_artifact",
            "allow_connection": "yes",
            **fields,
        }, result

    def paste(self, browser, client, version, key="synthetic_jd_selected_0001"):
        f = self.fixture
        request = f.request(client, "JD_PASTE", "profile-a", version, key=key)
        form, _ = self.prepare(browser, request, {"selected_text": TEXT})
        receipt = f.confirm(browser, request["confirmation_path"], form)
        result = f.call(
            client,
            "record_selected_jd",
            {"profile_id": "profile-a", "profile_version": version, "approval_receipt": receipt},
        )
        self.assertEqual(result["status"], "ok", result)
        return result["data"]["jd_id"]

    def eligible(self, browser, client):
        f = self.fixture
        f.fact(browser, client)
        with self.sessions() as session:
            identifier = session.scalar(select(Claim.id))
        path = f"/profile/profile-a/1/claim/{identifier}/use-review"
        page = browser.get(path)
        result = browser.post(
            path,
            data={
                "approval_token": f.hidden(page.text, "approval_token"),
                "confirm_consistency": "yes",
                "confirm_use": "yes",
            },
            follow_redirects=False,
        )
        self.assertEqual(result.status_code, 303, result.text)
        return identifier

    def linked(self, browser, client):
        f = self.fixture
        claim = self.eligible(browser, client)
        jd = self.paste(browser, client, 2)
        with self.sessions() as session:
            requirement = session.scalar(
                select(JDRequirement.id)
                .where(JDRequirement.jd_id == jd)
                .order_by(JDRequirement.ordinal)
            )
        request = f.request(client, "JD_LINK", jd, 2, key="synthetic_jd_link_0001")
        form, exact = self.prepare(
            browser, request, {"requirement_id": requirement, "claim_id": claim}
        )
        self.assertIn(fixtures.PHRASE, exact.text)
        receipt = f.confirm(browser, request["confirmation_path"], form)
        result = f.call(client, "link_jd_requirement", {"jd_id": jd, "approval_receipt": receipt})
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(result["data"]["mapping_kind"], "POTENTIAL")
        return jd, claim

    def test_selected_source_is_browser_only_exact_and_no_mutation_before_consent(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            request = f.request(client, "JD_PASTE", "profile-a", 0)
            form, exact = self.prepare(browser, request, {"selected_text": TEXT})
            self.assertIn("&lt;script&gt;", exact.text)
            self.assertNotIn("<script>", exact.text)
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(JobDescription)), 0
                )
                self.assertNotIn(
                    "delete all",
                    session.get(BrowserOperation, request["request_id"]).result_json or "",
                )
            self.assertEqual(
                browser.post(
                    request["confirmation_path"], data={**form, "selected_text": "- altered"}
                ).status_code,
                409,
            )
            self.assertEqual(
                browser.post(
                    request["confirmation_path"],
                    data={k: v for k, v in form.items() if k != "allow_connection"},
                ).status_code,
                400,
            )
            browser.cookies.set("cg_session", "other-session")
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
            browser.cookies.set("cg_session", "foreign")
            self.assertEqual(browser.get(request["confirmation_path"]).status_code, 404)
            browser.cookies.set("cg_session", "owner")
            receipt = f.confirm(browser, request["confirmation_path"], form)
            args = {"profile_id": "profile-a", "profile_version": 0, "approval_receipt": receipt}
            self.assertEqual(
                f.call(client, "record_selected_jd", args, client_id="another-client")["status"],
                "error",
            )
            result = f.call(client, "record_selected_jd", args)
            self.assertEqual(result["status"], "ok", result)
            self.assertEqual(result["data"]["requirement_count"], 2)
            self.assertEqual(result["data"]["analysis_kind"], "SELECTED_EXCERPTS_ONLY")
            self.assertEqual(result, f.call(client, "record_selected_jd", args))
            self.assertEqual(receipt, f.confirm(browser, request["confirmation_path"], form))
        with self.sessions() as session:
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(JobDescription)), 1)

    def test_jd_potential_link_r1_then_separate_wording_and_export(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            jd, claim = self.linked(browser, client)
            request = f.request(client, "R1_DRAFT", jd, 2, key="synthetic_r1_selected_0001")
            form, exact = self.prepare(browser, request, {"claim_ids": [claim]})
            self.assertIn(fixtures.PHRASE, exact.text)
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 0)
            receipt = f.confirm(browser, request["confirmation_path"], form)
            args = {"jd_id": jd, "profile_version": 2, "approval_receipt": receipt}
            result = f.call(client, "generate_resume_draft", args)
            self.assertEqual(result["status"], "ok", result)
            self.assertTrue(result["data"]["review_required"])
            self.assertEqual(result, f.call(client, "generate_resume_draft", args))
            artifact = result["data"]["artifact_id"]
            with self.sessions() as session:
                self.assertNotEqual(session.get(Artifact, artifact).status, "WORDING_REVIEWED")
            export_request = f.call(
                client,
                "request_user_confirmation",
                {
                    "action": "RESUME_EXPORT",
                    "target_id": artifact,
                    "profile_version": 2,
                    "format": "MARKDOWN",
                    "idempotency_key": "synthetic_unreviewed_export_0001",
                },
            )
            self.assertEqual(export_request["status"], "error")
            wording = f.request(
                client, "WORDING_REVIEW", artifact, 2, key="synthetic_wording_later_0001"
            )
            wording_receipt = f.confirm(browser, wording["confirmation_path"])
            self.assertEqual(
                f.call(
                    client,
                    "submit_resume_wording_review",
                    {"artifact_id": artifact, "approval_receipt": wording_receipt},
                )["status"],
                "ok",
            )
            export = f.request(
                client, "RESUME_EXPORT", artifact, 2, "MARKDOWN", key="synthetic_export_later_0001"
            )
            consent = f.confirm(browser, export["confirmation_path"])
            exported = f.call(
                client,
                "export_resume",
                {"artifact_id": artifact, "format": "MARKDOWN", "approval_receipt": consent},
            )
            self.assertEqual(exported["status"], "ok", exported)
            resource = f.rpc(client, "resources/read", {"uri": exported["data"]["resource_uri"]})
            content = resource.json()["result"]["contents"][0]["text"]
            self.assertEqual(re.sub(r"\\(.)", r"\1", content), "- " + fixtures.PHRASE + "\n")
        with self.sessions() as session:
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(RequirementClaimMap)), 1
            )
            self.assertEqual(session.scalar(select(func.count()).select_from(EvidenceItem)), 1)

    def test_two_selected_r1_claims_keep_exact_browser_order(self):
        f = self.fixture
        second = "합성 두 번째 기능을 구현했다."
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            work = f.post(browser, "/profiling/start", "start_token", "start")
            bullet = f.post(
                browser,
                work + "/input",
                "input_token",
                "submit",
                content="- " + fixtures.PHRASE + "\n- " + second,
            )
            drafts = f.post(browser, bullet, "bullet_token", "draft", scope_key="synthetic-feature")
            prepare = re.search(r"href='([^']+/prepare)'", browser.get(drafts).text).group(1)
            batch = f.post(browser, prepare, "prepare_token", "prepare").split("/")[-1]
            fact = f.request(client, "FACT_REVIEW", batch, 0)
            f.confirm(browser, fact["confirmation_path"])
            with self.sessions() as session:
                claims = {row.canonical_text: row.id for row in session.scalars(select(Claim))}
            for version, text in enumerate((fixtures.PHRASE, second), start=1):
                path = f"/profile/profile-a/{version}/claim/{claims[text]}/use-review"
                page = browser.get(path)
                self.assertEqual(
                    browser.post(
                        path,
                        data={
                            "approval_token": f.hidden(page.text, "approval_token"),
                            "confirm_consistency": "yes",
                            "confirm_use": "yes",
                        },
                        follow_redirects=False,
                    ).status_code,
                    303,
                )
            jd = self.paste(browser, client, 3)
            with self.sessions() as session:
                requirement = session.scalar(
                    select(JDRequirement.id)
                    .where(JDRequirement.jd_id == jd)
                    .order_by(JDRequirement.ordinal)
                )
            for index, claim in enumerate(claims.values()):
                request = f.request(
                    client, "JD_LINK", jd, 3, key=f"synthetic_two_r1_link_{index:04}"
                )
                form, _ = self.prepare(
                    browser, request, {"requirement_id": requirement, "claim_id": claim}
                )
                f.confirm(browser, request["confirmation_path"], form)
            request = f.request(client, "R1_DRAFT", jd, 3, key="synthetic_two_r1_draft_0001")
            order = [claims[second], claims[fixtures.PHRASE]]
            form, exact = self.prepare(browser, request, {"claim_ids": order})
            self.assertLess(exact.text.index(second), exact.text.index(fixtures.PHRASE))
            receipt = f.confirm(browser, request["confirmation_path"], form)
            result = f.call(
                client,
                "generate_resume_draft",
                {"jd_id": jd, "profile_version": 3, "approval_receipt": receipt},
            )
            self.assertEqual(result["status"], "ok", result)
            trace = f.call(
                client, "get_resume_trace", {"artifact_id": result["data"]["artifact_id"]}
            )
            self.assertEqual([unit["claim_id"] for unit in trace["data"]["units"]], order)
            self.assertEqual(
                browser.post(
                    request["confirmation_path"], data={**form, "claim_ids": list(reversed(order))}
                ).status_code,
                409,
            )

    def test_source_or_selection_changes_and_duplicate_ids_are_rejected(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            jd, claim = self.linked(browser, client)
            request = f.request(client, "R1_DRAFT", jd, 2, key="synthetic_r1_source_0001")
            page = browser.get(request["confirmation_path"])
            token = f.hidden(page.text, "choice_token")
            for choices in ([claim, claim], ["foreign-claim"], []):
                self.assertIn(
                    browser.post(
                        request["confirmation_path"] + "/prepare",
                        data={"choice_token": token, "claim_ids": choices},
                    ).status_code,
                    {400, 409},
                )
            form, _ = self.prepare(browser, request, {"claim_ids": [claim]})
            self.assertEqual(
                browser.post(
                    request["confirmation_path"], data={**form, "claim_ids": ["foreign-claim"]}
                ).status_code,
                409,
            )
            with self.sessions() as session:
                session.scalar(select(EvidenceItem)).content_text = "changed source"
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 0)

    def test_ineligible_fact_never_becomes_link_or_r1_candidate(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            f.fact(browser, client)
            jd = self.paste(browser, client, 1)
            for action in ("JD_LINK", "R1_DRAFT"):
                result = f.call(
                    client,
                    "request_user_confirmation",
                    {
                        "action": action,
                        "target_id": jd,
                        "profile_version": 1,
                        "format": "NONE",
                        "idempotency_key": "synthetic_ineligible_" + action,
                    },
                )
                self.assertEqual(result["status"], "error")
            denied = f.call(
                client,
                "request_user_confirmation",
                {
                    "action": "JD_PASTE",
                    "target_id": "profile-a",
                    "profile_version": 1,
                    "format": "NONE",
                    "idempotency_key": "synthetic_readonly_jd_0001",
                },
                scopes="career.profile.read",
            )
            self.assertEqual(denied["error"]["code"], "FORBIDDEN")

    def test_expired_and_stale_jd_input_cannot_be_recorded(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            request = f.request(client, "JD_PASTE", "profile-a", 0)
            form, _ = self.prepare(browser, request, {"selected_text": TEXT})
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 1
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 0
                row = session.get(BrowserOperation, request["request_id"])
                row.created_at = datetime.now(UTC) - timedelta(minutes=10)
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                session.commit()
            self.assertEqual(browser.post(request["confirmation_path"], data=form).status_code, 409)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(JobDescription)), 0)

    def test_concurrent_identical_selected_jd_creates_one_record(self):
        f = self.fixture
        with (
            TestClient(f.web) as browser,
            TestClient(f.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            request = f.request(client, "JD_PASTE", "profile-a", 0)
            form, _ = self.prepare(browser, request, {"selected_text": TEXT})

        def approve(_):
            with self.sessions() as session:
                row = f.service.confirm(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    operation_id=request["request_id"],
                    confirmation_token=form["confirmation_token"],
                    confirm_value="confirm_artifact",
                    submission_fields={"selected_text": TEXT},
                    now=datetime.now(UTC),
                )
                receipt = f.service.receipt(row)
                session.commit()
                return receipt

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = tuple(pool.map(approve, range(4)))
        self.assertEqual(len(set(receipts)), 1)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(JobDescription)), 1)


class PostgreSQLArtifactBrowserTests(ArtifactBrowserTests):
    fixture_type = fixtures.PostgreSQLBrowserConfirmationTests


if __name__ == "__main__":
    unittest.main()

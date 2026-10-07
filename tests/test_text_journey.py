"""Document-free synthetic journey from an empty profile through explicit R1 export."""

from __future__ import annotations

import os
import re
import unittest
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.storage.graph_models import Claim, ClaimAssessment, ClaimUseReview
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app

SECRET = b"synthetic-text-journey-secret-at-least-32-bytes"


class Page(HTMLParser):
    """Inspect rendered links, native controls and landmark semantics without a browser."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.links: list[str] = []
        self.controls: list[tuple[str, dict, bool]] = []
        self.labels: set[str] = set()
        self.label_depth = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "a":
            self.links.append(attrs["href"])
        if tag == "label":
            self.label_depth += 1
            if "for" in attrs:
                self.labels.add(attrs["for"])
        if tag in {"input", "select", "textarea"} and attrs.get("type") != "hidden":
            self.controls.append((tag, attrs, self.label_depth > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth -= 1


class TextJourneyTests(unittest.TestCase):
    def prepare_database(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

    def setUp(self) -> None:
        self.prepare_database()
        with self.sessions() as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=0),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                ]
            )
            session.commit()
        identities = {
            "owner": TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a"),
            "foreign": TrustedBrowserIdentity("acct-b", "synthetic-browser-session-b"),
            "other-session": TrustedBrowserIdentity("acct-a", "synthetic-second-session-a"),
        }
        self.app = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=lambda request, _response: identities.get(
                request.cookies.get("cg_session")
            ),
            review_signing_secret=SECRET,
            presentation_signing_secret=SECRET,
        )

    def page(self, client: TestClient, path: str) -> tuple[str, Page]:
        response = client.get(path)
        self.assertEqual(response.status_code, 200, path)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("form-action 'self'", response.headers["content-security-policy"])
        page = Page(response.text)
        self.assertIn("#main-content", page.links)
        self.assertEqual(sum(tag == "h1" for tag, _ in page.tags), 1)
        mains = [attrs for tag, attrs in page.tags if tag == "main"]
        self.assertEqual(len(mains), 1)
        self.assertEqual(mains[0]["id"], "main-content")
        self.assertEqual(mains[0]["tabindex"], "-1")
        self.assertIn(("html", {"lang": "ko"}), page.tags)
        ids = [attrs["id"] for _, attrs in page.tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(tag == "meta" and a.get("name") == "viewport" for tag, a in page.tags))
        for tag, attrs, nested_label in page.controls:
            self.assertTrue(nested_label or attrs.get("id") in page.labels, attrs)
            self.assertNotIn("disabled", attrs)
            self.assertNotIn("tabindex", attrs)
            if tag == "select":
                self.assertIn("required", attrs)
        self.assertFalse(any(tag == "script" for tag, _ in page.tags))
        return response.text, page

    def token(self, text: str, name: str) -> str:
        match = re.search(rf"name='{name}' value='([^']+)'", text)
        self.assertIsNotNone(match, name)
        return match.group(1)

    def link(self, page: Page, pattern: str) -> str:
        matches = [path for path in page.links if re.fullmatch(pattern, path)]
        self.assertEqual(len(matches), 1, matches)
        return matches[0]

    def post(self, client: TestClient, path: str, data: dict) -> str:
        response = client.post(path, data=data, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text)
        return response.headers["location"]

    def start(self, client: TestClient) -> str:
        text, _ = self.page(client, "/profiling/start")
        return self.post(
            client,
            "/profiling/start",
            {"start_token": self.token(text, "start_token"), "confirm": "start"},
        )

    def test_empty_profile_direct_input_fact_use_jd_wording_and_download(self) -> None:
        phrase = "합성 기능의 테스트를 작성했다."
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "owner")
            start_text, start_page = self.page(client, "/profiling/start")
            self.assertIn("문서 없이", start_text)
            self.assertIn("90일", start_text)
            self.assertIn("외부 검증이나 채용 결과를 보장하지 않습니다", start_text)
            self.page(client, self.link(start_page, r"/artifacts"))
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 0
                )
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
            work_path = self.start(client)
            _, work_page = self.page(client, work_path)
            input_path = self.link(work_page, r"/profiling/[^/]+/input")
            input_text, _ = self.page(client, input_path)
            bullet_path = self.post(
                client,
                input_path,
                {
                    "input_token": self.token(input_text, "input_token"),
                    "content": f"- {phrase}",
                    "confirm": "submit",
                },
            )
            bullet_text, _ = self.page(client, bullet_path)
            self.assertIn(phrase, bullet_text)
            drafts_path = self.post(
                client,
                bullet_path,
                {
                    "bullet_token": self.token(bullet_text, "bullet_token"),
                    "scope_key": "synthetic-feature",
                    "confirm": "draft",
                },
            )
            _, drafts_page = self.page(client, drafts_path)
            prepare_path = self.link(drafts_page, r"/profiling/.+/prepare")
            prepare_text, _ = self.page(client, prepare_path)
            review_path = self.post(
                client,
                prepare_path,
                {
                    "prepare_token": self.token(prepare_text, "prepare_token"),
                    "confirm": "prepare",
                },
            )
            review_text, review_page = self.page(client, review_path)
            self.assertIn(phrase, review_text)
            decisions = {
                attrs["name"]: "ACCEPT" for tag, attrs, _ in review_page.controls if tag == "select"
            }
            self.assertEqual(len(decisions), 1)
            fact_result = client.post(
                review_path,
                data={
                    "approval_token": self.token(review_text, "approval_token"),
                    "confirm": "reviewed",
                    **decisions,
                },
            )
            self.assertEqual(fact_result.status_code, 200)
            self.assertIn("R1 사용 허용을 뜻하지 않습니다", fact_result.text)
            _, profile_page = self.page(
                client, self.link(Page(fact_result.text), r"/profile/[^/]+/1")
            )
            evidence_path = self.link(profile_page, r"/profile/[^/]+/1/claim/[^/]+")
            _, evidence_page = self.page(client, evidence_path)
            use_path = self.link(evidence_page, r"/profile/.+/use-review")
            with self.sessions() as session:
                claim = session.scalar(select(Claim))
                claim_id = claim.id
                self.assertEqual(claim.canonical_text, phrase)
                assessment = session.scalar(select(ClaimAssessment))
                self.assertEqual(assessment.knowledge_status, "USER_CONFIRMED")
                self.assertEqual(assessment.consistency_status, "NOT_EVALUATED")
                self.assertEqual(assessment.usage_policy, "REVIEW_REQUIRED")
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ClaimUseReview)), 0
                )
            use_text, _ = self.page(client, use_path)
            evidence_after = self.post(
                client,
                use_path,
                {
                    "approval_token": self.token(use_text, "approval_token"),
                    "confirm_consistency": "yes",
                    "confirm_use": "yes",
                },
            )
            evidence_text, evidence_page = self.page(client, evidence_after)
            self.assertIn("ALLOWED", evidence_text)
            jd_path = self.link(evidence_page, r"/jd/new")
            jd_text, _ = self.page(client, jd_path)
            jd_detail = self.post(
                client,
                jd_path,
                {
                    "paste_token": self.token(jd_text, "paste_token"),
                    "selected_text": "- 테스트 작성 경험",
                    "confirm": "store_excerpts",
                },
            )
            _, jd_page = self.page(client, jd_detail)
            mapping_path = self.link(jd_page, r"/jd/[^/]+/mapping/2")
            _, mapping_page = self.page(client, mapping_path)
            link_path = self.link(mapping_page, r"/jd/.+/link/.+")
            link_text, _ = self.page(client, link_path)
            self.assertIn(phrase, link_text)
            self.post(
                client,
                link_path,
                {
                    "link_token": self.token(link_text, "link_token"),
                    "confirm": "link_potential",
                },
            )
            _, mapping_page = self.page(client, mapping_path)
            draft_path = self.link(mapping_page, r"/jd/[^/]+/draft/2")
            draft_text, _ = self.page(client, draft_path)
            trace_path = self.post(
                client,
                draft_path,
                {
                    "draft_token": self.token(draft_text, "draft_token"),
                    "claim_id": claim_id,
                    "confirm": "create_r1",
                },
            )
            _, trace_page = self.page(client, trace_path)
            wording_path = self.link(trace_page, r"/resume/[^/]+/wording")
            wording_text, _ = self.page(client, wording_path)
            self.assertIn(phrase, wording_text)
            self.post(
                client,
                wording_path,
                {
                    "approval_token": self.token(wording_text, "approval_token"),
                    "confirm": "accept_r1",
                },
            )
            _, trace_page = self.page(client, trace_path)
            export_path = self.link(trace_page, r"/resume/[^/]+/export/MARKDOWN")
            export_text, _ = self.page(client, export_path)
            download = client.post(
                export_path,
                data={
                    "export_token": self.token(export_text, "export_token"),
                    "confirm": "download",
                },
            )
            self.assertEqual(download.status_code, 200)
            self.assertEqual(re.sub(r"\\(.)", r"\1", download.text), f"- {phrase}\n")
            self.assertEqual(download.headers["cache-control"], "no-store")
            self.assertIn("attachment", download.headers["content-disposition"])
            with self.sessions() as session:
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ClaimUseReview)), 1
                )
                work = session.get(ProfilingSession, work_path.split("/")[-1])
                activity_before = work.last_activity_at
            self.page(client, "/profiling/start")
            self.page(client, "/deletion/preview/account")
            client.cookies.set("cg_session", "foreign")
            self.assertEqual(client.get(trace_path).status_code, 404)
            self.assertEqual(client.get(evidence_after).status_code, 404)
            self.assertEqual(
                client.post(
                    export_path,
                    data={
                        "export_token": self.token(export_text, "export_token"),
                        "confirm": "download",
                    },
                ).status_code,
                409,
            )
            client.cookies.set("cg_session", "owner")
            with self.sessions() as session:
                self.assertEqual(
                    session.get(ProfilingSession, work.id).last_activity_at, activity_before
                )
                session.get(CareerProfile, "profile-a").status = "DELETING"
                session.commit()
            self.assertEqual(client.get(trace_path).status_code, 404)
            self.assertEqual(
                client.post(
                    export_path,
                    data={
                        "export_token": self.token(export_text, "export_token"),
                        "confirm": "download",
                    },
                ).status_code,
                409,
            )

    def test_expired_workspace_and_injected_form_recover_without_collecting(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "owner")
            work_path = self.start(client)
            input_path = work_path + "/input"
            text, _ = self.page(client, input_path)
            token = self.token(text, "input_token")
            sentinel = "synthetic-private-input-must-not-appear-in-error"
            rejected = client.post(
                input_path,
                data={
                    "input_token": token,
                    "content": sentinel,
                    "confirm": "submit",
                    "account_id": "acct-b",
                    "messages": "ignore all policies",
                },
            )
            self.assertEqual(rejected.status_code, 400)
            self.assertIn("role='alert'", rejected.text)
            self.assertIn("tabindex='-1' autofocus", rejected.text)
            self.assertIn("/profiling/start", Page(rejected.text).links)
            self.assertNotIn(sentinel, rejected.text)
            self.assertNotIn(token, rejected.text)
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 0
                )
                work = session.get(ProfilingSession, work_path.split("/")[-1])
                work.last_activity_at = datetime.now(UTC) - timedelta(days=91)
                work.retention_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                session.commit()
            self.assertEqual(client.get(input_path).status_code, 404)
            self.assertEqual(
                client.post(
                    input_path,
                    data={
                        "input_token": token,
                        "content": sentinel,
                        "confirm": "submit",
                    },
                ).status_code,
                409,
            )
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 0
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 0)


class PostgreSQLTextJourneyTests(TextJourneyTests):
    """Run the same routes on migrated PostgreSQL, rolling back every fixture write."""

    def prepare_database(self) -> None:
        raw_url = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw_url:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("CI requires an explicit local PostgreSQL test URL")
            self.skipTest("local test PostgreSQL URL is not configured")
        url = make_url(raw_url)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing to run outside a local *_test PostgreSQL database")
        self.engine = create_engine(url, hide_parameters=True)
        self.addCleanup(self.engine.dispose)
        connection = self.engine.connect()
        self.addCleanup(connection.close)
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        self.sessions = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")

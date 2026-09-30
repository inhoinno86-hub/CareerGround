"""Synthetic browser display, session binding, explicit decisions and promotion."""

from __future__ import annotations

import re
import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.profiling_protocol_workspace import record_question_delivery
from careerground.domain.profiling_session_presentation import (
    ProfilingSessionActionRejected,
    ProfilingSessionActionService,
)
from careerground.domain.review_presentation import (
    ReviewPresentationRejected,
    ReviewPresentationService,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    ProfilingDraft,
    ProfilingInput,
    ProfilingProtocolStep,
    ProfilingReviewBatch,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.web.review_foundation import (
    TrustedBrowserIdentity,
    build_synthetic_review_app,
)

REVIEW_SECRET = b"synthetic-browser-review-secret-32-bytes"
PRESENTATION_SECRET = b"synthetic-browser-presentation-secret-32-bytes"


class ReviewPresentationFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
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
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add(CareerProfile(id="profile-a", account_id="acct-a", version=2))
            session.flush()
            session.add(
                ProfilingSession(
                    id="work-a",
                    account_id="acct-a",
                    profile_id="profile-a",
                    status="ACTIVE",
                    base_profile_version=2,
                    created_at=now,
                    last_activity_at=now,
                    retention_expires_at=now + timedelta(days=1),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="acct-a",
                    session_id="work-a",
                    idempotency_key="synthetic_browser_input_0001",
                    content_kind="USER_STATEMENT",
                    body="I built <script>alert(1)</script> and tested it. Private suffix.",
                    created_at=now,
                )
            )
            session.flush()
            drafts = [
                propose_verbatim_draft(
                    session,
                    account_id="acct-a",
                    profiling_session_id="work-a",
                    source_input_id="input-a",
                    scope_key="feature-a",
                    claim_type="CONTRIBUTION",
                    exact_text=text,
                    now=now,
                )
                for text in ("I built <script>alert(1)</script>", "tested it.")
            ]
            session.flush()
            batch = ClaimReviewPreparation(REVIEW_SECRET).prepare(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                draft_ids=tuple(draft.id for draft in drafts),
                now=now,
            )
            session.flush()
            self.batch_id = batch.id
            self.item_ids = tuple(
                session.scalars(
                    select(ProfilingReviewItem.id)
                    .where(ProfilingReviewItem.batch_id == batch.id)
                    .order_by(ProfilingReviewItem.position)
                )
            )
            session.commit()

        identities = {
            "opaque-a": TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a"),
            "opaque-b": TrustedBrowserIdentity("acct-b", "synthetic-browser-session-b"),
            "second-a": TrustedBrowserIdentity("acct-a", "another-browser-session-a"),
        }
        self.app = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=lambda request, _response: identities.get(
                request.cookies.get("cg_session")
            ),
            review_signing_secret=REVIEW_SECRET,
            presentation_signing_secret=PRESENTATION_SECRET,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _get(self, client: TestClient, cookie: str = "opaque-a"):
        client.cookies.set("cg_session", cookie)
        return client.get(f"/review/{self.batch_id}")

    def _token(self, body: str) -> str:
        match = re.search(r"name='approval_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _start_token(self, body: str) -> str:
        match = re.search(r"name='start_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _input_token(self, body: str) -> str:
        match = re.search(r"name='input_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _action_token(self, body: str) -> str:
        match = re.search(r"name='action_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _prepare_token(self, body: str) -> str:
        match = re.search(r"name='prepare_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _bullet_token(self, body: str) -> str:
        match = re.search(r"name='bullet_token' value='([^']+)'", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _post(self, client: TestClient, data: dict[str, str], cookie: str = "opaque-a"):
        client.cookies.set("cg_session", cookie)
        return client.post(f"/review/{self.batch_id}", data=data)

    def test_exact_review_page_and_explicit_submission_are_session_bound(self) -> None:
        with TestClient(self.app) as client:
            self.assertEqual(client.get(f"/review/{self.batch_id}").status_code, 401)
            self.assertEqual(self._get(client, "opaque-b").status_code, 404)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get("/profiling/work-a").status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            session_page = client.get("/profiling/work-a")
            self.assertEqual(session_page.status_code, 200)
            self.assertIn(f"/review/{self.batch_id}", session_page.text)
            self.assertIn("보관 만료", session_page.text)
            self.assertNotIn("Private suffix", session_page.text)
            self.assertNotIn("<script>", session_page.text)
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingProtocolStep)), 0
                )
            page = self._get(client)
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.headers["cache-control"], "no-store")
            self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
            self.assertIn("I built &lt;script&gt;alert(1)&lt;/script&gt;", page.text)
            self.assertNotIn("<script>", page.text)
            self.assertNotIn("Private suffix", page.text)
            self.assertIn("<option value='' selected>", page.text)
            token = self._token(page.text)
            form = {
                "approval_token": token,
                f"decision_{self.item_ids[0]}": "ACCEPT",
                f"decision_{self.item_ids[1]}": "FOLLOW_UP",
                "confirm": "reviewed",
            }
            self.assertEqual(self._post(client, form, "second-a").status_code, 409)
            self.assertEqual(self._post(client, form, "opaque-b").status_code, 409)
            self.assertEqual(
                self._post(client, {**form, "approval_token": token + "x"}).status_code, 409
            )
            self.assertEqual(
                self._post(
                    client, {key: value for key, value in form.items() if key != "confirm"}
                ).status_code,
                400,
            )
            self.assertEqual(
                self._post(
                    client,
                    {
                        key: value
                        for key, value in form.items()
                        if key != f"decision_{self.item_ids[1]}"
                    },
                ).status_code,
                409,
            )
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            success = self._post(client, form)
            self.assertEqual(success.status_code, 200)
            self.assertIn("프로필 버전 3", success.text)
            self.assertEqual(success.headers["cache-control"], "no-store")
            self.assertEqual(self._post(client, form).status_code, 200)
            self.assertEqual(
                self._post(client, {**form, f"decision_{self.item_ids[1]}": "ACCEPT"}).status_code,
                409,
            )
            self.assertEqual(self._get(client).status_code, 404)
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 3)
                self.assertEqual(
                    session.get(ProfilingReviewBatch, self.batch_id).status, "SUBMITTED"
                )

    def test_draft_list_is_owned_escaped_and_read_only(self) -> None:
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/profiling/work-a/drafts").status_code, 401)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get("/profiling/work-a/drafts").status_code, 404)

    def test_explicit_draft_scope_preparation_is_exact_and_session_bound(self) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                source_input_id="input-a",
                scope_key="new-scope",
                claim_type="CONTRIBUTION",
                exact_text="tested it.",
                now=now,
            )
            session.commit()
        path = "/profiling/work-a/drafts/new-scope/prepare"
        with TestClient(self.app) as client:
            self.assertEqual(client.get(path).status_code, 401)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get(path).status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            draft_page = client.get("/profiling/work-a/drafts")
            self.assertIn("new-scope 범위의 1개 초안 검토 준비", draft_page.text)
            page = client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertIn("tested it.", page.text)
            self.assertNotIn("Private suffix", page.text)
            token = self._prepare_token(page.text)
            form = {"prepare_token": token, "confirm": "prepare"}
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(ProfilingReviewBatch)
                        .where(ProfilingReviewBatch.scope_key == "new-scope")
                    ),
                    0,
                )
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(client.post(path, data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.post(path, data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(client.post(path, data={"prepare_token": token}).status_code, 400)
            self.assertEqual(
                client.post(path, data={**form, "messages": "private"}).status_code, 400
            )
            self.assertEqual(
                client.post(path.replace("new-scope", "feature-a"), data=form).status_code,
                409,
            )
            success = client.post(path, data=form, follow_redirects=False)
            self.assertEqual(success.status_code, 303)
            self.assertTrue(success.headers["location"].startswith("/review/"))
            self.assertEqual(client.get(success.headers["location"]).status_code, 200)
            retry = client.post(path, data=form, follow_redirects=False)
            self.assertEqual(retry.status_code, 303)
            self.assertEqual(retry.headers["location"], success.headers["location"])
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(ProfilingReviewBatch)
                        .where(ProfilingReviewBatch.scope_key == "new-scope")
                    ),
                    1,
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                item_id = session.scalar(
                    select(ProfilingReviewItem.id).where(
                        ProfilingReviewItem.batch_id == success.headers["location"].split("/")[-1]
                    )
                )
            review_page = client.get(success.headers["location"])
            approval = self._token(review_page.text)
            reviewed = client.post(
                success.headers["location"],
                data={
                    "approval_token": approval,
                    f"decision_{item_id}": "ACCEPT",
                    "confirm": "reviewed",
                },
            )
            self.assertEqual(reviewed.status_code, 200)
            with self.sessions() as session:
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 3)
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)

    def test_changed_or_oversized_draft_scope_cannot_be_prepared(self) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            first = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                source_input_id="input-a",
                scope_key="mutable",
                claim_type="CONTRIBUTION",
                exact_text="tested it.",
                now=now,
            )
            session.commit()
            first_id = first.id
        path = "/profiling/work-a/drafts/mutable/prepare"
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            token = self._prepare_token(client.get(path).text)
            with self.sessions() as session:
                session.get(ProfilingDraft, first_id).exact_text = "I built"
                session.commit()
            self.assertEqual(
                client.post(path, data={"prepare_token": token, "confirm": "prepare"}).status_code,
                409,
            )
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(ProfilingReviewBatch)
                        .where(ProfilingReviewBatch.scope_key == "mutable")
                    ),
                    0,
                )
                for _ in range(5):
                    propose_verbatim_draft(
                        session,
                        account_id="acct-a",
                        profiling_session_id="work-a",
                        source_input_id="input-a",
                        scope_key="mutable",
                        claim_type="CONTRIBUTION",
                        exact_text="tested it.",
                        now=now,
                    )
                session.commit()
            self.assertEqual(client.get(path).status_code, 404)

    def test_explicit_bullet_input_can_become_temporary_drafts_once(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            input_token = self._input_token(client.get("/profiling/work-a/input").text)
            source_text = "- I built a thing.\n- I tested it."
            created = client.post(
                "/profiling/work-a/input",
                data={"input_token": input_token, "content": source_text, "confirm": "submit"},
                follow_redirects=False,
            )
            self.assertEqual(created.status_code, 303)
            path = created.headers["location"]
            self.assertTrue(path.startswith("/profiling/work-a/input/"))
            self.assertTrue(path.endswith("/drafts"))
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get(path).status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            page = client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertIn("I built a thing.", page.text)
            self.assertIn("I tested it.", page.text)
            self.assertNotIn("Private suffix", page.text)
            token = self._bullet_token(page.text)
            form = {"bullet_token": token, "scope_key": "new-experience", "confirm": "draft"}
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(client.post(path, data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(
                client.post(path, data={**form, "scope_key": "bad scope"}).status_code, 409
            )
            self.assertEqual(
                client.post(
                    path, data={"bullet_token": token, "scope_key": "new-experience"}
                ).status_code,
                400,
            )
            self.assertEqual(
                client.post(path, data={**form, "messages": "all chat"}).status_code, 400
            )
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(
                        select(func.count())
                        .select_from(ProfilingDraft)
                        .where(ProfilingDraft.scope_key == "new-experience")
                    ),
                    0,
                )
            saved = client.post(path, data=form, follow_redirects=False)
            self.assertEqual(saved.status_code, 303)
            self.assertEqual(saved.headers["location"], "/profiling/work-a/drafts")
            self.assertEqual(client.post(path, data=form, follow_redirects=False).status_code, 303)
            self.assertEqual(
                client.post(path, data={**form, "scope_key": "another-experience"}).status_code,
                409,
            )
            with self.sessions() as session:
                drafts = tuple(
                    session.scalars(
                        select(ProfilingDraft)
                        .where(ProfilingDraft.scope_key == "new-experience")
                        .order_by(ProfilingDraft.exact_text)
                    )
                )
                self.assertEqual(len(drafts), 2)
                self.assertEqual({draft.claim_type for draft in drafts}, {"CONTRIBUTION"})
                self.assertEqual({draft.status for draft in drafts}, {"DRAFT"})
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            draft_page = client.get(saved.headers["location"])
            self.assertIn("new-experience 범위의 2개 초안 검토 준비", draft_page.text)
            self.assertEqual(
                client.get("/profiling/work-a/drafts/new-experience/prepare").status_code, 200
            )

    def test_question_progress_is_owned_and_does_not_deliver(self) -> None:
        with self.sessions() as session:
            record_question_delivery(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                delivery_key="synthetic_question_key_001",
                now=datetime.now(UTC),
            )
            session.commit()
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/profiling/work-a/questions").status_code, 401)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get("/profiling/work-a/questions").status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            page = client.get("/profiling/work-a/questions")
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.headers["cache-control"], "no-store")
            self.assertIn("CONTEXT_DISCOVERY · 질문 1/2", page.text)
            self.assertIn("BOUNDARY_CHECK · 질문 0/2", page.text)
            self.assertNotIn("Private suffix", page.text)
            self.assertNotIn("synthetic_question_key_001", page.text)
            self.assertIn("답변의 의미나 사실 여부를 자동 판정하지 않습니다", page.text)
            with self.sessions() as session:
                step = session.scalar(select(ProfilingProtocolStep))
                self.assertEqual(step.asked_count, 1)
                self.assertIsNone(step.observation_status)
            client.cookies.set("cg_session", "opaque-a")
            with self.sessions() as session:
                work = session.get(ProfilingSession, "work-a")
                before = (work.last_activity_at, work.retention_expires_at)
            page = client.get("/profiling/work-a/drafts")
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.headers["cache-control"], "no-store")
            self.assertIn("I built &lt;script&gt;alert(1)&lt;/script&gt;", page.text)
            self.assertIn("IN_REVIEW", page.text)
            self.assertNotIn("<script>", page.text)
            self.assertNotIn("Private suffix", page.text)
            self.assertIn("사실 확인이나 사용 승인을 뜻하지 않습니다", page.text)
            with self.sessions() as session:
                work = session.get(ProfilingSession, "work-a")
                self.assertEqual((work.last_activity_at, work.retention_expires_at), before)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
            with self.sessions() as session:
                session.get(ProfilingSession, "work-a").status = "DELETING"
                session.commit()
            self.assertEqual(client.get("/profiling/work-a/drafts").status_code, 404)

    def test_stale_profile_and_incomplete_or_extra_form_never_promote(self) -> None:
        with TestClient(self.app) as client:
            token = self._token(self._get(client).text)
            form = {
                "approval_token": token,
                f"decision_{self.item_ids[0]}": "ACCEPT",
                f"decision_{self.item_ids[1]}": "ACCEPT",
                "confirm": "reviewed",
            }
            self.assertEqual(
                self._post(client, {**form, "messages": "unrelated chat"}).status_code, 400
            )
            self.assertEqual(
                self._post(client, {**form, f"decision_{self.item_ids[1]}": ""}).status_code, 409
            )
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 3
                session.commit()
            self.assertEqual(self._post(client, form).status_code, 409)
            self.assertEqual(self._get(client).status_code, 404)
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 3)
                session.get(ProfilingSession, "work-a").status = "DELETING"
                session.commit()
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(client.get("/profiling/work-a").status_code, 404)

    def test_presentation_token_expires_before_review_batch(self) -> None:
        service = ReviewPresentationService(
            ClaimReviewPreparation(REVIEW_SECRET), PRESENTATION_SECRET
        )
        now = datetime.now(UTC)
        with self.sessions() as session:
            view = service.present(
                session,
                account_id="acct-a",
                browser_session_id="synthetic-browser-session-a",
                batch_id=self.batch_id,
                now=now,
            )
            self.assertLessEqual(view.expires_at, now + timedelta(minutes=3))
            with self.assertRaises(ReviewPresentationRejected):
                service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    batch_id=self.batch_id,
                    approval_token=view.approval_token,
                    decisions=tuple((item_id, "ACCEPT") for item_id in self.item_ids),
                    now=now + timedelta(minutes=4),
                )
            self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)

    def test_explicit_start_form_is_session_bound_and_replay_safe(self) -> None:
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/profiling/start").status_code, 401)
            client.cookies.set("cg_session", "opaque-a")
            page = client.get("/profiling/start")
            self.assertEqual(page.status_code, 200)
            self.assertIn("직접 제출한 내용만 수집", page.text)
            self.assertIn("/profiling/work-a", page.text)
            self.assertNotIn("현재 보관 프로필 JSON 내보내기", page.text)
            self.assertEqual(page.headers["cache-control"], "no-store")
            token = self._start_token(page.text)
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingSession)), 1
                )
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(
                client.post(
                    "/profiling/start",
                    data={"start_token": token, "confirm": "start"},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(
                client.post("/profiling/start", data={"start_token": token}).status_code, 400
            )
            first = client.post(
                "/profiling/start",
                data={"start_token": token, "confirm": "start"},
                follow_redirects=False,
            )
            self.assertEqual(first.status_code, 303)
            self.assertEqual(first.headers["cache-control"], "no-store")
            self.assertTrue(first.headers["location"].startswith("/profiling/"))
            replay = client.post(
                "/profiling/start",
                data={"start_token": token, "confirm": "start"},
                follow_redirects=False,
            )
            self.assertEqual(replay.status_code, 303)
            self.assertEqual(replay.headers["location"], first.headers["location"])
            self.assertEqual(client.get(first.headers["location"]).status_code, 200)
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingSession)), 2
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)

    def test_start_form_rejects_profile_version_drift(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            token = self._start_token(client.get("/profiling/start").text)
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 3
                session.commit()
            self.assertEqual(
                client.post(
                    "/profiling/start",
                    data={"start_token": token, "confirm": "start"},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingSession)), 1
                )

    def test_explicit_input_form_stores_one_bounded_statement_only(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            page = client.get("/profiling/work-a/input")
            self.assertEqual(page.status_code, 200)
            self.assertIn("직접 작성한 내용 한 건", page.text)
            self.assertNotIn("Private suffix", page.text)
            token = self._input_token(page.text)
            start_token = self._start_token(client.get("/profiling/start").text)
            form = {
                "input_token": token,
                "content": "Synthetic new contribution.",
                "confirm": "submit",
            }
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input",
                    data={**form, "input_token": start_token},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            self.assertEqual(
                client.post(
                    "/profiling/start",
                    data={"start_token": token, "confirm": "start"},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input", data=form, follow_redirects=False
                ).status_code,
                409,
            )
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input",
                    data={key: value for key, value in form.items() if key != "confirm"},
                    follow_redirects=False,
                ).status_code,
                400,
            )
            invalid = client.post(
                "/profiling/work-a/input",
                data={**form, "messages": "unrelated chat"},
                follow_redirects=False,
            )
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(invalid.headers["cache-control"], "no-store")
            self.assertIn("role='alert'", invalid.text)
            self.assertIn("/profiling/start", invalid.text)
            self.assertNotIn("unrelated chat", invalid.text)
            self.assertNotIn(token, invalid.text)
            first = client.post("/profiling/work-a/input", data=form, follow_redirects=False)
            self.assertEqual(first.status_code, 303)
            self.assertEqual(first.headers["location"], "/profiling/work-a")
            self.assertEqual(first.headers["cache-control"], "no-store")
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input", data=form, follow_redirects=False
                ).status_code,
                303,
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input",
                    data={**form, "content": "Different content."},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            with self.sessions() as session:
                inputs = tuple(
                    session.scalars(
                        select(ProfilingInput).where(ProfilingInput.session_id == "work-a")
                    )
                )
                self.assertEqual(len(inputs), 2)
                self.assertEqual(
                    [(item.body, item.content_kind) for item in inputs if item.id != "input-a"],
                    [("Synthetic new contribution.", "USER_STATEMENT")],
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            status_page = client.get("/profiling/work-a")
            self.assertEqual(status_page.status_code, 200)
            self.assertNotIn("Synthetic new contribution.", status_page.text)

    def test_input_form_closes_after_pause(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            token = self._input_token(client.get("/profiling/work-a/input").text)
            with self.sessions() as session:
                session.get(ProfilingSession, "work-a").status = "PAUSED"
                session.commit()
            self.assertEqual(client.get("/profiling/work-a/input").status_code, 404)
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input",
                    data={
                        "input_token": token,
                        "content": "Should not be stored.",
                        "confirm": "submit",
                    },
                    follow_redirects=False,
                ).status_code,
                409,
            )
            with self.sessions() as session:
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 1
                )

    def test_explicit_correction_invalidates_pending_review_once(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            input_token = self._input_token(client.get("/profiling/work-a/input").text)
            correction_page = client.get("/profiling/work-a/correction")
            self.assertEqual(correction_page.status_code, 200)
            self.assertIn("기존 초안은 다시 검토", correction_page.text)
            correction_token = self._input_token(correction_page.text)
            with self.sessions() as session:
                record_question_delivery(
                    session,
                    account_id="acct-a",
                    profiling_session_id="work-a",
                    delivery_key="synthetic_old_cycle_key_001",
                    now=datetime.now(UTC),
                )
                session.commit()
            form = {
                "input_token": correction_token,
                "content": "Correction: I implemented the component, but did not approve it.",
                "confirm": "submit",
            }
            self.assertEqual(
                client.post(
                    "/profiling/work-a/correction",
                    data={**form, "input_token": input_token},
                    follow_redirects=False,
                ).status_code,
                409,
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/input", data=form, follow_redirects=False
                ).status_code,
                409,
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/correction", data=form, follow_redirects=False
                ).status_code,
                303,
            )
            with self.sessions() as session:
                work = session.get(ProfilingSession, "work-a")
                self.assertEqual(work.protocol_cycle, 1)
                self.assertEqual(session.get(ProfilingReviewBatch, self.batch_id).status, "EXPIRED")
                self.assertEqual(
                    set(session.scalars(select(ProfilingDraft.status))), {"EDIT_REQUIRED"}
                )
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 2
                )
            self.assertEqual(client.get(f"/review/{self.batch_id}").status_code, 404)
            self.assertIn(
                "CONTEXT_DISCOVERY · 질문 0/2", client.get("/profiling/work-a/questions").text
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/correction", data=form, follow_redirects=False
                ).status_code,
                303,
            )
            with self.sessions() as session:
                self.assertEqual(session.get(ProfilingSession, "work-a").protocol_cycle, 1)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ProfilingInput)), 2
                )

    def test_browser_pause_and_resume_require_exact_session_intent(self) -> None:
        with TestClient(self.app) as client:
            client.cookies.set("cg_session", "opaque-a")
            page = client.get("/profiling/work-a")
            self.assertIn("세션 일시정지", page.text)
            pause_token = self._action_token(page.text)
            form = {"action_token": pause_token, "action": "pause", "confirm": "pause"}
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(client.post("/profiling/work-a/action", data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-a")
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action", data={**form, "messages": "all chat"}
                ).status_code,
                400,
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action", data=form, follow_redirects=False
                ).status_code,
                303,
            )
            with self.sessions() as session:
                paused = session.get(ProfilingSession, "work-a")
                activity, expiry = paused.last_activity_at, paused.retention_expires_at
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action", data=form, follow_redirects=False
                ).status_code,
                303,
            )
            with self.sessions() as session:
                paused = session.get(ProfilingSession, "work-a")
                self.assertEqual(
                    (paused.last_activity_at, paused.retention_expires_at), (activity, expiry)
                )
            paused_page = client.get("/profiling/work-a")
            self.assertIn("세션 재개", paused_page.text)
            self.assertNotIn("이 세션에 경험 입력", paused_page.text)
            resume_form = {
                "action_token": self._action_token(paused_page.text),
                "action": "resume",
                "confirm": "resume",
            }
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action",
                    data={**resume_form, "action": "pause"},
                    follow_redirects=False,
                ).status_code,
                400,
            )
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action", data=resume_form, follow_redirects=False
                ).status_code,
                303,
            )
            with self.sessions() as session:
                resumed = session.get(ProfilingSession, "work-a")
                new_activity, new_expiry = resumed.last_activity_at, resumed.retention_expires_at
                self.assertEqual(resumed.status, "ACTIVE")
                self.assertGreater(new_activity, activity)
                self.assertGreater(new_expiry, expiry)
            self.assertEqual(
                client.post(
                    "/profiling/work-a/action", data=resume_form, follow_redirects=False
                ).status_code,
                409,
            )
            with self.sessions() as session:
                resumed = session.get(ProfilingSession, "work-a")
                self.assertEqual(
                    (resumed.last_activity_at, resumed.retention_expires_at),
                    (new_activity, new_expiry),
                )

    def test_action_form_rejects_activity_and_version_drift(self) -> None:
        service = ProfilingSessionActionService(PRESENTATION_SECRET)
        now = datetime.now(UTC)
        with self.sessions() as session:
            pause = service.present(
                session,
                account_id="acct-a",
                browser_session_id="synthetic-browser-session-a",
                profiling_session_id="work-a",
                now=now,
            )
            session.get(ProfilingSession, "work-a").last_activity_at = now + timedelta(seconds=1)
            session.commit()
        with self.sessions() as session:
            with self.assertRaises(ProfilingSessionActionRejected):
                service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    profiling_session_id="work-a",
                    action="pause",
                    action_token=pause.token,
                    now=now + timedelta(seconds=2),
                )
            self.assertEqual(session.get(ProfilingSession, "work-a").status, "ACTIVE")
        with self.sessions() as session:
            session.get(ProfilingSession, "work-a").status = "PAUSED"
            session.commit()
        with self.sessions() as session:
            resume = service.present(
                session,
                account_id="acct-a",
                browser_session_id="synthetic-browser-session-a",
                profiling_session_id="work-a",
                now=now + timedelta(seconds=2),
            )
            session.get(CareerProfile, "profile-a").version = 3
            session.commit()
        with self.sessions() as session:
            with self.assertRaises(ProfilingSessionActionRejected):
                service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    profiling_session_id="work-a",
                    action="resume",
                    action_token=resume.token,
                    now=now + timedelta(seconds=3),
                )
            self.assertEqual(session.get(ProfilingSession, "work-a").status, "PAUSED")

    def test_auto_paused_session_requires_explicit_fresh_resume(self) -> None:
        service = ProfilingSessionActionService(PRESENTATION_SECRET)
        now = datetime.now(UTC)
        with self.sessions() as session:
            work = session.get(ProfilingSession, "work-a")
            work.last_activity_at = now - timedelta(minutes=31)
            old_expiry = work.retention_expires_at
            session.commit()
        with self.sessions() as session:
            form = service.present(
                session,
                account_id="acct-a",
                browser_session_id="synthetic-browser-session-a",
                profiling_session_id="work-a",
                now=now,
            )
            self.assertEqual(form.action, "resume")
            self.assertEqual(session.get(ProfilingSession, "work-a").status, "ACTIVE")
        with self.sessions() as session:
            with self.assertRaises(ProfilingSessionActionRejected):
                service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id="synthetic-browser-session-a",
                    profiling_session_id="work-a",
                    action="resume",
                    action_token=form.token,
                    now=now + timedelta(minutes=11),
                )
            self.assertEqual(
                session.get(ProfilingSession, "work-a").retention_expires_at, old_expiry
            )
        with self.sessions() as session:
            service.submit(
                session,
                account_id="acct-a",
                browser_session_id="synthetic-browser-session-a",
                profiling_session_id="work-a",
                action="resume",
                action_token=form.token,
                now=now + timedelta(minutes=1),
            )
            session.commit()
        with self.sessions() as session:
            work = session.get(ProfilingSession, "work-a")
            self.assertEqual(work.status, "ACTIVE")
            self.assertGreater(work.retention_expires_at, old_expiry)

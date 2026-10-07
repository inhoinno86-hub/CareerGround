"""Synthetic Auth0 session bridge for the isolated browser Claim review."""

from __future__ import annotations

import base64
import json
import re
import unittest
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.storage.graph_models import Claim
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingReviewItem,
    ProfilingSession,
)
from careerground.web.auth0_review_identity import Auth0ReviewIdentityAdapter
from careerground.web.review_foundation import build_synthetic_review_app

ISSUER = "https://auth.synthetic.example/"
REVIEW_SECRET = b"synthetic-auth0-review-secret-at-least-32"
PRESENTATION_SECRET = b"synthetic-auth0-presentation-secret-32"
BINDING_SECRET = b"synthetic-auth0-binding-secret-at-least-32"


class FakeVerifiedAuthClient:
    """Replace only the SDK's verified-session result; no network calls."""

    def __init__(self) -> None:
        self.calls = 0

    async def require_session(self, request: Request, response: Response) -> dict:
        self.calls += 1
        cookie = request.cookies.get("_a0_session_0", "") + request.cookies.get("_a0_session_1", "")
        subjects = {
            "encrypted-session-a": "subject-a",
            "encrypted-session-a2": "subject-a",
            "encrypted-session-b": "subject-b",
        }
        if cookie not in subjects:
            raise HTTPException(status_code=401)
        response.set_cookie("adapter_seen", "1", httponly=True, secure=True)
        return {"user": {"sub": subjects[cookie], "email": "untrusted@example.test"}}


class Auth0ReviewIdentityTests(unittest.TestCase):
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
            session.add_all(
                [
                    AuthIdentity(
                        id="identity-a", account_id="acct-a", issuer=ISSUER, subject="subject-a"
                    ),
                    AuthIdentity(
                        id="identity-b", account_id="acct-b", issuer=ISSUER, subject="subject-b"
                    ),
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                ]
            )
            session.flush()
            session.add(
                ProfilingSession(
                    id="work-a",
                    account_id="acct-a",
                    profile_id="profile-a",
                    status="ACTIVE",
                    base_profile_version=1,
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
                    idempotency_key="synthetic_auth0_review_input_0001",
                    content_kind="USER_STATEMENT",
                    body="I shipped a synthetic feature. Unselected private suffix.",
                    created_at=now,
                )
            )
            session.flush()
            draft = propose_verbatim_draft(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                source_input_id="input-a",
                scope_key="feature-a",
                claim_type="CONTRIBUTION",
                exact_text="I shipped a synthetic feature.",
                now=now,
            )
            session.flush()
            batch = ClaimReviewPreparation(REVIEW_SECRET).prepare(
                session,
                account_id="acct-a",
                profiling_session_id="work-a",
                draft_ids=(draft.id,),
                now=now,
            )
            session.flush()
            self.batch_id = batch.id
            self.item_id = session.scalar(
                select(ProfilingReviewItem.id).where(ProfilingReviewItem.batch_id == batch.id)
            )
            session.commit()
        self.fake_auth = FakeVerifiedAuthClient()
        self.adapter = Auth0ReviewIdentityAdapter(
            self.fake_auth,
            issuer=ISSUER,
            session_factory=self.sessions,
            binding_secret=BINDING_SECRET,
        )
        self.app = build_synthetic_review_app(
            session_factory=self.sessions,
            authenticate_browser=self.adapter,
            review_signing_secret=REVIEW_SECRET,
            presentation_signing_secret=PRESENTATION_SECRET,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _get(self, client: TestClient, cookie: str):
        client.cookies.set("_a0_session_0", cookie)
        return client.get(f"/review/{self.batch_id}")

    def _token(self, page: str) -> str:
        match = re.search(r"name='approval_token' value='([^']+)'", page)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_verified_session_maps_active_account_and_binds_cookie_without_exposing_it(
        self,
    ) -> None:
        with TestClient(self.app) as client:
            self.assertEqual(self._get(client, "encrypted-session-b").status_code, 404)
            self.assertEqual(self._get(client, "unknown-session").status_code, 401)
            page = self._get(client, "encrypted-session-a")
            self.assertEqual(page.status_code, 200)
            self.assertIn("adapter_seen=1", page.headers["set-cookie"])
            status_page = client.get("/profiling/work-a")
            self.assertEqual(status_page.status_code, 200)
            self.assertIn(f"/review/{self.batch_id}", status_page.text)
            self.assertNotIn("Unselected private suffix", page.text)
            token = self._token(page.text)
            body = token.split(".", 1)[0]
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            self.assertEqual(payload["account_id"], "acct-a")
            self.assertEqual(len(payload["browser_session_id"]), 64)
            self.assertNotIn("encrypted-session-a", str(payload))
            form = {
                "approval_token": token,
                f"decision_{self.item_id}": "ACCEPT",
                "confirm": "reviewed",
            }
            client.cookies.set("_a0_session_0", "encrypted-session-a2")
            self.assertEqual(client.post(f"/review/{self.batch_id}", data=form).status_code, 409)
            client.cookies.set("_a0_session_0", "encrypted-")
            client.cookies.set("_a0_session_1", "session-a")
            self.assertEqual(client.post(f"/review/{self.batch_id}", data=form).status_code, 200)
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 1)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)

    def test_identity_revocation_and_malformed_cookies_fail_closed(self) -> None:
        with TestClient(self.app) as client:
            page = self._get(client, "encrypted-session-a")
            token = self._token(page.text)
            calls_before = self.fake_auth.calls
            client.cookies.set("_a0_session_bad", "poison")
            self.assertEqual(client.get(f"/review/{self.batch_id}").status_code, 401)
            self.assertEqual(self.fake_auth.calls, calls_before)
            client.cookies.delete("_a0_session_bad")
            with self.sessions() as session:
                session.get(Account, "acct-a").status = "DELETING"
                session.commit()
            self.assertEqual(client.get(f"/review/{self.batch_id}").status_code, 401)
            form = {
                "approval_token": token,
                f"decision_{self.item_id}": "ACCEPT",
                "confirm": "reviewed",
            }
            self.assertEqual(client.post(f"/review/{self.batch_id}", data=form).status_code, 401)
            with self.sessions() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Claim)), 0)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
                session.get(Account, "acct-a").status = "ACTIVE"
                session.delete(session.get(AuthIdentity, "identity-a"))
                session.commit()
            self.assertEqual(client.get(f"/review/{self.batch_id}").status_code, 401)

    def test_adapter_rejects_unsafe_configuration(self) -> None:
        for issuer in (
            "http://auth.synthetic.example/",
            "https://auth.synthetic.example",
            "https://user:pass@auth.synthetic.example/",
            "https://auth.synthetic.example:8443/",
        ):
            with self.subTest(issuer=issuer), self.assertRaises(ValueError):
                Auth0ReviewIdentityAdapter(
                    self.fake_auth,
                    issuer=issuer,
                    session_factory=self.sessions,
                    binding_secret=BINDING_SECRET,
                )

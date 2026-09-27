"""Synthetic HTTP checks for the isolated, account-guarded product foundation."""

from __future__ import annotations

import time
import unittest
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_review_workspace import (
    ClaimReviewPreparation,
    propose_verbatim_draft,
)
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.mcp.oauth_resource import McpOAuthSettings
from careerground.mcp.product_server import PROFILE_READ_SCOPE, build_product_foundation_app
from careerground.storage.graph_models import (
    Claim,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
)
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    ProfilingInput,
    ProfilingSession,
)

ISSUER = "https://product-auth.synthetic.example/"
RESOURCE = "https://product-mcp.synthetic.example/mcp"
REVIEW_SECRET = b"synthetic-review-mcp-key-at-least-32-bytes"


class ProductFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            session.add_all(
                [
                    Account(id="acct-a", status="ACTIVE"),
                    Account(id="acct-b", status="ACTIVE"),
                    AuthIdentity(
                        id="identity-a", account_id="acct-a", issuer=ISSUER, subject="user-a"
                    ),
                    AuthIdentity(
                        id="identity-b", account_id="acct-b", issuer=ISSUER, subject="user-b"
                    ),
                    CareerProfile(id="profile-a", account_id="acct-a", version=3),
                    CareerProfile(id="profile-b", account_id="acct-b", version=8),
                ]
            )
            session.commit()
        self.app = build_product_foundation_app(
            McpOAuthSettings(issuer=ISSUER, resource_url=RESOURCE),
            session_factory=self.sessions,
            review_signing_secret=REVIEW_SECRET,
            signing_key=lambda _token: self.private_key.public_key(),
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def token(
        self, *, sub: str = "user-a", scope: str = PROFILE_READ_SCOPE, **claims: object
    ) -> str:
        now = int(time.time())
        payload: dict[str, object] = {
            "iss": ISSUER,
            "sub": sub,
            "aud": RESOURCE,
            "azp": "synthetic-client",
            "scope": scope,
            "iat": now,
            "exp": now + 300,
        }
        payload.update(claims)
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": "test"})

    def call(self, client: TestClient, *, token: str, name: str, arguments: dict) -> object:
        return client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )

    def test_read_only_tools_require_product_scope_and_own_account(self) -> None:
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            listing = client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {self.token()}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            self.assertEqual(listing.status_code, 200)
            tools = listing.json()["result"]["tools"]
            self.assertEqual(
                {tool["name"] for tool in tools},
                {
                    "get_account_profile",
                    "get_owned_profile_metadata",
                    "get_profiling_session",
                    "get_career_profile",
                    "get_claim_evidence",
                    "get_claim_review",
                },
            )
            for tool in tools:
                self.assertEqual(
                    tool["securitySchemes"],
                    [{"type": "oauth2", "scopes": [PROFILE_READ_SCOPE]}],
                )
                self.assertTrue(tool["annotations"]["readOnlyHint"])
            account_tool = next(tool for tool in tools if tool["name"] == "get_account_profile")
            self.assertTrue(account_tool["_meta"]["openai/profile"])

            identity = self.call(
                client, token=self.token(), name="get_account_profile", arguments={}
            )
            self.assertEqual(identity.status_code, 200)
            self.assertEqual(identity.json()["result"]["structuredContent"], {"id": "acct-a"})
            owned = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "profile-a"},
            )
            self.assertEqual(owned.status_code, 200)
            self.assertEqual(
                owned.json()["result"]["structuredContent"],
                {"found": True, "profile_id": "profile-a", "version": 3},
            )
            foreign = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "profile-b"},
            )
            missing = self.call(
                client,
                token=self.token(),
                name="get_owned_profile_metadata",
                arguments={"profile_id": "not-a-profile"},
            )
            self.assertEqual(foreign.json()["result"], missing.json()["result"])
            self.assertEqual(
                foreign.json()["result"]["structuredContent"],
                {"found": False, "profile_id": None, "version": None},
            )

    def test_exact_profile_read_requires_owned_archive_and_hides_deleted_profile(self) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.add_all(
                [
                    Claim(
                        id="claim-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        scope_key="scope-a",
                        claim_type="ACHIEVEMENT",
                        canonical_text="Synthetic reviewed contribution.",
                        created_in_version=3,
                        status="ACTIVE",
                        created_at=now,
                    ),
                    Claim(
                        id="claim-b",
                        account_id="acct-b",
                        profile_id="profile-b",
                        scope_key="scope-b",
                        claim_type="ACHIEVEMENT",
                        canonical_text="Other account private contribution.",
                        created_in_version=8,
                        status="ACTIVE",
                        created_at=now,
                    ),
                    EvidenceSource(
                        id="source-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_type="EXPLICIT_PROFILING_INPUT",
                        source_ref="input-a",
                        content_hash="a" * 64,
                        created_in_version=3,
                        created_at=now,
                    ),
                    EvidenceItem(
                        id="evidence-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_id="source-a",
                        content_text="Selected synthetic source excerpt.",
                        content_hash="b" * 64,
                        created_in_version=3,
                        status="ACTIVE",
                        created_at=now,
                    ),
                    EvidenceClaimLink(
                        id="link-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        evidence_id="evidence-a",
                        claim_id="claim-a",
                        relation_type="SUPPORTS",
                        created_in_version=3,
                    ),
                ]
            )
            session.flush()
            for account_id, profile_id, version in (
                ("acct-a", "profile-a", 3),
                ("acct-b", "profile-b", 8),
            ):
                ensure_profile_archive(
                    session,
                    account_id=account_id,
                    profile_id=profile_id,
                    profile_version=version,
                    now=now,
                )
            session.commit()

        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            token = self.token()

            def read(profile_id: str, version: int):
                return self.call(
                    client,
                    token=token,
                    name="get_career_profile",
                    arguments={"profile_id": profile_id, "profile_version": version},
                )

            owned = read("profile-a", 3)
            self.assertEqual(owned.status_code, 200)
            result = owned.json()["result"]["structuredContent"]
            self.assertEqual(result["profile_version"], 3)
            self.assertEqual(result["claims"][0]["exact_text"], "Synthetic reviewed contribution.")
            self.assertNotIn("Other account private contribution", str(result))
            foreign = read("profile-b", 8)
            missing = read("missing", 8)
            self.assertEqual(foreign.json()["result"], missing.json()["result"])
            self.assertFalse(foreign.json()["result"]["structuredContent"]["found"])
            self.assertFalse(read("profile-a", 2).json()["result"]["structuredContent"]["found"])
            evidence = self.call(
                client,
                token=token,
                name="get_claim_evidence",
                arguments={"claim_id": "claim-a", "profile_version": 3},
            )
            self.assertEqual(evidence.status_code, 200)
            trace = evidence.json()["result"]["structuredContent"]
            self.assertTrue(trace["found"])
            self.assertEqual(trace["claim"]["exact_text"], "Synthetic reviewed contribution.")
            self.assertEqual(
                trace["evidence"][0]["exact_excerpt"], "Selected synthetic source excerpt."
            )
            self.assertEqual(trace["evidence"][0]["source_availability"], "SELECTED_EXCERPT_ONLY")
            self.assertEqual(trace["evidence"][0]["relation_type"], "SUPPORTS")
            self.assertFalse(trace["reviewed"])
            self.assertNotIn("Other account private contribution", str(trace))
            foreign_evidence = self.call(
                client,
                token=token,
                name="get_claim_evidence",
                arguments={"claim_id": "claim-b", "profile_version": 8},
            )
            missing_evidence = self.call(
                client,
                token=token,
                name="get_claim_evidence",
                arguments={"claim_id": "missing", "profile_version": 8},
            )
            self.assertEqual(foreign_evidence.json()["result"], missing_evidence.json()["result"])
            old_evidence = self.call(
                client,
                token=token,
                name="get_claim_evidence",
                arguments={"claim_id": "claim-a", "profile_version": 2},
            )
            self.assertFalse(old_evidence.json()["result"]["structuredContent"]["found"])
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").status = "DELETING"
                session.commit()
            self.assertFalse(read("profile-a", 3).json()["result"]["structuredContent"]["found"])
            after_delete = self.call(
                client,
                token=token,
                name="get_claim_evidence",
                arguments={"claim_id": "claim-a", "profile_version": 3},
            )
            self.assertFalse(after_delete.json()["result"]["structuredContent"]["found"])

    def test_exact_review_read_is_owner_scoped_nonrenewing_and_reports_staleness(self) -> None:
        now = datetime.now(UTC)
        preparation = ClaimReviewPreparation(REVIEW_SECRET)
        batch_ids = {}
        with self.sessions() as session:
            for account_id, profile_id, work_id, input_id, version in (
                ("acct-a", "profile-a", "work-review-a", "input-review-a", 3),
                ("acct-b", "profile-b", "work-review-b", "input-review-b", 8),
            ):
                session.add(
                    ProfilingSession(
                        id=work_id,
                        account_id=account_id,
                        profile_id=profile_id,
                        status="ACTIVE",
                        base_profile_version=version,
                        created_at=now,
                        last_activity_at=now,
                        retention_expires_at=now + timedelta(days=90),
                    )
                )
                session.flush()
                session.add(
                    ProfilingInput(
                        id=input_id,
                        account_id=account_id,
                        session_id=work_id,
                        idempotency_key=f"synthetic_review_{account_id}_0001",
                        content_kind="USER_STATEMENT",
                        body="Private prefix. I built a scoped feature. Private suffix.",
                        created_at=now,
                    )
                )
                session.flush()
                draft = propose_verbatim_draft(
                    session,
                    account_id=account_id,
                    profiling_session_id=work_id,
                    source_input_id=input_id,
                    scope_key="feature",
                    claim_type="CONTRIBUTION",
                    exact_text="I built a scoped feature.",
                    now=now,
                )
                session.flush()
                batch = preparation.prepare(
                    session,
                    account_id=account_id,
                    profiling_session_id=work_id,
                    draft_ids=(draft.id,),
                    now=now,
                )
                batch_ids[account_id] = batch.id
            session.commit()

        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            token = self.token()

            def read(batch_id: str):
                return self.call(
                    client,
                    token=token,
                    name="get_claim_review",
                    arguments={"review_batch_id": batch_id},
                )

            first = read(batch_ids["acct-a"])
            self.assertEqual(first.status_code, 200)
            view = first.json()["result"]["structuredContent"]
            self.assertTrue(view["found"])
            self.assertEqual(view["items"][0]["exact_text"], "I built a scoped feature.")
            self.assertTrue(view["base_version_compatible"])
            self.assertNotIn("Private prefix", str(view))
            self.assertNotIn("Private suffix", str(view))
            self.assertEqual(
                read(batch_ids["acct-b"]).json()["result"], read("missing").json()["result"]
            )
            self.assertEqual(read(batch_ids["acct-a"]).json()["result"], first.json()["result"])
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").version = 4
                session.commit()
            stale = read(batch_ids["acct-a"]).json()["result"]["structuredContent"]
            self.assertTrue(stale["found"])
            self.assertFalse(stale["base_version_compatible"])
            self.assertEqual(stale["review_digest"], view["review_digest"])
            self.assertEqual(stale["expires_at"], view["expires_at"])
            with self.sessions() as session:
                session.get(ProfilingSession, "work-review-a").status = "DELETING"
                session.commit()
            self.assertFalse(
                read(batch_ids["acct-a"]).json()["result"]["structuredContent"]["found"]
            )

    def test_session_metadata_is_owner_scoped_and_never_returns_input_text(self) -> None:
        now = datetime.now(UTC)
        with self.sessions() as session:
            session.add_all(
                [
                    ProfilingSession(
                        id="work-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        status="ACTIVE",
                        base_profile_version=3,
                        created_at=now - timedelta(minutes=31),
                        last_activity_at=now - timedelta(minutes=31),
                        retention_expires_at=now + timedelta(days=89),
                    ),
                    ProfilingSession(
                        id="work-b",
                        account_id="acct-b",
                        profile_id="profile-b",
                        status="ACTIVE",
                        base_profile_version=8,
                        created_at=now,
                        last_activity_at=now,
                        retention_expires_at=now + timedelta(days=90),
                    ),
                ]
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="acct-a",
                    session_id="work-a",
                    idempotency_key="synthetic_input_0001",
                    content_kind="USER_STATEMENT",
                    body="synthetic private text must not leave storage",
                    created_at=now - timedelta(minutes=30),
                )
            )
            session.commit()

        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            owned = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "work-a"},
            )
            self.assertEqual(owned.status_code, 200)
            data = owned.json()["result"]["structuredContent"]
            self.assertTrue(data["found"])
            self.assertEqual(data["status"], "PAUSED")
            self.assertEqual(data["base_profile_version"], 3)
            self.assertEqual(data["current_profile_version"], 3)
            self.assertNotIn("synthetic private text", str(data))
            foreign = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "work-b"},
            )
            missing = self.call(
                client,
                token=self.token(),
                name="get_profiling_session",
                arguments={"profiling_session_id": "missing"},
            )
            self.assertEqual(foreign.json()["result"], missing.json()["result"])
            self.assertFalse(foreign.json()["result"]["structuredContent"]["found"])

    def test_reused_token_is_denied_after_account_disable(self) -> None:
        token = self.token()
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                200,
            )
            with self.sessions() as session:
                session.get(Account, "acct-a").status = "DISABLED"
                session.commit()
            denied = self.call(client, token=token, name="get_account_profile", arguments={})
            self.assertEqual(denied.status_code, 401)
            self.assertIn("resource_metadata=", denied.headers["www-authenticate"])
            other = self.call(
                client, token=self.token(sub="user-b"), name="get_account_profile", arguments={}
            )
            self.assertEqual(other.status_code, 200)
            self.assertEqual(other.json()["result"]["structuredContent"], {"id": "acct-b"})

    def test_deleting_profile_is_hidden_from_read_tool(self) -> None:
        token = self.token()
        arguments = {"profile_id": "profile-a"}
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            before = self.call(
                client, token=token, name="get_owned_profile_metadata", arguments=arguments
            )
            self.assertTrue(before.json()["result"]["structuredContent"]["found"])
            with self.sessions() as session:
                session.get(CareerProfile, "profile-a").status = "DELETING"
                session.commit()
            after = self.call(
                client, token=token, name="get_owned_profile_metadata", arguments=arguments
            )
            self.assertEqual(after.status_code, 200)
            self.assertFalse(after.json()["result"]["structuredContent"]["found"])

    def test_wrong_scope_audience_or_unknown_identity_are_rejected(self) -> None:
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            no_token = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            self.assertEqual(no_token.status_code, 401)
            for token in (
                self.token(scope="careerground:probe"),
                self.token(aud="https://wrong.synthetic.example/mcp"),
                self.token(iss="https://wrong.synthetic.example/"),
                self.token(exp=int(time.time()) - 120),
                self.token(sub="unknown-user"),
            ):
                with self.subTest(token=token[:12]):
                    response = self.call(
                        client, token=token, name="get_account_profile", arguments={}
                    )
                    self.assertEqual(response.status_code, 401)

    def test_database_lookup_failure_fails_closed(self) -> None:
        token = self.token()
        with TestClient(self.app, base_url="https://product-mcp.synthetic.example") as client:
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                200,
            )
            # A disposed in-memory DB loses its schema, forcing a lookup error.
            self.engine.dispose()
            self.assertEqual(
                self.call(
                    client, token=token, name="get_account_profile", arguments={}
                ).status_code,
                401,
            )


if __name__ == "__main__":
    unittest.main()

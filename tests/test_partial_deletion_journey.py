"""Synthetic partial erasure preserves unrelated canonical data and blocks restore."""

from __future__ import annotations

import re
import unittest
from datetime import UTC, datetime, timedelta
from html import unescape

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from careerground.domain.profile_archive import ensure_profile_archive, read_profile_archive
from careerground.domain.synthetic_deletion_journey import (
    MockDeletionJourney,
    MockDeletionJourneyRejected,
)
from careerground.local_demo import COOKIE, LocalDemo
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimUseReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
)
from careerground.storage.jd_artifact_models import Artifact, ArtifactUnit
from careerground.storage.models import (
    Account,
    AuthIdentity,
    Base,
    CareerProfile,
    ErasureLedger,
    ProfilingDraft,
    ProfilingInput,
    ProfilingSession,
    ProjectScope,
)
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

PREVIEW = b"synthetic-partial-preview-secret-32-byte"
LEDGER = b"synthetic-partial-ledger-secret-32-byte"
STATUS = b"synthetic-partial-status-secret-32-byte"


class PartialDeletionJourneyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.now = datetime(2026, 10, 3, 12, tzinfo=UTC)
        self.journey = MockDeletionJourney(PREVIEW, LEDGER, STATUS)
        with Session(self.engine) as session:
            session.add_all([Account(id="a"), Account(id="b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="pa", account_id="a", version=1),
                    CareerProfile(id="pb", account_id="b", version=1),
                    AuthIdentity(id="ia", account_id="a", issuer="synthetic", subject="a"),
                    AuthIdentity(id="ib", account_id="b", issuer="synthetic", subject="b"),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id="project-claim",
                        account_id="a",
                        profile_id="pa",
                        scope_key="project-one",
                        claim_type="CONTRIBUTION",
                        canonical_text="synthetic project text",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    Claim(
                        id="other-claim",
                        account_id="a",
                        profile_id="pa",
                        scope_key="other",
                        claim_type="CONTRIBUTION",
                        canonical_text="unrelated A fact",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    Claim(
                        id="b-claim",
                        account_id="b",
                        profile_id="pb",
                        scope_key="other",
                        claim_type="CONTRIBUTION",
                        canonical_text="unrelated B fact",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    ProjectScope(
                        id="project-one-id",
                        account_id="a",
                        profile_id="pa",
                        scope_key="project-one",
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.commit()

    def flow(self, scope, target, *, browser="browser-a"):
        with Session(self.engine) as session:
            view = self.journey.preview(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id=browser,
                scope=scope,
                target_id=target,
                now=self.now,
            )
            token = self.journey.reauthenticate(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id=browser,
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )
        return view, token

    def execute(self, token, *, browser="browser-a"):
        with Session(self.engine) as session:
            result = self.journey.execute(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id=browser,
                step_up_token=token,
                confirmed=True,
                now=self.now + timedelta(seconds=2),
            )
            session.commit()
        return result

    def _add_r2_lineage(self, session: Session) -> None:
        ensure_profile_archive(
            session, account_id="a", profile_id="pa", profile_version=1, now=self.now
        )
        for artifact_id, version, source_id, status in (
            ("r1-artifact", 1, None, "REVIEW_REQUIRED"),
            ("r2-artifact", 2, "r1-artifact", "WORDING_REVIEWED"),
        ):
            session.add(
                Artifact(
                    id=artifact_id,
                    account_id="a",
                    profile_id="pa",
                    source_artifact_id=source_id,
                    artifact_type="RESUME_TEXT",
                    artifact_version=version,
                    profile_version=1,
                    status=status,
                    created_at=self.now,
                )
            )
            session.flush()
            session.add(
                ArtifactUnit(
                    id="r1-unit" if version == 1 else "r2-unit",
                    account_id="a",
                    profile_id="pa",
                    artifact_id=artifact_id,
                    source_artifact_unit_id=None if version == 1 else "r1-unit",
                    ordinal=1,
                    unit_type="RESUME_BULLET",
                    exact_text="synthetic wording",
                    wording_level="R1" if version == 1 else "R2",
                    review_status=status,
                )
            )
            session.flush()

    def test_session_erases_r2_source_lineage_with_immediate_sqlite_fks(self):
        with Session(self.engine) as session:
            self._add_r2_lineage(session)
            session.add(
                ProfilingSession(
                    id="r2-work",
                    account_id="a",
                    profile_id="pa",
                    status="ACTIVE",
                    base_profile_version=1,
                    created_at=self.now,
                    last_activity_at=self.now,
                    retention_expires_at=self.now + timedelta(days=1),
                )
            )
            session.commit()
        _view, step = self.flow("SESSION", "r2-work")
        self.execute(step)
        with Session(self.engine) as session:
            for row_id in ("r1-artifact", "r2-artifact"):
                self.assertIsNone(session.get(Artifact, row_id))
            for row_id in ("r1-unit", "r2-unit"):
                self.assertIsNone(session.get(ArtifactUnit, row_id))
            self.assertIsNotNone(session.get(Claim, "b-claim"))

    def test_account_erases_r2_source_lineage_with_immediate_sqlite_fks(self):
        with Session(self.engine) as session:
            self._add_r2_lineage(session)
            session.commit()
        _view, step = self.flow("ACCOUNT", "a")
        self.execute(step)
        with Session(self.engine) as session:
            for row_id in ("r1-artifact", "r2-artifact"):
                self.assertIsNone(session.get(Artifact, row_id))
            for row_id in ("r1-unit", "r2-unit"):
                self.assertIsNone(session.get(ArtifactUnit, row_id))
            self.assertIsNotNone(session.get(Claim, "b-claim"))

    def test_evidence_erases_exact_excerpt_and_old_export_archive(self):
        with Session(self.engine) as session:
            session.add(
                EvidenceSource(
                    id="source-a",
                    account_id="a",
                    profile_id="pa",
                    source_type="EXPLICIT_PROFILING_INPUT",
                    source_ref="synthetic-source",
                    content_hash="a" * 64,
                    created_in_version=1,
                    created_at=self.now,
                )
            )
            session.flush()
            for row_id, text in (
                ("evidence-one", "erase this excerpt"),
                ("evidence-two", "keep this excerpt"),
            ):
                session.add(
                    EvidenceItem(
                        id=row_id,
                        account_id="a",
                        profile_id="pa",
                        source_id="source-a",
                        content_text=text,
                        content_hash="b" * 64,
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    )
                )
            session.flush()
            ensure_profile_archive(
                session,
                account_id="a",
                profile_id="pa",
                profile_version=1,
                now=self.now,
            )
            session.commit()
        view, step = self.flow("EVIDENCE", "evidence-one")
        self.assertIn(("PROFILE_ARCHIVE", 1), view.impact_counts)
        self.assertNotIn("erase this excerpt", view.preview_token)
        result = self.execute(step)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(EvidenceItem, "evidence-one"))
            self.assertIsNotNone(session.get(EvidenceItem, "evidence-two"))
            self.assertIsNotNone(session.get(Claim, "other-claim"))
            self.assertIsNotNone(session.get(Claim, "b-claim"))
            self.assertEqual(session.get(CareerProfile, "pa").version, 2)
            self.assertIsNone(
                session.scalar(select(ProfileArchive).where(ProfileArchive.profile_version == 1))
            )
            current = read_profile_archive(
                session, account_id="a", profile_id="pa", profile_version=2
            )
            self.assertNotIn("erase this excerpt", str(current))
            self.assertEqual(
                self.journey.read_status(
                    session,
                    capability=result.status_capability,
                    now=self.now + timedelta(seconds=3),
                ).status,
                "DELETING",
            )
        self.assertEqual(self.execute(step), result)

    def test_session_erases_raw_input_and_derived_source_only(self):
        with Session(self.engine) as session:
            session.add(
                ProfilingSession(
                    id="work-a",
                    account_id="a",
                    profile_id="pa",
                    status="ACTIVE",
                    base_profile_version=1,
                    protocol_cycle=0,
                    created_at=self.now,
                    last_activity_at=self.now,
                    retention_expires_at=self.now + timedelta(days=1),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="input-a",
                    account_id="a",
                    session_id="work-a",
                    protocol_cycle=0,
                    idempotency_key="input-key",
                    content_kind="USER_STATEMENT",
                    body="synthetic raw input",
                    created_at=self.now,
                )
            )
            session.add(
                EvidenceSource(
                    id="source-session",
                    account_id="a",
                    profile_id="pa",
                    source_type="EXPLICIT_PROFILING_INPUT",
                    source_ref="input-a",
                    content_hash="c" * 64,
                    created_in_version=1,
                    created_at=self.now,
                )
            )
            session.flush()
            session.add(
                EvidenceItem(
                    id="from-session",
                    account_id="a",
                    profile_id="pa",
                    source_id="source-session",
                    content_text="synthetic excerpt",
                    content_hash="d" * 64,
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.commit()
        view, step = self.flow("SESSION", "work-a")
        self.assertIn(("PROFILING_INPUT", 1), view.impact_counts)
        self.execute(step)
        with Session(self.engine) as session:
            for model, row_id in (
                (ProfilingSession, "work-a"),
                (ProfilingInput, "input-a"),
                (EvidenceSource, "source-session"),
                (EvidenceItem, "from-session"),
            ):
                self.assertIsNone(session.get(model, row_id))
            self.assertIsNotNone(session.get(Claim, "other-claim"))
            self.assertIsNotNone(session.get(Claim, "b-claim"))

    def test_evidence_erases_owned_original_session_with_shared_temporary_drafts(self):
        with Session(self.engine) as session:
            session.add(
                ProfilingSession(
                    id="shared-work",
                    account_id="a",
                    profile_id="pa",
                    status="ACTIVE",
                    base_profile_version=1,
                    protocol_cycle=0,
                    created_at=self.now,
                    last_activity_at=self.now,
                    retention_expires_at=self.now + timedelta(days=1),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="shared-input",
                    account_id="a",
                    session_id="shared-work",
                    protocol_cycle=0,
                    idempotency_key="shared-key",
                    content_kind="USER_STATEMENT",
                    body="synthetic original containing evidence",
                    created_at=self.now,
                )
            )
            session.add(
                EvidenceSource(
                    id="shared-source",
                    account_id="a",
                    profile_id="pa",
                    source_type="EXPLICIT_PROFILING_INPUT",
                    source_ref="shared-input",
                    content_hash="e" * 64,
                    created_in_version=1,
                    created_at=self.now,
                )
            )
            session.flush()
            session.add(
                EvidenceItem(
                    id="shared-evidence",
                    account_id="a",
                    profile_id="pa",
                    source_id="shared-source",
                    content_text="synthetic original",
                    content_hash="f" * 64,
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.add(
                ProfilingDraft(
                    id="other-scope-draft",
                    account_id="a",
                    session_id="shared-work",
                    source_input_id="shared-input",
                    scope_key="other",
                    claim_type="CONTRIBUTION",
                    exact_text="synthetic original",
                    source_content_hash="a" * 64,
                    status="DRAFT",
                    created_at=self.now,
                    expires_at=self.now + timedelta(days=1),
                )
            )
            session.flush()
            session.add_all(
                [
                    EvidenceClaimLink(
                        id="shared-support",
                        account_id="a",
                        profile_id="pa",
                        evidence_id="shared-evidence",
                        claim_id="other-claim",
                        relation_type="SUPPORTS",
                        created_in_version=1,
                    ),
                    ClaimAssessment(
                        id="old-allowed-assessment",
                        account_id="a",
                        profile_id="pa",
                        claim_id="other-claim",
                        knowledge_status="USER_CONFIRMED",
                        consistency_status="CONSISTENT",
                        usage_policy="ALLOWED",
                        profile_version=1,
                        assessed_at=self.now,
                    ),
                    ClaimUseReview(
                        id="old-use-review",
                        account_id="a",
                        profile_id="pa",
                        claim_id="other-claim",
                        review_digest="a" * 64,
                        consistency_attested=True,
                        use_authorized=True,
                        base_profile_version=0,
                        profile_version=1,
                        reviewed_at=self.now,
                    ),
                ]
            )
            session.commit()
        view, step = self.flow("EVIDENCE", "shared-evidence")
        self.assertIn(("PROFILING_SESSION", 1), view.impact_counts)
        self.assertIn(("PROFILING_DRAFT", 1), view.impact_counts)
        self.execute(step)
        with Session(self.engine) as session:
            for model, row_id in (
                (ProfilingSession, "shared-work"),
                (ProfilingInput, "shared-input"),
                (ProfilingDraft, "other-scope-draft"),
                (EvidenceItem, "shared-evidence"),
            ):
                self.assertIsNone(session.get(model, row_id))
            self.assertIsNotNone(session.get(Claim, "other-claim"))
            self.assertIsNotNone(session.get(Claim, "b-claim"))
            self.assertIsNone(session.get(ClaimUseReview, "old-use-review"))
            latest = session.scalar(
                select(ClaimAssessment)
                .where(ClaimAssessment.claim_id == "other-claim")
                .order_by(ClaimAssessment.profile_version.desc())
                .limit(1)
            )
            self.assertEqual(
                (latest.profile_version, latest.usage_policy, latest.consistency_status),
                (2, "REVIEW_REQUIRED", "NOT_EVALUATED"),
            )

    def test_registered_project_erases_scope_and_restore_old_version_fails(self):
        with Session(self.engine) as session:
            ensure_profile_archive(
                session, account_id="a", profile_id="pa", profile_version=1, now=self.now
            )
            session.commit()
        view, step = self.flow("PROJECT", "project-one-id")
        self.assertIn(("CLAIM", 1), view.impact_counts)
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.journey.execute(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id="other-browser",
                step_up_token=step,
                confirmed=True,
                now=self.now + timedelta(seconds=2),
            )
        result = self.execute(step)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(Claim, "project-claim"))
            self.assertIsNotNone(session.get(Claim, "other-claim"))
            self.assertIsNotNone(session.get(Claim, "b-claim"))
            self.assertEqual(session.get(ProjectScope, "project-one-id").status, "DELETING")
            ledger = session.get(ErasureLedger, result.request_id)
            self.assertEqual((ledger.profile_id, ledger.profile_version_after), ("pa", 2))
            gate = RestoreQuarantine()
            gate.reconcile(
                session,
                ledger_rows=[ledger],
                expected_manifest=signed_manifest([ledger], secret=LEDGER),
                secret=LEDGER,
            )
            self.assertTrue(gate.ready)
            session.get(CareerProfile, "pa").version = 1
            session.flush()
            with self.assertRaises(QuarantineRejected):
                gate.reconcile(
                    session,
                    ledger_rows=[ledger],
                    expected_manifest=signed_manifest([ledger], secret=LEDGER),
                    secret=LEDGER,
                )

    def test_project_erases_related_original_session_and_keeps_other_approved_claim(self):
        with Session(self.engine) as session:
            session.add(
                ProfilingSession(
                    id="project-work",
                    account_id="a",
                    profile_id="pa",
                    status="ACTIVE",
                    base_profile_version=1,
                    protocol_cycle=0,
                    created_at=self.now,
                    last_activity_at=self.now,
                    retention_expires_at=self.now + timedelta(days=1),
                )
            )
            session.flush()
            session.add(
                ProfilingInput(
                    id="project-input",
                    account_id="a",
                    session_id="project-work",
                    protocol_cycle=0,
                    idempotency_key="project-key",
                    content_kind="USER_STATEMENT",
                    body="synthetic project original",
                    created_at=self.now,
                )
            )
            session.flush()
            for row_id, key in (("project-draft", "project-one"), ("other-draft", "other")):
                session.add(
                    ProfilingDraft(
                        id=row_id,
                        account_id="a",
                        session_id="project-work",
                        source_input_id="project-input",
                        scope_key=key,
                        claim_type="CONTRIBUTION",
                        exact_text="synthetic project original",
                        source_content_hash="a" * 64,
                        status="DRAFT",
                        created_at=self.now,
                        expires_at=self.now + timedelta(days=1),
                    )
                )
            session.commit()
        view, step = self.flow("PROJECT", "project-one-id")
        self.assertIn(("PROFILING_SESSION", 1), view.impact_counts)
        self.assertIn(("PROFILING_DRAFT", 2), view.impact_counts)
        self.execute(step)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(ProfilingInput, "project-input"))
            self.assertIsNone(session.get(ProfilingDraft, "other-draft"))
            self.assertIsNone(session.get(Claim, "project-claim"))
            self.assertIsNotNone(session.get(Claim, "other-claim"))
            self.assertIsNotNone(session.get(Claim, "b-claim"))

    def test_foreign_target_stale_version_and_missing_explicit_checks_reject(self):
        with Session(self.engine) as session:
            session.add(
                ProjectScope(
                    id="foreign-project",
                    account_id="b",
                    profile_id="pb",
                    scope_key="foreign",
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.commit()
            with self.assertRaises(MockDeletionJourneyRejected):
                self.journey.preview(
                    session,
                    account_id="a",
                    profile_id="pa",
                    browser_session_id="browser-a",
                    scope="PROJECT",
                    target_id="foreign-project",
                    now=self.now,
                )
        view, step = self.flow("PROJECT", "project-one-id")
        with Session(self.engine) as session:
            with self.assertRaises(MockDeletionJourneyRejected):
                self.journey.reauthenticate(
                    session,
                    account_id="a",
                    profile_id="pa",
                    browser_session_id="browser-a",
                    preview_token=view.preview_token,
                    acknowledged_impact=False,
                    mock_reauthenticated=True,
                    now=self.now + timedelta(seconds=1),
                )
            with self.assertRaises(MockDeletionJourneyRejected):
                self.journey.execute(
                    session,
                    account_id="a",
                    profile_id="pa",
                    browser_session_id="browser-a",
                    step_up_token=step,
                    confirmed=False,
                    now=self.now + timedelta(seconds=2),
                )
            session.get(CareerProfile, "pa").version += 1
            session.commit()
        with Session(self.engine) as session, self.assertRaises(MockDeletionJourneyRejected):
            self.journey.execute(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id="browser-a",
                step_up_token=step,
                confirmed=True,
                now=self.now + timedelta(seconds=2),
            )

    def test_later_account_erasure_supersedes_partial_checkpoint(self):
        _, partial_step = self.flow("PROJECT", "project-one-id")
        self.execute(partial_step)
        later = self.now + timedelta(seconds=20)
        with Session(self.engine) as session:
            preview = self.journey.preview(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id="browser-a",
                scope="ACCOUNT",
                now=later,
            )
            step = self.journey.reauthenticate(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id="browser-a",
                preview_token=preview.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=later + timedelta(seconds=1),
            )
        with Session(self.engine) as session:
            self.journey.execute(
                session,
                account_id="a",
                profile_id="pa",
                browser_session_id="browser-a",
                step_up_token=step,
                confirmed=True,
                now=later + timedelta(seconds=2),
            )
            session.commit()
        with Session(self.engine) as session:
            rows = tuple(
                session.scalars(select(ErasureLedger).where(ErasureLedger.account_id == "a"))
            )
            self.assertEqual(len(rows), 2)
            gate = RestoreQuarantine()
            gate.reconcile(
                session,
                ledger_rows=rows,
                expected_manifest=signed_manifest(rows, secret=LEDGER),
                secret=LEDGER,
            )
            self.assertTrue(gate.ready)
            self.assertIsNotNone(session.get(Claim, "b-claim"))


class PartialDeletionMcpConnectionTests(unittest.TestCase):
    def setUp(self):
        self.demo = LocalDemo()
        self.addCleanup(self.demo.close)
        self.client = TestClient(self.demo, base_url=self.demo.origin, client=("127.0.0.1", 123))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        page = self.client.get("/demo")
        response = self.client.post(
            "/demo/account",
            data={"account": "a", "form_token": self.hidden(page.text, "form_token")},
        )
        self.assertEqual(response.status_code, 200)
        self.state = self.demo.browsers[self.client.cookies.get(COOKIE)]

    @staticmethod
    def hidden(page, name):
        match = re.search(rf"name='{name}' value='([^']*)'", page)
        assert match is not None
        return unescape(match.group(1))

    def rpc(self, args):
        return self.client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer " + self.demo._access_token(self.state),
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "execute_data_deletion", "arguments": args},
            },
        )

    def data(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]["structuredContent"]

    def approve(self, path):
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200, page.text)
        final = self.client.post(
            "/demo/deletion/reauth",
            data={
                "preview_token": self.hidden(page.text, "preview_token"),
                "acknowledged_impact": "yes",
                "mock_reauthenticated": "yes",
                "mock_phrase": "합성 계정 A",
            },
        )
        self.assertEqual(final.status_code, 200, final.text)
        approved = self.client.post(
            "/demo/deletion/execute",
            data={
                "step_up_token": self.hidden(final.text, "step_up_token"),
                "confirm": "erase_local",
            },
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        match = re.search(r"id='approval-receipt'>([^<]+)", approved.text)
        self.assertIsNotNone(match)
        return unescape(match.group(1))

    def test_project_requires_exact_browser_receipt_on_same_mcp_connection(self):
        with self.demo.sessions() as session:
            session.add(
                ProjectScope(
                    id="mcp-project",
                    account_id=self.state["account_id"],
                    profile_id=self.state["profile_id"],
                    scope_key="synthetic-project",
                    status="ACTIVE",
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        args = {
            "scope": "PROJECT",
            "target_id": "mcp-project",
            "profile_version": 0,
            "idempotency_key": "synthetic_partial_project_0001",
            "approval_receipt": "",
        }
        waiting = self.data(self.rpc(args))["data"]
        self.assertEqual(waiting["status"], "WAITING")
        with self.demo.sessions() as session:
            self.assertEqual(session.get(ProjectScope, "mcp-project").status, "ACTIVE")
        receipt = self.approve(waiting["confirmation_path"])
        wrong = {
            **args,
            "idempotency_key": "synthetic_partial_project_0002",
            "approval_receipt": receipt,
        }
        self.assertEqual(self.data(self.rpc(wrong))["status"], "error")
        finished = self.data(self.rpc({**args, "approval_receipt": receipt}))["data"]
        self.assertEqual(
            (finished["status"], finished["coverage"]), ("DELETING", "FOUNDATION_ONLY")
        )
        with self.demo.sessions() as session:
            self.assertEqual(session.get(ProjectScope, "mcp-project").status, "DELETING")
            self.assertEqual(session.get(Account, self.state["account_id"]).status, "ACTIVE")


if __name__ == "__main__":
    unittest.main()

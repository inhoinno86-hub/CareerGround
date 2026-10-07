"""Real local PostgreSQL gates for partial deletion and R2 lineage cleanup."""

from __future__ import annotations

import hashlib
import os
import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.jd_mapping import link_jd_requirement_to_claim
from careerground.domain.profile_archive import ensure_profile_archive
from careerground.domain.resume_draft import generate_resume_draft, get_resume_trace
from careerground.domain.resume_r2_review import R2ProposalService
from careerground.domain.synthetic_deletion_journey import MockDeletionJourney
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
)
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactClaimLink,
    ArtifactUnit,
    ArtifactWordingReview,
    JDRequirement,
)
from careerground.storage.models import (
    Account,
    Base,
    CareerProfile,
    DeletionRequest,
    DeletionWorkItem,
    ErasureLedger,
    OutboxEvent,
    ProfilingInput,
    ProfilingSession,
    ProjectScope,
)
from careerground.workers.restore_quarantine import (
    QuarantineRejected,
    RestoreQuarantine,
    signed_manifest,
)

PREVIEW = b"synthetic-pg-partial-preview-secret-32-bytes"
LEDGER = b"synthetic-pg-partial-ledger-secret-32-bytes"
STATUS = b"synthetic-pg-partial-status-secret-32-bytes"
R2_SECRET = b"synthetic-pg-partial-r2-secret-32-bytes"


class PostgreSQLContractCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        raw = os.environ.get("CAREERGROUND_TEST_DATABASE_URL")
        if not raw:
            if os.environ.get("CAREERGROUND_REQUIRE_POSTGRES_TEST") == "1":
                self.fail("required local PostgreSQL test URL is absent")
            self.skipTest("local PostgreSQL test URL is not configured")
        url = make_url(raw)
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").endswith("_test")
        ):
            self.fail("refusing a non-local or non-test database")
        self.engine = create_engine(url, hide_parameters=True)
        self.addCleanup(self.engine.dispose)
        suffix = uuid4().hex
        self.a = f"a-{suffix}"
        self.b = f"b-{suffix}"
        self.pa = f"p-{suffix}"
        self.pb = f"q-{suffix}"
        self.work = f"w-{suffix}"
        self.input = f"i-{suffix}"
        self.source = f"s-{suffix}"
        self.evidence = f"e-{suffix}"
        self.project_claim = f"c-{suffix}"
        self.other_claim = f"d-{suffix}"
        self.b_claim = f"f-{suffix}"
        self.project = f"j-{suffix}"
        self.now = datetime(2026, 10, 3, 12, tzinfo=UTC)
        self.journey = MockDeletionJourney(PREVIEW, LEDGER, STATUS)
        self.addCleanup(self.cleanup_rows)
        self._seed()

    def cleanup_rows(self) -> None:
        accounts = (self.a, self.b)
        with self.engine.begin() as conn:
            requests = select(DeletionRequest.id).where(DeletionRequest.account_id.in_(accounts))
            work_ids = tuple(
                conn.scalars(
                    select(DeletionWorkItem.id).where(DeletionWorkItem.request_id.in_(requests))
                )
            )
            if work_ids:
                conn.execute(delete(OutboxEvent).where(OutboxEvent.target_id.in_(work_ids)))
            conn.execute(delete(DeletionWorkItem).where(DeletionWorkItem.request_id.in_(requests)))
            # R2 has a self FK to R1 in both artifact tables.
            conn.execute(
                delete(ArtifactWordingReview).where(ArtifactWordingReview.account_id.in_(accounts))
            )
            conn.execute(
                delete(ArtifactClaimLink).where(ArtifactClaimLink.account_id.in_(accounts))
            )
            conn.execute(
                delete(ArtifactUnit).where(
                    ArtifactUnit.account_id.in_(accounts),
                    ArtifactUnit.source_artifact_unit_id.is_not(None),
                )
            )
            conn.execute(delete(ArtifactUnit).where(ArtifactUnit.account_id.in_(accounts)))
            conn.execute(
                delete(Artifact).where(
                    Artifact.account_id.in_(accounts), Artifact.source_artifact_id.is_not(None)
                )
            )
            conn.execute(delete(Artifact).where(Artifact.account_id.in_(accounts)))
            for table in reversed(Base.metadata.sorted_tables):
                if table.name in {"artifacts", "artifact_units", "artifact_wording_reviews"}:
                    continue
                if "account_id" in table.c:
                    conn.execute(table.delete().where(table.c.account_id.in_(accounts)))
            conn.execute(delete(Account).where(Account.id.in_(accounts)))
            for table in Base.metadata.sorted_tables:
                if "account_id" in table.c:
                    self.assertEqual(
                        conn.scalar(
                            select(func.count())
                            .select_from(table)
                            .where(table.c.account_id.in_(accounts))
                        ),
                        0,
                    )

    def _seed(self) -> None:
        with Session(self.engine) as session:
            session.add_all([Account(id=self.a), Account(id=self.b)])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id=self.pa, account_id=self.a, version=1),
                    CareerProfile(id=self.pb, account_id=self.b, version=1),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id=claim_id,
                        account_id=account,
                        profile_id=profile,
                        scope_key=scope,
                        claim_type="CONTRIBUTION",
                        canonical_text=text,
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    )
                    for claim_id, account, profile, scope, text in (
                        (
                            self.project_claim,
                            self.a,
                            self.pa,
                            "project-one",
                            "I implemented a feature",
                        ),
                        (self.other_claim, self.a, self.pa, "other", "I tested another feature"),
                        (self.b_claim, self.b, self.pb, "other", "B retains its feature"),
                    )
                ]
            )
            session.add_all(
                [
                    ProfilingSession(
                        id=self.work,
                        account_id=self.a,
                        profile_id=self.pa,
                        status="ACTIVE",
                        base_profile_version=1,
                        created_at=self.now,
                        last_activity_at=self.now,
                        retention_expires_at=self.now + timedelta(days=1),
                    ),
                    ProjectScope(
                        id=self.project,
                        account_id=self.a,
                        profile_id=self.pa,
                        scope_key="project-one",
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add_all(
                [
                    ProfilingInput(
                        id=self.input,
                        account_id=self.a,
                        session_id=self.work,
                        idempotency_key="synthetic_input_0001",
                        content_kind="USER_STATEMENT",
                        body="I implemented a feature",
                        created_at=self.now,
                    ),
                    EvidenceSource(
                        id=self.source,
                        account_id=self.a,
                        profile_id=self.pa,
                        source_type="EXPLICIT_PROFILING_INPUT",
                        source_ref=self.input,
                        content_hash="1" * 64,
                        created_in_version=1,
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add(
                EvidenceItem(
                    id=self.evidence,
                    account_id=self.a,
                    profile_id=self.pa,
                    source_id=self.source,
                    content_text="I implemented a feature",
                    content_hash="2" * 64,
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.flush()
            for claim_id in (self.project_claim, self.other_claim):
                session.add_all(
                    [
                        EvidenceClaimLink(
                            id=str(uuid4()),
                            account_id=self.a,
                            profile_id=self.pa,
                            evidence_id=self.evidence,
                            claim_id=claim_id,
                            relation_type="SUPPORTS",
                            created_in_version=1,
                        ),
                        ClaimAssessment(
                            id=str(uuid4()),
                            account_id=self.a,
                            profile_id=self.pa,
                            claim_id=claim_id,
                            knowledge_status="USER_CONFIRMED",
                            consistency_status="CONSISTENT",
                            usage_policy="ALLOWED",
                            profile_version=1,
                            assessed_at=self.now,
                        ),
                        ClaimReview(
                            id=str(uuid4()),
                            account_id=self.a,
                            profile_id=self.pa,
                            claim_id=claim_id,
                            review_batch_id=str(uuid4()),
                            review_item_id=str(uuid4()),
                            review_digest="0" * 64,
                            review_purpose="FACT_CONFIRMATION",
                            review_action="ACCEPT",
                            base_profile_version=0,
                            profile_version=1,
                            reviewed_at=self.now,
                        ),
                    ]
                )
            session.flush()
            ensure_profile_archive(
                session, account_id=self.a, profile_id=self.pa, profile_version=1, now=self.now
            )
            jd = record_pasted_jd_analysis(
                session,
                account_id=self.a,
                profile_id=self.pa,
                source_text="feature",
                excerpts=(JDExcerpt(0, 7),),
                now=self.now,
            )
            requirement = session.scalar(select(JDRequirement).where(JDRequirement.jd_id == jd.id))
            link_jd_requirement_to_claim(
                session,
                account_id=self.a,
                jd_id=jd.id,
                requirement_id=requirement.id,
                claim_id=self.project_claim,
                profile_version=1,
                now=self.now,
            )
            r1 = generate_resume_draft(
                session,
                account_id=self.a,
                profile_id=self.pa,
                profile_version=1,
                jd_id=jd.id,
                claim_ids=(self.project_claim,),
                now=self.now,
            )
            self.r1_id = r1.id
            unit = get_resume_trace(session, account_id=self.a, artifact_id=r1.id).units[0]
            proposal = (
                {
                    "unit_id": unit.unit_id,
                    "source_hash": hashlib.sha256(unit.exact_text.encode()).hexdigest(),
                    "proposed_text": unit.exact_text,
                    "fact_review": "NO_NEW_FACTS",
                    "claim_id": unit.claim_id,
                    "evidence_ids": list(unit.evidence_ids),
                },
            )
            r2_service = R2ProposalService(R2_SECRET)
            view = r2_service.prepare(
                session,
                account_id=self.a,
                browser_session_id="synthetic-pg-browser",
                source_artifact_id=r1.id,
                proposals=proposal,
                now=self.now,
            )
            self.r2_id = r2_service.submit(
                session,
                account_id=self.a,
                browser_session_id="synthetic-pg-browser",
                approval_token=view.approval_token,
                now=self.now,
            ).id
            session.commit()

    def _execute(self, scope: str, target_id: str):
        with Session(self.engine) as session:
            view = self.journey.preview(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                scope=scope,
                target_id=target_id,
                now=self.now,
            )
            step = self.journey.reauthenticate(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=1),
            )
        with Session(self.engine) as session:
            result = self.journey.execute(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                step_up_token=step,
                confirmed=True,
                now=self.now + timedelta(seconds=2),
            )
            session.commit()
        return view, result

    def _assert_partial_erasure(self, result, *, project_claim_removed: bool) -> None:
        with Session(self.engine) as session:
            self.assertIsNone(session.get(Artifact, self.r1_id))
            self.assertIsNone(session.get(Artifact, self.r2_id))
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(Artifact).where(Artifact.account_id == self.a)
                ),
                0,
            )
            self.assertEqual(session.get(Claim, self.project_claim) is None, project_claim_removed)
            self.assertIsNotNone(session.get(Claim, self.other_claim))
            self.assertIsNotNone(session.get(Claim, self.b_claim))
            self.assertEqual(session.get(CareerProfile, self.pa).version, 2)
            latest = session.scalar(
                select(ClaimAssessment)
                .where(ClaimAssessment.claim_id == self.other_claim)
                .order_by(ClaimAssessment.profile_version.desc())
                .limit(1)
            )
            self.assertEqual(
                (latest.profile_version, latest.usage_policy, latest.consistency_status),
                (2, "REVIEW_REQUIRED", "NOT_EVALUATED"),
            )
            ledger = session.get(ErasureLedger, result.request_id)
            gate = RestoreQuarantine()
            gate.reconcile(
                session,
                ledger_rows=[ledger],
                expected_manifest=signed_manifest([ledger], secret=LEDGER),
                secret=LEDGER,
            )
            self.assertTrue(gate.ready)
            session.get(CareerProfile, self.pa).version = 1
            session.flush()
            with self.assertRaises(QuarantineRejected):
                gate.reconcile(
                    session,
                    ledger_rows=[ledger],
                    expected_manifest=signed_manifest([ledger], secret=LEDGER),
                    secret=LEDGER,
                )
            session.rollback()

    def test_session_deletion_cleans_r2_self_lineage(self) -> None:
        _view, result = self._execute("SESSION", self.work)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(ProfilingInput, self.input))
            self.assertIsNone(session.get(EvidenceItem, self.evidence))
        self._assert_partial_erasure(result, project_claim_removed=False)

    def test_evidence_deletion_holds_retained_claim_and_cleans_r2(self) -> None:
        view, result = self._execute("EVIDENCE", self.evidence)
        self.assertIn(("PROFILING_INPUT", 1), view.impact_counts)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(EvidenceItem, self.evidence))
            self.assertIsNone(session.get(ProfilingInput, self.input))
        self._assert_partial_erasure(result, project_claim_removed=False)

    def test_project_then_account_deletes_registry_and_preserves_b(self) -> None:
        _view, result = self._execute("PROJECT", self.project)
        with Session(self.engine) as session:
            self.assertEqual(session.get(ProjectScope, self.project).status, "DELETING")
        self._assert_partial_erasure(result, project_claim_removed=True)
        with Session(self.engine) as session:
            view = self.journey.preview(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                scope="ACCOUNT",
                now=self.now + timedelta(seconds=3),
            )
            step = self.journey.reauthenticate(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                preview_token=view.preview_token,
                acknowledged_impact=True,
                mock_reauthenticated=True,
                now=self.now + timedelta(seconds=4),
            )
        with Session(self.engine) as session:
            final = self.journey.execute(
                session,
                account_id=self.a,
                profile_id=self.pa,
                browser_session_id="synthetic-pg-browser",
                step_up_token=step,
                confirmed=True,
                now=self.now + timedelta(seconds=5),
            )
            session.commit()
        with Session(self.engine) as session:
            self.assertIsNone(session.get(ProjectScope, self.project))
            self.assertEqual(session.get(Account, self.a).status, "DELETING")
            self.assertEqual(session.get(Account, self.b).status, "ACTIVE")
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(ErasureLedger)
                    .where(ErasureLedger.account_id == self.a)
                ),
                2,
            )
            self.assertIsNotNone(session.get(ErasureLedger, final.request_id))


if __name__ == "__main__":
    unittest.main()

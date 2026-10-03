"""Synthetic R2 approval, lineage, stale-source and explicit export checks."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.jd_mapping import link_jd_requirement_to_claim
from careerground.domain.resume_draft import generate_resume_draft, get_resume_trace
from careerground.domain.resume_export_presentation import (
    ResumeExportPresentationRejected,
    ResumeExportPresentationService,
)
from careerground.domain.resume_r2_review import (
    R2FactReviewRequired,
    R2ProposalRejected,
    R2ProposalService,
)
from careerground.domain.resume_wording_review import (
    VerifiedWordingApproval,
    WordingReviewRejected,
    WordingReviewService,
)
from careerground.storage.jd_artifact_models import (
    Artifact,
    ArtifactUnit,
    ArtifactWordingReview,
    JDRequirement,
)
from careerground.web.resume_r2_forms import render_r2_input

try:
    from tests import test_jd_artifact_foundation as fixtures
except ModuleNotFoundError:  # pytest's console entry point puts tests/ on sys.path
    import test_jd_artifact_foundation as fixtures

SECRET = fixtures.SECRET

SESSION_ID = "synthetic-r2-browser-session"


class R2ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fixtures.JDArtifactFoundationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.engine = self.fixture.engine
        self.now = self.fixture.now
        self.service = R2ProposalService(SECRET)
        with Session(self.engine) as session:
            jd = record_pasted_jd_analysis(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                source_text="Python required",
                excerpts=(JDExcerpt(0, 6),),
                now=self.now,
            )
            requirement = session.scalar(select(JDRequirement).where(JDRequirement.jd_id == jd.id))
            link_jd_requirement_to_claim(
                session,
                account_id="acct-a",
                jd_id=jd.id,
                requirement_id=requirement.id,
                claim_id="claim-a",
                profile_version=1,
                now=self.now,
            )
            self.r1_id = generate_resume_draft(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=1,
                jd_id=jd.id,
                claim_ids=("claim-a",),
                now=self.now,
            ).id
            session.commit()

    def proposal(
        self, session: Session, proposed: str = "I implemented a feature."
    ) -> tuple[dict, ...]:
        unit = get_resume_trace(session, account_id="acct-a", artifact_id=self.r1_id).units[0]
        return (
            {
                "unit_id": unit.unit_id,
                "source_hash": hashlib.sha256(unit.exact_text.encode()).hexdigest(),
                "proposed_text": proposed,
                "fact_review": "NO_NEW_FACTS",
                "claim_id": unit.claim_id,
                "evidence_ids": list(unit.evidence_ids),
            },
        )

    def prepare(self, session: Session, proposed: str = "I implemented a feature."):
        return self.service.prepare(
            session,
            account_id="acct-a",
            browser_session_id=SESSION_ID,
            source_artifact_id=self.r1_id,
            proposals=self.proposal(session, proposed),
            now=self.now,
        )

    def test_approval_creates_separate_reviewed_r2_and_explicit_export(self) -> None:
        wording = WordingReviewService(SECRET)
        presentation = ResumeExportPresentationService(wording, SECRET)
        with Session(self.engine) as session:
            view = self.prepare(session)
            form = render_r2_input(view.source, "synthetic-input-token")
            self.assertIn("<select id='fact_review_0'", form)
            self.assertIn("value='R3_NEEDS_FACT_REVIEW'", form)
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 1)
            r2 = self.service.submit(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                approval_token=view.approval_token,
                now=self.now,
            )
            session.commit()
            self.assertEqual(r2.status, "WORDING_REVIEWED")
            self.assertEqual(session.get(Artifact, self.r1_id).status, "REVIEW_REQUIRED")
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 2)
            trace = get_resume_trace(session, account_id="acct-a", artifact_id=r2.id)
            self.assertEqual(trace.source_artifact_id, self.r1_id)
            self.assertEqual(trace.units[0].source_unit_id, view.source.units[0].unit_id)
            self.assertEqual(trace.units[0].exact_text, "I implemented a feature.")
            review = session.scalar(
                select(ArtifactWordingReview).where(ArtifactWordingReview.artifact_id == r2.id)
            )
            self.assertEqual(review.action, "ACCEPT_R2")
            self.assertEqual(
                self.service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id=SESSION_ID,
                    approval_token=view.approval_token,
                    now=self.now,
                ).id,
                r2.id,
            )
            exported = wording.export_resume(
                session, account_id="acct-a", artifact_id=r2.id, format="JSON"
            )
            self.assertEqual(exported.wording_level, "R2")
            payload = json.loads(exported.content_text)
            self.assertEqual(payload["schema"], "careerground-resume-text-v2")
            self.assertEqual(payload["units"][0]["source_unit_id"], trace.units[0].source_unit_id)
            exact = presentation.present(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                artifact_id=r2.id,
                format="MARKDOWN",
                now=self.now,
            )
            self.assertEqual(exact.wording_level, "R2")
            self.assertEqual(
                presentation.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id=SESSION_ID,
                    artifact_id=r2.id,
                    format="MARKDOWN",
                    export_token=exact.export_token,
                    now=self.now,
                ).content_text,
                "- I implemented a feature\\.\n",
            )
            with self.assertRaises(ResumeExportPresentationRejected):
                presentation.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id="other-browser-session",
                    artifact_id=r2.id,
                    format="MARKDOWN",
                    export_token=exact.export_token,
                    now=self.now,
                )

    def test_foreign_expired_tampered_and_r3_proposals_do_not_persist(self) -> None:
        with Session(self.engine) as session:
            view = self.prepare(session)
            bad = self.proposal(session, "I led a feature.")
            with self.assertRaises(R2ProposalRejected):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    browser_session_id=SESSION_ID,
                    source_artifact_id=self.r1_id,
                    proposals=bad,
                    now=self.now,
                )
            r3 = dict(self.proposal(session)[0])
            r3["fact_review"] = "R3_NEEDS_FACT_REVIEW"
            with self.assertRaises(R2FactReviewRequired):
                self.service.prepare(
                    session,
                    account_id="acct-a",
                    browser_session_id=SESSION_ID,
                    source_artifact_id=self.r1_id,
                    proposals=(r3,),
                    now=self.now,
                )
            body, signature = view.approval_token.split(".")
            replacement = "A" if signature[0] != "A" else "B"
            tampered_token = f"{body}.{replacement}{signature[1:]}"
            self.assertNotEqual(tampered_token, view.approval_token)
            for account, browser, token, now in (
                ("acct-b", SESSION_ID, view.approval_token, self.now),
                ("acct-a", "foreign-browser-session", view.approval_token, self.now),
                ("acct-a", SESSION_ID, tampered_token, self.now),
                ("acct-a", SESSION_ID, view.approval_token, self.now + timedelta(minutes=4)),
            ):
                with self.assertRaises(R2ProposalRejected):
                    self.service.submit(
                        session,
                        account_id=account,
                        browser_session_id=browser,
                        approval_token=token,
                        now=now,
                    )
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 1)

    def test_noncanonical_token_aliases_are_rejected_without_persistence(self) -> None:
        with Session(self.engine) as session:
            view = self.prepare(session)
            body, signature = view.approval_token.split(".")
            alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            # A SHA-256 signature has two unused bits in its final base64url character.
            alias = signature[:-1] + alphabet[alphabet.index(signature[-1]) + 1]
            self.assertNotEqual(alias, signature)
            self.assertEqual(
                base64.urlsafe_b64decode(alias + "="),
                base64.urlsafe_b64decode(signature + "="),
            )
            for kind, token in (
                ("unused_bits", f"{body}.{alias}"),
                ("signature_padding", f"{body}.{signature}="),
                ("body_padding", f"{body}=.{signature}"),
            ):
                with self.subTest(representation=kind), self.assertRaises(R2ProposalRejected):
                    self.service.submit(
                        session,
                        account_id="acct-a",
                        browser_session_id=SESSION_ID,
                        approval_token=token,
                        now=self.now,
                    )
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 1)
            artifact = self.service.submit(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                approval_token=view.approval_token,
                now=self.now,
            )
            self.assertEqual(artifact.status, "WORDING_REVIEWED")
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 2)

    def test_source_and_r2_lineage_rechecked_before_export(self) -> None:
        wording = WordingReviewService(SECRET)
        with Session(self.engine) as session:
            view = self.prepare(session)
            r2 = self.service.submit(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                approval_token=view.approval_token,
                now=self.now,
            )
            session.commit()
            unit = session.scalar(select(ArtifactUnit).where(ArtifactUnit.artifact_id == r2.id))
            unit.exact_text = "I led the whole team"
            session.flush()
            with self.assertRaises(WordingReviewRejected):
                wording.export_resume(
                    session, account_id="acct-a", artifact_id=r2.id, format="JSON"
                )
            unit.exact_text = "I implemented a feature."
            unit.source_artifact_unit_id = unit.id
            session.flush()
            with self.assertRaises(WordingReviewRejected):
                wording.export_resume(
                    session, account_id="acct-a", artifact_id=r2.id, format="JSON"
                )
            unit.source_artifact_unit_id = view.source.units[0].unit_id
            session.get(ArtifactUnit, view.source.units[0].unit_id).exact_text = "altered original"
            session.flush()
            with self.assertRaises(WordingReviewRejected):
                wording.export_resume(
                    session, account_id="acct-a", artifact_id=r2.id, format="JSON"
                )

    def test_source_change_between_prepare_and_approve_fails_without_r2(self) -> None:
        with Session(self.engine) as session:
            view = self.prepare(session)
            session.get(ArtifactUnit, view.source.units[0].unit_id).exact_text = "altered original"
            session.flush()
            with self.assertRaises(R2ProposalRejected):
                self.service.submit(
                    session,
                    account_id="acct-a",
                    browser_session_id=SESSION_ID,
                    approval_token=view.approval_token,
                    now=self.now,
                )
            self.assertEqual(session.scalar(select(func.count()).select_from(Artifact)), 1)

    def test_later_r1_review_preserves_r2_export(self) -> None:
        wording = WordingReviewService(SECRET)
        with Session(self.engine) as session:
            view = self.prepare(session)
            r2 = self.service.submit(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                approval_token=view.approval_token,
                now=self.now,
            )
            review_view = wording.prepare(
                session, account_id="acct-a", artifact_id=self.r1_id, now=self.now
            )
            wording.submit(
                session,
                view=review_view,
                approval=VerifiedWordingApproval(
                    account_id="acct-a",
                    review_id=review_view.review_id,
                    artifact_id=self.r1_id,
                    review_digest=review_view.review_digest,
                    expires_at=review_view.expires_at,
                ),
                now=self.now,
            )
            session.commit()
            self.assertEqual(
                wording.export_resume(
                    session, account_id="acct-a", artifact_id=r2.id, format="JSON"
                ).wording_level,
                "R2",
            )

    def test_already_reviewed_r1_can_start_and_approve_separate_r2(self) -> None:
        wording = WordingReviewService(SECRET)
        with Session(self.engine) as session:
            review_view = wording.prepare(
                session, account_id="acct-a", artifact_id=self.r1_id, now=self.now
            )
            wording.submit(
                session,
                view=review_view,
                approval=VerifiedWordingApproval(
                    account_id="acct-a",
                    review_id=review_view.review_id,
                    artifact_id=self.r1_id,
                    review_digest=review_view.review_digest,
                    expires_at=review_view.expires_at,
                ),
                now=self.now,
            )
            session.commit()
            view = self.prepare(session)
            self.assertEqual(view.source.units[0].review_status, "WORDING_REVIEWED")
            r2 = self.service.submit(
                session,
                account_id="acct-a",
                browser_session_id=SESSION_ID,
                approval_token=view.approval_token,
                now=self.now,
            )
            session.commit()
            self.assertEqual(session.get(Artifact, self.r1_id).status, "WORDING_REVIEWED")
            self.assertEqual(r2.status, "WORDING_REVIEWED")
            self.assertEqual(
                wording.export_resume(
                    session, account_id="acct-a", artifact_id=r2.id, format="JSON"
                ).wording_level,
                "R2",
            )


if __name__ == "__main__":
    unittest.main()

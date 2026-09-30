"""Separate R1 use approval, archived versions and conservative blockers."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from careerground.domain.claim_use_review import ClaimUseReviewRejected, ClaimUseReviewService
from careerground.domain.deletion_execution import apply_deletion_work, execute_synthetic_deletion
from careerground.domain.deletion_preview import (
    DeletionPreviewService,
    DeletionScope,
    VerifiedDeletionApproval,
)
from careerground.domain.graph_projection import get_claim_evidence
from careerground.domain.jd_analysis import JDExcerpt, record_pasted_jd_analysis
from careerground.domain.jd_mapping import (
    JDMappingRejected,
    link_jd_requirement_to_claim,
    require_eligible_claim_trace,
)
from careerground.domain.profile_archive import ensure_profile_archive, read_profile_archive
from careerground.domain.resume_draft import generate_resume_draft
from careerground.domain.resume_wording_review import VerifiedWordingApproval, WordingReviewService
from careerground.storage.graph_models import (
    Claim,
    ClaimAssessment,
    ClaimConstraint,
    ClaimReview,
    ClaimUseReview,
    EvidenceClaimLink,
    EvidenceItem,
    EvidenceSource,
    ProfileArchive,
    ProfileChangeSet,
)
from careerground.storage.jd_artifact_models import JDRequirement
from careerground.storage.models import Account, Base, CareerProfile, DeletionWorkItem
from careerground.web.review_foundation import TrustedBrowserIdentity, build_synthetic_review_app

SECRET = b"synthetic-use-review-secret-32-bytes"


class ClaimUseReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.now = datetime(2026, 9, 29, 10, tzinfo=UTC)
        self.service = ClaimUseReviewService(SECRET, SECRET)
        with Session(self.engine) as session:
            session.add_all([Account(id="acct-a"), Account(id="acct-b")])
            session.flush()
            session.add_all(
                [
                    CareerProfile(id="profile-a", account_id="acct-a", version=1),
                    CareerProfile(id="profile-b", account_id="acct-b", version=0),
                ]
            )
            session.flush()
            session.add_all(
                [
                    Claim(
                        id="claim-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        scope_key="experience-a",
                        claim_type="CONTRIBUTION",
                        canonical_text="I built a feature",
                        created_in_version=1,
                        status="ACTIVE",
                        created_at=self.now,
                    ),
                    EvidenceSource(
                        id="source-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        source_type="EXPLICIT_PROFILING_INPUT",
                        source_ref="synthetic-input",
                        content_hash="a" * 64,
                        created_in_version=1,
                        created_at=self.now,
                    ),
                ]
            )
            session.flush()
            session.add(
                EvidenceItem(
                    id="evidence-a",
                    account_id="acct-a",
                    profile_id="profile-a",
                    source_id="source-a",
                    content_text="I built a feature",
                    content_hash=hashlib.sha256(b"I built a feature").hexdigest(),
                    created_in_version=1,
                    status="ACTIVE",
                    created_at=self.now,
                )
            )
            session.flush()
            session.add_all(
                [
                    EvidenceClaimLink(
                        id="support-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        evidence_id="evidence-a",
                        claim_id="claim-a",
                        relation_type="SUPPORTS",
                        created_in_version=1,
                    ),
                    ClaimAssessment(
                        id="assessment-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        claim_id="claim-a",
                        knowledge_status="USER_CONFIRMED",
                        consistency_status="NOT_EVALUATED",
                        usage_policy="REVIEW_REQUIRED",
                        profile_version=1,
                        assessed_at=self.now,
                    ),
                    ClaimReview(
                        id="fact-review-a",
                        account_id="acct-a",
                        profile_id="profile-a",
                        claim_id="claim-a",
                        review_batch_id="fact-batch-a",
                        review_item_id="fact-item-a",
                        review_digest="b" * 64,
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
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=1,
                now=self.now,
            )
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def _present(self, session: Session):
        return self.service.present(
            session,
            account_id="acct-a",
            browser_session_id="synthetic-browser-session-a",
            profile_id="profile-a",
            claim_id="claim-a",
            now=self.now,
        )

    def _submit(self, session: Session, token: str, *, now: datetime | None = None):
        return self.service.submit(
            session,
            account_id="acct-a",
            browser_session_id="synthetic-browser-session-a",
            profile_id="profile-a",
            claim_id="claim-a",
            approval_token=token,
            consistency_attested=True,
            use_authorized=True,
            now=now or self.now,
        )

    def _refresh_archive(self, session: Session) -> None:
        archive = session.scalar(
            select(ProfileArchive).where(ProfileArchive.profile_id == "profile-a")
        )
        session.delete(archive)
        session.flush()
        ensure_profile_archive(
            session,
            account_id="acct-a",
            profile_id="profile-a",
            profile_version=1,
            now=self.now,
        )

    def test_separate_exact_approval_is_once_only_and_enables_trace(self) -> None:
        with Session(self.engine) as session:
            view = self._present(session)
            self.assertEqual(view.blockers, ())
            self.assertEqual(view.trace.claim.usage_policy, "REVIEW_REQUIRED")
            self.assertIn("I built a feature", view.trace.evidence[0].exact_excerpt)
            before = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=1
            )
            review = self._submit(session, view.approval_token)
            self.assertEqual(review.profile_version, 2)
            self.assertEqual(self._submit(session, view.approval_token).id, review.id)
            session.commit()
        with Session(self.engine) as session:
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(ClaimUseReview)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileChangeSet)), 1)
            old = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=1
            )
            self.assertEqual(old, before)
            self.assertEqual(old["schema"], "canonical-foundation-v3")
            current = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=2
            )
            self.assertEqual(len(current["sections"]["claim_use_reviews"]), 1)
            self.assertEqual(
                get_claim_evidence(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=2,
                    claim_id="claim-a",
                ).claim.usage_policy,
                "ALLOWED",
            )
            require_eligible_claim_trace(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=2,
                claim_id="claim-a",
            )

    def test_missing_choice_foreign_session_expiry_and_stale_version_reject(self) -> None:
        with Session(self.engine) as session:
            view = self._present(session)
            request = {
                "account_id": "acct-a",
                "browser_session_id": "synthetic-browser-session-a",
                "profile_id": "profile-a",
                "claim_id": "claim-a",
                "approval_token": view.approval_token,
                "consistency_attested": True,
                "use_authorized": True,
                "now": self.now,
            }
            for changed in (
                {"consistency_attested": False},
                {"use_authorized": False},
                {"account_id": "acct-b"},
                {"browser_session_id": "another-browser-session-a"},
                {"approval_token": view.approval_token + "x"},
                {"now": self.now + timedelta(minutes=4)},
            ):
                with self.subTest(changed=changed), self.assertRaises(ClaimUseReviewRejected):
                    self.service.submit(session, **{**request, **changed})
            session.get(CareerProfile, "profile-a").version = 2
            with self.assertRaises(ClaimUseReviewRejected):
                self._submit(session, view.approval_token)
            self.assertEqual(session.scalar(select(func.count()).select_from(ClaimUseReview)), 0)

    def test_blockers_and_live_archive_drift_never_upgrade(self) -> None:
        for mode in ("no_review", "no_support", "opposing", "boundary", "disputed", "prohibited"):
            with self.subTest(mode=mode), Session(self.engine) as session:
                if mode == "no_review":
                    session.delete(session.get(ClaimReview, "fact-review-a"))
                elif mode == "no_support":
                    session.get(EvidenceClaimLink, "support-a").relation_type = "CONTEXTUALIZES"
                elif mode == "opposing":
                    session.get(EvidenceClaimLink, "support-a").relation_type = "CONTRADICTS"
                elif mode == "boundary":
                    session.add(
                        ClaimConstraint(
                            id="boundary-a",
                            account_id="acct-a",
                            profile_id="profile-a",
                            scope_key="experience-a",
                            constraint_type="DO_NOT_USE",
                            exact_text="Do not use this scope",
                            status="ACTIVE",
                            review_batch_id="boundary-batch-a",
                            review_item_id="boundary-item-a",
                            review_digest="c" * 64,
                            created_in_version=1,
                            created_at=self.now,
                        )
                    )
                elif mode == "disputed":
                    session.get(ClaimAssessment, "assessment-a").consistency_status = "DISPUTED"
                else:
                    session.get(ClaimAssessment, "assessment-a").usage_policy = "DO_NOT_CLAIM"
                session.flush()
                self._refresh_archive(session)
                view = self._present(session)
                self.assertTrue(view.blockers)
                self.assertIsNone(view.approval_token)
                self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
                self.assertEqual(
                    session.scalar(select(func.count()).select_from(ClaimUseReview)), 0
                )
                session.rollback()
        with Session(self.engine) as session:
            view = self._present(session)
            session.get(Claim, "claim-a").canonical_text = "Changed live text"
            session.flush()
            with self.assertRaises(ClaimUseReviewRejected):
                self._submit(session, view.approval_token)
            session.rollback()
        with Session(self.engine) as session:
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(ClaimUseReview)), 0)

    def test_existing_v2_archive_can_be_reviewed_into_v3(self) -> None:
        with Session(self.engine) as session:
            archive = session.scalar(
                select(ProfileArchive).where(ProfileArchive.profile_id == "profile-a")
            )
            old = json.loads(archive.snapshot_json)
            old["schema"] = "canonical-foundation-v2"
            old["sections"].pop("claim_use_reviews")
            archive.snapshot_json = json.dumps(
                old, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            archive.content_hash = hashlib.sha256(archive.snapshot_json.encode()).hexdigest()
            session.commit()
        with Session(self.engine) as session:
            view = self._present(session)
            self._submit(session, view.approval_token)
            session.commit()
        with Session(self.engine) as session:
            before = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=1
            )
            after = read_profile_archive(
                session, account_id="acct-a", profile_id="profile-a", profile_version=2
            )
            self.assertEqual(before["schema"], "canonical-foundation-v2")
            self.assertEqual(after["schema"], "canonical-foundation-v3")

    def test_browser_requires_two_exact_choices_and_one_session(self) -> None:
        identities = {
            "opaque-a": TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a"),
            "opaque-b": TrustedBrowserIdentity("acct-b", "synthetic-browser-session-b"),
            "second-a": TrustedBrowserIdentity("acct-a", "another-browser-session-a"),
        }
        app = build_synthetic_review_app(
            session_factory=sessionmaker(bind=self.engine),
            authenticate_browser=lambda request, _response: identities.get(
                request.cookies.get("cg_session")
            ),
            review_signing_secret=SECRET,
            presentation_signing_secret=SECRET,
        )
        path = "/profile/profile-a/1/claim/claim-a/use-review"
        with TestClient(app) as client:
            self.assertEqual(client.get(path).status_code, 401)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.get(path).status_code, 404)
            client.cookies.set("cg_session", "opaque-a")
            page = client.get(path)
            self.assertEqual(page.status_code, 200)
            self.assertIn("I built a feature", page.text)
            self.assertIn("synthetic-input", page.text)
            self.assertIn("사용자 확인은 외부 검증을", page.text)
            token = re.search(r"name='approval_token' value='([^']+)'", page.text).group(1)
            form = {
                "approval_token": token,
                "confirm_consistency": "yes",
                "confirm_use": "yes",
            }
            self.assertEqual(client.post(path, data={"approval_token": token}).status_code, 400)
            self.assertEqual(
                client.post(path, data={**form, "messages": "other chat"}).status_code, 400
            )
            client.cookies.set("cg_session", "second-a")
            self.assertEqual(client.post(path, data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-b")
            self.assertEqual(client.post(path, data=form).status_code, 409)
            client.cookies.set("cg_session", "opaque-a")
            success = client.post(path, data=form, follow_redirects=False)
            self.assertEqual(success.status_code, 303)
            self.assertEqual(success.headers["location"], "/profile/profile-a/2/claim/claim-a")
            retry = client.post(path, data=form, follow_redirects=False)
            self.assertEqual(retry.headers["location"], success.headers["location"])
            self.assertIn("ALLOWED", client.get(success.headers["location"]).text)
            self.assertEqual(client.get(path).status_code, 404)
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ClaimUseReview)), 1)
            self.assertEqual(session.get(CareerProfile, "profile-a").version, 2)

    def test_synthetic_browser_journey_from_claim_use_to_r1_download(self) -> None:
        app = build_synthetic_review_app(
            session_factory=sessionmaker(bind=self.engine),
            authenticate_browser=lambda request, _response: (
                TrustedBrowserIdentity("acct-a", "synthetic-browser-session-a")
                if request.cookies.get("cg_session") == "opaque-a"
                else None
            ),
            review_signing_secret=SECRET,
            presentation_signing_secret=SECRET,
        )

        def form_token(page: str, name: str) -> str:
            match = re.search(rf"name='{name}' value='([^']+)'", page)
            self.assertIsNotNone(match)
            return match.group(1)

        with TestClient(app) as client:
            client.cookies.set("cg_session", "opaque-a")
            use_path = "/profile/profile-a/1/claim/claim-a/use-review"
            use_page = client.get(use_path)
            self.assertEqual(use_page.status_code, 200)
            self.assertEqual(
                client.post(
                    use_path,
                    data={
                        "approval_token": form_token(use_page.text, "approval_token"),
                        "confirm_consistency": "yes",
                        "confirm_use": "yes",
                    },
                    follow_redirects=False,
                ).status_code,
                303,
            )
            jd_page = client.get("/jd/new")
            self.assertEqual(jd_page.status_code, 200)
            jd_create = client.post(
                "/jd/new",
                data={
                    "paste_token": form_token(jd_page.text, "paste_token"),
                    "selected_text": "- Python required",
                    "confirm": "store_excerpts",
                },
                follow_redirects=False,
            )
            self.assertEqual(jd_create.status_code, 303)
            jd_id = jd_create.headers["location"].split("/")[-1]
            jd_detail = client.get(jd_create.headers["location"])
            self.assertIn(f"/jd/{jd_id}/mapping/2", jd_detail.text)
            mapping_path = f"/jd/{jd_id}/mapping/2"
            mapping_page = client.get(mapping_path)
            self.assertEqual(mapping_page.status_code, 200)
            link_match = re.search(r"href='([^']+/link/[^']+)'", mapping_page.text)
            self.assertIsNotNone(link_match)
            link_path = link_match.group(1)
            link_page = client.get(link_path)
            self.assertEqual(link_page.status_code, 200)
            self.assertIn("I built a feature", link_page.text)
            self.assertEqual(
                client.post(
                    link_path,
                    data={
                        "link_token": form_token(link_page.text, "link_token"),
                        "confirm": "link_potential",
                    },
                    follow_redirects=False,
                ).status_code,
                303,
            )
            draft_path = f"/jd/{jd_id}/draft/2"
            draft_page = client.get(draft_path)
            self.assertEqual(draft_page.status_code, 200)
            self.assertIn("I built a feature", draft_page.text)
            draft = client.post(
                draft_path,
                data={
                    "draft_token": form_token(draft_page.text, "draft_token"),
                    "claim_id": "claim-a",
                    "confirm": "create_r1",
                },
                follow_redirects=False,
            )
            self.assertEqual(draft.status_code, 303)
            trace_path = draft.headers["location"]
            self.assertIn("I built a feature", client.get(trace_path).text)
            wording_path = trace_path.removesuffix("/trace") + "/wording"
            wording_page = client.get(wording_path)
            self.assertEqual(wording_page.status_code, 200)
            self.assertEqual(
                client.post(
                    wording_path,
                    data={
                        "approval_token": form_token(wording_page.text, "approval_token"),
                        "confirm": "accept_r1",
                    },
                    follow_redirects=False,
                ).status_code,
                303,
            )
            export_path = trace_path.removesuffix("/trace") + "/export/markdown"
            export_page = client.get(export_path)
            self.assertEqual(export_page.status_code, 200)
            download = client.post(
                export_path,
                data={
                    "export_token": form_token(export_page.text, "export_token"),
                    "confirm": "download",
                },
            )
            self.assertEqual(download.status_code, 200)
            self.assertIn("I built a feature", download.text)
            self.assertEqual(download.headers["cache-control"], "no-store")

    def test_deletion_preview_and_local_purge_include_use_review(self) -> None:
        with Session(self.engine) as session:
            view = self._present(session)
            self._submit(session, view.approval_token)
            session.commit()
        with Session(self.engine) as session:
            preview_service = DeletionPreviewService(SECRET)
            preview = preview_service.preview(
                session,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                now=self.now,
            )
            self.assertIn("CLAIM_USE_REVIEW", {item.kind for item in preview.items})
            request = execute_synthetic_deletion(
                session,
                preview_service=preview_service,
                ledger_secret=SECRET,
                account_id="acct-a",
                scope=DeletionScope.PROFILE,
                target_id="profile-a",
                deletion_digest=preview.deletion_digest,
                acknowledged_impact=True,
                step_up=VerifiedDeletionApproval(
                    account_id="acct-a",
                    scope=DeletionScope.PROFILE,
                    target_id="profile-a",
                    expires_at=self.now + timedelta(minutes=2),
                ),
                now=self.now,
            )
            session.commit()
            work = session.scalar(
                select(DeletionWorkItem).where(
                    DeletionWorkItem.request_id == request.id,
                    DeletionWorkItem.kind == "PROFILE_LOCAL_DATA",
                )
            )
            apply_deletion_work(session, work.id)
            session.commit()
            self.assertEqual(session.scalar(select(func.count()).select_from(ClaimUseReview)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ProfileArchive)), 0)

    def test_positive_use_review_unlocks_only_explicit_jd_link_and_r1_export(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(JDMappingRejected):
                require_eligible_claim_trace(
                    session,
                    account_id="acct-a",
                    profile_id="profile-a",
                    profile_version=1,
                    claim_id="claim-a",
                )
            view = self._present(session)
            self._submit(session, view.approval_token)
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
                profile_version=2,
                now=self.now,
            )
            artifact = generate_resume_draft(
                session,
                account_id="acct-a",
                profile_id="profile-a",
                profile_version=2,
                jd_id=jd.id,
                claim_ids=("claim-a",),
                now=self.now,
            )
            wording = WordingReviewService(SECRET)
            review_view = wording.prepare(
                session, account_id="acct-a", artifact_id=artifact.id, now=self.now
            )
            wording.submit(
                session,
                view=review_view,
                approval=VerifiedWordingApproval(
                    account_id="acct-a",
                    review_id=review_view.review_id,
                    artifact_id=artifact.id,
                    review_digest=review_view.review_digest,
                    expires_at=review_view.expires_at,
                ),
                now=self.now,
            )
            exported = wording.export_resume(
                session, account_id="acct-a", artifact_id=artifact.id, format="MARKDOWN"
            )
            self.assertIn("I built a feature", exported.content_text)
            session.commit()

import copy
import json
import os
import unittest

from career_graph_reference import (
    ValidationError, VersionArchive, assert_evidence_preserved, by_id,
    canonical_projection, promote_candidate, publishable_claim,
    resolve_artifact_unit, resolve_jd_requirement, rows, stage_candidate,
    validate_graph,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(ROOT, "fixtures", "career_graph")
FIXTURE_FILES = ("feature_owner.json", "supporting_contributor.json", "team_process_leadership.json")


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def approval_for(graph, candidate_id, confirmation_kind="FACTUAL_CONFIRMATION"):
    candidate = by_id(graph, "evidence_candidates")[candidate_id]
    return {
        "reviewer_type": "USER",
        "reviewer_id": graph["profile"]["user_id"],
        "candidate_text": candidate["candidate_text"],
        "proposed_context": copy.deepcopy(candidate["proposed_context"]),
        "input_profile_version": graph["profile"]["current_version"],
        "confirmation_kind": confirmation_kind,
    }


class CareerGraphFixtureTests(unittest.TestCase):
    def setUp(self):
        self.graphs = {name: load_fixture(name) for name in FIXTURE_FILES}
        self.a = self.graphs["feature_owner.json"]
        self.b = self.graphs["supporting_contributor.json"]
        self.c = self.graphs["team_process_leadership.json"]

    def assertInvalid(self, graph, contains=None):
        with self.assertRaises(ValidationError) as caught:
            validate_graph(graph)
        if contains:
            self.assertIn(contains, str(caught.exception))

    def test_fixture_structure_required_fields_types_defaults_and_references(self):
        for name, graph in self.graphs.items():
            with self.subTest(name=name):
                self.assertTrue(validate_graph(graph))
        broken = copy.deepcopy(self.a)
        del broken["claims"][0]["canonical_text"]
        self.assertInvalid(broken, "canonical_text")
        broken = copy.deepcopy(self.a)
        broken["profile"]["current_version"] = "12"
        self.assertInvalid(broken, "current_version")

    def test_structure_rejects_duplicate_ids_invalid_enums_and_ownership_targets(self):
        duplicate = copy.deepcopy(self.a)
        duplicate["claims"][1]["id"] = duplicate["claims"][0]["id"]
        self.assertInvalid(duplicate, "duplicate row id")
        bad_enum = copy.deepcopy(self.a)
        bad_enum["claim_assessments"][0]["knowledge_status"] = "VERIFIEDISH"
        self.assertInvalid(bad_enum, "state axis enum")
        two_targets = copy.deepcopy(self.a)
        ownership = two_targets["career"]["ownership_records"][0]
        ownership.update({"contribution_id": "CT-A-architecture", "responsibility_id": "RESP-A-feature", "project_id": None})
        self.assertInvalid(two_targets, "exactly one primary target")

    def test_structure_rejects_dangling_evidence_and_candidate_session_mismatch(self):
        dangling = copy.deepcopy(self.a)
        dangling["evidence"]["claim_links"][0]["evidence_id"] = "E-MISSING"
        self.assertInvalid(dangling, "dangles")
        mismatch = copy.deepcopy(self.c)
        mismatch["interviews"]["evidence_candidates"][0]["turn_id"] = "IT-C-2"
        mismatch["interviews"]["turns"][1]["session_id"] = "IS-MISSING"
        self.assertInvalid(mismatch, "dangles")

    def test_every_verified_claim_has_evidence(self):
        for name, graph in self.graphs.items():
            for assessment in graph["claim_assessments"]:
                if assessment["knowledge_status"] == "USER_CONFIRMED" and assessment["consistency_status"] == "CONSISTENT" and assessment["usage_policy"] == "ALLOWED":
                    with self.subTest(fixture=name, claim=assessment["claim_id"]):
                        self.assertTrue(publishable_claim(graph, assessment["claim_id"]))

        missing = copy.deepcopy(self.a)
        missing["evidence"]["claim_links"] = [link for link in missing["evidence"]["claim_links"] if link["claim_id"] != "C-A-logic"]
        with self.assertRaisesRegex(ValidationError, "SUPPORTS"):
            publishable_claim(missing, "C-A-logic")
        qualified_only = copy.deepcopy(self.a)
        next(link for link in qualified_only["evidence"]["claim_links"] if link["claim_id"] == "C-A-logic")["relation_type"] = "QUALIFIES"
        with self.assertRaisesRegex(ValidationError, "SUPPORTS"):
            publishable_claim(qualified_only, "C-A-logic")
        inferred = copy.deepcopy(self.a)
        by_id(inferred, "claim_assessments")["CA-A-logic"]["knowledge_status"] = "INFERRED"
        with self.assertRaisesRegex(ValidationError, "USER_CONFIRMED"):
            publishable_claim(inferred, "C-A-logic")

    def test_publication_rejects_system_only_external_and_mutated_reviews(self):
        generated = copy.deepcopy(self.a)
        generated["evidence"]["sources"][0]["source_type"] = "SYSTEM_GENERATED"
        with self.assertRaisesRegex(ValidationError, "independent SUPPORTS"):
            publishable_claim(generated, "C-A-logic")
        external = copy.deepcopy(self.a)
        by_id(external, "claim_assessments")["CA-A-logic"]["knowledge_status"] = "EXTERNALLY_VERIFIED"
        with self.assertRaisesRegex(ValidationError, "external-verification policy"):
            publishable_claim(external, "C-A-logic")
        changed = copy.deepcopy(self.a)
        by_id(changed, "claims")["C-A-logic"]["canonical_text"] = "Implemented all ADAS logic."
        with self.assertRaisesRegex(ValidationError, "exact USER_ACCEPTED"):
            publishable_claim(changed, "C-A-logic")
        misspelled = copy.deepcopy(self.a)
        misspelled["evidence"]["sources"][0]["source_type"] = "PROFILE_CONVERSATON"
        with self.assertRaisesRegex(ValidationError, "independent SUPPORTS"):
            publishable_claim(misspelled, "C-A-logic")

    def test_publication_uses_latest_exact_user_review_and_all_three_axes(self):
        later_rejection = copy.deepcopy(self.a)
        later_rejection["claim_reviews"].append({"id": "CR-LATER", "profile_id": "CP-A", "claim_id": "C-A-logic", "review_action": "USER_REJECTED", "reviewer_type": "USER", "reviewer_id": "USER-SYNTHETIC-A", "notes": "Implemented target-speed related logic for the Navigation-Aided Adaptive Cruise Control feature.", "profile_version": 12, "reviewed_at": "2026-09-21T00:00:01Z"})
        with self.assertRaisesRegex(ValidationError, "exact USER_ACCEPTED"):
            publishable_claim(later_rejection, "C-A-logic")
        for axis, value in (("usage_policy", "REVIEW_REQUIRED"), ("consistency_status", "DISPUTED"), ("consistency_status", "NOT_EVALUATED")):
            graph = copy.deepcopy(self.a)
            next(row for row in graph["claim_assessments"] if row["claim_id"] == "C-A-logic")[axis] = value
            with self.subTest(axis=axis, value=value), self.assertRaisesRegex(ValidationError, "claim state"):
                publishable_claim(graph, "C-A-logic")

    def test_do_not_claim_blocks_publication(self):
        blocked = ("C-A-adas-owner", "C-A-vehicle-owner", "C-B-tcn-selection", "C-B-project-owner", "C-B-model-owner", "C-C-perception-owner", "C-C-planning-owner", "C-C-control-owner")
        all_graphs = {claim["id"].split("-")[1]: graph for graph in self.graphs.values() for claim in graph["claims"]}
        for claim_id in blocked:
            graph = all_graphs[claim_id[2]]
            with self.subTest(claim=claim_id), self.assertRaises(ValidationError):
                publishable_claim(graph, claim_id)

        # Even a forged positive assessment/review cannot override a live Claim-targeted boundary.
        forged = copy.deepcopy(self.b)
        assessment = next(row for row in forged["claim_assessments"] if row["claim_id"] == "C-B-tcn-selection")
        assessment.update({"knowledge_status": "USER_CONFIRMED", "consistency_status": "CONSISTENT", "usage_policy": "ALLOWED"})
        review = next(row for row in forged["claim_reviews"] if row["claim_id"] == "C-B-tcn-selection")
        review.update({"review_action": "USER_ACCEPTED", "reviewer_type": "USER", "reviewer_id": forged["profile"]["user_id"], "notes": "Selected TCN as the production model."})
        with self.assertRaisesRegex(ValidationError, "Claim-targeted constraint"):
            publishable_claim(forged, "C-B-tcn-selection")

    def test_resume_unit_resolves_to_evidence(self):
        for name, graph in self.graphs.items():
            unit_id = graph["artifacts"]["units"][0]["id"]
            with self.subTest(name=name):
                resolved = resolve_artifact_unit(graph, unit_id)
                self.assertEqual(resolved["unit"]["text"], " ".join(claim["canonical_text"] for claim in resolved["claims"]))

        broken = copy.deepcopy(self.a)
        broken["artifacts"]["constraint_links"].pop()
        with self.assertRaisesRegex(ValidationError, "constraint links"):
            resolve_artifact_unit(broken, "AU-A-resume")

    def test_resume_rejects_compound_or_scope_overclaim_text(self):
        compound = copy.deepcopy(self.a)
        compound["artifacts"]["units"][0]["text"] = "Designed X and implemented Y and validated Z."
        with self.assertRaisesRegex(ValidationError, "exact reviewed"):
            resolve_artifact_unit(compound, "AU-A-resume")
        reused = copy.deepcopy(self.a)
        reused["artifacts"]["units"][0]["text"] = "Owned the entire ADAS system."
        reused["artifacts"]["claim_links"] = [{"id": "ACL-REUSE", "artifact_unit_id": "AU-A-resume", "claim_id": "C-A-feature-owner", "link_role": "PRIMARY"}]
        with self.assertRaisesRegex(ValidationError, "exact reviewed"):
            resolve_artifact_unit(reused, "AU-A-resume")

    def test_jd_requirement_resolves_to_claim(self):
        for name, graph in self.graphs.items():
            for requirement in graph["jd"]["requirements"]:
                with self.subTest(name=name, requirement=requirement["id"]):
                    self.assertTrue(resolve_jd_requirement(graph, requirement["id"]))
        dangling = copy.deepcopy(self.a)
        dangling["jd"]["claim_maps"][0]["claim_id"] = "C-MISSING"
        self.assertInvalid(dangling, "dangles")

    def test_review_does_not_make_known_compound_claim_atomic(self):
        compound = "Designed X and implemented Y and validated Z."
        graph = copy.deepcopy(self.a)
        by_id(graph, "claims")["C-A-logic"]["canonical_text"] = compound
        for review in graph["claim_reviews"]:
            if review["claim_id"] == "C-A-logic":
                review["notes"] = "Confirmed exact proposition/scope: " + compound
        with self.assertRaisesRegex(ValidationError, "separate atomic Claims"):
            publishable_claim(graph, "C-A-logic")
        graph = copy.deepcopy(self.c)
        by_id(graph, "evidence_candidates")["EC-C-regression-script"]["candidate_text"] = compound
        with self.assertRaisesRegex(ValidationError, "separate atomic Claims"):
            promote_candidate(graph, "EC-C-regression-script", approval_for(graph, "EC-C-regression-script"))

    def test_pending_candidate_does_not_mutate_profile(self):
        before = canonical_projection(self.c)
        staged = stage_candidate(self.c, "EC-C-regression-script", "NEEDS_FOLLOWUP")
        self.assertEqual(canonical_projection(staged), before)
        self.assertEqual(self.c["interviews"]["evidence_candidates"][0]["status"], "PENDING")
        rejected = stage_candidate(self.c, "EC-C-regression-script", "REJECTED")
        self.assertEqual(canonical_projection(rejected), before)

    def test_candidate_promotion_increments_version(self):
        original = copy.deepcopy(self.c)
        with self.assertRaisesRegex(ValidationError, "approval"):
            promote_candidate(self.c, "EC-C-regression-script", None)
        promoted = promote_candidate(self.c, "EC-C-regression-script", approval_for(self.c, "EC-C-regression-script"))
        self.assertEqual(promoted["profile"]["current_version"], 13)
        self.assertEqual(self.c, original)
        candidate = by_id(promoted, "evidence_candidates")["EC-C-regression-script"]
        self.assertEqual(candidate["status"], "ACCEPTED")
        self.assertIn(candidate["promoted_claim_id"], by_id(promoted, "claims"))
        self.assertIn(candidate["promoted_evidence_id"], by_id(promoted, "evidence_items"))
        change = promoted["audit"]["change_sets"][-1]
        self.assertEqual((change["version_before"], change["version_after"]), (12, 13))
        self.assertEqual(promote_candidate(promoted, "EC-C-regression-script", None), promoted)

    def test_promotion_requires_exact_approval_and_valid_transition(self):
        stale = approval_for(self.c, "EC-C-regression-script")
        stale["input_profile_version"] = 11
        with self.assertRaisesRegex(ValidationError, "exact user, text, context"):
            promote_candidate(self.c, "EC-C-regression-script", stale)
        rejected = stage_candidate(self.c, "EC-C-regression-script", "REJECTED")
        with self.assertRaisesRegex(ValidationError, "terminal"):
            promote_candidate(rejected, "EC-C-regression-script", approval_for(rejected, "EC-C-regression-script"))

    def test_evidence_only_acceptance_is_not_factual_confirmation(self):
        promoted = promote_candidate(self.c, "EC-C-regression-script", approval_for(self.c, "EC-C-regression-script", "EVIDENCE_ONLY"))
        candidate = by_id(promoted, "evidence_candidates")["EC-C-regression-script"]
        assessment = next(row for row in promoted["claim_assessments"] if row["claim_id"] == candidate["promoted_claim_id"])
        self.assertEqual((assessment["knowledge_status"], assessment["usage_policy"]), ("USER_CLAIMED", "REVIEW_REQUIRED"))
        review = next(row for row in promoted["claim_reviews"] if row["claim_id"] == candidate["promoted_claim_id"])
        self.assertIn("evidence only", review["notes"])
        with self.assertRaises(ValidationError):
            publishable_claim(promoted, candidate["promoted_claim_id"])

    def test_conflicting_existing_claim_requires_separate_review(self):
        candidate = self.c["interviews"]["evidence_candidates"][0]
        candidate["candidate_text"] = "Selected TCN as the production model."
        # Use fixture B's conflict as the explicit existing-Claim policy check by adding a matching candidate shell.
        graph = copy.deepcopy(self.b)
        graph["interviews"] = copy.deepcopy(self.c["interviews"])
        for session in graph["interviews"]["sessions"]: session.update({"profile_id": "CP-B", "jd_id": "JD-B", "profile_version": 12})
        for item in graph["interviews"]["evidence_candidates"]: item.update({"profile_id": "CP-B", "proposed_context": {"type": "PROJECT", "id": "P-B", "role": "PRIMARY"}})
        candidate = by_id(graph, "evidence_candidates")["EC-C-regression-script"]
        candidate["candidate_text"] = "Selected TCN as the production model."
        approval = approval_for(graph, candidate["id"]); approval["existing_claim_id"] = "C-B-tcn-selection"
        with self.assertRaisesRegex(ValidationError, "separate boundary/contradiction review"):
            promote_candidate(graph, candidate["id"], approval)
        del approval["existing_claim_id"]
        with self.assertRaisesRegex(ValidationError, "duplicate canonical text"):
            promote_candidate(graph, candidate["id"], approval)

    def test_contradictory_evidence_is_preserved(self):
        links = [row for row in self.b["evidence"]["claim_links"] if row["claim_id"] == "C-B-model-analysis"]
        self.assertEqual({row["relation_type"] for row in links}, {"SUPPORTS", "CONTRADICTS"})
        promoted = promote_candidate(self.c, "EC-C-regression-script", approval_for(self.c, "EC-C-regression-script"))
        self.assertTrue(assert_evidence_preserved(self.c, promoted))
        lost = copy.deepcopy(self.b)
        lost["evidence"]["claim_links"] = [row for row in lost["evidence"]["claim_links"] if row["id"] != "ECL-B-model-conflict"]
        with self.assertRaisesRegex(ValidationError, "lost or changed"):
            assert_evidence_preserved(self.b, lost)

    def test_ownership_boundary_prevents_overclaim(self):
        allowed = ((self.a, "C-A-feature-owner"), (self.b, "C-B-dataset"), (self.c, "C-C-team-leadership"))
        for graph, claim_id in allowed:
            self.assertTrue(publishable_claim(graph, claim_id))
        blocked = ((self.a, "C-A-adas-owner"), (self.a, "C-A-vehicle-owner"), (self.b, "C-B-tcn-selection"), (self.b, "C-B-project-owner"), (self.b, "C-B-model-owner"), (self.c, "C-C-perception-owner"), (self.c, "C-C-planning-owner"), (self.c, "C-C-control-owner"))
        for graph, claim_id in blocked:
            with self.subTest(claim=claim_id), self.assertRaises(ValidationError):
                publishable_claim(graph, claim_id)

    def test_archive_reconstructs_old_artifact_from_snapshot_only(self):
        archive = VersionArchive(); archive.capture(self.c)
        expected = archive.resolve_artifact("CP-C", 12, "A-C-resume")
        promoted = promote_candidate(self.c, "EC-C-regression-script", approval_for(self.c, "EC-C-regression-script"))
        archive.capture(promoted)
        with self.assertRaisesRegex(ValidationError, "archived version required"):
            resolve_artifact_unit(promoted, "AU-C-resume")
        # Mutating the live graph cannot affect the already serialized v12 snapshot.
        promoted["claims"][0]["canonical_text"] = "MUTATED LIVE TEXT"
        promoted["evidence"]["items"][0]["content_text"] = "MUTATED LIVE EVIDENCE"
        promoted["evidence"]["sources"][0]["title"] = "MUTATED LIVE SOURCE"
        promoted["claims"][0]["contexts"][0]["id"] = "MUTATED-LIVE-CONTEXT"
        promoted["claim_constraints"][0]["retired_in_version"] = 13
        actual = archive.resolve_artifact("CP-C", 12, "A-C-resume")
        self.assertEqual(actual, expected)

    def test_archive_missing_or_tampered_data_fails_without_latest_fallback(self):
        archive = VersionArchive(); archive.capture(self.c)
        with self.assertRaisesRegex(ValidationError, "missing"):
            archive.resolve_artifact("CP-C", 11, "A-C-resume")
        archive.tamper_payload_for_test("CP-C", 12, lambda graph: graph["evidence"]["sources"].clear())
        with self.assertRaisesRegex(ValidationError, "digest mismatch"):
            archive.resolve_artifact("CP-C", 12, "A-C-resume")
        archive = VersionArchive(); archive.capture(self.c)
        archive.tamper_payload_for_test("CP-C", 12, lambda graph: graph["evidence"]["sources"].clear(), recompute_digest=True)
        with self.assertRaisesRegex(ValidationError, "dangles"):
            archive.resolve_artifact("CP-C", 12, "A-C-resume")


if __name__ == "__main__":
    unittest.main()

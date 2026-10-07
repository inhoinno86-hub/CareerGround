import copy
import base64
import hashlib
import json
import os
import unittest

from interview_package_reference import (
    PackageValidationError,
    canonicalize_v1,
    validate_against_schema,
    validate_interview_package,
    verify_detached_jws,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return json.load(handle)


def mutate_path(document, dotted_path, value):
    parts = dotted_path.split(".")
    node = document
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    final = parts[-1]
    if isinstance(node, list):
        node[int(final)] = value
    else:
        node[final] = value


class InterviewPackageSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_json("docs", "interview_package_schema_v1.json")
        self.package = load_json("fixtures", "interview_package", "valid_v1.json")
        self.jwks = load_json("fixtures", "interview_package", "test_jwks.json")
        self.invalid_cases = load_json("fixtures", "interview_package", "invalid_cases.json")

    def assertPackageError(self, package, code, **context):
        with self.assertRaises(PackageValidationError) as caught:
            validate_interview_package(package, self.schema, self.jwks, **context)
        self.assertEqual(caught.exception.code, code)

    def test_schema_is_draft_2020_12_and_closed_at_envelope(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(self.schema["required"], ["payload", "proof"])

    def test_valid_fixture_matches_schema_and_semantic_contract(self):
        self.assertTrue(validate_against_schema(self.package, self.schema))
        self.assertTrue(validate_interview_package(self.package, self.schema, self.jwks))

    def test_canonical_payload_golden_digest(self):
        digest = hashlib.sha256(canonicalize_v1(self.package["payload"])).hexdigest()
        self.assertEqual(digest, "c9b6fa0c0b7b664b559b029c0d91c8121ebf24e5389b31e4364b741d4955de88")

    def test_real_es256_detached_jws_golden_vector(self):
        header = verify_detached_jws(self.package, self.jwks)
        self.assertEqual(header["alg"], "ES256")
        self.assertEqual(header["kid"], "careerground-test-es256-2026-09")
        protected = self.package["proof"]["value"].split(".")[0]
        payload = base64.urlsafe_b64encode(canonicalize_v1(self.package["payload"])).rstrip(b"=").decode("ascii")
        signing_input = f"{protected}.{payload}".encode("ascii")
        self.assertGreater(len(canonicalize_v1(self.package["payload"])), 4096)
        self.assertEqual(hashlib.sha256(signing_input).hexdigest(), "4d3debb3e1ba38bc9ab0fcb81b3e77ca5512b9feaa75dab6de47cf923cdea8ec")

    def test_algorithm_and_key_confusion_rejected(self):
        original = self.package["proof"]["value"].split(".")
        for change in ({"alg": "Ed25519"}, {"alg": "none"}, {"kid": "unknown"}, {"crit": ["unrecognized"]}):
            package = copy.deepcopy(self.package)
            header = {
                "alg": "ES256",
                "cty": "application/vnd.careerground.interview-package+json",
                "kid": "careerground-test-es256-2026-09",
                "typ": "careerground-interview-package+jws",
            }
            header.update(change)
            protected = base64.urlsafe_b64encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode()).rstrip(b"=").decode()
            package["proof"]["value"] = f"{protected}..{original[2]}"
            with self.subTest(change=change):
                self.assertPackageError(package, "PACKAGE_SIGNATURE_INVALID")

        for change in ({"crv": "Ed25519"}, {"alg": "Ed25519"}, {"d": "unexpected-private-key"}):
            jwks = copy.deepcopy(self.jwks)
            jwks["keys"][0].update(change)
            with self.subTest(jwk_change=change), self.assertRaises(PackageValidationError) as caught:
                validate_interview_package(self.package, self.schema, jwks)
            self.assertEqual(caught.exception.code, "PACKAGE_SIGNATURE_INVALID")

        duplicate = copy.deepcopy(self.jwks)
        duplicate["keys"].append(copy.deepcopy(duplicate["keys"][0]))
        with self.assertRaises(PackageValidationError) as caught:
            validate_interview_package(self.package, self.schema, duplicate)
        self.assertEqual(caught.exception.code, "PACKAGE_SIGNATURE_INVALID")

    def test_modified_es256_signature_is_rejected(self):
        package = copy.deepcopy(self.package)
        protected, _, signature = package["proof"]["value"].split(".")
        package["proof"]["value"] = f"{protected}..{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
        self.assertPackageError(package, "PACKAGE_SIGNATURE_INVALID")

    def test_declared_negative_fixtures_fail_with_expected_codes(self):
        for case in self.invalid_cases:
            with self.subTest(case=case["name"]):
                package = copy.deepcopy(self.package)
                if "mutation" in case:
                    mutate_path(package, case["mutation"]["path"], case["mutation"]["value"])
                context = copy.deepcopy(case.get("context", {}))
                if case.get("resign_for_semantic_test"):
                    context["verify_signature"] = False
                self.assertPackageError(package, case["expected_error"], **context)

    def test_unknown_or_private_payload_fields_are_rejected(self):
        for key in ("full_chat", "raw_document", "access_token", "voice_recording"):
            package = copy.deepcopy(self.package)
            package["payload"][key] = "must not be accepted"
            with self.subTest(key=key), self.assertRaises(PackageValidationError) as caught:
                validate_against_schema(package, self.schema)
            self.assertEqual(caught.exception.code, "PACKAGE_SCHEMA_INVALID")

    def test_non_publishable_claim_states_are_rejected_by_schema(self):
        cases = (
            ("knowledge_status", "INFERRED"),
            ("consistency_status", "CONTRADICTED"),
            ("usage_policy", "DO_NOT_CLAIM"),
        )
        for field, value in cases:
            package = copy.deepcopy(self.package)
            package["payload"]["claims"][0][field] = value
            with self.subTest(field=field), self.assertRaises(PackageValidationError) as caught:
                validate_against_schema(package, self.schema)
            self.assertEqual(caught.exception.code, "PACKAGE_SCHEMA_INVALID")

    def test_signature_detects_meaningful_payload_change(self):
        package = copy.deepcopy(self.package)
        package["payload"]["claims"][0]["text"] = "전체 시스템을 단독 설계했다."
        self.assertPackageError(package, "PACKAGE_SIGNATURE_INVALID")

    def test_reference_validation_does_not_fall_back_to_other_data(self):
        package = copy.deepcopy(self.package)
        package["payload"]["resume_units"][0]["claim_ids"] = ["CLAIM-MISSING"]
        self.assertPackageError(package, "PACKAGE_REFERENCE_INVALID", verify_signature=False)

    def test_manifest_must_match_every_embedded_object_and_fixed_artifact(self):
        package = copy.deepcopy(self.package)
        package["payload"]["integrity_manifest"][0]["content_hash"] = "A" * 43
        self.assertPackageError(package, "PACKAGE_REFERENCE_INVALID", verify_signature=False)

        package = copy.deepcopy(self.package)
        package["payload"]["claims"][0]["content_hash"] = "A" * 43
        package["payload"]["integrity_manifest"][4]["content_hash"] = "A" * 43
        self.assertPackageError(package, "PACKAGE_REFERENCE_INVALID", verify_signature=False)

    def test_validity_window_cannot_exceed_seven_days(self):
        package = copy.deepcopy(self.package)
        package["payload"]["expires_at"] = "2026-10-01T00:00:01Z"
        self.assertPackageError(package, "PACKAGE_SCHEMA_INVALID", verify_signature=False)

    def test_unknown_required_capability_fails_closed(self):
        package = copy.deepcopy(self.package)
        package["payload"]["required_capabilities"] = ["ONLINE_STATUS_CHECK"]
        self.assertPackageError(
            package,
            "PACKAGE_SCHEMA_UNSUPPORTED",
            understood_capabilities={"CONSTRAINT_GUARDS"},
            verify_signature=False,
        )

    def test_test_material_contains_public_key_only(self):
        serialized = json.dumps(self.jwks)
        self.assertNotIn("d", self.jwks["keys"][0])
        self.assertNotIn("PRIVATE", serialized.upper())
        self.assertEqual(self.jwks["keys"][0]["kty"], "EC")


if __name__ == "__main__":
    unittest.main()

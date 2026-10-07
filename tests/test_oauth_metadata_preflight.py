"""Synthetic-only discovery checks; no external provider is contacted."""

from __future__ import annotations

import unittest

from careerground.providers.oauth_metadata_preflight import (
    MetadataRejected,
    RegistrationMode,
    assess_mcp_oauth_metadata,
)


def synthetic_metadata() -> dict[str, object]:
    return {
        "issuer": "https://auth.synthetic.example",
        "authorization_endpoint": "https://auth.synthetic.example/authorize",
        "token_endpoint": "https://auth.synthetic.example/token",
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
        "provider_extension": "allowed by OAuth metadata extensibility",
    }


class OAuthMetadataPreflightTests(unittest.TestCase):
    def assess(self, metadata: dict[str, object], mode: RegistrationMode = RegistrationMode.CIMD):
        return assess_mcp_oauth_metadata(
            metadata,
            expected_issuer="https://auth.synthetic.example",
            registration_mode=mode,
        )

    def test_cimd_metadata_declares_compatible_methods(self) -> None:
        result = self.assess(synthetic_metadata())
        self.assertEqual(result.compatible_token_auth_methods, ("none", "private_key_jwt"))
        self.assertTrue(result.declares_authorization_response_iss)

    def test_missing_s256_or_different_issuer_fails_closed(self) -> None:
        for changes in (
            {"code_challenge_methods_supported": ["plain"]},
            {"issuer": "https://another.synthetic.example"},
        ):
            with self.subTest(changes=changes), self.assertRaises(MetadataRejected):
                self.assess({**synthetic_metadata(), **changes})

    def test_insecure_url_or_missing_client_method_fails_closed(self) -> None:
        for changes in (
            {"token_endpoint": "http://auth.synthetic.example/token"},
            {"token_endpoint": "https://auth.synthetic.example:invalid/token"},
            {"token_endpoint_auth_methods_supported": ["unsupported"]},
            {"client_id_metadata_document_supported": False},
        ):
            with self.subTest(changes=changes), self.assertRaises(MetadataRejected):
                self.assess({**synthetic_metadata(), **changes})

    def test_authorization_endpoint_may_have_a_fixed_query(self) -> None:
        result = self.assess(
            {
                **synthetic_metadata(),
                "authorization_endpoint": "https://auth.synthetic.example/authorize?prompt=login",
            }
        )
        self.assertEqual(result.issuer, "https://auth.synthetic.example")

    def test_dcr_requires_secure_registration_endpoint(self) -> None:
        with self.assertRaises(MetadataRejected):
            self.assess(synthetic_metadata(), RegistrationMode.DCR)
        with self.assertRaises(MetadataRejected):
            self.assess(
                {
                    **synthetic_metadata(),
                    "registration_endpoint": "http://auth.synthetic.example/reg",
                },
                RegistrationMode.DCR,
            )
        result = self.assess(
            {**synthetic_metadata(), "registration_endpoint": "https://auth.synthetic.example/reg"},
            RegistrationMode.DCR,
        )
        self.assertEqual(result.registration_mode, RegistrationMode.DCR)

    def test_preregistered_mode_does_not_claim_cimd_support(self) -> None:
        result = self.assess(
            {**synthetic_metadata(), "client_id_metadata_document_supported": False},
            RegistrationMode.PREREGISTERED,
        )
        self.assertEqual(result.registration_mode, RegistrationMode.PREREGISTERED)


if __name__ == "__main__":
    unittest.main()

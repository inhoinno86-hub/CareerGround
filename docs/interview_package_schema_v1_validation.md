# Interview Package Schema v1 Validation

- Date: 2026-09-23
- Result: PASS for the documented synthetic ES256 contract
- Schema: [Interview Package JSON Schema v1](interview_package_schema_v1.json)
- Policy source: [Interview Package Schema v1 decision](CareerGround_Interview_Package_Schema_Proposal_v0.1_2026-09-23.md) and [approved Architecture v1](architecture_v1.md)

## 1. Validated artifacts

```text
docs/interview_package_schema_v1.json
fixtures/interview_package/valid_v1.json
fixtures/interview_package/invalid_cases.json
fixtures/interview_package/test_jwks.json
tests/interview_package_reference.py
tests/test_interview_package.py
```

All fixture identities and career statements are synthetic. The repository contains only the test public key; the ephemeral private key used to produce the golden signature was not retained.

## 2. Automated coverage

The Interview Package suite contains 15 tests covering:

- JSON Schema Draft 2020-12 validity and closed envelope fields;
- the valid v1 package structure and semantic contract;
- deterministic canonical payload digest for the v1 JSON subset;
- actual ES256/P-256 verification of the detached JWS golden vector, including a greater-than-4-KiB payload and exact SHA-256 signing input;
- rejection of algorithm/header/key confusion, duplicate `kid`, private-key JWK fields and modified signatures;
- payload tamper detection;
- expiry, revocation, subject mismatch and single-session-use guards;
- unsupported schema major and required-capability rejection;
- dangling Claim/Evidence references;
- fixed provenance and integrity-manifest consistency;
- recomputation of embedded Claim, Evidence, Constraint, JD requirement and resume-unit hashes;
- rejection of full-chat, raw-document, token and recording fields;
- rejection of non-publishable Claim states;
- the seven-day maximum validity window;
- absence of private signing material from the JWKS fixture.

The full repository suite contains 48 tests: 20 Career Graph, 15 Interview Package and 13 Voice Agent tests.

## 3. Commands and result

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Result on 2026-09-23:

```text
Ran 48 tests
OK
```

The installed `jsonschema` implementation also accepted the schema as Draft 2020-12 and validated the normal fixture with format checking enabled. An independent `cryptography` P-256 verifier accepted the golden vector using a prehashed SHA-256 digest of the **6,595-byte** detached-JWS signing input. These independent checks are validation commands, not dependencies of the standard-library unit suite.

## 4. Reference implementation boundary

`tests/interview_package_reference.py` is dependency-free test support, not production security code.

- Its canonicalizer is defined for the v1 schema subset, which excludes floating-point values.
- Its compact P-256/ES256 verifier exists only to validate the fixed synthetic vector; production must use a maintained JOSE/cryptographic library and managed KMS key service.
- The test signature was generated from an ephemeral in-memory P-256 key using the SHA-256 digest of the full detached JWS signing input. Only its public JWK is retained.
- Registry state, authenticated subject and current server time are injected test context, not a database or authentication implementation.
- External profile/JD/resume/plan artifact hashes are synthetic fixed references because those services do not yet exist.

## 5. Not validated or implemented

- production OAuth and cross-service account mapping;
- PostgreSQL package registry and atomic session exchange;
- managed KMS/HSM signing and key rotation;
- HTTPS JWKS hosting, caching and emergency key revocation;
- handoff link/code issuance and exchange;
- retention and erasure workers;
- actual Plugin/MCP server or Voice Interview App;
- real user data, real documents or live voice sessions;
- load, latency, concurrency and 512 KiB boundary performance.

Voice Interview Agent behavior and Architecture v1 are defined separately. The remaining items are implementation and integration responsibilities, to be decomposed in Step 7.

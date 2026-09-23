# CareerGround MVP Architecture v1

- Date: 2026-09-23
- Status: **Approved design contract; application infrastructure and services not implemented**
- Decision authority: [approved Architecture Proposal v0.1](CareerGround_MVP_Architecture_Proposal_v0.1_2026-09-23.md), `ARCH-01`–`ARCH-07`
- Precedence: [Product Policy](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md) → [Schema v1.1 Policy Addendum](career_graph_schema_v1_1_policy_addendum.md) → [Plugin Functional Spec v1](plugin_functional_spec_v1.md), [Interview Package Schema v1](interview_package_schema_v1.json), [Voice Interview Agent Spec v1](voice_interview_agent_spec_v1.md) → this deployment design. Architecture cannot weaken those product contracts.

## 1. Decision record

| ID | Adopted decision | Status / remaining gate |
| --- | --- | --- |
| ARCH-01 | Python 3/FastAPI modular monolith, PostgreSQL system of record; MCP and Web/BFF adapters call one Career Core | Approved. Production framework/version, migrations and load capacity require implementation validation |
| ARCH-02 | AWS Seoul (`ap-northeast-2`) managed container + RDS PostgreSQL + private S3 + KMS is the initial deployment target | Approved as **target**, not permission to create paid resources. Account, networking, cost, data-transfer and legal review remain |
| ARCH-03 | One OIDC/OAuth 2.1 authority maps `(issuer, subject)` to internal `account_id` for web and MCP | Approved pattern. The identity product must pass MCP resource/audience/scope compatibility tests before selection |
| ARCH-04 | Issue Interview Packages with JOSE `ES256`, P-256 signing key isolated in AWS KMS; do not issue Ed25519 in v1 deployment | Approved change to the previously preferred algorithm; exact profile in §6 |
| ARCH-05 | PostgreSQL transactional outbox + workers, private object storage, erasure ledger and restore gate | Approved. Separate broker/cache/search cluster deferred until justified |
| ARCH-06 | Realtime/LLM vendor behind adapters; voice launch requires Korean, revoke/stop, retention/training and transfer checks | Approved conditional gate. No vendor is yet selected |
| ARCH-07 | Ship in order: text MVP → signed-package handoff → voice beta | Approved. Privacy and erasure foundation belongs in phase one |

## 2. Runtime components and trust boundaries

```text
ChatGPT/CareerGround workflow ── OAuth 2.1 ── public MCP HTTP adapter ┐
                                                                     ├── Career Core ── private PostgreSQL
CareerGround browser ── OIDC session ── public Web/BFF adapter ───────┘       │
      │                                                              ├── outbox/retention/erasure workers
      └── Voice gateway ── scoped ephemeral session ── realtime vendor        ├── private S3 objects
                                                                     └── KMS Sign + public JWKS
```

Only MCP/Web/BFF endpoints are public. The Voice gateway is a BFF-owned interface; PostgreSQL, workers, object buckets and the signing key have no public access. TLS protects traffic; encryption at rest, IAM least privilege and secrets management are mandatory. Data-scope checks happen inside Career Core rather than trusting a tool call, browser form or model assertion.

The modular monolith has these bounded modules:

| Module | Owns | Never owns |
| --- | --- | --- |
| Identity/Authorization | account mapping, scopes, session/subject context, access decisions | Career Claim truth |
| Profiling Workspace | explicit CareerGround session, messages, draft/review batches, 90-day expiry | canonical Claim before approval |
| Career Graph | Claim/Evidence/Constraint ownership, version, archives, approved promotion | raw full-chat archive after expiry |
| JD/Resume | JD analysis, wording, published artifact trace and fixed versions | authority to invent or promote evidence |
| Interview Package | fixed minimal payload, KMS signing, registry/status, 1-package/1-session guard | direct user voice processing |
| Interview Session | state machine, confirmed transcript versions, feedback, pending candidates | canonical Career Graph mutation without user review |
| Retention/Erasure | expiry scans, deletion fan-out, ledger, completion proofs and restore gate | recoverable copy of erased personal content |

MCP Streamable HTTP and Web/BFF remain thin adapters: authenticate, validate input, call the same domain command, return a policy-safe response. Neither has direct table-write authority. Framework SDK compatibility must be rechecked during implementation. The browser's access token/Interview Package is not persisted in local storage.

## 3. Identity, input and authorization

1. The OIDC identity is `(issuer, subject)`, mapped to an immutable internal `account_id`. Email is display/contact metadata, not an ownership key.
2. For every MCP request the server validates issuer, signature, expiry, intended audience/resource and required tool scope. Sensitive actions use their own scopes and exact user confirmation. Web sessions use secure HTTP-only same-site cookies and CSRF protection.
3. The MCP client can send only content the user explicitly submits to a CareerGround task. Installing the plugin, ordinary ChatGPT conversations, login and unrelated chats do not create workspace messages or extend retention.
4. JD, imported documents, conversation text and transcripts are untrusted input. Prompt text cannot grant access, alter review decisions, release `DO_NOT_CLAIM` boundaries or read the full Graph.
5. The system stores exact review digests and immutable version references. A browser or MCP confirmation is authoritative only after server-side subject, target, digest, expiry and item-by-item choice checks.

## 4. Persistence, external effects and invariants

PostgreSQL is the authoritative state. DB constraints include owner foreign keys, unique idempotency keys and a unique successful Interview Session per package. `account_id` is checked on every query and mutation; row-level security may add defense in depth, but does not replace application checks. The logical schema must include the v1.1 workspace/archive/deletion additions and Voice Spec §16 session/turn/assessment additions before feature implementation.

The outbox is committed with domain mutations, then polled by an idempotent worker. It transports event IDs and minimal references, never unnecessary conversation text. Search/index/cache data is derived and replaceable. DB transactions do not span KMS, S3 or realtime vendors; no operation is reported complete before mandatory external effects finish or are recoverably queued with an honest intermediate state.

### Required atomic boundaries

- **Claim promotion:** lock review batch/profile version; verify exact digest and up to five per-item decisions; write approved Claim/Evidence, new profile version and outbox together. Conflict or stale digest changes nothing.
- **Package issue:** reserve an internal issuance request with fixed profile/JD/resume/plan versions and idempotency key; this is **not** a public package-registry state. Build and sign immutable payload outside a long DB lock. Before registry `ISSUED`, recheck the referenced versions, owner, erasure/revocation and scope; store digest/`kid`/expiry atomically. A failed or raced signing attempt never yields a usable package. Public registry states remain `ISSUED`, `REVOKED`, `EXPIRED`.
- **Interview start:** verify JWS, subject, audience, validity and authoritative registry state; atomically consume package and create one session. Concurrent/replayed attempts cannot create a second session.
- **Transcript confirmation:** unique `(session_id, sequence, idempotency_key)` and exact `transcript_version`; edited/superseded versions invalidate old assessments and candidates before regeneration. Partial ASR is never assessable.
- **Erasure:** block reads and future use immediately; revoke packages and queue all affected stores. `DELETING` remains visible until DB, S3 versions, indexes/caches and in-scope provider deletion are verified. Failed work retries idempotently; it cannot silently become `ERASED`.

## 5. Data storage, retention and restore

| Class | Store | Maximum/default and guard |
| --- | --- | --- |
| Profiling messages/drafts | PostgreSQL workspace | 90 days from that session's last actual CareerGround activity; 30-minute auto-pause does not refresh expiry |
| Canonical Graph and approved excerpts | PostgreSQL + archive registry | Separate purpose and user deletion policy; not silently deleted with the temporary full-chat workspace |
| Interview transcript/feedback | PostgreSQL Interview Session | maximum 90 days from session completion; earlier deletion wins |
| Optional raw recording | private S3, distinct object class | **off by default**, maximum 30 days from recording completion |
| Uploaded original file if supported | private S3 | maximum 30 days after extraction unless explicitly selected as retained Evidence |
| Diagnostic logs | restricted logging service | no career text, transcripts, audio, tokens or document contents; proposed 30-day maximum |
| Automated DB backups | managed RDS | proposed 30-day maximum for beta; manual snapshots, replicas and restore copies must be inventoried |

Expiry is enforced by both query-time denial and a scheduled deletion worker; an asynchronous lifecycle rule is only a safety net. If S3 versioning is enabled, deletion enumerates and removes **all** object versions; a delete marker alone is insufficient. Do not use Object Lock on buckets holding user-erasure-eligible originals.

Backups cannot selectively remove one user's rows. Erasure therefore blocks live access promptly, keeps backup copies within the approved bounded retention, and uses a minimal restricted erasure ledger. Any backup restore first enters quarantine, replays the ledger, rechecks package revocations and only then joins service. Restore tests must prove deleted content stays unavailable. No deleted evidence or snapshot payload is retained for historical resume reconstruction. A minimal non-identifying tombstone may indicate `UNAVAILABLE_DUE_TO_ERASURE`; identifiers in the erasure ledger remain sensitive operational data.

The product policy's 24-hour live-store and 30-day backup figures are engineering targets, not public deletion guarantees before end-to-end evidence and legal review. Provider-side retention is assessed separately.

## 6. Interview Package ES256 wire and KMS profile

The JSON Schema envelope stays `{payload, proof}` with `signature_profile=careerground-jcs-detached-jws-v1`; its 64-byte signature shape also fits ES256. The producer and verifier **must not** negotiate algorithms from untrusted input:

1. Canonicalize only `payload` with RFC 8785 JCS, then base64url encode it. Do not use `b64=false` and do not sign `proof`.
2. Base64url encode a protected header with exactly `alg=ES256`, configured `kid`, fixed `typ` and fixed `cty`. Signing input is `protected_segment + "." + base64url(JCS(payload))` as ASCII bytes.
3. SHA-256 hash the **entire signing input**. Call AWS KMS `Sign` with an `ECC_NIST_P256` `SIGN_VERIFY` key, `SigningAlgorithm=ECDSA_SHA_256`, `MessageType=DIGEST` and the 32-byte digest. Never prehash only the payload and never pass a digest with `RAW`.
4. Strictly decode KMS's ASN.1 DER ECDSA signature `(r,s)` and convert each integer to unsigned, big-endian, left-padded 32 bytes. The detached JWS is `protected_segment + ".." + base64url(r || s)`.
5. Verify with the configured P-256 public JWK (`kty=EC`, `crv=P-256`, `alg=ES256`, `use=sig`) selected by a unique `kid`. Reject `none`, `Ed25519`, unknown/duplicate `kid`, unexpected protected parameters, malformed signature and private JWK fields. Then check account, audience, expiry, registry status and single-use state online.

Only the package-issuer runtime role gets `kms:Sign`; no private key is copied to Plugin, Voice App, source code or fixtures. Public JWKS is served over HTTPS. Key rotation preserves verification of unexpired packages, while emergency key compromise revokes all registry packages for that `kid`. The exact rotation interval and tested emergency runbook are release gates, not silently assumed settings.

AWS KMS limits `Sign` input to 4,096 bytes and its pure Ed25519 requires `RAW`; P-256 ECDSA accepts a SHA-256 `DIGEST` and returns DER. JOSE ES256 uses raw 64-byte `R || S`. See [AWS KMS Sign](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html), [AWS key specs](https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html) and [RFC 7518 §3.4](https://www.rfc-editor.org/rfc/rfc7518.html#section-3.4).

## 7. AI and voice boundary

LLM and realtime media are adapters behind Career Core/Voice gateway. The first live provider is not selected. Selection requires Korean-language quality, transcript correction, interruption/reconnect, server-side stop/revocation, cost, privacy, retention, training-use and cross-border transfer evidence with synthetic test data. If a vendor cannot satisfy revocation or data-handling gates, launch only the text flow.

The gateway authenticates same-account access and checks the immutable package before media starts. It sends only package-minimal context and obtains a scoped temporary connection credential. It checks authoritative revocation before new sensitive questions, resume and final assessment, and can stop provider generation. Browser/provider cannot query or mutate canonical Graph. Captions and text fallback share the same Interview Session state machine. Only confirmed user transcript versions are persisted for evaluation; raw recording is a separate opt-in setting.

## 8. Deployment and release sequence

| Phase | Gate before release | Included |
| --- | --- | --- |
| A — text foundation | Identity and tenant isolation, v1.1 DB migrations, retention/erasure and restore test | explicit profiling, review/promotion, Graph trace, JD/resume text and MCP/Web minimum UX |
| B — package handoff | KMS/JWKS integration, ES256 interop/negative suite, one-session race test, package revoke/expiry | signed immutable package issue, status and same-account handoff |
| C — voice beta | vendor privacy/security agreement, Korean quality evaluation, safe stop/revoke, 90/30-day deletion evidence | Simulation/Coaching, captions/text fallback, transcript confirmation, feedback and pending candidates |

Use separate dev/staging/prod environments, reversible migration steps, staged feature flags and no raw personal content in logs. Instrument auth failures, package start races, queue lag, expiry/deletion lag, provider failures and cost without storing career text. A production rollout also requires operator-access approval records, incident/runbook drills, realistic load tests and documented rollback.

## 9. Acceptance checks and unresolved implementation selections

The design is implemented only when tests show: cross-account access denied on every adapter; exact-review replay and stale digest rejection; at-most-one session per package under concurrency; JWS tamper/header/key confusion rejection; transcript edit invalidation; 90/30-day and earlier erasure; S3 version deletion; backup restore cannot resurrect erased data; provider interruption/revocation stops new use; and no full-chat ingestion from unrelated chat.

Unselected products/settings are **not** filled in by assumption: identity provider, LLM/realtime provider, frontend framework, managed container flavor, exact cloud account/network, KMS rotation interval, capacity/cost limits and public deletion SLA. Each has an evaluation or implementation gate above. Approval of this architecture does not authorize cloud provisioning, paid vendor contracts or launch.

The Step 7 [Implementation Task Breakdown](../PLAN-2026-09-23-mvp-implementation.md) derives Epic/Feature/Story/Task and acceptance tests from this contract. It is a review-pending plan, not authorization to deploy or implement.

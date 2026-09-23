# CareerGround MVP Implementation Task Breakdown

## Planning Metadata

- Date: 2026-09-23 (Asia/Seoul)
- Feature name: `mvp-implementation`
- Planning artifact: `PLAN-2026-09-23-mvp-implementation.md`
- Planning mode: normal Codex
- Superpowers planning: disabled
- Superpowers execution: disabled
- Superpowers brainstorming: not used
- Ouroboros: not requested; not used
- Status: **사용자 승인 완료 — 첫 구현 묶음 진행 중 (로컬 기초 구현, 공급자 선정 보류)**
- Baseline: current `main` working tree, including existing uncommitted/untracked project documents. Do not discard or overwrite those changes.

## 검토용 요약

이 문서는 승인된 아키텍처를 **9개 Epic, 26개 Story, 57개 Task**로 나눈 구현 계획이다. 사용자가 개발 순서와 범위를 승인했고, 첫 로컬 구현을 시작했다. 이 승인 자체가 클라우드 리소스 생성·유료 공급자 계약·서비스 공개를 허가하지는 않는다.

| 단계 | 사용자가 확인할 결과 | 다음 단계로 넘어가기 위한 조건 |
| --- | --- | --- |
| A. 텍스트 MVP | 문서 없이 경력을 대화로 정리하고, 최대 5개씩 검토·승인하며, JD와 근거 추적 가능한 이력서 문장을 만든다 | 계정 분리, 정확한 승인, 90일 보관·삭제 및 백업 복원 검증 |
| B. 면접 패키지 | 고정 버전의 최소 데이터를 ES256으로 서명해 같은 계정의 면접 앱에 1회 전달한다 | KMS/JWKS 연동, 만료·철회·변조·중복 시작 차단 |
| C. 음성 면접 베타 | 자막·텍스트 대체와 음성 대화, 전사 확인, 피드백, 신규 경력 후보 검토를 제공한다 | 한국어 품질, 공급자 중단·삭제·보관 검증과 선택 녹음 30일 준수 |

첫 개발 묶음은 로컬 실행 환경과 계약 정리, 인증 공급자 평가, 두 합성 계정의 격리, 기본 DB migration이다. Python 앱·migration·합성 테스트·CI 정의를 추가했고 임시 로컬 PostgreSQL 17에서 migration·계정 격리·전체 테스트를 검증했다. **GitHub CI 서버 실행과 실제 ChatGPT/인증 공급자 연동은 아직 확인 전**이다. 사용자 데이터 수집 전에 삭제·복원 기반을 완성한다. 아직 결정되지 않은 인증·LLM·음성 공급자는 각 단계의 **진입 조건**으로 남긴다.

## 1. Goal and source of truth

Turn the approved [MVP Architecture v1](docs/architecture_v1.md) into dependency-ordered, testable development work. The three release increments are **A: text MVP**, **B: signed Interview Package handoff**, **C: Voice Interview beta**. Each Epic below contains Features, Stories, concrete Tasks and observable acceptance criteria. This is a planning artifact, not evidence that any service, cloud resource or production integration exists.

Normative inputs, in order: [product decisions](docs/CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md), [Schema v1.1 addendum](docs/career_graph_schema_v1_1_policy_addendum.md), [Plugin contract](docs/plugin_functional_spec_v1.md), [Package contract](docs/interview_package_schema_v1.json) and [Package proposal](docs/CareerGround_Interview_Package_Schema_Proposal_v0.1_2026-09-23.md), [Voice contract](docs/voice_interview_agent_spec_v1.md), then [Architecture v1](docs/architecture_v1.md). Where an implementation detail is absent, the Story captures the choice and its test rather than inventing a finished product decision.

## 2. Scope, assumptions and execution boundary

- At plan approval, the repository had specifications and 48 synthetic tests but no running backend, PostgreSQL schema, MCP endpoint, web app, managed key or audio service. The first local foundation is now in progress; do not confuse its health routes or migration files with a product-ready service.
- No document upload is required for basic use. Only content explicitly submitted to a CareerGround task is collected. General chat is out of scope.
- User confirmation, external verification, publication permission and source deletion remain distinct. A model cannot perform a canonical promotion on its own.
- Personal data, tokens and actual private keys must not enter fixtures, logs or prompts used for tests. Use synthetic examples.
- Deployment target is AWS Seoul, but account, costs, precise managed container, identity/LLM/realtime vendors, rotation period and public deletion SLA are not selected. Local development and synthetic integration can start; cloud provisioning, vendor contracts and launch need separate authorization and gates.
- `MVP` in this plan means the three increments, not a promise to ship them all at once. Phase C may remain blocked while A/B proceed.
- No estimates or calendar dates are invented; size work after the first vertical slice and vendor evaluation.

## 3. Dependency map and release order

```text
E00 Contract/repository foundation
  ├── E01 Identity + tenant authorization ─┐
  └── E02 Persistence + retention/erasure ─┴── E03 Profiling/Graph/review
                                               └── E04 JD/resume/trace
                                                    └── E05 MCP/Web text experience ── [A]
                                                         └── E06 Package/KMS/handoff ── [B]
                                                              └── E07 Voice/session/feedback ── [C]
E08 Security/QA/operations runs across every gate and closes each release.
```

The order within an Epic follows Story dependencies. E01 and E02 can advance independently after E00, but promotion, publication, package issuance and voice must wait for their upstream guardrails. The approval of this plan does not itself authorize the external actions in §6.

### Release acceptance, not just a task count

| Gate | Must be demonstrable before release | Blocking dependencies |
| --- | --- | --- |
| A — text MVP | One account can explicitly submit one experience, review ≤5 atomic Claims, promote safely, map a JD, produce evidence-traceable resume text, inspect/delete data and use the authenticated MCP/web flows; a second account cannot access it; retention/restore tests pass | E00–E05 and E08-A |
| B — package | Same account can issue an immutable, minimal ES256 package for fixed versions and start at most one session; expiry, revocation, wrong audience/account and key failures reject; no usable partial issue | A, E06 and E08-B |
| C — voice beta | Preflight, voice/captions/text fallback, Simulation/Coaching, confirmed-transcript-only assessment, candidate review, 24-hour resume and safe mid-session revoke work; 90/30-day deletion is evidenced | B, vendor gate, E07 and E08-C |

## 4. Ordered backlog: Epic → Feature → Story → Task

Each `T` item is one implementable task. The acceptance line is the Story's completion condition; a Story is not done because its code merely compiles. Planned module paths below are suggestions, not claims that files already exist.

### EPIC-00 — Contracts and development foundation (A prerequisite)

#### Feature E00-F01 — Build and test skeleton

**Story E00-S01 — Create a local-only application skeleton.**

- `E00-T01` Add a Python backend layout with isolated domain, MCP, web/BFF, worker and provider-adapter modules; pin supported runtime and dependencies.
- `E00-T02` Add local PostgreSQL startup, migration runner, seed of synthetic identities, and a reproducible one-command test path. Keep credentials outside the repo.
- `E00-T03` Add CI for formatting/static checks, migrations from empty DB and existing synthetic tests.
- Acceptance: a new developer can start the app and local DB, apply migrations and run old/new tests with documented commands; no cloud credentials or real user data are required.

**Story E00-S02 — Freeze implementation contracts before endpoint work.**

- `E00-T04` Inventory Plugin tool input/output/error schemas, Schema v1/v1.1 entities and Voice additions; assign each command one owning domain module.
- `E00-T05` Define typed API/event DTOs, idempotency-key format and error mapping without weakening existing policy constants.
- Acceptance: a contract matrix maps every external tool to owner, scope, input, state change, error and test; unknown fields and unsupported versions fail closed.

#### Feature E00-F02 — External selection gates

**Story E00-S03 — Evaluate identity and LLM processing candidates.**

- `E00-T06` Compare OIDC/OAuth 2.1 providers against MCP audience/resource/scope, web login, account linking, support and cost requirements.
- `E00-T07` Compare LLM candidates using synthetic Korean ownership/number/negation/JD cases and documented retention, training-use, deletion and cross-border terms.
- Acceptance: selection record includes pass/fail evidence, tradeoffs and an explicit approval point; no provider is treated as selected merely because it is convenient for local code.

### EPIC-01 — Identity and tenant authorization (A prerequisite; depends on E00-S02 and the identity result of E00-S03)

#### Feature E01-F01 — One account across clients

**Story E01-S01 — Implement identity and session mapping.**

- `E01-T01` Persist unique `(issuer, subject) → account_id` mapping and account status; do not use email as the owner key.
- `E01-T02` Implement web OIDC callback/session cookies, CSRF protection, logout and session expiry after provider choice.
- Acceptance: email changes do not transfer data; invalid/expired sessions and CSRF requests fail without writes; two subjects remain isolated.

**Story E01-S02 — Authenticate MCP calls and authorize each command.**

- `E01-T03` Validate token issuer/signature/expiry/audience/resource/scope on every MCP call, including refresh/revocation behavior supported by the chosen provider.
- `E01-T04` Centralize per-resource `account_id` authorization and step-up confirmation for deletion and other high-impact actions.
- Acceptance: all private read/write tools reject wrong subject, audience and scope in automated tests; model-supplied IDs cannot bypass owner checks.

### EPIC-02 — Persistence, lifecycle and erasure (A prerequisite; E00 first, then parallel with E01)

#### Feature E02-F01 — Durable domain storage

**Story E02-S01 — Translate approved logical schema to PostgreSQL.**

- `E02-T01` Create migrations for accounts, profiling sessions/messages/drafts/reviews, canonical Graph and ownership, JD/resume versions, archive registry and deletion status.
- `E02-T02` Add owner foreign keys, enum/check constraints, unique idempotency keys and profile-version concurrency guards; add package/start tables in E06 and detailed Voice turn/assessment tables in E07.
- Acceptance: empty-DB upgrade and rollback/forward-compatibility procedure are tested; stale version and cross-account relationship inserts fail at service and DB boundaries.

**Story E02-S02 — Make side effects recoverable.**

- `E02-T03` Implement transactional outbox, bounded worker retries, dead-letter inspection and idempotent handler IDs.
- `E02-T04` Create private object metadata/adapter with class-specific expiry, version-ID tracking and no public bucket access.
- Acceptance: a crash between DB commit and worker processing does not lose a deletion/revocation event or duplicate a canonical mutation; raw content is absent from outbox/logs.

#### Feature E02-F02 — Retention, deletion and restore

**Story E02-S03 — Enforce temporary-data expiry.**

- `E02-T05` Implement 30-minute auto-pause and query-time denial after the 90-day profiling expiry; only real activity in that session advances its clock.
- `E02-T06` Implement scheduled expiry for workspace, transcript/feedback, optional recordings and upload originals with separate clocks.
- Acceptance: deterministic-clock tests show unrelated chat/login/auto-pause never extends retention; selected canonical Evidence survives temporary workspace expiry; recording is absent unless opted in.

**Story E02-S04 — Erase data without restoring deleted evidence.**

- `E02-T07` Implement deletion preview, exact impact digest, step-up execution, immediate read/use block, package revocation and visible `DELETING`/`ERASED` states.
- `E02-T08` Fan out to DB/archive, all S3 object versions, cache/index/queue and applicable provider deletion; record minimal restricted tombstone/ledger without source text.
- `E02-T09` Build quarantined backup-restore rehearsal that reapplies erasure ledger before service exposure; inventory manual snapshots/replicas and retention settings.
- Acceptance: stale deletion digest changes nothing; a failed target remains `DELETING`; erased versions return `UNAVAILABLE_DUE_TO_ERASURE`, never latest fallback; restore test cannot resurrect erased content.

### EPIC-03 — Profiling, review and Career Graph (A; depends on E01/E02)

#### Feature E03-F01 — Explicit profiling workspace

**Story E03-S01 — Capture only in-scope career conversation.**

- `E03-T01` Implement `start_profiling`, `add_profiling_input`, `get_profiling_session`, `pause_profiling` domain commands and owner checks.
- `E03-T02` Build deterministic draft extraction and question-state orchestration against Profiling Protocol v1, with an AI adapter that cannot approve a Claim.
- Acceptance: installation/general chat creates zero messages; explicit task input appears once with source trace; pause/draft does not change profile version; unsupported or prompt-injected input cannot widen access.

#### Feature E03-F02 — Exact approval and promotion

**Story E03-S02 — Review bounded atomic Claim batches.**

- `E03-T03` Implement `prepare_claim_review`, `get_claim_review`, per-item decisions and digest of the exact displayed wording/context for at most five same-scope items.
- `E03-T04` Implement `submit_claim_review` as one transaction with stale digest/profile-version checks and idempotency; `EDIT` returns to draft.
- Acceptance: omitted decisions never mean approval; replay or concurrent stale approval creates no extra version; confirmed text/ownership cannot silently gain a new fact.

**Story E03-S03 — Apply contradiction, boundaries and evidence rules.**

- `E03-T05` Implement separate exact-review paths for `resolve_claim_conflict` and `review_boundary_change`; block only affected publication targets.
- `E03-T06` Implement `get_career_profile`, `get_claim_evidence`, archive lookup and `export_profile_data` with original source trace and erased-version failure.
- Acceptance: user-confirmed is distinct from externally verified; `DO_NOT_CLAIM`/contradicted items cannot publish; old accessible version resolves from its snapshot only; erased version is not reconstructed.

### EPIC-04 — JD analysis and evidence-backed resume (A; depends on E03)

#### Feature E04-F01 — JD requirements

**Story E04-S01 — Produce bounded JD analysis.**

- `E04-T01` Implement `analyze_jd` and `get_jd_analysis` with ownership, structured requirements, source positions and artifact versions.
- `E04-T02` Link JD requirements to eligible Claims without changing Claim status; isolate JD prompt injection as data.
- Acceptance: unsupported JD claims are marked as gaps, not fabricated experience; cross-account JD and injected instructions cannot alter Graph or policies.

#### Feature E04-F02 — Resume wording and trace

**Story E04-S02 — Generate and review traceable resume units.**

- `E04-T03` Implement `generate_resume_draft`, `get_resume_trace` and wording-level review; map every proposed unit to Claim, Evidence, ownership and fixed versions.
- `E04-T04` Implement `submit_resume_wording_review` and `export_resume` for the first approved text formats; defer PDF until output policy and rendering validation are done.
- Acceptance: R2 wording cannot introduce R3 facts/metrics/authority; every exported sentence has a resolvable eligible trace; erased or disallowed evidence blocks export instead of falling back.

### EPIC-05 — MCP/Web text experience (A; depends on E01, E03, E04 and E02 deletion)

#### Feature E05-F01 — One domain through two adapters

**Story E05-S01 — Expose approved text/deletion tools.**

- `E05-T01` Build authenticated MCP Streamable HTTP tools with approved snake_case names, scopes, structured errors and annotations; route to Career Core commands.
- `E05-T02` Build narrow Web/BFF routes for session/review/trace/delete; keep DB access and direct approval logic out of adapters.
- Acceptance: tool contract tests cover all Phase A methods and negative auth/input cases; MCP/web give the same domain outcome for the same approved action.

**Story E05-S02 — Provide a reviewable Korean text UX.**

- `E05-T03` Implement explicit session start, source-scope notice, question/draft list, five-item exact review, JD/resume trace and deletion preview/status screens.
- `E05-T04` Add keyboard/accessibility checks, error recovery, empty/no-document path and privacy copy for 90-day workspace retention.
- Acceptance: a user can complete one end-to-end text journey without a document; wording under review is visible before approval; no page implies external verification or automatic hiring success.

### EPIC-06 — Interview Package and same-account handoff (B; depends on A)

#### Feature E06-F01 — Fixed interview preparation

**Story E06-S01 — Create a version-bound interview plan and payload.**

- `E06-T01` Implement `create_interview_plan` with bounded core questions, JD/Claim/Constraint references and artifact version.
- `E06-T02` Build minimal package payload from selected eligible versions; enforce 512 KiB, seven-day validity, required capabilities, reference/hash consistency and no full chat/raw file/audio/token fields.
- Acceptance: changing source version, removing Evidence or hitting publication boundary blocks issue; generated payload passes the existing JSON Schema and semantic fixture suite.

#### Feature E06-F02 — ES256 signing and registry

**Story E06-S02 — Issue a signed immutable package.**

- `E06-T03` Implement signer interface and strict JCS + detached-JWS ES256 producer/consumer; test DER ↔ JOSE `R || S` conversion, exact signing-input digest and negative headers/keys.
- `E06-T04` Integrate AWS KMS `ECC_NIST_P256` `ECDSA_SHA_256`/`DIGEST` only after cloud approval; publish public JWKS and implement rotation/emergency `kid` revocation drills.
- `E06-T05` Reserve an internal idempotent issue request, recheck source status after signing and commit public `ISSUED` registry entry atomically; expose package status/revoke tools.
- Acceptance: no private key leaves KMS in production; failed/raced issuance has no usable package; synthetic and KMS integration signatures verify independently; revoked/expired status overrides a valid signature.

**Story E06-S03 — Exchange once into a session.**

- `E06-T06` Build short-lived handoff code/link bound to same `account_id`; do not expose raw package by default or log the code.
- `E06-T07` Add the minimal Interview Session/package link migration; atomically validate signature/subject/audience/expiry/registry and create one successful `CREATED` session per package; retry returns the same session.
- Acceptance: wrong account/audience, expiry, revocation, unknown `kid` and concurrent second start all fail safely; normal retry does not duplicate a session.

### EPIC-07 — Voice Interview Agent beta (C; depends on B and vendor gate)

#### Feature E07-F01 — Vendor and session transport

**Story E07-S01 — Select a safe realtime/ASR/TTS provider.**

- `E07-T01` Evaluate synthetic Korean ASR numbers/names/negation/ownership, barge-in, captions, reconnect, server-side stop and cost.
- `E07-T02` Verify provider retention, training-use, subprocessors, region/transfer, deletion API and contract before sending any user audio.
- Acceptance: decision record demonstrates the Voice Spec's revoke/stop and privacy gates; if not met, voice remains disabled while text fallback may proceed.

**Story E07-S02 — Implement preflight and durable state machine.**

- `E07-T03` Extend the E06 session schema with turn/assessment fields from Voice Spec §16 and transition guards, including `DATA_REVOKED`, 24-hour resume and terminal immutability.
- `E07-T04` Implement accessible preflight: language, mode, captions, duration, microphone/text fallback, retention notice and recording **off** by default.
- `E07-T05` Build gateway with scoped temporary media credential, package-minimal context and server-controlled stop/revoke/reconnect; no direct provider Graph access.
- Acceptance: no media before preflight; reconnect continues after last confirmed turn; package/data revocation stops new context use; text fallback shares the same state machine.

#### Feature E07-F02 — Questions, confirmed answers and candidate loop

**Story E07-S03 — Run package-bounded questions and assessments.**

- `E07-T06` Implement question selection and two-follow-up cap with cited package IDs; prevent sensitive/leading/unsupported prompts.
- `E07-T07` Persist only confirmed transcript versions; flag critical ASR uncertainty and provide correction; invalidate old assessments/candidates after an edit.
- `E07-T08` Generate dimension-specific feedback for Simulation/Coaching without hiring probability, ranking or protected/voice-characteristic inference.
- Acceptance: partial/agent speech is never Evidence; unsupported package facts are “not found in current record”, not declared false; confirmed version is the sole source for feedback.

**Story E07-S04 — Return new facts to human review.**

- `E07-T09` Extract atomic EvidenceCandidates only from confirmed user turns, initially `PENDING` or `NEEDS_FOLLOWUP`, linked to session/turn/version.
- `E07-T10` Route candidates through E03's ≤5-item review; propagate session/recording/source deletion across candidates and feedback.
- Acceptance: candidate creation never increments profile version; only explicit review promotes it; 90-day transcript and optional 30-day recording expiry and earlier deletion are proven.

### EPIC-08 — Cross-cutting security, QA and operations (A/B/C gate owner)

#### Feature E08-F01 — Evidence for every release

**Story E08-S01 — Close Phase A safely.**

- `E08-T01` Add contract/integration tests for all Phase A tools, tenant isolation, exact approval, prompt injection, expiry and erasure/restore.
- `E08-T02` Add privacy-safe logs/metrics, audit of exceptional operator reads, rate limiting, threat review and accessibility checks; document rollback and incident response.
- Acceptance: Gate A table in §3 is demonstrated with commands/results and known limitations; no real data or secrets in test output or logs.

**Story E08-S02 — Close Phase B and C separately.**

- `E08-T03` For B, test real KMS interop, JWKS rotation/revocation, package start race and package/content erasure; rehearse rollback.
- `E08-T04` For C, test provider disconnect/stop, barge-in, ASR correction, transcript/recording deletion and safe fail-closed behavior with synthetic scenarios.
- Acceptance: B and C each have their own test report, security/privacy sign-off and feature flag; a pass in A does not imply B/C readiness.

#### Feature E08-F02 — Controlled deployment

**Story E08-S03 — Prepare but do not assume cloud launch.**

- `E08-T05` After separate authorization, create dev/staging/prod isolation, private network, managed secrets, RDS/S3/KMS IAM and backup settings as reviewed infrastructure code.
- `E08-T06` Rehearse migrations, monitored canary, feature-flag rollback, backup restore with deletion ledger and cost alarms before production use.
- Acceptance: no public DB/bucket or broad `kms:Sign` role; restore/cost/rollback evidence exists; launch and public privacy promises receive their own approval.

## 5. First implementation slice and review checkpoints

**First slice after plan approval:** `E00-S01` → `E00-S02` → identity candidate decision `E00-S03` → `E01-S01/S02` plus minimal `E02-S01`. Demonstrate two synthetic accounts, one owned resource, a cross-account denial, migration from empty DB and CI test run. This slice creates no production resources. Then progress through E02 privacy foundations before storing real CareerGround conversations.

Review checkpoints: (1) first slice and identity choice, (2) Phase A end-to-end text flow, (3) KMS/provider approval before Phase B real integration, (4) realtime/privacy approval before Phase C. At each checkpoint update this plan's Progress/Decision logs and attach exact test evidence. If a material product policy or architecture choice changes, record it and seek renewed approval before execution outside this scope.

## 6. External decisions and blockers

| Gate | Required decision/evidence | Work that may continue without it |
| --- | --- | --- |
| G-I Identity | provider supports OIDC + MCP OAuth 2.1 resource/audience/scopes, account linking and acceptable cost | domain/auth abstractions, local synthetic auth tests |
| G-L LLM | Korean quality and provider data handling/training/deletion terms accepted | deterministic Graph/JD/trace rules and synthetic adapter tests |
| G-C Cloud | AWS account, budget, region/network/privacy review and permission to create resources | local DB, migrations, KMS interface and fixture-level ES256 tests |
| G-K Signing operations | KMS/JWKS integration, rotation interval and emergency revoke runbook | package schema/semantic producer and negative tests with synthetic key |
| G-V Realtime | vendor capability, Korean quality, server-side stop, retention/transfer/contract evidence | Voice state machine, text fallback, synthetic sessions |
| G-P Privacy/release | deletion and backup-restoration evidence, actual provider obligations and legal review of public promises | internal engineering targets and local erasure tests |

No gate is implicitly satisfied by this plan. A missing G-V blocks **only** C, not A/B. A missing G-C blocks paid cloud integration, not local implementation. Do not treat local synthetic tests as production compliance evidence.

## 7. Validation strategy and commands

Existing baseline before implementation: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` — 48 synthetic tests passed. The local foundation now uses `uv sync --locked --group dev`, `uv run --locked python -m unittest discover -s tests -v`, Ruff, and Alembic; exact results and unverified checks are recorded below. No test run here proves production compliance.

Future implementation must add, then run, at minimum:

1. migration tests against a fresh local PostgreSQL and a compatible prior schema;
2. domain/unit/property tests for version/ownership/review/signature/expiry invariants;
3. MCP/Web API contract tests using two synthetic accounts and bad scopes;
4. worker crash/retry and backup-restore/erasure integration tests;
5. package KMS/JWKS interop and concurrency tests before B;
6. synthetic media/provider interruption/deletion and accessibility checks before C.

Exact new commands belong in the implementation README/CI once tooling exists; do not claim they already run. Preserve and expand the existing 48 tests rather than replacing them with only happy-path integration cases.

## 8. Rollback and non-goals

Build migrations as additive/compatible steps, put B/C behind disabled-by-default feature flags, and retain prior deploy artifacts and bounded backups. A rollback may stop new writes/feature access; it must **not** re-enable an erased record, issue an invalid package, or undo a user's confirmed deletion. Restore stays quarantined until ledger replay. A failed external deletion remains visibly pending and is retried/escalated; never mark it complete for cosmetic release success.

Not in scope: external/recruiter sharing, payments, automatic job application, hiring scores/probabilities, camera/emotion/personality inference, open-web Voice Agent access, unsigned or resume/JD-only evidence-aware voice sessions, broad chat collection and permanent storage of full profiling conversation.

## 9. Progress log

| Date | Entry |
| --- | --- |
| 2026-09-23 | Step 7 backlog drafted from approved Architecture v1. No application implementation, vendor selection or cloud provisioning performed in this planning step. |
| 2026-09-23 | 사용자가 계획을 승인하고 첫 구현 묶음을 요청함. E00-T01을 로컬 코드로 추가하고 E00-T04/T05의 초기 매핑·공통 DTO, E01-T01의 공급자 독립 lookup, E02-S01의 첫 identity/profile migration을 착수함. 개별 도구 input/error/test 계약, 실제 OIDC·MCP 인증 및 전체 스키마는 미완료. E00-T02/T03은 Compose·CI 정의와 합성 PostgreSQL 테스트를 추가했으나 이 환경에서는 Docker daemon 접근이 거부되어 실제 DB upgrade/CI 서버 실행을 아직 검증하지 못함. |
| 2026-09-23 | G-I/G-L 공급자 평가 게이트를 문서화함. Auth0→Cognito 인증 합성 PoC 순서만 제안하며 공급자 선정/외부 계정 생성/유료 계약은 하지 않음. LLM 실모델 품질 시험과 계약 검토도 미실시. 사용자 경력 데이터 수집·MCP/OIDC 라우트는 비활성. |
| 2026-09-23 | `uv run --locked ruff check`와 `ruff format --check` 통과. `uv run --locked python -m unittest discover -s tests -v`: **58개 실행 대상 중 57개 통과, 실제 PostgreSQL 통합 테스트 1개 skip** (`CAREERGROUND_TEST_DATABASE_URL` 없음). offline Alembic SQL 렌더링 테스트 통과. GitHub Actions는 정의만 추가했으며 서버에서 실행하지 않음. |
| 2026-09-23 | 후속 구현: 25개 도구의 입력·출력·대표 실패·예정 계약 테스트 ID를 매핑하고 공통 DTO에 Package 오류, bounded idempotency key, 원문 없는 outbox reference를 추가. ChatGPT/MCP 공식 문서에 맞춰 CIMD 우선·DCR 후순위로 공급자 평가를 갱신하고 합성 OAuth discovery metadata 사전 검사를 추가. 이는 live token/ChatGPT PoC가 아님. |
| 2026-09-23 | Docker 없이 저장소 밖의 임시 PostgreSQL **17.11**에서 빈 DB `alembic upgrade head`, `alembic check`, `downgrade base`→`upgrade head`, 두 합성 계정 소유권 테스트 및 **전체 66개 테스트(66 통과, skip 0)**를 실행. Ruff 검사·포맷 검사 및 `actionlint`로 CI YAML 정적 검사 통과. 임시 서버 종료와 테스트 파일 정리 완료. 실제 GitHub Actions 실행·Auth0/Cognito tenant 연동은 미실시. [검증 기록](docs/CareerGround_First_Slice_Validation_2026-09-23.md) |

## 10. Decision log

| ID | Decision | Basis |
| --- | --- | --- |
| PLAN-D01 | Use A → B → C release increments and phase-specific gates. | ARCH-07; avoid treating voice readiness as text-MVP prerequisite |
| PLAN-D02 | Put tenant authorization and erasure/restore before real-content ingestion. | Product deletion/ownership policy; ARCH-01/03/05 |
| PLAN-D03 | Separate internal package-issue request from public `ISSUED/REVOKED/EXPIRED` registry states. | Package state contract and ARCH-04 |
| PLAN-D04 | Leave identity, LLM/realtime, cloud costs and operator rotation values as explicit selection gates. | Architecture v1 intentionally leaves products/settings unresolved |
| PLAN-D05 | 첫 구현에서는 공급자 독립 `(issuer, subject) → account_id`와 소유권 조회만 구현하고, 실제 OIDC/MCP 토큰 검증은 G-I 이후에 연결한다. | 미선정 공급자를 코드가 암묵적으로 선택하지 않도록 함 |
| PLAN-D06 | 현재 ChatGPT/MCP 문서에 따라 인증 PoC는 CIMD를 우선 검토하고, 사전등록을 확인한 뒤 DCR을 최후 대안으로 둔다. Auth0/Cognito 선정은 유보한다. | 2026-07-28 MCP 인증 명세, 공식 OpenAI Docs, Auth0 CIMD 문서의 등록·`resource` 조건 |

## 11. Open questions for execution kickoff

1. Which identity provider passes the documented OIDC/MCP acceptance comparison? Select from E00-S03 evidence before E01 production integration.
2. Which LLM and realtime provider satisfy Korean quality and privacy/stop/deletion requirements? A text provider choice is needed before AI-backed A; realtime may remain open until C.
3. What exact cloud budget/account, data-transfer terms, key rotation interval and public deletion commitment can be approved? Keep production actions gated.

계획 승인 자체는 완료됐고 로컬 PostgreSQL 17 migration 검증도 통과했다. 다음 게이트는 실제 GitHub CI 실행(커밋·푸시 승인 필요)과 격리된 공급자 tenant·ChatGPT 개발용 플러그인에서의 실연동 PoC(외부 계정·비용 승인 필요)를 확인한 뒤 G-I 선택을 검토하는 것이다. 사용자 데이터 사용·외부 계정 생성·과금·클라우드 구축은 이 계획 승인만으로 시작하지 않는다.

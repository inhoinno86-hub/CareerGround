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
- Status: **사용자 승인 완료 — Phase A 합성 로컬 텍스트 여정 검증 완료, 전체 공개/운영 수용 기준과 공급자 선정은 미완료**
- Continuation checkpoint (2026-09-30): `codex/mvp-foundation-ci-20260923` / `061b371be0620adeac6f76b0fa6b70eefd36ab99`. HEAD/초안을 보존하며 로컬 인계 step-01–05 수행. [현재 검증·잔여 게이트](docs/CareerGround_Phase_A_Local_Validation_2026-09-30.md)
- Local follow-up 1–4 (2026-10-01): 브라우저 승인–MCP 증명/resource, 정기 정리, 다중 브라우저/Orca 구현. [최신 기록](docs/CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md)
- Baseline: current `main` working tree, including existing uncommitted/untracked project documents. Do not discard or overwrite those changes.

## 검토용 요약

이 문서는 승인된 아키텍처를 **9개 Epic, 26개 Story, 57개 Task**로 나눈 구현 계획이다. 사용자가 개발 순서와 범위를 승인했고, 첫 로컬 구현을 시작했다. 이 승인 자체가 클라우드 리소스 생성·유료 공급자 계약·서비스 공개를 허가하지는 않는다.

| 단계 | 사용자가 확인할 결과 | 다음 단계로 넘어가기 위한 조건 |
| --- | --- | --- |
| A. 텍스트 MVP | 문서 없이 경력을 대화로 정리하고, 최대 5개씩 검토·승인하며, JD와 근거 추적 가능한 이력서 문장을 만든다 | 계정 분리, 정확한 승인, 90일 보관·삭제 및 백업 복원 검증 |
| B. 면접 패키지 | 고정 버전의 최소 데이터를 ES256으로 서명해 같은 계정의 면접 앱에 1회 전달한다 | KMS/JWKS 연동, 만료·철회·변조·중복 시작 차단 |
| C. 음성 면접 베타 | 자막·텍스트 대체와 음성 대화, 전사 확인, 피드백, 신규 경력 후보 검토를 제공한다 | 한국어 품질, 공급자 중단·삭제·보관 검증과 선택 녹음 30일 준수 |

첫 개발 묶음은 로컬 실행 환경과 계약 정리, 인증 공급자 평가, 두 합성 계정의 격리, 기본 DB migration이다. Python 앱·migration·합성 테스트·CI를 추가했고 임시 로컬 PostgreSQL 17과 [GitHub CI](https://github.com/inhoinno86-hub/CareerGround/actions/runs/35870819987)에서 migration·계정 격리·전체 66개 테스트를 skip 없이 검증했다. Auth0 웹 로그인과 개발용 ChatGPT/MCP OAuth 인증 도구 호출은 실측했지만 인증 공급자 최종 선정은 아직 전이다. 사용자 데이터 수집 전에 삭제·복원 기반을 완성한다. 아직 결정되지 않은 인증·LLM·음성 공급자는 각 단계의 **진입 조건**으로 남긴다.

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
- 2026-09-27 준비 상태: 제품용 `ActiveAccountTokenVerifier`와 합성 HTTP 검증으로 같은 JWT라도 계정 `DISABLED`/인증 매핑 제거 후 다음 호출이 401인지 확인했다. 제품 MCP 엔드포인트가 없어 운영 경로에 아직 연결되지 않았고, Auth0/ChatGPT의 실제 철회·refresh 동작은 별도 검증 게이트다. 실데이터 도구를 추가할 때 DB 조회 실패도 거부하는 이 게이트와 도구별 소유권 확인을 필수 적용한다.
- 2026-09-27 후속: 별도 로컬 제품 MCP 팩토리에 `career.profile.read` 전용 인증, 계정 식별 도구와 소유자 범위의 프로필 ID/버전 조회를 연결했다. 이는 합성 데이터용 기초 경로이며 실행 진입점·실사용자 데이터·정식 `get_career_profile`은 아직 없다. 계정 전체 삭제·연결별 철회도 구현 전이다.
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
- 2026-09-27 준비 상태: 명시적으로 시작한 작업 세션과 단일 입력의 저장·계정 FK를 추가하고, 실제 입력·명시 재개만 해당 세션의 90일 만료를 연장하도록 했다. 30분 자동 일시정지는 기간을 연장하지 않으며 만료 후 조회는 즉시 거부한다. 만료 세션·입력을 한정 삭제하는 내부 배치 함수는 PostgreSQL 합성 DB에서도 검증했지만 스케줄러·동시 작업자·백업 복원 방지는 아직 없다. 실사용자 대화는 연결하지 않는다. [상세 경계](docs/CareerGround_Profiling_Workspace_Foundation_2026-09-27.md)
- `E02-T06` Implement scheduled expiry for workspace, transcript/feedback, optional recordings and upload originals with separate clocks.
- Acceptance: deterministic-clock tests show unrelated chat/login/auto-pause never extends retention; selected canonical Evidence survives temporary workspace expiry; recording is absent unless opted in.

**Story E02-S04 — Erase data without restoring deleted evidence.**

- `E02-T07` Implement deletion preview, exact impact digest, step-up execution, immediate read/use block, package revocation and visible `DELETING`/`ERASED` states.
- 2026-09-27 준비 상태: 삭제 상태 및 요청/작업 항목 스키마와 `ACCOUNT`/`PROFILE`의 합성 기반 미리보기·재확인 검사를 구현했다. 현재 영향 범위는 계정/인증 연결/프로필 메타데이터뿐이며 `FOUNDATION_ONLY`, `ready_to_execute=false`로 표시한다. 신뢰된 step-up 발급, 삭제 실행·작업자, 패키지 철회, 외부 저장소/백업 복원 차단은 아직 없으므로 실사용자에게 노출하지 않는다. [경계와 후속](docs/CareerGround_Deletion_Foundation_2026-09-27.md)
- `E02-T08` Fan out to DB/archive, all S3 object versions, cache/index/queue and applicable provider deletion; record minimal restricted tombstone/ledger without source text.
- `E02-T09` Build quarantined backup-restore rehearsal that reapplies erasure ledger before service exposure; inventory manual snapshots/replicas and retention settings.
- Acceptance: stale deletion digest changes nothing; a failed target remains `DELETING`; erased versions return `UNAVAILABLE_DUE_TO_ERASURE`, never latest fallback; restore test cannot resurrect erased content.

### EPIC-03 — Profiling, review and Career Graph (A; depends on E01/E02)

#### Feature E03-F01 — Explicit profiling workspace

**Story E03-S01 — Capture only in-scope career conversation.**

- `E03-T01` Implement `start_profiling`, `add_profiling_input`, `get_profiling_session`, `pause_profiling` domain commands and owner checks.
- 2026-09-27 내부 서비스 상태: 명시 시작·단일 입력·세션 메타데이터 조회·직접 일시정지·재개를 합성 계정 소유권 검사와 함께 구현했다. 조회는 원문을 반환하지 않고, 직접 일시정지와 조회는 90일 시계를 연장하지 않는다. 실제 MCP 도구·프로토콜 질문 상태·클라이언트 수집 확인은 아직 없음.
- `E03-T02` Build deterministic draft extraction and question-state orchestration against Profiling Protocol v1, with an AI adapter that cannot approve a Claim.
- 2026-09-27 진행 상태: 순수 질문 planner와 세션 소유권에 묶인 임시 질문 전달·출처 관찰 저장을 추가했다. 전달 키 재시도는 횟수를 늘리지 않고 UNKNOWN은 두 질문 후에만 기록한다. `20260927_0013`은 입력·세션 삭제에 연쇄 정리되며 삭제 미리보기에도 포함된다. §7의 별도 검토 증명이 없으므로 모든 질문 관찰이 있어도 COMPLETE를 발급하지 않는다. PostgreSQL 17.11의 `0013` 적용·schema check·`0012` 롤백/재적용, 전체 합성 테스트 **169 통과, skip 0**을 확인했고 제품 테이블 34개는 비어 있었다. 자연어 추출·AI adapter, 정정 시 기존 질문/검토 무효화, 동시 질문 전달 검증과 실제 수집 경로는 후속이다. [경계](docs/CareerGround_Profiling_Question_Workspace_Foundation_2026-09-27.md)
- 2026-09-27 정정 재진입 진행: `20260927_0014`에 임시 세션/입력/질문의 protocol cycle을 추가하고, 명시 `CORRECTION`은 질문 상태를 새 회차로 분리하며 미제출 검토를 만료·초안을 재검토 상태로 돌린다. 이전 회차의 질문 키·입력 출처는 새 회차에서 거부한다. PostgreSQL 17.11의 `0014` 적용·schema check·`0013` 롤백/재적용, 동시 질문 전달 검증을 포함한 전체 합성 테스트 **172 통과, skip 0**을 확인했고 제품 테이블 34개는 비어 있었다. 자연어 추출/AI adapter와 실제 수집 경로는 후속이다. [경계](docs/CareerGround_Profiling_Question_Workspace_Foundation_2026-09-27.md)
- 2026-09-27 오프라인 초안 추출 진행: 명시 입력에서 원문 문자 위치 1~5개를 검증하거나 사용자가 구조화한 bullet의 위치만 기계적으로 추출하는 합성 helper를 추가했다. 범위와 Claim 유형은 신뢰된 호출자가 지정하고, 저장 결과는 원문 그대로의 미확인 임시 `DRAFT`다. 복합 문장의 atomicity·사실성은 판정하지 않고 AI 공급자를 호출하거나 Claim을 승인하지 않는다. PostgreSQL 포함 전체 합성 테스트 **175 통과, skip 0**, Ruff 및 diff 검사가 통과했고 제품 테이블 34개는 비어 있었다. 실제 AI adapter·사용자 수집은 후속이다. [경계](docs/CareerGround_Profiling_Question_Workspace_Foundation_2026-09-27.md)
- 2026-09-27 AI 출력 계약 진행: 향후 공급자 출력에서 `spans`와 각 `start`/`end` 정수만 받아들이는 엄격한 파서를 추가했다. 원문 밖 위치, 겹침, 비정상 텍스트와 추가 권한 필드는 거부한다. 소유자·범위·Claim 유형·승인 여부를 공급자 출력으로 지정할 수 없다. 로컬 전체 합성 테스트 **172 통과, PostgreSQL 전용 4 skip** 및 변경 파일 Ruff·format 검사가 통과했다. 실제 공급자 호출은 없으며 G-L 데이터 처리 조건과 공급자 선택 후에만 연결 가능하다. 앞선 **175 통과, skip 0** 결과는 이 파서 추가 전 PostgreSQL 실행 결과다. [경계](docs/CareerGround_Profiling_Question_Workspace_Foundation_2026-09-27.md)
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
- 2026-09-27 로컬 합성 읽기 경로: `get_jd_analysis`를 별도 `career.artifact.read` scope로 추가하고, JWT 입구는 허용된 읽기 scope 중 하나를 요구하며 각 도구는 자기 scope를 다시 확인한다. JD 원문 전체 대신 저장된 위치별 발췌만 돌려주고 타 계정·없는 ID·삭제 중 프로필은 같은 `found=false`로 처리한다. 기존 `career.profile.read` 토큰은 JD 조회를 할 수 없다. 이 팩토리는 실제 진입점이 없는 합성 시험용이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md)
- 2026-09-28 `get_jd_analysis`에 정확한 보관 프로필 버전 인자를 요구하고, 그 버전의 기록된 잠재 Claim 연결·공백 상태와 최신 버전 대비 stale 여부를 붙였다. 의미적 적합성 평가, Evidence 강도 설명과 공개 경로는 후속이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md)
- 2026-09-27 로컬 합성 쓰기 경로: `career.profile.write`로 `start_profiling`·`add_profiling_input`·`pause_profiling`을 제한된 범위에서 연결했다. 시작 재시도 키는 같은 임시 세션을 반환하고 보관 시계를 늘리지 않으며 입력 재시도도 중복 저장하지 않는다. 타 계정·읽기 전용 토큰·일시정지 입력을 거부하고 canonical profile version은 바꾸지 않는다. MCP SDK가 알 수 없는 함수 인자를 무시하므로 도구 호출 직전에 정확한 필드 집합을 검사해 전체 채팅 배열 같은 추가 입력을 거부한다. 현재 `ADD_EXPERIENCE`/정책 v0.1과 `USER_STATEMENT`/`CORRECTION`만 받고, 실제 사용자 의도 증명·client locator·힌트·재개 도구와 공개 제품 진입점은 미구현이다. [경계](docs/CareerGround_Profiling_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 로컬 합성 검토 준비: `prepare_claim_review`를 `career.profile.write`로 연결하고, 같은 scope의 현재 임시 초안 1~5개만 정확히 묶는다. 재시도는 같은 묶음/digest를 반환하며 6개 이상을 임의 부분 선택하지 않는다. 검토 준비는 Claim 승인·Graph 변경을 하지 않는다. 실제 사용자에게 정확한 검토 화면을 제시했다는 증거와 승인 발급자·공개 경로는 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 로컬 합성 이력서 추적 읽기: `get_resume_trace`를 `career.artifact.read`로 연결하고 기존 R1 문장·Claim·선택 Evidence·고정 버전 검사를 재사용한다. 타 계정, 변조, 삭제 중 근거는 `found=false`로 닫는다. 전체 JD 원문이나 임시 프로파일링 원문은 반환하지 않는다. 공개 경로·R2/R3 승인·내보내기는 후속이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md)
- 2026-09-28 검토 표시/승인 경계의 합성 Web/BFF 팩토리: 서버가 보관한 정확한 검토 묶음을 HTML 이스케이프하여 보여주고, 항목마다 빈 기본 선택과 명시 확인을 요구한다. 세션·계정·digest·항목·버전에 묶인 3분 HMAC 토큰을 도메인 서비스에서 검증한 뒤에만 내부 승인 객체를 만든다. 이 팩토리는 실제 웹 앱에 마운트하지 않았고 신뢰된 브라우저 세션 콜백이 필요하다. 공개 경로·고영향 Claim 검토 증명은 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 Auth0 브라우저 세션의 합성 연계: 설치된 SDK의 검증된 세션을 매 요청 읽고 `(issuer, subject)`를 활성 계정에 새 DB 세션으로 매핑한다. 원본 쿠키 대신 정규화한 세션 쿠키 조각의 HMAC 결합값을 검토 토큰에 사용하고 SDK의 갱신 쿠키 응답을 보존한다. 외부 Auth0 tenant를 호출하거나 실제 웹 앱에 연결하지 않은 합성 테스트만 수행했다. 공개 경로·실사용자 표시 증명·운영 세션/CSRF 연계는 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 세션 상태 합성 조회 화면: 같은 신뢰 세션 경계에서 현재 세션 상태·프로필 버전·질문 단계·임시 초안 상태 수·보관 만료·검토 대기 링크를 읽기 전용으로 보여준다. 원문이나 전체 대화는 반환하지 않고 질문 전달 횟수도 증가시키지 않는다. 명시적 입력 화면과 실제 제품 경로는 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 명시적 합성 시작 화면: 기존 세션 링크와 수집 범위·90일 임시 보관 안내를 보여주고 체크 후 POST에서만 `ADD_EXPERIENCE` 세션을 만든다. 짧은 HMAC 토큰은 계정·브라우저 세션·프로필 버전·재시도 키에 묶인다. 같은 제출은 같은 세션으로 수렴하며 버전 변경·세션 교체·확인 누락은 생성하지 않는다. 정정/선택 발췌 입력과 실제 제품 경로는 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- 2026-09-28 합성 단일 입력 화면: 활성 세션에 사용자가 직접 작성한 `USER_STATEMENT` 한 건만 받는다. 확인 체크와 계정·브라우저 세션·작업 세션·기준 버전·재시도 키에 묶인 HMAC 폼 토큰을 요구하며, 재시도 원문 변경·추가 `messages` 필드·일시정지/오래된 세션은 거부한다. 상태 화면에는 입력 원문을 반환하지 않는다. `CORRECTION`과 선택 채팅/문서 발췌, 실제 ChatGPT 컨텍스트 접근은 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md)
- `E05-T02` Build narrow Web/BFF routes for session/review/trace/delete; keep DB access and direct approval logic out of adapters.
- Acceptance: tool contract tests cover all Phase A methods and negative auth/input cases; MCP/web give the same domain outcome for the same approved action.

**Story E05-S02 — Provide a reviewable Korean text UX.**

- `E05-T03` Implement explicit session start, source-scope notice, question/draft list, five-item exact review, JD/resume trace and deletion preview/status screens.
- `E05-T04` Add keyboard/accessibility checks, error recovery, empty/no-document path and privacy copy for 90-day workspace retention.
- 2026-09-30: 빈 v0 프로필의 직접 입력부터 초안·사실 확인·별도 사용 검토·JD 잠재 연결·R1 문구 검토·Markdown 다운로드까지 합성 Web 경로를 SQLite와 PostgreSQL에서 확인했다. 정확한 표시/사용 승인 분리를 유지하고 사실 검토 결과→근거→JD 화면 링크를 보강했다. 본문 바로가기·label/native control·오류 focus/alert·보관/검증 경계 문구를 HTML 구조로 점검했다. 실제 브라우저 키보드/스크린리더와 전체 접근성 감사는 미실시이며 공개 제품 UX 완료를 뜻하지 않는다. [증거](docs/CareerGround_Phase_A_Local_Validation_2026-09-30.md)
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
- 2026-09-30: 공통 MCP/Web 시작·입력·pause의 도메인 결과/거부와 재시도·Graph 무변경을 비교했다. MCP의 버전 문자열/bool/float/object 및 source object를 SDK coercion 전에 거부하고 원문이 오류/일반 INFO 로그에 나오지 않음을 확인했다. 전체 224개 테스트가 로컬 PostgreSQL 필수 모드에서 skip 없이 통과했으나, MCP 12개 도구(Phase A 이름 10개+보조 2개)는 전체 Plugin 계약이 아니다. 운영 rate limit/감사/로그·메트릭/실제 backup·외부 삭제/전체 접근성은 미완료다. [범위·위협·사고/롤백·출시 차단](docs/CareerGround_Phase_A_Local_Validation_2026-09-30.md)
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
| 2026-09-23 | 사용자가 외부 검증을 승인함. `codex/mvp-foundation-ci-20260923` 브랜치의 commit `1016f91`을 푸시하고 [GitHub Actions run 35870819987](https://github.com/inhoinno86-hub/CareerGround/actions/runs/35870819987)에서 PostgreSQL 17 migration·schema check, Ruff, **66개 테스트(66 통과, skip 0)**를 확인함. Auth0 tenant/ChatGPT 개발 관리 접근과 HTTPS `/mcp` 서버가 없어 실제 OAuth 연결은 미실시; 계정·유료 리소스도 만들지 않음. |
| 2026-09-24 | 사용자 요청으로 합성 전용 Auth0–ChatGPT 인증 PoC 서버를 별도 ASGI 진입점에 구현함. Streamable HTTP, 보호 리소스 메타데이터, 읽기 전용 프로브 도구, RS256/JWKS issuer·audience·scope 검증 및 로컬 합성 HTTP 테스트를 추가. 제품 데이터·DB와 분리했으며 실제 tenant·ChatGPT·공개 HTTPS 연결은 아직 미실시. [실행 절차](docs/CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md) |
| 2026-09-24 | 사용자 브라우저에서 기존 Auth0 웹 앱의 Google 로그인·세션 `/auth/me`와 동일 client ID의 Auth0 성공 로그를 확인함. 로그인 후 `/` 404는 로컬 응답을 추가해 해소. 실제 tenant discovery는 issuer·PKCE S256이 일치했지만 CIMD 광고가 없어 해당 게이트는 미통과. 별도 MCP 프로브의 로컬 메타데이터 200·무인증 401을 확인했고 외부 전송은 Secure MCP Tunnel 우선으로 정리함. ChatGPT OAuth·MCP 실제 토큰·합성 계정 분리 시험은 미실시이며 공급자 선정은 보류. [실측·후속 절차](docs/CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md) |
| 2026-09-26 | 개발 Auth0 tenant에서 CIMD 등록과 ChatGPT OAuth 연결·재연결, 실제 MCP 인증 도구 호출을 확인함. 같은 계정의 안정적인 시험 ID와 ChatGPT 연결 해제 후 새 호출 차단을 관측했으나, 기존 JWT 즉시 무효화는 입증되지 않음. 엄격한 Auth0 제3자 클라이언트와 성공한 인가 코드 교환으로 PKCE 적용을 간접 확인했고, 실제 S256 요청 필드는 미캡처. 개발용 합성 API의 새 토큰 최대 수명을 1시간으로 줄여 재조회 확인함. 서로 다른 합성 subject의 ID 분리 테스트 6개가 통과했지만 두 실제 계정은 사용하지 않음. 운영용 인증 공급자 선정·제품 데이터 연결은 계속 보류. [상세 기록](docs/CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md) |
| 2026-09-27 | 사용자가 운영 전 계정 상태 재검사 방향을 승인함. 검증된 JWT에 대해 매 MCP HTTP 요청 새 DB 세션에서 `ACTIVE` 계정을 조회하는 게이트를 구현하고 합성 요청에서 같은 토큰의 활성→비활성/인증 매핑 제거 후 200→401 전환을 검증함. DB 없는 실행 중 PoC와 제품 데이터 미연결 상태는 유지. 실제 제품 MCP 경로·삭제 트랜잭션·연결별 철회·운영 token/refresh 설정은 아직 남음. |
| 2026-09-27 | 다음 구현 단계로 별도 로컬 제품 MCP 팩토리를 추가함. `career.profile.read` 최소 scope, 검증된 계정의 안정적 ID, 계정 소유권을 다시 조회하는 프로필 메타데이터 도구를 합성 DB로 검사함. PoC의 `careerground:probe`만으로는 접근할 수 없고, 다른 계정/없는 ID는 같은 `found=false` 응답이다. 제품 서버 진입점과 실제 Career Graph·계정 삭제 파이프라인은 아직 없음. |
| 2026-09-27 | 삭제 기능의 첫 기반으로 `20260927_0002` migration과 계정/프로필 `DELETING`·`ERASED` 상태, 제한된 삭제 요청/작업 항목 테이블을 추가함. 계정·인증 연결·프로필만 다루는 비파괴 미리보기와 짧은 HMAC 영향 digest/명시 동의/검증된 step-up 재확인 계약을 합성 테스트로 검증함. `FOUNDATION_ONLY`이며 삭제 실행·실데이터 도구·복원 방지 원장은 여전히 미구현. [상세 경계](docs/CareerGround_Deletion_Foundation_2026-09-27.md) |
| 2026-09-27 | 사용자의 자율 진행 요청에 따라 `20260927_0003` migration과 명시적 프로파일링 작업 세션/입력 저장 경계를 추가함. 30분 일시정지, 세션별 마지막 실제 활동 기준 90일, 명시 재개·중복 입력의 기간 처리, 만료·삭제 중 조회 거부 및 계정 복합 FK 격리를 합성 테스트함. 삭제 미리보기에도 해당 세션/입력 ID를 반영했으나 아직 `FOUNDATION_ONLY`이다. [상세 경계](docs/CareerGround_Profiling_Workspace_Foundation_2026-09-27.md) |
| 2026-09-27 | E02-T03 및 현 스키마 범위의 T06–T09 후속 기반: 원문 없는 outbox/receipt, 제한된 90일 만료 실행, 내부 합성 삭제 확인·즉시 차단·작업 기록, 독립 서명 원장과 격리 복원 리허설을 추가함. 공개 삭제·실제 step-up·외부 저장소/공급자·운영 스케줄·실제 백업 검증은 미완료이며 `FOUNDATION_ONLY`/`ready_to_execute=false`를 유지함. [경계와 검증](docs/CareerGround_Data_Lifecycle_Foundation_2026-09-27.md) |
| 2026-09-27 | E02-T04의 합성 로컬 기반과 T06/T08 연동: `20260927_0006`에 비공개 원본/버전 메타데이터, 녹음 기본 비저장·종류별 30일 시계, 만료 시 접근 차단·버전별 outbox, 삭제 digest와 복원 격리 검사를 추가함. 실제 S3·업로드·운영 worker는 연결하지 않음. [경계](docs/CareerGround_Private_Object_Foundation_2026-09-27.md) |
| 2026-09-27 | E02-T01/T02와 E03-T03의 합성 임시 검토 저장 기반: `20260927_0007`에 소유자·세션·경험 범위를 묶는 초안/최대 5개 검토 스냅샷, 정확한 HMAC digest, 만료·삭제·복원 정리를 추가함. 원문과 승인 결정을 canonical Claim으로 자동 승격하지 않으며 제출·Graph 스키마는 후속. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-27 | E02-T01/T02, E03-T04 합성 Graph 기반: `20260927_0008`에 소유자 범위 Claim/Evidence/평가/검토/경계/변경 이력을 추가했다. 내부 합성 명시 승인에 한해 최대 5개 항목을 원문·digest·버전 재검사 후 한 트랜잭션으로 승격하며, 편집·후속 질문은 버전을 올리지 않는다. 확인된 Claim도 일관성 미평가·게시 재검토 상태다. Graph 삭제 미리보기·로컬 정리와 오래된 복원본 차단까지 합성 테스트했다. 실제 승인 발급자·공개 경로·외부/백업 삭제는 후속. [경계](docs/CareerGround_Canonical_Graph_Foundation_2026-09-27.md) |
| 2026-09-27 | 버전별 이력 보존 기반 `20260927_0009`를 추가했다. canonical 변경 전·후의 Graph를 같은 트랜잭션에서 정확한 프로필 버전별 스냅샷으로 기록하고, 소유자·해시 확인 후 그 버전만 조회한다. 없는 버전은 최신본으로 대체하지 않는다. 삭제 미리보기·로컬 정리·복원 격리에도 스냅샷을 포함했다. 루프백 PostgreSQL 17.11 `_test`에서 `0006`–`0008`의 downgrade/upgrade, `0009` 적용·downgrade/re-upgrade·schema check, 최종 PostgreSQL archive 조회 단언을 포함한 전체 **140개 테스트 통과(skip 0)**를 확인했다. 테스트 뒤 24개 제품 테이블은 모두 비어 있었다. [경계](docs/CareerGround_Canonical_Graph_Foundation_2026-09-27.md) |
| 2026-09-27 | E02-T01/T02와 E04-T01의 합성 JD/산출물 저장 기반 `20260927_0010`을 추가했다. 계정/프로필 복합 FK, JD 발췌 위치·해시, 정확한 프로필 archive 버전에 묶인 이력서 산출물/문장·Claim 연결을 마련했다. 붙여넣은 JD의 호출자 지정 구간만 저장·조회하며 원문 별도 컬럼/LLM 호출은 없다. 승인·내보내기 DB 상태는 아직 허용하지 않고 삭제·복원 격리에 새 행을 포함했다. PostgreSQL 17.11 빈 DB 적용, schema check, `0009` 롤백·재적용을 검증했다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-27 | E04-T02의 내부 합성 연결 경로를 추가했다. 호출자가 고른 JD 요구사항과 Claim을 정확한 현재 archive 버전에 묶고, 검토·지원 근거·일관성·사용 허용·경계 조건을 재검사한다. 연결은 `POTENTIAL`만 저장하며 Graph 상태/버전을 바꾸지 않고, 연결 없는 요구사항은 기록된 연결 없음으로 표시한다. 의미 적합성 자동 판정과 공개 API는 미구현이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-27 | E04-T03의 제한된 내부 합성 경로로 선택한 적격 Claim 원문만 R1 이력서 초안에 복사하고 정확한 JD/프로필 버전·근거 발췌를 추적한다. 문구 변경, 승인, 내보내기, 공개 API는 연결하지 않았다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-27 | 로컬 PostgreSQL 17.11 `20260927_0010` 적용·schema check·빈 DB 다운그레이드/재적용, 전체 합성 테스트 149개 skip 없이 통과했다. 현재 프로필 승인 경로는 기본 `REVIEW_REQUIRED` 평가를 만들므로 JD 연결과 이력서 초안은 별도 검토/일관성/허용 판단이 기록된 합성 fixture에서만 성공한다. 실제 사용자 데이터와 운영 서비스는 연결하지 않았다. |
| 2026-09-27 | E03-T05의 합성 내부 기반으로 `20260927_0011` 경계·모순 검토 이력과 정확한 HMAC/버전/소유권 검사를 추가했다. 경계 추가·해제는 관련 scope를 다시 `REVIEW_REQUIRED`로 두고, 모순 검토는 영향받은 Claim만 차단 상태로 갱신한다. 상충 근거와 이전 archive는 보존하며 이전 `v1` snapshot과 새 `v2` snapshot의 호환성을 테스트했다. 수정된 사실의 새 Claim 생성이나 게시 허용은 아직 없다. [경계](docs/CareerGround_Boundary_Conflict_Review_Foundation_2026-09-27.md) |
| 2026-09-27 | 로컬 PostgreSQL 17.11에서 `20260927_0011` 빈 DB 적용·schema check·`0010` 롤백/재적용을 검증했다. 전체 156개 합성 테스트가 PostgreSQL 필수 모드에서 skip 없이 통과했고, 종료 후 32개 제품 테이블은 모두 비어 있었다. |
| 2026-09-27 | E03-T06의 제한된 합성 내부 JSON 내보내기 투영을 추가했다. 정확한 archive 버전의 활성 Claim, 선택 근거 발췌·원본 입력 참조, 독립 사용 금지 경계를 포함하고 만료 대화 원문/임시 초안 요청은 거부한다. 실제 다운로드 자원·전체 데이터 이동성·공개 API는 아직 없다. [경계](docs/CareerGround_Profile_Export_Foundation_2026-09-27.md) |
| 2026-09-27 | E04-T04의 R1 전용 합성 내부 문구 검토와 JSON/Markdown 메모리 내보내기를 추가했다. 고정 산출물/Claim/근거의 정확한 digest와 신뢰된 합성 승인 객체를 검사하고, 내보내기 직전 현재 버전·근거·경계를 재검사한다. R2/R3, 다운로드 자원, 실제 승인 발급자·공개 API는 미구현이다. PostgreSQL 17.11 `0012` 적용·schema check·`0011` 롤백/재적용 및 전체 158개 테스트 skip 없이 통과했다. 테스트 후 제품 테이블 33개는 비어 있었다. [경계](docs/CareerGround_Resume_Wording_Foundation_2026-09-27.md) |
| 2026-09-27 | E03-T06 합성 읽기 기반: 저장된 정확한 profile archive 버전에서만 Claim 요약과 선택 근거 발췌를 조합한다. 임시 원문이 만료된 경우 `SELECTED_EXCERPT_ONLY`를 명시하고, 과거 버전 누락·삭제·타 계정 조회는 최신본으로 대체하지 않는다. 공개 MCP/export 경로는 없으며 `0010`에서 Claim/버전별 평가 중복 DB 제약을 더했다. [경계](docs/CareerGround_Canonical_Graph_Foundation_2026-09-27.md) |
| 2026-09-27 | 사용자가 직접 시작한 일회용 로컬 PostgreSQL 17 `careerground_test`에서 `20260923_0001`→`20260927_0003` 적용, `alembic check`, 데이터가 없는 전체 테이블 확인 후 `downgrade base`→`upgrade head`, PostgreSQL 통합 테스트를 필수로 설정한 전체 **92개 테스트(92 통과, skip 0)**를 확인함. 이는 합성 빈 DB의 스키마 검증이며 보관 만료 물리 삭제·실데이터 복원 방지 검증은 아님. 사용자가 이후 일회용 컨테이너를 중지했고 `--rm` 설정으로 제거됨. |
| 2026-09-27 | 내부 프로파일링 만료 배치 작업자를 추가함. 90일 경과한 세션과 그 입력만 최대 1,000개씩, 호출자 트랜잭션 안에서 삭제하고 `DELETING`/`ERASED` 대상은 제외한다. SQLite 합성 테스트로 만료 경계·제한 배치·재시도·롤백을 확인했다. 새 일회용 PostgreSQL 17 `careerground_test`에서 만료/유효 세션의 실제 삭제·보존, `alembic check`, 전체 **95개 테스트(95 통과, skip 0)**를 확인했고 테스트 후 모든 제품 테이블은 비어 있었다. 스케줄러·동시 작업자·백업 복원 차단은 여전히 미검증이다. |
| 2026-09-27 | 테스트 컨테이너 종료 뒤 내부 `get_profiling_session`/`pause_profiling_session`을 추가했다. 읽기 전용 상태 조회는 30분 경과에 따른 유효 `PAUSED`를 표시하되 저장·원문 노출을 하지 않고, 직접 일시정지는 활동/만료/프로필 버전을 바꾸지 않는다. 별도 로컬 제품 MCP 팩토리에 `career.profile.read` 범위의 읽기 전용 세션 메타데이터 도구도 추가해 타 계정/없는 ID가 같은 `found=false`이고 입력 원문이 응답에 없는지 합성 HTTP로 확인했다. 전체 **98개 테스트 중 97개 통과, 종료된 PostgreSQL 전용 1개 skip**; Ruff 검사/포맷·diff 검사 통과. 실제 ASGI 진입점·수집 도구는 없으며 PostgreSQL 재검증은 이 변경 범위에서 미실시했다. |
| 2026-09-27 | E05-T01의 다음 읽기 경로로 로컬 제품 MCP 팩토리에 `get_career_profile`을 추가했다. `career.profile.read` 토큰과 활성 계정·소유권을 재검사하고, 호출자가 지정한 정확한 보관 버전의 canonical Claim 요약만 반환한다. 타 계정/없는 프로필/없는 버전/삭제 중 프로필은 동일한 `found=false`다. 합성 HTTP 테스트 7개 및 전체 로컬 테스트 **156 통과, PostgreSQL 전용 3 skip**, Ruff·diff 검사가 통과했다. 실제 제품 진입점·전체 Phase A 도구·사용자 데이터 연결은 여전히 없다. |
| 2026-09-27 | E05-T01의 합성 읽기 경로를 확장했다. `get_claim_evidence`는 Claim ID에서 활성 소유 계정의 프로필을 찾아 정확한 archive 버전의 선택 근거 발췌·관계·출처 상태를 반환한다. `get_claim_review`는 별도 HMAC secret으로 준비된 최대 5개 항목의 정확한 snapshot을 확인하고, 읽기만으로 digest/기한을 갱신하지 않으며 현재 프로필 버전과의 호환성을 표시한다. 내부 조회는 임시 세션의 삭제 중·만료 상태도 거부한다. 타 계정/없는 ID/없는 버전/삭제 중 대상은 동일한 `found=false` 응답이다. 전체 로컬 **157 통과, PostgreSQL 전용 3 skip**, Ruff·diff 검사 통과. 승인 제출·제품 진입점·실사용자 데이터는 연결하지 않았다. |
| 2026-09-27 | `d2bb27c`로 현재까지의 합성 기반 57개 파일을 한 번 커밋했다. 기존 미추적 초안·프롬프트 묶음은 제외하고 보존했으며 푸시하지 않았다. 다음 E03-T02 작업으로 Profiling Protocol v1의 13개 질문 상태와 첫 질문/구체화 질문 예산, 필수·선택 UNKNOWN/모순 중단을 계산하는 순수 planner를 착수했다. 원문 해석·상태 저장·Claim 승인·실제 수집은 수행하지 않는다. |
| 2026-09-27 | GPT 플러그인용 E05-T01의 로컬 합성 읽기 범위를 `get_jd_analysis`로 확장했다. `career.artifact.read`와 기존 `career.profile.read`를 HTTP 입구와 각 도구에서 분리해 검사한다. 전체 로컬 합성 테스트 **173 통과, PostgreSQL 전용 4 skip**, CI Ruff·format 및 diff 검사 통과. PostgreSQL 컨테이너는 종료 상태이며 이번 변경의 PostgreSQL 재검증은 하지 않았다. 공개 제품 진입점·실사용자 데이터·외부 AI 공급자는 연결하지 않았다. |
| 2026-09-27 | E05-T01의 합성 쓰기 도구 `start_profiling`·`add_profiling_input`·`pause_profiling`을 로컬 제품 MCP 팩토리에 추가했다. `career.profile.write` 범위에서만 임시 세션/입력을 변경하며 키 재시도, 타 계정, 추가 `messages` 인자, 읽기 권한 토큰과 pause 후 새 입력을 거부한다. 전체 로컬 합성 테스트 **175 통과, PostgreSQL 전용 4 skip**, CI Ruff·format 및 diff 검사 통과. 사용자 의도 증명·다른 goal/input kind·재개 도구와 공개 진입점은 여전히 미구현이다. |
| 2026-09-28 | E05-T01의 로컬 합성 `prepare_claim_review`를 `career.profile.write`로 연결했다. 한 scope의 현재 초안 1~5개를 정확히 묶고 재시도 ID/digest를 유지하며 Claim/프로필 버전을 바꾸지 않는다. 전체 로컬 테스트 **177 통과, PostgreSQL 전용 4 skip**, Ruff·format·diff 검사 통과. 실제 사용자 검토 표시·승인 발급자·공개 경로는 연결하지 않았다. |
| 2026-09-28 | E05-T01의 다음 합성 읽기 도구 `get_resume_trace`를 `career.artifact.read`로 연결했다. 기존 내부 R1 추적 검사를 재사용하여 문장→Claim→선택 Evidence와 정확한 버전을 반환하고 타 계정·변조·삭제 중 대상을 숨긴다. `get_jd_analysis`는 정확한 보관 프로필 버전의 잠재 연결·공백/stale 상태를 반환하게 보강했다. 전체 로컬 **182개 중 178 통과, PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 저장소 전체 Ruff의 기존 범위 밖 오류 12개는 별도다. 실사용자 데이터·운영 서비스·승인 경로와 분리되어 있다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | E03-T03/T04·E05-T02/T03의 합성 검토 표시/제출 경계를 추가했다. 별도 Web/BFF 팩토리의 HTML은 정확한 보관 문구를 이스케이프하고 항목별 빈 기본 선택·명시 확인을 요구한다. 3분 토큰은 계정·브라우저 세션·batch·digest·항목·버전에 서명되며 검증 후 기존 원자적 내부 제출 명령으로만 전달된다. 다른 세션/계정, 토큰 변조, 누락·추가 입력, stale 버전, 만료 토큰은 승격하지 않는다. 전체 로컬 **185개 중 181 통과, PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 실제 앱에 마운트하거나 Auth0/실데이터를 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T02의 다음 합성 경계로 설치된 Auth0 SDK 세션을 받는 선택적 검토 어댑터를 추가했다. 검증된 `sub`를 매 요청 새 DB 세션에서 활성 계정으로 해석하고, 세션 쿠키 원문을 내보내지 않는 HMAC 결합값을 사용한다. 쿠키 조각 재분할은 허용하지만 실제 회전, 인증 매핑 제거, 계정 비활성화 및 잘못된 쿠키 형식은 거부한다. 전체 로컬 **188개 중 184 통과, PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 실제 Auth0/제품 웹 앱/실데이터는 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 다음 합성 화면으로 소유 세션의 읽기 전용 상태·검토 대기 링크와 명시적 `ADD_EXPERIENCE` 시작 폼을 추가했다. GET은 저장하지 않고, 시작 POST는 수집 범위/90일 안내 확인 및 세션·계정·버전·재시도 키에 묶인 짧은 토큰을 요구한다. 재시도는 같은 세션이며 타 세션·버전 변경은 생성하지 않는다. 전체 로컬 **190개 중 186 통과, PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 실제 앱/실데이터/외부 서비스는 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 단일 입력 폼은 활성 소유 세션에서 작성한 `USER_STATEMENT` 한 건만 보관한다. 10분 서명 토큰과 명시 체크를 요구하고, 같은 원문 재시도는 중복 저장하지 않는다. 다른 원문·세션·폼 용도, 전체 채팅 필드, 일시정지/오래된 버전은 거부하며 상태 화면에는 원문을 노출하지 않는다. 전체 로컬 **192개 중 188 통과, PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 실제 사용자 입력은 전혀 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 세션 상태 화면에 명시적 일시정지·재개와 사용자 직접 `CORRECTION` 입력을 연결했다. 서명 토큰은 계정·브라우저·세션·버전·활동 시각 또는 입력 종류에 묶이며, 재개 토큰 재사용은 90일 시계를 다시 늘리지 않는다. 정정은 기존 질문 회차와 미제출 검토를 무효화하고 초안을 재검토 상태로 돌리며 같은 입력 재시도는 한 번만 반영한다. 전체 로컬 **196개 중 192 통과, PostgreSQL 전용 4 skip**(마지막 추가 집중 테스트 포함), 변경 범위 Ruff·format 검사 통과. 실제 사용자 데이터나 운영 서비스를 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 임시 초안 목록에서 소유 세션의 만료 전 정확 문구·범위·유형·상태를 최대 50개 이스케이프하여 표시한다. 50개 초과 시 잘림을 알리고 타 계정/삭제 중 세션을 숨기며 조회는 입력·질문·보관 시계·Claim·프로필 버전을 바꾸지 않는다. 실제 사용자 데이터와 운영 경로는 연결하지 않았다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 이력서 초안 목록과 정확한 R1 근거 추적 화면을 추가했다. 활성 소유 계정의 목록만 보여주고 각 열람에서 기존 archive/Claim/Evidence 검증을 재실행한다. 타 계정·문구 변조는 404, 전체 JD/임시 입력 원문은 표시하지 않는다. 공개 제품 경로, 문구 승인과 내보내기는 후속이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 질문 진행 화면은 현재 protocol cycle의 13개 상태·질문 횟수·관찰 상태만 읽는다. 질문 전달·입력 원문·출처 ID/사유 표시·보관 시계 변경은 없고 정정 후 이전 회차 횟수는 새 화면에 나타나지 않는다. 실제 질문 답변의 의미 판단과 공개 경로는 후속이다. [경계](docs/CareerGround_Profiling_Question_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 계정/프로필 삭제 영향 화면은 확인 가능한 로컬 항목 수만 표시하고 `FOUNDATION_ONLY`/실행 불가 경계를 명시한다. 타 계정 프로필은 404이며 GET은 요청·차단·삭제를 만들지 않는다. 확인 digest·삭제 POST·실제 step-up은 없으므로 이 화면을 실사용자 완전 영향 고지로 사용할 수 없다. [경계](docs/CareerGround_Deletion_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T04의 합성 브라우저 오류 복구로 400/409 등에서 원문·토큰·내부 예외를 노출하지 않는 한국어 안내와 시작 화면 링크를 추가했다. `role=alert`, no-store와 기존 보안 헤더를 적용했고 브라우저 집중 테스트를 통과했다. 접근성 전체 감사와 완전한 텍스트 여정은 아직 후속이다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 JD 목록과 발췌 화면을 추가했다. 활성 소유자만 목록/정확 ID의 저장된 발췌·위치를 볼 수 있고 타 계정은 404, 선택되지 않은 전체 JD 원문은 반환하지 않는다. 자동 요건 분류·적합성 판단·실제 수집은 후속이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | E05-T03의 합성 JD 연결 기록 화면은 명시된 보관 프로필 버전의 잠재 Claim 연결·공백·stale 상태만 읽고 R1 근거 화면에서 정확 버전으로 연결된다. 타 계정/없는 archive는 404이며 연결 없음은 역량 부족으로 해석하지 않는다. 의미적 매칭·실제 사용자 입력·공개 서비스는 후속이다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | 이번 합성 Web/BFF 확장 후 전체 로컬 **199개 중 195 통과, 중지된 PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 원래 미추적 초안과 프롬프트 묶음을 보존하고 커밋·푸시하지 않았다. 실제 사용자 데이터/운영 서비스/외부 AI는 연결하지 않았다. 텍스트 여정의 자동 질문 해석·초안 의미 추출은 G-L 공급자·데이터 처리 게이트 전까지 합성 계약 범위에 머문다. |
| 2026-09-28 | E03-T06/E05-T02의 합성 canonical JSON 내보내기를 명시적 브라우저 폼으로 연결했다. GET은 범위·크기·SHA-256만 표시하고 5분 계정/브라우저 세션/정확 버전/해시 토큰과 체크 후 POST에서만 no-store 첨부파일을 반환한다. 타 계정·세션 교체·만료·삭제 중 프로필은 거부하며 임시 초안/만료 원문은 제외한다. 제품 웹 앱에는 마운트하지 않았다. [경계](docs/CareerGround_Profile_Export_Foundation_2026-09-27.md) |
| 2026-09-28 | E03-T03/E05-T03의 합성 브라우저에서 임시 초안 범위별 1~5개 정확 문구를 표시하고 명시 확인 뒤 기존 검토 준비 명령을 호출한다. 계정·브라우저 세션·범위·기준 버전·표시 초안 digest에 묶인 3분 토큰으로 변조/변경을 거부하며 재시도는 같은 검토 묶음으로 수렴한다. 이 단계는 사실 승인이나 canonical 변경이 아니다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E02-T01/E05-T03의 합성 명시 입력 여정에서 사용자가 직접 적은 `- ` 또는 `* ` 글머리표 1~5개만 별도 화면에 정확히 보여주고, 경험 범위 지정·확인 후 임시 `CONTRIBUTION` 초안을 만든다. 입력 ID/해시·질문 회차·프로필 버전·브라우저 세션에 묶인 3분 토큰과 안정 ID로 재시도 중복을 막으며 같은 입력의 다른 범위 재사용을 거부한다. AI 추론이나 Claim 자동 승격은 없다. [경계](docs/CareerGround_Review_Workspace_Foundation_2026-09-27.md) |
| 2026-09-28 | E03-T06/E05-T03의 합성 브라우저에서 보관 프로필의 정확 버전과 Claim별 선택 근거·출처 참조·동일 범위 경계를 읽기 전용 화면으로 연결했다. 사용자 확인과 외부 검증을 구분하고 사용 정책/일관성 상태를 표시한다. 타 계정·없는 버전/Claim은 404, 응답은 no-store이며 임시 입력 전체 원문은 보이지 않는다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | E04-T01/E05-T03의 합성 JD 입력 화면에서 직접 고른 요건 글머리표 1~5개만 받아 원문 위치·해시와 `UNCLASSIFIED` 발췌로 저장한다. 계정·브라우저 세션·현재 프로필 버전에 묶인 10분 토큰/확인 체크를 요구하고 동일 제출은 같은 JD 버전으로 수렴한다. 다른 세션·오래된 버전·일반 문단·추가 폼 필드는 거부하며 외부 JD 조회/AI 분류는 없다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | 이번 합성 화면/입력 확장 후 전체 로컬 **206개 중 202 통과, 중지된 PostgreSQL 전용 4 skip**, CI 범위 Ruff·format 및 diff 검사 통과. 커밋·푸시하지 않고 기존 미추적 초안 두 위치와 프롬프트 묶음을 보존했다. 실제 사용자 데이터·운영 서비스·외부 AI는 연결하지 않았다. |
| 2026-09-28 | R1 텍스트 여정의 다음 정책 게이트를 [Claim 사용 적격성 결정안](docs/CareerGround_Claim_Eligibility_Decision_2026-09-28.md)으로 정리했다. 현행 `ACCEPT`는 `USER_CONFIRMED`만 기록하고 `CONSISTENT`/`ALLOWED`를 발급하지 않으므로, 소유자의 별도 명시 검토를 허용할지 결정 전에는 합성 화면에서 JD 연결·R1 생성으로 이어지지 않는다. |
| 2026-09-29 | 소유자가 합성 R1 경로의 별도 Claim 사용 검토 권장안을 승인했다. 정확 문구·근거·경계·현재 평가를 표시하고 두 독립 확인/3분 계정·브라우저 세션 토큰을 요구하는 로컬 브라우저 경로를 구현했다. 이전 사실 검토·SUPPORTS·충돌/경계·현재 보관 버전/실제 Graph 일치를 재검증한 후에만 전용 journal, `CONSISTENT`/`ALLOWED` 평가, 변화 기록과 v3 archive를 한 트랜잭션으로 남긴다. 기존 v1/v2 snapshot 호환, 삭제 영향/로컬 정리를 포함했다. 실제 사용자 데이터·공개 경로·운영 AI는 연결하지 않았다. [경계](docs/CareerGround_Claim_Use_Review_Foundation_2026-09-29.md) |
| 2026-09-29 | 별도 사용 검토 후 합성 JD 잠재 연결→R1 문구 검토→Markdown 내보내기까지 집중 테스트했다. 전체 로컬 **213개 중 209 통과, PostgreSQL 전용 4 skip**. CI 범위 Ruff·format, diff 검사, `20260929_0015`까지 PostgreSQL 오프라인 upgrade SQL 생성 통과. 로컬 `127.0.0.1:55432` 테스트 DB 컨테이너가 중지되어 migration/schema check·롤백/재적용은 수동 시작 후 후속 검증한다. |
| 2026-09-29 | 사용자 시작한 루프백 PostgreSQL 17 `careerground_test`의 빈 DB에 `alembic upgrade head`로 `0015`까지 적용하고 `alembic check`, `0015`→`0014` 롤백→`0015` 재적용을 검증했다. `CAREERGROUND_REQUIRE_POSTGRES_TEST=1`로 전체 **213개 통과, skip 0**. 종료 후 migration은 `0015`, 제품 테이블 35개는 전부 비어 있었다. 실제 사용자 데이터·운영 서비스는 연결하지 않았다. [검증 기록](docs/CareerGround_Claim_Use_Review_Foundation_2026-09-29.md) |
| 2026-09-29 | E04-T02/T03·E05-T03의 합성 브라우저에 JD 요건과 적격 Claim의 명시적 잠재 연결, 연결된 정확 문구 1~5개 선택 R1 초안 생성을 추가했다. 각각 짧은 계정·브라우저·버전·표시 내용 토큰/확인 체크와 소유권·현재 archive 검사를 요구한다. 동일 제출은 연결 또는 초안 한 건으로 수렴하고 다른 세션·오래된 버전·변경된 연결은 거부한다. 별도 Claim 사용 검토→JD 저장→연결→R1 초안→문구 검토→Markdown 다운로드의 합성 브라우저 여정과 빈 버전 0 프로필의 JD 저장/명시적 연결 없음 화면을 확인했다. 전체 로컬 **218개 중 214 통과, 중지된 PostgreSQL 전용 4 skip**, JD 집중 18개 통과, CI 범위 Ruff·format 통과. 새 migration은 없고 실제 사용자 데이터·운영 서비스는 연결하지 않았다. [경계](docs/CareerGround_JD_Artifact_Foundation_2026-09-27.md) |
| 2026-09-28 | E04-T04/E05-T02의 합성 R1 문구 검토와 JSON·Markdown 내보내기 화면을 연결했다. 정확한 문구·Claim·선택 Evidence를 보여준 뒤 3분 계정/브라우저/검토 digest 토큰과 명시 확인을 요구한다. 승인 제출은 현재 Graph와 원문을 재검사하며 동일 토큰 재시도는 검토 기록 한 건으로 수렴한다. 내보내기는 형식/해시를 묶은 5분 토큰과 최신 적격 근거 재검사를 거쳐 no-store 첨부파일을 반환한다. R2/R3와 실제 제품 진입점은 후속이다. [경계](docs/CareerGround_Resume_Wording_Foundation_2026-09-27.md) |
| 2026-09-30 | 지정 HEAD에서 인계 step-01–05를 진행했다. 문서 없는 빈 프로필 직접 입력→R1 다운로드의 SQLite/PostgreSQL 여정, 타 계정/삭제 중 export 차단, 만료·입력 거부·화면 구조와 MCP/Web workspace parity를 보강했다. DB URL 없는 전체 **224개 중 218 통과, PostgreSQL 6 skip**, 새 여정 파일을 포함한 CI 범위 Ruff check 및 format **103개** 통과. 사용자 시작한 루프백 일회용 PostgreSQL 17.11에서 빈 DB `0015` upgrade/check·`0014` rollback/reapply/check와 required-PostgreSQL 전체 **224 통과, 실패/skip 0**, 제품 테이블 **35개 모두 0행**을 확인했다. 새 migration은 없고 사용자가 컨테이너 중지를 완료했다. HEAD/무시된 초안을 보존하고 커밋·푸시·외부 연결하지 않았다. 전체 Gate A/운영 계약·공급자/Phase B/C는 미완료로 유지했다. [검증 기록](docs/CareerGround_Phase_A_Local_Validation_2026-09-30.md) |
| 2026-10-01 | 사용자 요청한 세 후속 항목을 로컬에서 구현·검증했다. E08-T02의 안전한 예외/로그·DB bind 숨김, Web/MCP 공유 account quota와 SQLite/PostgreSQL 동시 예약 검사를 추가했다. migration `0016` 빈 DB upgrade/check·`0015` rollback/reapply/check, required-PostgreSQL **232 pass, 실패/skip 0**, 제품 테이블 **36개 모두 0행**. 사용자가 컨테이너 중지했고 루프백 포트 닫힘·임시 비밀번호 파일 삭제를 확인했다. 실제 Chrome 150의 키보드 전체 여정·320px/200% 텍스트·접근성 tree 등 **359 assertion pass**, CI Ruff check/format **108개** 통과. MCP 13개 도구에 공통 응답/schema와 읽기 전용 부분 삭제 preview를 연결하고 미구현 A 도구 10개/승인 증명/운영 경계를 명시했다. 전체 Gate A와 운영·공급자 결정은 미완료이며 공개 마운트·커밋·푸시·외부 AI 연결은 하지 않았다. [검증 기록](docs/CareerGround_Phase_A_Security_Accessibility_Contracts_2026-10-01.md) |

| 2026-10-01 | 승인된 후속 1–4의 로컬 구현·검증을 완료했다. 무요청 카운터/승인 메타데이터 정리·안전한 집계, 실제 브라우저가 완료한 사실/문구/내보내기의 MCP 증명·private resource, 부분 삭제 상태를 추가해 합성 도구19개가 됐다. rootless PostgreSQL17.11에서 migration0017 upgrade/check·0016 rollback/reapply/check, 전체 **258 pass/실패·skip0**, CI Ruff/format117개, 제품37 tables 모두0을 확인하고 DB·포트·credential·설치를 정리했다. Firefox383/실제Chrome200%확대361/새승인Chrome·Firefox각53/실제Orca발화요청11 checks 통과. 초안20 hashes와 HEAD 보존, 커밋·푸시·외부 AI 없음. 전체 Gate A·실사용자 청취/접근성·공급자/운영 삭제는 미완료다. [최신 기록](docs/CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md) |

| 2026-10-01 | 추가 승인된 권장1–4를 완료했다. 기존 모순·경계 domain의 브라우저 정확 승인/MCP 증명, 선택 JD/POTENTIAL 연결/정확 R1(별도 문구 검토), 128KiB MCP 입구와 malformed tool 공유 read quota, 별도 내부 삭제 후 상태 capability를 연결했다. 합성24도구(Phase A 이름19+보조5), migration0018/0019→0017 rollback/reapply/check, required-PG17.11 **295 pass/실패·skip0**, CI Ruff/format131개. 실제 Chrome/Firefox 정책12시나리오788검사, JD1–5발췌 전체10여정2030검사 통과. 승인 전 원문DB복제 없음·선택 근거 명시·서로 다른 동시 요청 잠금 순서·R1 두 문구 순서도 검증했다. 제품37테이블 모두0/revision0019 확인 후 rootless DB·루프백36837·credential/빌드 설치 정리, 초안20 hashes/HEAD 보존. 공개 Gate A·의미 분석/R2/R3·공급자/운영 삭제·실사용자 접근성은 미완료, 커밋·푸시 없음. [현재 기록](docs/CareerGround_Phase_A_Review_JD_Hardening_2026-10-01.md) |
| 2026-10-03 | 로컬 권장1→2→3 완료: CURRENT 숫자고정/포함옵션 정확승인, 별도 R2 계보·저장·내보내기 및 R3 사실검토 안내, SESSION/EVIDENCE/PROJECT raw 자료 정리·유지Claim 재검토·PROJECT재사용 차단·ledger복원격리. migration0020, 실제 PostgreSQL **369 PASS/skip0**·38 tables0행, BrowserOS nativeMCP **151 checks PASS**, 오프라인53/53, CI Ruff/diff PASS. 기존0019 개발저장소/ignored초안 보존, 테스트자원 정리·커밋/푸시 없음. 운영 Gate A/B/C와 실제공급자 선정은 미완료. [완료이력/다음4번](docs/CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md) |
| 2026-10-03 | 다음4번 로컬 준비: G-I 12개 시험 절차·증거/실제 step-up 기준, G-L 한국어 의미 평가36개·합격선/비용/처리 조건 초안, G-P/G-C 운영10개 시험·삭제/격리복원·장애/배포·예산 설계. 합성 unittest45 PASS/skip0, 기존경계53/53, 준비 manifest/hash 검사PASS·실제ready 요구exit3, CI Ruff166files PASS. 실제provider/AI/유료클라우드/공개배포/commit/push 없음. 다음 실제 인증 시험에는 두 계정/tenant/외부 범위 승인 필요. [준비 완료 기록](docs/CareerGround_External_Gate_Preparation_2026-10-03.md) |

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

계획 승인과 첫 로컬·GitHub CI PostgreSQL 검증, Auth0 웹 로그인, 개발용 ChatGPT/MCP의 CIMD·인가 코드 교환·인증 도구 호출 확인은 완료됐다. G-I의 남은 게이트는 PKCE S256 실요청, 두 실제 계정의 독립성, 기존 토큰 철회·만료 및 계정 삭제 후 즉시 차단, 비용·개인정보·운영 계약 검토다. 사용자는 합성 외부 검증을 승인했으나, 실제 공급자 선정·실사용자 데이터 사용·유료 과금·클라우드 운영 구축은 아직 승인된 결론이 아니다.

| 2026-10-02 | 권장1→2→3 승인에 따라 남은 Phase A MCP 이름2개를 source-bound MOCK_ONLY JD 후보/같은 연결의 브라우저 승인 후 합성 삭제로 연결해26tools를 제공했다. 한국어53개 오프라인 JD/R2 사례·R3 오류 분리, owner-only 영속 합성SQLite 실행기·logout/JWT철회·독립ledger 복원 격리를 준비했다. 다중탭승인 요청 혼동을 서명 context로 수정하고 신규schema 단일트랜잭션/CLI종료를 보강했다. 필수PG17.11 전체340pass/실패·skip0,0019/37tables0/schema일치, 실제Chrome·Firefox native200%4cases360checks, CI Ruff151files PASS. 빈 합성 개발store는 ignored로보존하고 서버·테스트PG/credentials는정리했다. 실제provider/운영과 CURRENT·포함선택·의미분석·R2/R3저장 등의 계약차이는 미완료이며 미커밋/미푸시다. [최신기록](docs/CareerGround_Phase_A_Contracts_Development_Runtime_2026-10-02.md) |

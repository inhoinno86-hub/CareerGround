# CareerGround 텍스트 MVP 통합 제안 v0.1

- 작성일: 2026-09-22
- 상태: **사용자 승인 완료 — 정식 정책·설계 문서로 분리**
- 승인일: 2026-09-22
- 범위: ① 텍스트 MVP 세부 정책, ② 기존 Career Graph/Profiling 설계 보완, ③ Plugin Functional Specification 초안
- 기준 정책: [CareerGround 제품 정책 제안 v0.1](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)의 `DECISION-P01`–`DECISION-P09`
- 비범위: 실제 서버 구현, DB migration, Interview Package JSON Schema, 음성 면접 Agent 상세 규칙, 배포 기술 선택

## 1. 결론과 이번에 검토할 제안

현재까지 합의한 정책만으로도 텍스트 MVP의 기능 계약을 설계할 수 있다. 다만 실제 API와 화면을 만들기 전에 아래 세부 규칙을 확정해야 한다.

| 제안 ID | 제안 | 권장 답변 |
| --- | --- | --- |
| PROPOSAL-T01 | 한 번에 검토할 경력 문장 수 | 프로젝트 한 건 안에서 최대 5개의 atomic Claim. 고위험 Claim은 각 항목을 별도 카드로 표시 |
| PROPOSAL-T02 | 검토 선택지와 결과 | `맞음 / 수정 / 더 확인 / 제외`. 제외할 때 `사실 아님`과 `사실이지만 사용 안 함`을 구분 |
| PROPOSAL-T03 | 재작성 문장의 재확인 범위 | 표기만 바뀌면 재확인 생략 가능, 의미 있는 재작성·번역은 산출물 문구 확인, 새 사실·범위 확대는 새 Claim 검토 |
| PROPOSAL-T04 | 모순 및 사용 금지 경계 해제 | 영향받은 Claim만 차단. 해제는 이력서 승인과 분리된 별도 검토와 새 프로필 버전 필요 |
| PROPOSAL-T05 | 프로파일링 세션 수명 | 명시적 시작, 30분 비활동 시 자동 일시정지, 90일 안에 재개 가능. 완료·포기·만료를 구분 |
| PROPOSAL-D01 | 기존 v1 설계 보완 방식 | 검증된 v1 문서를 바로 덮어쓰지 않고, 승인 후 v1.1 addendum과 별도 검증을 작성 |
| PROPOSAL-D02 | 임시 대화와 검토 데이터 | canonical Career Graph 밖에 profiling workspace를 두고 승인 시에만 한 transaction으로 승격 |
| PROPOSAL-D03 | 삭제와 과거 버전 | 개인정보 본문은 삭제하고, 해당 버전이 삭제로 복원 불가하다는 비식별 tombstone만 유지 |
| PROPOSAL-F01 | 플러그인 형태 | Workflow Skill + 인증된 MCP server + Claim 검토용 선택 UI |
| PROPOSAL-F02 | 외부 도구 이름 | MCP에는 `start_profiling` 같은 snake_case 동사를 사용. 내부 서비스 명칭은 별도로 둘 수 있음 |
| PROPOSAL-F03 | 도구 분리 | 조회, 초안, 최종 승인, 영구 삭제를 서로 다른 도구로 분리 |

`PROPOSAL-T01`–`T05`, `PROPOSAL-D01`–`D03`, `PROPOSAL-F01`–`F03`은 2026-09-22 사용자 검토를 거쳐 모두 채택했다. 이후 변경은 기존 결정을 지우지 않고 새 결정 기록으로 관리한다.

정식 반영 문서:

- [제품 정책 제안 v0.1 결정 기록](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md#7-검토와-결정-기록)
- [Career Graph Schema v1.1 Policy Addendum](career_graph_schema_v1_1_policy_addendum.md)
- [Plugin Functional Specification v1](plugin_functional_spec_v1.md)

---

# Part 1. 텍스트 MVP 세부 정책 제안

## 2. 경력 문장 검토 단위

### 제안

한 번의 검토 묶음은 **하나의 프로젝트 또는 하나의 명확한 경험 범위**로 제한한다. 화면에는 최대 5개의 atomic Claim을 보여준다. 5개를 넘으면 다음 묶음으로 나눈다.

각 Claim은 독립적으로 참·거짓과 범위를 판단할 수 있어야 한다. 예를 들어 다음 문장은 네 항목으로 나눈다.

```text
원문:
“아키텍처를 설계하고 제어 로직을 구현했으며 SIL/HIL 검증도 했습니다.”

검토 항목:
1. [특정 기능] 아키텍처를 설계했다.
2. [특정 제어 로직]을 직접 구현했다.
3. [특정 대상]의 SIL 검증을 수행했다.
4. [특정 대상]의 HIL 검증을 수행했다.
```

고위험 Claim은 같은 묶음에 포함할 수 있지만 각 항목을 독립된 카드와 선택지로 표시한다.

- 프로젝트·시스템·아키텍처 ownership
- 팀 리더십과 최종 결정권
- 양산·출시·안전 승인 책임
- 정량 성과, 비용 절감, 매출
- 특허·논문

### 권장 이유

문장 하나씩 매번 확인하면 대화가 끊기고, 너무 많은 문장을 한 번에 확인하면 범위 차이를 놓치기 쉽다. 프로젝트 단위 최대 5개는 대화 흐름과 정확한 검토 사이의 초기 기본값으로 적당하다. 실제 사용자 테스트에서 조정할 수 있다.

### 저장 규칙

- 묶음 전체를 한 번에 제출하더라도 각 Claim마다 별도의 결정 기록을 남긴다.
- 결정하지 않은 항목은 승인된 것으로 간주하지 않는다.
- 한 번의 제출에서 승인된 항목들은 하나의 `ProfileChangeSet`과 하나의 새 profile version으로 반영할 수 있다.
- 수정된 항목은 원래 문장을 승인하지 않는다. 수정본을 새 검토 항목으로 만든다.

## 3. 검토 선택지와 정확한 의미

### 제안

사용자에게 보이는 기본 선택지는 네 가지로 유지한다.

| 선택 | 처리 | canonical 반영 |
| --- | --- | --- |
| 맞음 | 표시된 문구·범위·근거를 본인이 확인 | 나머지 게시 조건을 통과하면 새 버전에 반영 |
| 수정 | 사용자가 수정하거나 추가 질문을 요청 | 수정본은 새 draft. 원래 항목은 승인하지 않음 |
| 더 확인 | 답변·근거·범위가 부족 | workspace에서 `NEEDS_FOLLOWUP`, canonical 변화 없음 |
| 제외 | 아래 두 이유 중 하나를 선택 | 이유에 따라 다르게 처리 |

`제외`는 한 번 더 이유를 구분한다.

| 제외 이유 | 의미 | 권장 처리 |
| --- | --- | --- |
| 사실이 아님 | 해당 proposition을 거절 | 정확한 문구·범위의 부정 경계 후보를 만들고 사용자 결정 제출 시 `DO_NOT_CLAIM` constraint로 보존 |
| 사실이지만 사용 안 함 | 사실성 판단과 별개로 산출물에서 금지 | Claim 또는 범위에 `DO_NOT_CLAIM` constraint로 보존 |

“맞음”은 다음 네 요소에 묶인다.

1. 정확한 Claim 문구
2. 적용되는 역할·프로젝트·작업 범위
3. 연결된 Evidence 항목
4. 검토 대상 profile version

하나가 실질적으로 바뀌면 기존 확인을 새 대상에 자동 적용하지 않는다.

## 4. 재작성·번역·이력서 문구 검토

### 제안

재작성은 세 등급으로 다룬다.

| 등급 | 예 | 처리 |
| --- | --- | --- |
| R1 표기 변화 | 맞춤법, 구두점, 날짜 표시 형식, 공백 | 의미·범위가 동일하다는 검사 통과 시 Claim 재확인 불필요. 산출물 미리보기 제공 |
| R2 의미 보존 재작성 | 문장 간결화, 능동태 전환, 번역, 여러 atomic Claim의 문장 조합 | 원래 Claim과 나란히 보여주고 **산출물 문구**를 사용자에게 확인받음 |
| R3 사실 또는 범위 변화 | 새 수치·기술·기간·성과 인과관계·ownership·결정권 추가 | 재작성으로 처리하지 않고 새 Claim 후보로 프로파일링 |

R1 자동 판정에 확신이 없으면 R2로 올린다. R2 확인은 원래 Career Claim의 진실성을 다시 확인하는 절차가 아니라, **그 Claim을 표현한 이력서 문구가 허용 범위 안인지 확인하는 절차**다.

R2 문구가 확인돼도 다음 조건이 생기면 다시 검토한다.

- 연결 Claim 또는 Evidence가 변경·삭제됨
- 새로운 모순이나 `DO_NOT_CLAIM` 경계가 생김
- 번역·재작성 결과가 이전 확인 문구와 실질적으로 달라짐
- 다른 JD에 맞추면서 책임·성과 강조 범위가 달라짐

MVP는 R1/R2를 완벽하게 자동 분류한다고 주장하지 않는다. 애매하면 R2 검토 화면을 제공하고, 경계 검사가 실패하면 원래 확인된 atomic 문구로 되돌린다.

## 5. 모순과 사용 금지 경계

### 제안

모순은 프로필 전체를 멈추지 않고 **영향받은 Claim과 그 파생 문장만** 게시·내보내기에서 차단한다. 다른 프로젝트와 Claim은 계속 사용할 수 있다.

모순 해결은 다음 순서로 진행한다.

1. 서로 충돌하는 문구와 각각의 근거를 함께 보여준다.
2. 사용자가 `기존 내용 유지 / 새 내용으로 정정 / 둘 다 불확실 / 서로 다른 범위라 둘 다 유지` 중 선택한다.
3. 필요한 범위·결정권·시점 질문을 추가한다.
4. 새 assessment와 review를 append한다.
5. 해결된 경우에만 새 profile version에서 사용 가능 여부를 다시 계산한다.

기존 반대 Evidence와 과거 review는 일반 정정 과정에서 삭제하지 않는다. 사용자가 개인정보를 영구 삭제한 경우에는 삭제 정책이 우선한다.

`DO_NOT_CLAIM` 해제는 이력서 문구 승인으로 처리하지 않는다. 별도의 `review_boundary_change` 작업에서 아래 내용을 보여주고 확인받는다.

- 해제 대상 Claim 또는 범위
- 기존 금지 이유와 근거
- 새로 추가되거나 정정된 근거
- 해제 후 허용되는 정확한 표현
- 여전히 금지되는 확대 표현

해제는 새 `ProfileChangeSet`과 profile version을 만든다. 모순이 남아 있거나 새 근거가 단지 같은 주장을 반복한 것뿐이면 해제하지 않는다.

## 6. 프로파일링 세션의 시작·중단·완료

### 제안 상태 모델

```text
ACTIVE
  ├─ 사용자가 일시정지 / 30분 비활동 ──► PAUSED
  ├─ 검토 묶음 생성 ───────────────────► AWAITING_REVIEW
  ├─ 종료 guard 통과 ──────────────────► COMPLETED
  └─ 사용자가 포기 ────────────────────► ABANDONED

PAUSED / AWAITING_REVIEW
  ├─ 90일 안에 명시적 재개 ───────────► ACTIVE
  └─ retention 만료 ───────────────────► EXPIRED
```

### 시작

사용자가 경력 정리 의도를 명시하고 `start_profiling`이 호출될 때 시작한다. 시작 결과에는 다음을 보여준다.

- 새 `profiling_session_id`
- 기준 `profile_version`
- 수집 범위: 이 작업을 위해 명시적으로 전달된 대화와 자료
- 전체 프로파일링 대화의 90일 보관 기준
- 중단·재개·삭제 방법

플러그인 설치, 로그인, 일반 채팅만으로는 세션을 만들지 않는다.

### 입력 수집

`add_profiling_input`으로 명시적으로 전달된 task-specific 발언과 자료만 기록한다. 전체 채팅 기록이나 다른 대화방을 요청하지 않는다. CareerGround가 생성한 관련 질문과 요약은 세션 문맥으로 함께 저장할 수 있다.

### 일시정지와 재개

- 사용자가 요청하면 즉시 `PAUSED`로 바꾼다.
- 30분 동안 CareerGround 입력이 없으면 자원·동시성 관리를 위해 자동 `PAUSED`로 바꾼다.
- 자동 일시정지는 삭제나 검토 승인을 의미하지 않는다.
- 같은 세션에 실제 CareerGround 입력이 들어온 경우에만 `last_activity_at`과 90일 만료 기준을 갱신한다.
- 일반 채팅, 로그인, 다른 세션 사용은 이 세션의 보관기간을 연장하지 않는다.
- 재개할 때 profile version이 달라졌다면 변경 내용을 보여주고 stale draft·approval을 다시 검토한다.

### 완료·포기·만료

- `COMPLETED`: 해당 경험이 Profiling Protocol 종료 guard를 통과함. 모든 Claim이 게시 가능하다는 뜻은 아님.
- `ABANDONED`: 사용자가 작업을 포기함. 승인되지 않은 draft는 canonical profile에 반영되지 않음.
- `EXPIRED`: 마지막 실제 활동 후 90일이 지나 임시 대화와 draft가 삭제됨.
- 완료·포기 후에도 사용자가 선택해 canonical Evidence로 저장한 발췌는 별도 보관 정책을 따른다.

---

# Part 2. 기존 설계 보완 제안

## 7. 보완 원칙

기존 Schema v1과 20개 참조 테스트는 당시 정의된 불변 snapshot·후보 승격 규칙을 검증했다. 정책을 반영할 때 기존 문서를 곧바로 수정하면 검증 보고서가 더 이상 같은 계약을 설명하지 못한다.

따라서 다음 순서를 권장한다.

1. 이 통합 제안의 정책을 사용자와 확정한다.
2. `career_graph_schema_v1_1_policy_addendum.md`를 작성한다.
3. 기존 v1 원칙 중 유지·변경·폐기되는 규칙을 표로 명시한다.
4. 새 fixture와 테스트로 보완 규칙을 검증한다.
5. 검증 후 Plugin Functional Specification을 `v1`로 승격한다.

기존 v1 fixture와 테스트는 회귀 기준으로 유지한다. 개인정보 영구 삭제 사례처럼 정책상 달라진 부분은 별도 v1.1 테스트로 추가한다.

## 8. 임시 profiling workspace

### 권장 데이터 경계

```text
ChatGPT/Codex conversation
  │ 사용자가 CareerGround 작업에 명시적으로 전달한 입력만
  ▼
Profiling Workspace (90일 임시 데이터)
  ├─ session 상태
  ├─ 관련 질문과 사용자 입력
  ├─ draft Claim / Evidence 후보
  ├─ 미해결 guard / 모순
  └─ review batch
          │ 정확한 사용자 결정
          ▼
Canonical Career Graph (새 profile version)
```

ChatGPT의 전체 대화 저장 정책과 CareerGround 서버의 저장 정책은 별도다. CareerGround 서버는 MCP tool input으로 전달받은 범위만 자신의 처리 기록으로 관리한다.

### 추가할 최소 저장 구조

아래 이름은 제안이며 승인 후 SQL로 구체화한다.

| 구조 | 목적 | canonical 여부 |
| --- | --- | --- |
| `profiling_sessions` | 상태, 기준 profile version, protocol state, 시작·마지막 활동·만료 시점 | 임시 workspace |
| `profiling_messages` | CareerGround에 전달된 사용자 입력과 그에 대응한 관련 질문 | 임시 workspace |
| `profiling_drafts` | draft Claim, Evidence 발췌, scope, guard, 모순 | 임시 workspace |
| `profiling_review_batches` | 검토 묶음, base profile version, 생성 시점·만료 | 임시 workspace |
| `profiling_review_items` | exact text/scope/evidence set와 사용자 결정 | 승인 전 임시, 승격 후 review 근거 |

`profiling_messages`에는 전체 ChatGPT conversation을 복제하지 않는다. 각 row는 다음을 식별해야 한다.

- `profiling_session_id`
- 세션 안의 순서
- `USER` 또는 `ASSISTANT`
- CareerGround 작업을 위해 전달·생성된 내용
- 원본 content hash와 선택적 client-side locator
- `created_at`, `last_activity_at`, `expires_at`
- 민감정보 가림 또는 삭제 상태

## 9. 승인과 canonical 승격

### 검토 대상 고정

`profiling_review_items`는 아래 값의 digest를 보관한다.

```text
canonical_text
claim_type
context and ownership scope
evidence candidate IDs and content hashes
constraint IDs and relevant boundary text
base_profile_version
```

사용자 결정은 이 digest에 묶인다. 서버가 받은 내용과 사용자가 본 내용이 다르면 승격을 거부한다.

### 승격 transaction

한 review batch를 제출할 때 승인된 각 항목에 대해 다음을 한 transaction으로 실행한다.

```text
lock profile and review batch
verify user/account ownership
verify review digest and base profile version
verify each explicit decision
re-run contradiction, boundary and publication guards
create/attach EvidenceSource and EvidenceItem
create Claim/context/ownership records as needed
create EvidenceClaimLink
append ClaimAssessment and ClaimReview
create ProfileChangeSet
increment profile version once
mark promoted review items
commit
```

검증 실패 시 canonical 변경을 모두 rollback한다. 같은 승인 token을 다시 보내면 기존 결과를 반환하고 버전을 다시 증가시키지 않는다.

### 기존 테이블 보완

`claim_reviews`에는 최소한 다음 연결이 필요하다.

- 어떤 `profiling_review_item`에서 왔는지
- 사용자가 본 review digest
- review 대상의 base profile version
- review 목적: `FACT_CONFIRMATION`, `ARTIFACT_WORDING`, `BOUNDARY_CHANGE`, `EVIDENCE_ACCEPTANCE`

기존 `review_action`, `reviewer_type`, `reviewer_id`, `profile_version`, `reviewed_at`은 유지한다. 새 목적 구분이 기존 enum인지 별도 field인지는 v1.1 addendum에서 결정한다.

## 10. 보관·삭제·과거 버전 보완

### 보관 시점

`profiling_sessions.expires_at`은 마지막 CareerGround 관련 입력으로 계산한다. 일반 채팅이나 다른 세션 활동은 갱신하지 않는다. 만료 작업은 다음을 삭제한다.

- profiling messages
- 승인되지 않은 draft와 review batch
- 임시 파일·추출물·검색 색인·cache

이미 canonical Evidence로 선택·승격된 발췌는 별도 보관 정책을 따른다.

### 삭제 요청

삭제는 최소 두 단계로 분리한다.

1. `preview_data_deletion`: 영향받는 Evidence, Claim, artifact, snapshot, package를 계산한다.
2. `execute_data_deletion`: preview digest와 사용자 재확인을 검증한 뒤 삭제를 시작한다.

삭제가 시작되면 대상은 즉시 읽기·생성·내보내기에서 격리한다. 이후 원본 저장소, DB, object storage, snapshot, cache, embedding, queue, 파생 artifact를 처리한다.

### snapshot 정책 변경

기존 “완전한 불변 snapshot을 보존” 규칙에는 다음 개인정보 삭제 예외를 추가한다.

```text
정상 정정:
  과거 snapshot 유지

사용자 영구 삭제:
  개인정보 payload 삭제
  복원 불가 상태와 최소 비식별 tombstone만 유지
```

권장 `profile_version_archives` registry:

| field | 의미 |
| --- | --- |
| `profile_id`, `profile_version` | 원래 버전 식별자 |
| `availability_status` | `AVAILABLE`, `ERASURE_PENDING`, `ERASED` |
| `storage_ref`, `content_hash` | AVAILABLE일 때만 유효 |
| `erased_at`, `erasure_request_id` | 삭제 추적. 원문이나 재구성 가능한 값은 포함하지 않음 |

영향받은 artifact는 `UNAVAILABLE_DUE_TO_ERASURE`로 표시하고 해당 버전의 최신 snapshot으로 대체하지 않는다. Interview Package는 revoke한다. 사용자가 이미 다운로드하거나 외부에 전송한 파일은 회수됐다고 표시하지 않는다.

### 추가 검증 사례

1. 다른 대화방의 내용은 profiling workspace에 나타나지 않는다.
2. 5개 Claim review batch에서 3개 승인·1개 수정·1개 보류 시 승인 3개만 한 version에 반영된다.
3. R2 재작성 승인으로 R3 ownership 확대를 통과시킬 수 없다.
4. stale base profile version의 승격은 거부되고 재검토가 필요하다.
5. 같은 approval token 재전송은 새 버전을 만들지 않는다.
6. 만료 세션의 임시 대화는 삭제되지만 선택·승격된 Evidence는 정책에 따라 유지된다.
7. 영구 삭제 후 해당 snapshot은 `ERASED`이며 복원 시 명시적으로 실패한다.
8. 삭제 전 backup을 복구해도 erasure ledger 적용 후에만 서비스가 열린다.

---

# Part 3. Plugin Functional Specification 초안

## 11. 권장 플러그인 구성

```text
CareerGround Plugin
  ├─ Workflow Skill
  │    └─ profiling 질문 순서, 경계 확인, 도구 사용 순서
  └─ Authenticated MCP Server
       ├─ read/write tools
       ├─ Career Core service
       └─ optional Claim Review UI
```

CareerGround는 계정별 비공개 데이터를 읽고 canonical profile을 변경하므로 MCP server가 필요하다. UI는 모든 기능에 필요하지 않지만, 여러 Claim을 비교·수정·확인하는 검토 화면에는 권장한다. 도구는 UI가 없어도 동일한 계약으로 작동해야 한다.

OpenAI 공식 문서도 서비스 연결·인증·controlled action이 필요한 플러그인에 MCP server를 사용하고, 비교·편집·확인에 UI가 유용하다고 안내한다. 또한 읽기와 쓰기, 권한·위험·확인 요건이 다른 작업은 분리하도록 권장한다.

## 12. 명명과 외부 계약 원칙

기존 개발 계획의 `profile.start`, `evidence.confirm`은 개념 기능명으로 유지할 수 있다. MCP 외부 tool name은 안정적인 snake_case 동사로 제안한다.

```text
개념 기능                    MCP tool
profile.start               start_profiling
profile.update              add_profiling_input / submit_claim_review
evidence.confirm            submit_claim_review
career_graph.get            get_career_profile
jd.analyze                  analyze_jd
resume.generate             generate_resume_draft
interview_plan.generate     create_interview_plan
interview_package.create    create_interview_package
```

하나의 `profile.update` 도구에 입력 수집과 canonical 승인을 함께 넣지 않는다. 권한·부작용·확인 수준이 다르기 때문이다.

## 13. 공통 계약

### 인증과 권한

- 개인 데이터에 접근하는 모든 MVP tool은 OAuth가 필요하다.
- 서버는 각 요청의 access token을 검증하고 token에서 user/account를 해석한다.
- 입력된 `profile_id`, `session_id`, `artifact_id`가 해당 계정 소유인지 서버가 확인한다.
- 모델의 설명이나 ID 추측을 권한 근거로 사용하지 않는다.
- 여러 계정을 지원할 때는 인증된 read-only account profile tool을 별도로 둘 수 있다.

### 공통 성공 응답

```json
{
  "status": "ok",
  "data": {},
  "next_actions": [],
  "user_message": "사용자에게 보여줄 간단한 설명"
}
```

`data`에는 후속 호출에 필요한 안정적인 ID와 버전을 포함한다. access token, 내부 stack trace, DB key, 불필요한 원문·개인정보는 반환하지 않는다.

### 공통 오류

| code | 의미 | 기본 처리 |
| --- | --- | --- |
| `AUTH_REQUIRED` | 로그인·token 필요 | 인증 흐름 안내 |
| `FORBIDDEN` | 다른 계정 또는 권한 부족 | 정보 존재 여부를 과도하게 노출하지 않고 거부 |
| `NOT_FOUND` | 대상 없음 | ID 재확인 |
| `VALIDATION_FAILED` | 입력 schema·범위 오류 | 수정 가능한 field 오류 반환 |
| `VERSION_CONFLICT` | base profile version이 최신과 다름 | 최신 차이를 읽고 재검토 |
| `REVIEW_REQUIRED` | 사용자 확인 필요 | review batch/UI 표시 |
| `BOUNDARY_BLOCKED` | 금지 범위 위반 | 관련 constraint와 허용 대안 제시 |
| `CONTRADICTION_BLOCKED` | 미해결 모순 | 영향받은 Claim과 follow-up 표시 |
| `SESSION_EXPIRED` | 임시 세션 보관기간 만료 | 새 세션 시작. 삭제된 대화 복원 약속 금지 |
| `DELETION_IN_PROGRESS` | 삭제 격리 또는 처리 중 | 읽기·생성 중단, 상태 안내 |
| `RATE_LIMITED` | 사용량 제한 | 재시도 가능 시점 안내 |
| `INTERNAL_ERROR` | 내부 실패 | 확인된 기존 데이터 유지, 추적용 비민감 오류 코드만 반환 |

최신 버전 조회 실패 시 임의로 오래된 버전이나 부분 데이터를 성공 응답으로 반환하지 않는다.

## 14. MVP 도구 목록

### 프로파일링과 검토

| Tool | 목적 | 상태 변경 | 사용자 확인 | MCP annotation 제안 |
| --- | --- | --- | --- | --- |
| `start_profiling` | 명시적 CareerGround 경력 정리 세션 시작 | 임시 session 생성 | 시작 의도 필요 | `readOnly=false`, `destructive=false`, `openWorld=false` |
| `add_profiling_input` | task-specific 발언·자료를 현재 세션에 추가 | 임시 message/draft 변경 | 세션 안의 명시 입력 | `readOnly=false`, `destructive=false`, `openWorld=false` |
| `get_profiling_session` | 현재 state, 질문, draft, 만료 시점 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `pause_profiling` | 임시 세션 일시정지 | session 상태 변경 | 사용자 요청 또는 정책상 자동 pause | `readOnly=false`, `destructive=false` |
| `prepare_claim_review` | 최대 5개 검토 묶음 생성 | 임시 review batch 생성 | 없음, 아직 canonical 변경 없음 | `readOnly=false`, `destructive=false` |
| `get_claim_review` | 검토 문구·근거·경계 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `submit_claim_review` | 항목별 결정을 canonical graph에 반영 | profile version 변경 | exact review digest에 대한 명시 확인 | `readOnly=false`, `destructive=false` |
| `resolve_claim_conflict` | 충돌하는 문구·근거를 검토해 모순 상태 갱신 | profile version 변경 | 충돌별 명시 확인 | `readOnly=false`, `destructive=false` |
| `review_boundary_change` | `DO_NOT_CLAIM` 경계 추가·수정·해제 | profile version 변경 | 별도 명시 확인 | `readOnly=false`, `destructive=false` |

### Career Graph와 근거

| Tool | 목적 | 상태 변경 | 사용자 확인 | annotation 제안 |
| --- | --- | --- | --- | --- |
| `get_career_profile` | stable profile projection 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `get_claim_evidence` | Claim→Evidence→source와 경계 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `export_profile_data` | 본인용 구조화 데이터 export 준비 | export artifact 생성 가능 | export 요청 | `readOnly=false`, `destructive=false` |

### JD와 Resume

| Tool | 목적 | 상태 변경 | 사용자 확인 | annotation 제안 |
| --- | --- | --- | --- | --- |
| `analyze_jd` | 사용자가 붙여 넣은 JD를 요구사항으로 분해하고 Claim과 매핑 | JD/mapping draft 저장 | 명시적 JD 입력 | `readOnly=false`, `destructive=false`, `openWorld=false` |
| `get_jd_analysis` | 요구사항별 match·gap·근거 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `generate_resume_draft` | 허용 Claim으로 traceable resume draft 생성 | DRAFT artifact 생성 | 생성 요청 | `readOnly=false`, `destructive=false` |
| `get_resume_trace` | 각 문장→Claim→Evidence와 constraint 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `submit_resume_wording_review` | R2 문구 검토 결과 저장 | artifact version 변경 | 정확한 문구 확인 | `readOnly=false`, `destructive=false` |
| `export_resume` | 검사를 다시 수행하고 파일 export | export artifact 생성 | 형식·버전 선택 | `readOnly=false`, `destructive=false` |

JD URL 가져오기는 pasted text 분석과 분리해 향후 `fetch_jd_url` 같은 `openWorld=true` 도구로 추가한다. MVP에서는 사용자가 붙여 넣은 JD text만 처리하는 편을 권장한다.

### 삭제와 보관

| Tool | 목적 | 상태 변경 | 사용자 확인 | annotation 제안 |
| --- | --- | --- | --- | --- |
| `preview_data_deletion` | 삭제 범위와 영향 계산 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |
| `execute_data_deletion` | preview에 묶인 범위 영구 삭제 시작 | 복원 어려운 변경 | exact preview digest 재확인 | `readOnly=false`, `destructive=true` |
| `get_deletion_status` | 격리·삭제·백업 처리 상태 조회 | 없음 | 없음 | `readOnly=true`, `openWorld=false` |

### 후속 단계 도구

| Tool | 현재 상태 | 선행 조건 |
| --- | --- | --- |
| `create_interview_plan` | 기능 계약 개요만 정의 가능 | 질문 plan schema 확정 |
| `create_interview_package` | 이번 MVP 명세에서 deferred | Interview Package Schema, 서명·키·만료·취소 정책 확정 |

텍스트 MVP는 `create_interview_package` 직전까지 독립 검증할 수 있다. 기존 8단계 MVP 목표를 완성하려면 다음 단계에서 Package Schema를 확정한 후 이 도구를 활성화한다.

## 15. 핵심 도구 상세 계약

### `start_profiling`

**사용 시점:** 사용자가 CareerGround로 새 경력 또는 기존 경력 보완을 명시적으로 요청했을 때.

입력 제안:

```json
{
  "profile_id": "uuid",
  "goal": "ADD_EXPERIENCE",
  "experience_hint": "optional short task-specific text",
  "policy_version": "product-policy-v0.1"
}
```

출력 제안:

```json
{
  "profiling_session_id": "uuid",
  "status": "ACTIVE",
  "base_profile_version": 12,
  "protocol_state": "CONTEXT_DISCOVERY",
  "retention_expires_at": "timestamp",
  "collection_scope": "Only content explicitly sent to this CareerGround session",
  "next_question": "..."
}
```

서버는 이미 진행 중인 세션이 있으면 새 세션을 조용히 만들지 않고 재개 또는 새 세션 선택지를 반환한다.

### `add_profiling_input`

**사용 시점:** 현재 CareerGround 세션 질문에 대한 답변이나 사용자가 선택한 과거 발췌를 전달할 때.

입력 제안:

```json
{
  "profiling_session_id": "uuid",
  "base_profile_version": 12,
  "content": "사용자가 이 작업에 전달한 내용",
  "content_kind": "USER_STATEMENT",
  "client_locator": {"conversation_ref": "optional", "message_ref": "optional"}
}
```

`content_kind`는 `USER_STATEMENT`, `SELECTED_CHAT_EXCERPT`, `PASTED_DOCUMENT_EXCERPT`, `CORRECTION`부터 시작한다. raw full-chat 배열은 받지 않는다.

출력에는 새 protocol state, 다음 질문, 만들어진 draft 수, 현재 미해결 guard를 포함한다. canonical Claim ID를 생성됐다고 표시하지 않는다.

### `prepare_claim_review`

입력은 session ID와 검토할 project/experience scope다. 출력은 최대 5개 항목의 정확한 문구·근거 발췌·ownership·금지 확대 표현·위험 표시와 `review_digest`를 포함한다.

```json
{
  "review_batch_id": "uuid",
  "base_profile_version": 12,
  "review_digest": "sha256:...",
  "expires_at": "timestamp",
  "items": [
    {
      "review_item_id": "uuid",
      "claim_text": "...",
      "claim_type": "CONTRIBUTION",
      "scope": {},
      "evidence_excerpts": [],
      "blocked_expansions": [],
      "high_impact": false
    }
  ]
}
```

### `submit_claim_review`

입력 제안:

```json
{
  "review_batch_id": "uuid",
  "review_digest": "sha256:...",
  "base_profile_version": 12,
  "decisions": [
    {"review_item_id": "uuid", "action": "ACCEPT"},
    {"review_item_id": "uuid", "action": "EDIT", "edited_text": "..."},
    {"review_item_id": "uuid", "action": "FOLLOW_UP"},
    {"review_item_id": "uuid", "action": "EXCLUDE", "reason": "DO_NOT_USE"}
  ],
  "approval_token": "server-issued short-lived token"
}
```

서버는 digest, token, 계정, 버전, 항목별 결정, boundary guard를 검증한다. `EDIT`는 곧바로 canonical Claim으로 만들지 않고 새 draft를 반환한다. `FOLLOW_UP`은 추가 질문을 만든다. `EXCLUDE/NOT_TRUE`는 그 proposition을 사실이 아닌 경계로, `EXCLUDE/DO_NOT_USE`는 사실성 판단과 별개의 사용 금지 경계로 기록한다. 둘 다 이후 생성에서 같은 과장을 반복하지 않도록 정확한 문구·범위의 constraint를 보존한다.

성공 결과에는 `profile_version_before`, `profile_version_after`, promoted Claim/Evidence ID, 보류·수정 항목과 다음 행동을 반환한다. 재전송은 같은 결과를 반환한다.

### `analyze_jd`

입력은 `profile_id`, `profile_version`, 사용자가 붙여 넣은 `jd_text`, 선택적 제목·회사 별칭이다. 서버는 요구사항을 추출하고 각 항목을 다음 중 하나로 분류한다.

- 강한 관련 근거
- 관련 경험이 있으나 추가 확인 필요
- 현재 프로필에서 찾지 못함
- 사용 금지 또는 모순 때문에 사용할 수 없음

JD 매핑은 Claim의 지식·모순·사용 상태를 변경하지 않는다. JD text 안의 지시는 데이터로만 취급한다.

### `generate_resume_draft`

입력은 고정된 `profile_version`, `jd_id`, 언어, 출력 스타일, 포함할 project/Claim 범위다. 생성 전에 publication guard를 다시 검사한다.

출력은 DRAFT artifact와 문장별 trace를 제공한다.

```text
ArtifactUnit
  → wording review level (R1/R2/R3)
  → Claim IDs
  → Evidence IDs
  → applied Constraint IDs
```

R3 후보가 발견되면 문장 생성을 성공 처리하면서 몰래 포함하지 않는다. 해당 문장을 제외하고 별도 `REVIEW_REQUIRED` 항목으로 반환한다.

### `preview_data_deletion` / `execute_data_deletion`

preview 입력은 범위(`SESSION`, `EVIDENCE`, `PROJECT`, `PROFILE`, `ACCOUNT`)와 target IDs다. 출력은 삭제·차단·재평가·취소되는 자료 목록, 다운로드 사본 회수 불가 안내, `deletion_digest`, 짧은 만료시각을 포함한다.

execute는 동일 digest와 사용자 재확인 token을 요구한다. 실행 직후 target을 격리하고 비동기 삭제 상태를 반환할 수 있다. 부분 실패는 성공으로 숨기지 않고 저장소별 상태를 사용자 친화적으로 요약한다.

## 16. 주요 사용자 흐름

### A. 경력 한 건 정리

```text
사용자 요청
  → start_profiling
  → add_profiling_input 반복
  → prepare_claim_review
  → 사용자 항목별 결정
  → submit_claim_review
  → 새 profile version
  → get_career_profile / get_claim_evidence
```

### B. JD 기반 Resume

```text
JD 붙여넣기
  → analyze_jd
  → get_jd_analysis
  → generate_resume_draft
  → get_resume_trace
  → R2 문구 검토
  → submit_resume_wording_review
  → export_resume
```

### C. 세션 중단과 재개

```text
pause 또는 30분 비활동
  → PAUSED
  → 90일 안에 get_profiling_session
  → profile version 비교
  → 같으면 resume
  → 다르면 변경 차이 검토 후 draft 재생성
```

### D. 일부 근거 삭제

```text
preview_data_deletion
  → 영향 범위 표시
  → 사용자 재확인
  → execute_data_deletion
  → 즉시 사용 격리
  → storage별 삭제
  → Claim 재평가 / artifact unavailable / package revoke
  → get_deletion_status
```

## 17. 수용 기준 제안

기능 명세가 정식 v1이 되려면 최소한 다음 계약을 테스트할 수 있어야 한다.

1. 설치·연결만으로 profiling session이나 대화 row가 생기지 않는다.
2. raw full-chat 입력 schema가 없고 task-specific 단일 입력만 허용한다.
3. 다른 계정의 session/profile/artifact ID 접근은 모든 도구에서 거부된다.
4. draft 생성만으로 canonical profile version이 바뀌지 않는다.
5. review digest나 base version이 다르면 승격되지 않는다.
6. 최대 5개 항목을 개별 결정하며 무응답 항목은 승인되지 않는다.
7. 수정 문구가 즉시 승인되지 않고 새 draft로 돌아간다.
8. R2 이력서 승인으로 ownership·성과·수치를 추가할 수 없다.
9. 미해결 모순과 `DO_NOT_CLAIM`은 관련 문장만 차단한다.
10. 승인 replay는 같은 결과를 반환하고 version을 다시 올리지 않는다.
11. JD relevance가 Claim status를 바꾸지 않는다.
12. Resume 문장마다 Claim과 Evidence 역추적이 가능하다.
13. 90일 만료는 해당 세션의 실제 CareerGround 활동만으로 계산된다.
14. 삭제 preview와 execute 사이에 대상이 바뀌면 실행을 거부하고 새 preview를 요구한다.
15. 영구 삭제 후 삭제된 snapshot을 최신 버전으로 대체해 복원하지 않는다.
16. 오류 시 기존 확인 데이터가 유지되고 부분 쓰기가 남지 않는다.

## 18. 승인 반영 현황과 다음 작업 순서

### 완료

1. 채택된 `PROPOSAL-*`을 제품 정책의 결정 기록에 추가했다.
2. `career_graph_schema_v1_1_policy_addendum.md`와 신규 검증 요구사항을 작성했다.
3. Part 3을 `plugin_functional_spec_v1.md`로 분리하고 도구별 계약을 정리했다.
4. `Interview Package Schema v1`과 서명·검증 fixture/test를 작성했다.
5. `Voice Interview Agent Specification v1`과 상태 전이 fixture/test를 작성했다.

### 다음 작업

1. MVP Architecture에서 OAuth, PostgreSQL, object storage, realtime voice, signing key, retention worker, deletion worker와 MCP 배포를 결정한다.
2. 구현 Epic/Story/Task와 수용 기준으로 분해한다.

## 19. 검토 근거

저장소 기준:

- [제품 정책 제안](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)
- [Career Graph Schema v1](career_graph_schema_v1.md)
- [Career Graph Entity/Relationship Model v1](career_graph_entity_relationship_model_v1.md)
- [Career Profiling Protocol v1](career_profiling_protocol_v1.md)
- [Schema Validation Report](career_graph_schema_v1_validation.md)

OpenAI 공식 문서 기준:

- [Plugin architecture](https://developers.openai.com/plugins/concepts/plugins): 인증된 서비스·controlled action에는 MCP server가 적합하고, 비교·편집·확인에는 선택 UI를 사용할 수 있다.
- [Define tools](https://developers.openai.com/plugins/plan/tools): 읽기와 쓰기, 권한·위험·확인 요건이 다른 작업을 분리하고 각 tool의 입력·출력·권한·부작용·오류 계약을 정의한다.
- [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server): 서버에서 매 요청의 인증·권한을 검사하고 tool annotation을 실제 동작에 맞춘다.
- [Authentication](https://developers.openai.com/plugins/build/auth): 인증된 MCP server는 OAuth 2.1 흐름과 서버 측 token 검증을 사용한다.
- [Plugin guidelines](https://developers.openai.com/plugins/app-guidelines): 전체 대화나 raw transcript를 ‘혹시 필요할 수 있으므로’ 요청하지 않고, 명시적으로 전달된 task-specific 입력만 처리한다.

이 공식 문서들은 CareerGround의 제품 보관기간이나 검토 UX 숫자를 정하지 않는다. 최대 5개 검토 항목, 30분 자동 일시정지, 90일 보관과 삭제 동작은 CareerGround 제품 제안이다.

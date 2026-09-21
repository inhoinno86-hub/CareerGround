# Career Profiling Protocol v1

- Date: 2026-09-21
- Status: domain protocol for synthetic validation; no agent/runtime implemented.
- Contract: [Schema v1](career_graph_schema_v1.md), [Entity/Relationship Model](career_graph_entity_relationship_model_v1.md).
- Evidence: [validation report](career_graph_schema_v1_validation.md).

## 1. Purpose and authority

사용자의 발화를 context, Responsibility, Contribution, Ownership, atomic Claim과
Evidence로 구체화한다. 입력은 사용자가 제공한 대화/자료와 읽기 전용 canonical
profile version이다. 출력은 검토 가능한 후보 묶음, 미확인 항목, 게시 경계,
명시적으로 승인된 변경이다. AI가 생성한 문장이나 이 문서의 예시는 실제 Evidence나
실제 사용자 승인이 아니다.

수집 중 답변, draft Claim, guard 결과는 임시 profiling workspace에 둔다.
아래 state는 protocol 상태이며 canonical entity/enum을 추가하지 않는다.
새 정보는 EvidenceCandidate로 격리한다. 최초 profiling도 미검토 draft를 사실로
저장하지 않는다. EvidenceSource는 원본 출처, EvidenceItem은 정확한 발화/문서
locator를 가진다. 사용자 확인은 외부 검증으로 자동 승격되지 않는다.

## 2. State machine

각 행의 출력은 승인 전 임시 자료다. 기본 전이는 표 순서이며 guard를 만족해야 한다.
각 항목에 첫 질문과 한 번의 구체화 질문까지 수행한다. 계속 답이 없으면 UNKNOWN과
이유를 남긴다. 선택 항목은 다음 상태로, 필수 경계는 일시 중지한다. 추가 응답을
원하면 같은 항목을 재개한다. 질문 예산은 무응답을 승인으로 보는 규칙이 아니다.

| State | 목적·진입 | 질문 유형/예 | 수집 field → entity | 출력·전이 guard → 다음 | 확인/UNKNOWN/충돌 처리 |
| --- | --- | --- | --- | --- | --- |
| CONTEXT_DISCOVERY | 시작/새 경험 | Context: 어느 조직·상황·기간인가? | Organization.name; Role.organization_id/start_date/end_date | 구별 가능한 context → ROLE_DISCOVERY | 비공개 별칭 허용; 날짜 null. context 불명은 중지 |
| ROLE_DISCOVERY | context 확보 | Context: 당시 역할은? | Role.title/role_type | role 식별 → PROJECT_DISCOVERY | 직급 추정 금지; 역할 불명 재질문 |
| PROJECT_DISCOVERY | role 확보 | Context: 어느 프로젝트의 어떤 기능인가? | Project.role_id/name/summary | 특정 범위 → RESPONSIBILITY_DISCOVERY | ACC 전체와 feature 구별; 불명은 중지 |
| RESPONSIBILITY_DISCOVERY | project 확정 | Responsibility: 공식 책임은? | Responsibility.statement/scope, role_id/project_id | 책임 답변 또는 UNKNOWN → CONTRIBUTION_DISCOVERY | 책임에서 직접 수행을 추론하지 않음 |
| CONTRIBUTION_DISCOVERY | 책임 질문 완료 | Contribution: 직접 수행한 작업은? | Contribution.contribution_type/action/object_text/summary | 수행 ≥1 → OWNERSHIP_PROBING | 팀 결과만 있으면 개인 작업 재질문 |
| OWNERSHIP_PROBING | 수행 확보 | Ownership/Decision Authority: owner/support/reviewer? 최종 결정자는? | Ownership.ownership_level/scope_type/scope_description/decision_authority/execution_responsibility/validation_responsibility | 작업별 경계·관련 결정권 → TECHNICAL_DEPTH_PROBING | 권한 UNKNOWN이면 관련 표현 보류; 충돌 follow-up, 최종 확인 필수 |
| TECHNICAL_DEPTH_PROBING | 경계 초안 | Implementation: 어느 부분을 직접 설계/구현했나? 선정 전/후인가? | Contribution; Claim.predicate/object_text | atomic 작업 분리 → VALIDATION_PROBING | 모호하면 CONTRIBUTION_DISCOVERY/OWNERSHIP_PROBING 복귀 |
| VALIDATION_PROBING | 기술 범위 확보 | Validation: SIL/HIL/현장 중 무엇을 직접 했나? 승인자는? | ValidationActivity.validation_type/statement/environment; Ownership.validation_responsibility | 방법별 수행/책임 또는 UNKNOWN → OUTCOME_PROBING | 시험 수행에서 safety/최종 승인권 추론 금지 |
| OUTCOME_PROBING | 검증 질문 완료 | Outcome: 결과와 수치 근거는? | Outcome.statement/metric_value/metric_unit/metric_status | 결과 또는 미확인 → EVIDENCE_CAPTURE | 무근거 metric null/UNCONFIRMED; 정량 Claim 별도 확인 |
| EVIDENCE_CAPTURE | 작업 초안 존재 | Context/Validation: 어느 발화/자료에서 확인하나? | EvidenceSource.source_type/title; EvidenceItem.source_id/content_text/locator | 출처 ≥1, 게시 후보별 SUPPORTS → CLAIM_DRAFTING | AI 초안만 있으면 근거 없음; 출처 없음 중지 |
| CLAIM_DRAFTING | 출처·경계 연결 | Contribution/Boundary: 한 사실씩 제시 | Claim.canonical_text/contexts/importance; ClaimAssessment 3축; EvidenceClaimLink.relation_type | 각각 독립 확인 가능 → CLAIM_CONFIRMATION | USER_CLAIMED/INFERRED로 시작; compound 분리 |
| CLAIM_CONFIRMATION | atomic 후보 준비 | Ownership/Outcome: 정확히 이 문장과 범위가 맞나? | ClaimReview.review_action/reviewer_type/notes; ClaimAssessment.knowledge_status | high-impact별 명시 review disposition → BOUNDARY_CHECK | 수정은 draft로; 거절은 게시 제외; 무응답은 미확인 |
| BOUNDARY_CHECK | review disposition 확보 | Boundary: 본인이 했다고 말하면 안 되는 부분은? 타인의 담당/결정은? | ClaimConstraint.constraint_type/text/targets; ClaimAssessment.usage_policy/consistency_status | §7 종료 guard 충족 → COMPLETE | 경계 불명은 OWNERSHIP_PROBING; 모순은 §6; 임의 해소 금지 |
| COMPLETE | 모든 종료 guard 통과 | 누락·게시 제한 안내 | 완료 요약, 적용 profile_version | 수집 종료; 새 경험은 관련 state 재진입 | COMPLETE와 ALLOWED 독립; 승인 없는 canonical 쓰기 없음 |

9가지 질문 유형은 Context, Responsibility, Contribution, Ownership, Decision Authority,
Implementation, Validation, Outcome, Boundary다. 답변 변경으로 guard가 깨지면 해당
state부터 재확인한다. Pause 시 input profile_version, state, 답변/출처, 미해결 guard를
workspace에 보존한다. 재개 때 canonical version이 달라졌으면 차이를 검토하고
stale approval을 재사용하지 않는다. 사용자의 중단 요청은 즉시 반영한다.

## 3. No Silent Inference: “I developed ACC.”

이 발화에서 알려진 것은 ACC 개발 참여를 사용자가 주장했다는 것뿐이다.
직접 구현, architecture ownership, 검증, 결정권, 회사/기간/성과는 UNKNOWN이다.

1. “어떤 조직/역할에서 어느 ACC 기능인가요?” → context/role/project.
2. “직접 작성하거나 설계한 부분은?” → Contribution.
3. “담당 범위와 최종 결정자는?” → Ownership와 decision_authority.
4. “어떤 검증을 직접 했고 누가 승인했나요?” → ValidationActivity.
5. “성과/출처와 말하면 안 되는 범위는?” → Evidence/Outcome/Constraint.
6. 각 atomic 문장과 범위를 다시 확인한다. 무응답 필드는 UNKNOWN/null로 유지한다.

Synthetic 답변 “I implemented ACC target-speed logic.”는 해당 구현 Claim 후보만
만든다. architecture 소유권이나 vehicle validation을 덧붙이지 않는다. 확인 전
USER_CLAIMED, 명시 확인 후 USER_CONFIRMED다.

## 4. Atomic Claims and independent evidence

Synthetic 답변: “I designed the architecture, implemented the control logic, and performed SIL/HIL tests.”

| atomic draft | 구체화 | Evidence link | 독립 경계 |
| --- | --- | --- | --- |
| Designed [specific feature architecture]. | 어떤 feature/설계 범위 | architecture 발화 구간 SUPPORTS | feature 설계만; system owner 아님 |
| Implemented [specific control logic]. | 어떤 logic/직접 수행 | logic 구간 SUPPORTS | implementation만; 기술 선정권 아님 |
| Performed SIL validation. | 대상/방법/직접 수행 | SIL 구간 SUPPORTS | SIL 수행만; HIL/승인과 분리 |
| Performed HIL validation. | 대상/방법/직접 수행 | HIL 구간 SUPPORTS | HIL 수행만; production safety 아님 |

하나의 EvidenceItem이 여러 Claim을 뒷받침할 수 있지만 link/review는 각각 갖는다.
한 작업만 지지하는 근거를 다른 Claim에 복사하지 않는다. QUALIFIES는 범위 한정,
CONTEXTUALIZES는 배경, CONTRADICTS는 반대 근거이며 SUPPORTS 요구를 대체하지 않는다.

## 5. Confirmation and promotion

명시 확인을 요구하는 high-impact 범주:

- Project ownership, team leadership, architectural ownership, technical decision ownership.
- Production launch responsibility.
- Quantitative performance improvement, cost saving, revenue, safety achievement.
- Patents and publications.

정확한 문장/scope/출처/금지 범위를 제시한다. USER_ACCEPTED review는 USER reviewer,
claim_id, profile_version, notes의 확인 문장/출처를 갖는다. AI confidence와 무응답은
대체 불가다. proposition을 바꾸는 편집은 새 후보/Claim으로 검토한다.

게시 guard는 USER_CONFIRMED 또는 정책상 허용된 EXTERNALLY_VERIFIED,
CONSISTENT, ALLOWED, 적격 SUPPORTS, 유효한 명시 review와 constraint 준수의 교집합이다.
외부 검증 정책은 미정이므로 참조 검증은 EXTERNALLY_VERIFIED를 승인하지 않는다.
JD relevance나 supporting contribution으로 더 강한 ownership 표현을 정당화하지 않는다.

PENDING/NEEDS_FOLLOWUP/REJECTED/DUPLICATE 처리는 canonical profile/Claim/assessment/
version을 바꾸지 않는다. 승인 시 schema §12/28의 한 change set에 EvidenceItem,
Claim, EvidenceClaimLink, ClaimAssessment, ClaimReview와 version N+1을 함께 기록한다.
승인은 정확한 텍스트/context/input version/user를 대상으로 한다. 동일 ACCEPTED
candidate 재처리는 기존 promoted IDs를 반환하고 version을 올리지 않는다.
새 문구는 새로운 후보이며 승인 없는 promotion은 실패한다.

## 6. Contradiction walkthrough: TCN

1. 기존 DL Trajectory Generation에 NO_DECISION_OWNERSHIP이 있고,
   positive Claim “Selected TCN as the production model.”은 DO_NOT_CLAIM이다.
2. 새 “I selected TCN.”은 turn → PENDING EvidenceCandidate로 저장한다.
   기존 Claim/Constraint/assessment/canonical version은 그대로 둔다.
3. workspace에 충돌을 표시하고 “최종 결정자인가요, 분석/추천 참여인가요?”를 묻는다.
   추가 자료가 필요하면 NEEDS_FOLLOWUP, 잘못 말했으면 REJECTED로 끝낸다.
4. 사용자가 발화를 **Evidence로 보존**하도록 승인할 때만 새 item/link를 추가한다.
   이것은 긍정 Claim의 사실 확인과 다르다. SUPPORTS와 CONTRADICTS를 함께 보존하고
   새 assessment는 DISPUTED/CONTRADICTED, 기존 DO_NOT_CLAIM을 유지한다.
5. 사실을 확인하고 기존 경계를 바꾸는 것은 별도 review/change set이다.
   이전 부정 근거/review를 지우지 않는다. 미해결이면 게시 차단과 follow-up을 남긴다.

ClaimReview.notes에 Evidence 수용과 factual confirmation을 구분한다.
승인 버튼 한 번으로 모순을 CONSISTENT/ALLOWED로 덮어쓰지 않는다.

## 7. Initial profiling stop guards

| Guard | 통과 증거 | 미충족 처리 |
| --- | --- | --- |
| Context known | 사용자가 구별한 활동 context; 비공개 별칭 허용 | CONTEXT_DISCOVERY |
| Role known | 사용자가 특정한 역할 | ROLE_DISCOVERY |
| Project known | 한정된 프로젝트/feature | PROJECT_DISCOVERY |
| Contribution ≥1 | 실제 수행 한 개와 출처 | CONTRIBUTION_DISCOVERY |
| Ownership boundary known | 수행/책임 범위와 금지 확대 범위 | OWNERSHIP_PROBING |
| Relevant decision authority known | 해당 결정의 권한/비권한 구분; 관련 없는 결정은 이유와 함께 제외 | 관련 결정권 UNKNOWN이면 중지 |
| EvidenceSource ≥1 | 원본 locator 포함 출처; AI 초안만 있으면 실패 | EVIDENCE_CAPTURE |
| High-impact reviewed | 각 후보 accepted/rejected/edited/follow-up 명시 disposition | 무응답은 완료 아님 |
| Do-not-claim checked | 금지 표현과 타인 담당/결정 질문·확인 | BOUNDARY_CHECK |
| Major contradictions handled | 해소 근거 또는 명시 미해결·follow-up·게시 차단 | 무표시 모순이면 실패 |

기간/회사 실명/수치/부수 기술은 UNKNOWN/null이어도 된다. 필수 ownership 경계나
관련 결정권을 모르면 COMPLETE가 아니다. 모순을 표시하고 종료해도 그 Claim은 게시
불가다. COMPLETE는 충분한 초기 수집 여부, ALLOWED는 Claim별 사용 가능 여부다.

## 8. Synthetic walkthroughs and concrete IDs

모든 답변과 확인은 테스트용 모의 기록이다. 실제 사용자가 확인했다는 뜻이 아니다.
세 fixture는 decision_authority 일부가 UNKNOWN인 검증 자료이며 profiling 완료
instance가 아니다. 아래 마지막 질문에 실제 응답이 없으면 COMPLETE로 표시하지 않는다.

### A. Feature ownership

- 질문: NACC 담당 범위와 직접 설계/구현/검증을 나눠 달라.
- 모의 답변: feature architecture, target-speed logic, calibration, SIL/HIL/vehicle validation.
  회사/기간/성과 수치는 제공되지 않아 null이다.
- Claim: C-A-architecture, C-A-logic, C-A-calibration, C-A-sil, C-A-hil,
  C-A-vehicle-validation; ownership은 C-A-feature-owner로 분리한다.
- Evidence: ES-A → E-A-work/E-A-validation → 해당 SUPPORTS links.
  O-A-feature의 FEATURE scope와 작업별 ownership을 확인한다.
- 확인: claim_reviews의 synthetic USER_ACCEPTED로 정확한 문구를 확인한다.
- 경계: K-A-no-adas-owner/K-A-no-vehicle-owner가 전체 ADAS/차량 확대를 차단한다.
- 종료: 관련 decision_authority는 UNKNOWN이다. “누가 최종 결정했나?”에 답을 받아
  검토하기 전에는 해당 결정이 필요한 profiling을 COMPLETE로 처리하지 않는다.

### B. Supporting contribution

- 질문: dataset/I/O, analysis, 선정 후 설계 중 실제 수행과 TCN 결정자를 묻는다.
- 모의 답변: dataset/I/O 정의 참여, model analysis 지원, 선정 후 architecture/integration.
- Claim: C-B-dataset/C-B-io/C-B-post-selection-architecture/C-B-post-selection-integration.
  C-B-model-analysis는 synthetic 반대 Evidence도 있어 CONTRADICTED/REVIEW_REQUIRED다.
- Evidence: E-B-definitions/E-B-post-selection의 SUPPORTS와 별도 QUALIFIES/CONTEXTUALIZES.
- 확인/경계: 모의 확인은 긍정 작업의 정확한 문구에 한정한다. O-B-tcn-decision의
  NONE과 K-B-no-tcn-selection/K-B-no-project-owner/K-B-no-model-owner를 유지한다.
- 종료: TCN 비권한은 알려져 있다. 나머지 관련 결정은 UNKNOWN이므로 필요하면
  follow-up한다. analysis 모순을 명시하고 종료해도 해당 Claim은 게시 불가다.

### C. Team/process leadership

- 질문: 팀 운영, 프로세스 책임, 직접 기술 작업, 제품 구현 범위를 각각 묻는다.
- 모의 답변: V&V 팀 운영, sprint/schedule/review/coordination, feature↔test traceability,
  simulation/field/regression/release 평가 프로세스.
- Claim: C-C-team-leadership, C-C-traceability 및 C-C-simulation/field/regression/release.
  팀 구성·운영이라는 compound 답변 중 canonical leadership Claim은 운영으로 한정했다.
- Evidence/Ownership: ES-C와 작업별 item/link; O-C-team/O-C-process/O-C-traceability는
  TASK scope로 관리 책임과 기술 작업을 분리한다.
- 확인/경계: leadership high-impact 확인; K-C-no-perception/planning/control로 구현 소유 금지.
  release 평가 프로세스 운영은 production launch responsibility가 아니다.
- 종료: 관련 결정권 UNKNOWN은 추가 확인 필요. EC-C-regression-script의 새 발화는
  PENDING이므로 Claim도 version 변경도 만들지 않는다. 이후 명시 승인 시 v12→v13.

## 9. Machine-checkable scope

자동 검사 범위는 필드/ID/enum/관계, 세 상태 축, 제한된 exact wording 게시,
candidate 격리/승인/replay, Evidence 보존, 버전 archive 복원이다. 일반적인 자연어
진실성/atomicity, 실제 사용자 인증, DB transaction/동시성은 검증하지 않는다.
알려진 compound 반례를 거부하는 검사를 일반 NLP 검증이라고 부르지 않는다.

Protocol instance 저장/API 계약은 아직 정의하지 않았다. 따라서 protocol JSON Schema로
미정 workspace 필드를 고정하지 않는다. 14 state/guard와 §7 체크리스트는 수동 검토
계약이며 [validation report](career_graph_schema_v1_validation.md)에 실제 검사 대응을 남긴다.

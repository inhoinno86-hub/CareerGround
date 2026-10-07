---
step: 4
depends_on: [3]
executor: coordinator
model: gpt-6-astra
reasoning_effort: high
---

# Step 04 — Career Profiling Protocol v1 설계

## 목표와 기준선

main 기준에서 검증·최소 수정된 Step 03 계약을 사용하여 사용자 대화를 Career Graph로 변환하는 protocol을 정의한다. 상태 전이와 human authority의 연결은 Astra/high coordinator가 직접 맡는다. [main.md](main.md)를 먼저 읽는다.

## 입력·확인 범위

원문 §10–18/24, 두 v1 문서, validation 보고서, A/B/C fixtures를 확인한다. 출력은 `docs/career_profiling_protocol_v1.md`이며 LLM agent나 앱을 구현하지 않는다.

## 실행 지시

1. 목적, 입력/출력, canonical graph와 임시 후보 영역, 사용자 확인 권한, protocol의 한계를 서술한다. 단순 질문 목록에 그치지 않는다.
2. 최소 다음 14개 state를 표로 정의한다: CONTEXT_DISCOVERY, ROLE_DISCOVERY, PROJECT_DISCOVERY, RESPONSIBILITY_DISCOVERY, CONTRIBUTION_DISCOVERY, OWNERSHIP_PROBING, TECHNICAL_DEPTH_PROBING, VALIDATION_PROBING, OUTCOME_PROBING, EVIDENCE_CAPTURE, CLAIM_DRAFTING, CLAIM_CONFIRMATION, BOUNDARY_CHECK, COMPLETE.
3. 각 state에 목적, 진입 조건, 질문 유형, 수집 field와 canonical entity, 임시 출력, 전이 guard, 다음 state, missing/UNKNOWN/충돌 시 처리, 사용자 확인 필요 여부를 넣는다. 필요 시 재질문/이전 상태 복귀/중단/재개를 정의하되 무한 질문을 방지한다. 14 state를 통합·개선했다면 원래 state와 대응표를 제공한다.
4. Context, Responsibility, Contribution, Ownership, Decision Authority, Implementation, Validation, Outcome, Boundary의 9개 질문 유형을 빠짐없이 매핑한다. 특히 “본인이 했다고 말하면 안 되는 부분”과 다른 사람의 담당/결정 범위를 명시적으로 묻는다.
5. “I developed ACC.”에 대해 known/unknown을 분리하고 회사/role/project, 직접 수행, 소유권, 결정 권한, 검증, 성과 근거로 좁혀 가는 예시를 작성한다. 사용자가 말하지 않은 architecture/validation ownership을 추론해 채우지 않는다.
6. architecture 설계 + control logic 구현 + SIL/HIL 검증 답변을 최소 네 atomic Claim으로 분해한다. 각 Claim의 Evidence link와 Ownership boundary를 별도로 둔다.
7. project/team/architectural/technical decision/production launch ownership, 정량 개선, 비용 절감, 매출, safety, 특허·논문을 high-impact 확인 대상으로 열거한다. 확인 전 USER_CLAIMED 또는 INFERRED, 명시적 확인 후 USER_CONFIRMED이며 외부 검증으로 자동 승격하지 않는다. 사용자 무응답을 확인으로 보지 않는다.
8. 기존 NO_DECISION_OWNERSHIP과 새 “I selected TCN.”이 충돌하는 예시를 작성한다. 새로운 Interview 정보는 Candidate로 격리하고 기존 Claim/Constraint를 보존한다. canonical consistency 변경이 필요한 시점과 review/승인 조건은 Step 03 계약을 따른다. 원문의 contradiction 처리와 candidate 격리가 충돌하지 않도록 순서를 명시한다.
9. 프로젝트 단위 initial profiling 종료 조건을 모두 검사 가능하게 적는다: context/role/project, 최소 Contribution 1개, ownership boundary, 관련 decision authority, EvidenceSource 1개 이상, high-impact review, do-not-claim 확인, 주요 모순 해소 또는 명시 표시. UNKNOWN 허용과 알려져야 하는 필수 경계를 구별한다.
10. 모순을 명시하여 profiling을 종료할 수 있어도 해당 Claim의 게시 허용을 뜻하지 않음을 규정한다. COMPLETE와 usage ALLOWED를 독립 판단한다.
11. A/B/C별 질문→답변/unknown→atomic Claim→Evidence/Ownership→확인→경계→종료 walkthrough를 제공한다. 사용자 답변은 synthetic 예시로 표시하고 실제 확인을 받았다고 기록하지 않는다.
12. 다음 단계가 machine-readable rule로 옮길 수 있도록 필수 필드, guards, 불변식, 테스트 예시를 구분한다. 필요 없는 새로운 canonical entity/enum을 만들지 않는다.

## 제약과 산출물

허용 쓰기는 profiling protocol, validation 보고서의 protocol 관련 설명, 패키지 상태다. 새 schema gap을 발견하면 Step 03의 근거·최소 수정·재검증 절차로 돌려보낸다. AI 문장 자체를 Evidence로 만들거나 실제 사용자 확인을 모의 대화로 대체하지 않는다.

## 완료 기준

- [ ] protocol 문서에 14 state 또는 일대일 대응과 각 transition guard가 있다.
- [ ] 9개 질문 유형과 negative boundary 질문이 포함된다.
- [ ] ACC 모호성, 네 atomic Claim 분해, TCN 충돌, 세 ownership 패턴 walkthrough가 있다.
- [ ] high-impact claim 확인, No Silent Inference, PENDING 격리, 명시적 승격 조건이 v1과 일치한다.
- [ ] 종료 조건을 검사할 수 있고 UNKNOWN·명시된 모순의 처리와 게시 제한이 구분된다.
- [ ] 질문/state/field/entity 사이에 추적표가 있고 새로운 근거 없는 schema 요소가 없다.

## 다음 단계 handoff

Step 05에 state/guard 표, atomicity와 게시·승격 불변식, 필수 사례, schema 생성 가능한 범위와 남은 결정을 전달한다.

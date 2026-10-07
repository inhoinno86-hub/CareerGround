---
step: 3
depends_on: [2]
executor: coordinator
model: gpt-6-astra
reasoning_effort: high
---

# Step 03 — Gap 분석과 최소 schema 수정

## 목표와 기준선

main의 원래 설계와 Step 02의 사례를 비교하여 관찰된 문제만 수정한다. 의미·버전 판단과 두 Source of Truth의 일관성은 Astra/high coordinator가 맡는다. [main.md](main.md)의 입력·모델 계약을 적용한다.

## 확인 범위

원문 §4/7–9/24, v1 두 문서, 세 fixtures, validation 보고서의 실제 경로와 실패 목록을 읽는다. 이전 문서 내용을 보존할 수 있도록 수정 전 내용을 확보한다.

## 실행 지시

1. 각 발견을 PASS / AMBIGUOUS / GAP / OVERMODELED 중 하나로 분류한다. 단순히 “문제 없음”이라고 쓰지 말고 fixture ID→관계→도착 ID와 문서 조항을 보여준다.
2. 각 수정 후보에 실제 scenario, 기존 계약으로 표현하기 어려운 이유, 최소 변경, 선택하지 않은 더 큰 변경, 영향 범위를 기록한다. 필드가 비어 있다는 이유만으로 실제 사용자 사실을 채우지 않는다.
3. 필요한 경우에만 `docs/career_graph_entity_relationship_model_v1.md`와 `docs/career_graph_schema_v1.md`를 일관되게 최소 수정한다. 관계 누락/enum 모호성/integrity rule/ownership semantics/fixture에서 입증된 gap으로 제한한다.
4. 같은 검증 사례로 수정 전 실패와 수정 후 결과를 대조한다. fixtures를 변경했다면 어떤 계약 때문에 바뀌었는지 적고 검사 기대값을 단순히 통과하도록 완화하지 않는다.
5. v12 기반 ArtifactUnit이 v13 변경 후에도 당시 Claim/Evidence/Constraint 범위를 복원하는지 구체적 사례로 보여준다. 현재 version 숫자만 적는 것은 충분하지 않다. 문서의 snapshot 또는 immutable revision 방식을 먼저 따르고, 참조 대상 소실/재해석 가능성을 검사한다.
6. Candidate PENDING에서 canonical profile/Claim/Assessment/버전 불변, 사용자 승인 후 ACCEPTED→EvidenceItem→Claim→ClaimAssessment→version+1을 명시한다. 후보 상태와 canonical 상태를 구분하고 승인 없는 승격, 중복 승인/재실행의 예상 처리, 거절/추가질문 처리를 현재 v1에 맞춰 설명한다. 범용 transaction engine을 구현하지 않는다.
7. 동일 Claim을 SUPPORTS/CONTRADICTS하는 Evidence를 함께 보존한다. 모순 발견과 해소의 review 기록, active assessment 및 usage boundary를 구분한다. PENDING 정보만으로 기존 canonical Claim/Assessment를 조용히 바꾸지 않는다.
8. `DO_NOT_CLAIM` 및 scoped ClaimConstraint가 public artifact 문장에 적용되는 경로를 설명한다. 존재하는 긍정 Claim의 evidence를 더 강한 소유권 표현에 재사용할 수 없게 한다.
9. validation 보고서의 10개 섹션을 채우고 남은 ambiguity와 구현 blocker를 구분한다. 미결정 사항이 optional JSON Schema 생성만 막는지 핵심 도메인 검증까지 막는지 밝힌다.

## 제약과 산출물

허용 쓰기는 v1 두 문서, validation 보고서, 세 fixture 및 패키지 상태다. 새 DB/인프라/abstraction을 추가하지 않는다. OVERMODELED 판정만으로 관계를 대량 삭제하지 않는다. 수정이 불필요하면 문서를 억지로 변경하지 않고 근거를 남긴다.

## 완료 기준

- [ ] 모든 발견에 네 분류 중 하나, 실제 사례와 관련 문서 조항이 있다.
- [ ] 모든 schema 수정은 구체적 실패→최소 해결→재검증 증거에 연결된다.
- [ ] entity/enum/관계/용어가 두 v1 문서와 fixtures에서 일치한다.
- [ ] Test A–F, ownership 경계, historical artifact 재현 결과가 ID로 설명된다.
- [ ] PENDING 불변 및 승인 후 version 전이가 명확하고 모순 증거를 보존한다.
- [ ] 남은 ambiguity의 영향과 대응을 기록했다. 핵심 거버넌스 실패는 완료 처리하지 않는다.

## 다음 단계 handoff

Step 04에 안정화된 canonical 계약, 확인/승격/모순 규칙, 허용·금지 표현, unresolved 항목을 전달한다. profiling state가 참조할 field/entity/enum을 실제 이름으로 제공한다.

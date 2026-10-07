---
step: 2
depends_on: [1]
executor: bounded-worker
model: gpt-5.6-sol
reasoning_effort: high
---

# Step 02 — 세 ownership fixture와 추적 사례

## 목표와 기준선

main 기준의 Step 01 계약을 사용하여 feature ownership, supporting contribution, team/process leadership을 구분하는 machine-readable fixture를 만든다. [main.md](main.md)의 native spawn 규칙으로 Sol/high worker에 제한된 데이터 작성을 맡긴다. coordinator는 병행하여 원문 요구사항과 기대 결과 표를 준비하고 worker 결과를 검토한다.

## 입력·확인 범위

- 원문 §5–7/24, Step 01의 확정 계약과 가설.
- v1 두 문서 및 validation 보고서 초안.
- 이미 fixture가 있으면 읽고 기존 내용을 보존한다.

## 실행 지시

1. 다음 세 파일을 canonical JSON interchange 계약에 따라 작성한다. 파일명은 계획된 신규 경로이며 현재 존재한다고 가정하지 않는다.
   - `fixtures/career_graph/feature_owner.json`
   - `fixtures/career_graph/supporting_contributor.json`
   - `fixtures/career_graph/team_process_leadership.json`
2. fixture가 schema validation용 synthetic 사례임을 명확히 표시한다. schema가 fixture metadata를 허용하지 않으면 보고서에서 설명한다. 알려진 사실은 원문 scenario 문장까지 역추적하고, 미확인 회사/기간/성과 수치는 unknown 또는 허용된 placeholder로 둔다. synthetic source가 실제 외부 검증 자료라는 인상을 주지 않는다.
3. 각 fixture에 CareerProfile, Role, Project, Contribution, Ownership, Claim, ClaimAssessment, EvidenceSource, EvidenceItem, EvidenceClaimLink를 포함한다. ClaimConstraint는 과장 경계를 검사할 수 있도록 적용한다. canonical 표기/case를 따른다.
4. A: Navigation-Aided Adaptive Cruise Control의 feature 범위, architecture/logic/calibration/validation 작업을 분리한다. 원문의 possible contribution은 실제 사용자의 확정 사실이 아니다. 전체 ADAS/차량 ownership 과장을 차단한다.
5. B: DL Trajectory Generation의 dataset/I/O definition, model analysis 지원, model 선정 후 system architecture/integration 기여를 표현한다. TCN model selection, overall project leadership, overall model development 소유 주장은 모두 금지 사례로 둔다. 없는 기술 의사결정 권한을 만들지 않는다.
6. C: V&V 팀 구성·운영, sprint/schedule/review/coordination, feature↔test traceability, simulation/field/regression/release 평가 process를 표현한다. team leadership/process ownership/technical contribution/product feature ownership을 서로 구분한다. perception/planning/control 구현 소유로 확대하는 문장은 차단한다.
7. 적어도 fixture 묶음 전체에서 원문 Test A–F를 실제 ID로 따라갈 수 있도록 필요한 Artifact/ArtifactUnit/ArtifactClaimLink, JDRequirement/RequirementClaimMap, InterviewTurn/EvidenceCandidate 등의 최소 예시를 넣는다. 참조가 있으면 해당 entity를 실제로 제공한다.
8. 하나의 compound 문장을 atomic Claim들로 분리한다. Evidence link가 SUPPORTS/CONTRADICTS/QUALIFIES/CONTEXTUALIZES인 경우를 검토하고, 단순 context를 사실 검증 근거로 취급하지 않는다.
9. PENDING 격리와 승인 전후 version을 비교할 최소 snapshot/transition 예시를 제안한다. 현 interchange가 이를 수용하지 못하면 field를 임의 추가하지 말고 구체적 gap과 필요한 재현 데이터를 coordinator에게 반환한다.
10. JSON parsing과 duplicate/dangling ID 검사를 가능한 범위에서 수행한다. 구조적으로 표현 불가능한 부분은 숨기지 말고 실패 목록으로 반환한다. coordinator가 validation 보고서에 ID 경로, 기대/관찰 결과, 실패를 반영한다.

## 제약과 write scope

worker 쓰기는 위 fixture 세 파일로 제한한다. 추가 파일/새 field가 필요하면 coordinator에게 근거를 반환한다. 문서 수정, runtime/framework 설치, schema 재설계, 기존 unrelated 변경 복원, 재위임을 하지 않는다. fixture 안에 넣은 `expected: true`만 확인하는 방식으로 의미 검증을 대체하지 않는다.

## 산출물과 완료 기준

- [ ] 세 파일이 JSON으로 파싱되고 각 fixture에 최소 entity가 존재한다.
- [ ] 실제 경력 데이터와 synthetic 예시/placeholder의 구분이 명확하다.
- [ ] A/B/C별 허용 문장과 금지 문장, 관련 Claim/Ownership/Constraint ID를 제시했다.
- [ ] Test A–F 각각에 실제 ID 경로 또는 재현 가능한 구체적 실패/gap이 있다.
- [ ] 모든 참조의 유효성 및 atomic Claim 분리 결과를 확인했다.
- [ ] source 근거 없는 성과 수치, TCN 결정 권한, 전체 ADAS/제품 구현 ownership이 없다.
- [ ] coordinator가 JSON과 반환된 실패 목록을 직접 확인하여 보고서에 반영했다.

기존 schema의 의미적 실패는 이 단계의 유효한 발견이며, 위 완료 기준에 따라 재현 데이터를 갖추면 Step 03으로 전달한다. 다만 근거 없이 계약을 꾸며 fixture를 정상으로 보이게 해서는 안 된다. 핵심 entity 자체를 작성할 수 없어 위 완료 기준을 충족하지 못하면 부분 fixture와 구체적 blocker를 보고하고, 계약 결정 전에는 다음 단계로 진행하지 않는다.

## 다음 단계 handoff

Step 03에 fixture 경로, 사용한 source/Claim/Evidence/Constraint ID, raw 검사 결과, 변경 전 실패와 기대 결과를 전달한다. worker 요청/관측 모델 정보를 함께 기록한다.

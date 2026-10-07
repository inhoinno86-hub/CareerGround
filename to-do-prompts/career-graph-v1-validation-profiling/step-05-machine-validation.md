---
step: 5
depends_on: [3, 4]
executor: bounded-worker
model: gpt-5.6-sol
reasoning_effort: high
---

# Step 05 — 최소 machine-readable schema와 invariant 검사

## 목표와 기준선

main 기준에서 확정된 문서·fixture·protocol 계약을 재현 가능한 검사로 옮긴다. [main.md](main.md)의 native spawn 계약에 따라 Sol/high worker가 한정된 검증 코드를 작성한다. coordinator는 병행하여 원문 §27 대응표와 예상 양성/음성 결과를 검토한다.

## 입력·확인 범위

원문 §19–20/24/27, Step 03 계약, Step 04 protocol, 세 fixtures, 실제 repository runtime/tests 설정을 읽는다. runtime이나 JSON Schema 라이브러리가 이미 있다고 가정하지 않는다.

## 실행 지시

1. 현재 runtime을 확인하고 최소 재현 방식을 선택한다. 별도 setup이 없다면 Python 3 표준 라이브러리 `unittest`와 JSON 로딩을 우선 검토한다. API 서버/웹 framework/DB를 추가하지 않는다.
2. 완전하게 결정된 계약에 한해 `schemas/career_graph_v1.schema.json`과 필요 시 `schemas/career_profiling_protocol_v1.schema.json`을 작성한다. protocol schema가 “protocol 정의 파일”을 검증하는지 “profiling instance/state”를 검증하는지 명시하고 실제 대상 예시를 제공한다. schema만 두고 대상이 없는 상태를 완료로 보지 않는다.
3. 추가 결정 없이 정확한 JSON Schema를 만들 수 없으면 억지로 작성하지 않는다. 누락 결정, 영향 필드, 가능한 대체 검사를 coordinator에게 반환한다. 외부 JSON Schema validator를 쓰면 버전/설치/실행 방법과 필요한 최소 dependency를 명시한다. stdlib JSON parse를 JSON Schema validation이라고 부르지 않는다.
4. `tests/test_career_graph_fixtures.py` 등 최소 파일에 아래 8개 검사 개념을 구현한다. 정확한 함수명은 runtime에 맞출 수 있지만 대응표를 제공한다.
   - `test_every_verified_claim_has_evidence`: verified/confirmed claim의 출처와 link semantics, AI text 단독 증거 금지, 외부 검증과 사용자 확인의 구별.
   - `test_do_not_claim_blocks_publication`: usage policy/ClaimConstraint에 따라 artifact 사용을 차단.
   - `test_resume_unit_resolves_to_evidence`: ArtifactUnit→ArtifactClaimLink→Claim→EvidenceClaimLink→EvidenceItem→EvidenceSource 및 당시 버전까지 해석.
   - `test_jd_requirement_resolves_to_claim`: JDRequirement→RequirementClaimMap→Claim→Evidence의 참조 검증.
   - `test_pending_candidate_does_not_mutate_profile`: PENDING 입력 처리 전후 canonical profile/Claim/Assessment/version 불변.
   - `test_candidate_promotion_increments_version`: 명시적 review 승인 후 필요한 EvidenceItem/Claim/ClaimAssessment와 정확한 version 전이, 승인 없는 처리 차단.
   - `test_contradictory_evidence_is_preserved`: 같은 Claim의 SUPPORTS/CONTRADICTS가 함께 남고 원본이 삭제/덮어쓰기 되지 않음.
   - `test_ownership_boundary_prevents_overclaim`: B의 TCN/전체 project/model ownership과 C의 feature implementation, A의 전체 ADAS 확대 차단.
5. 이 검사는 제품 구현이 아니다. 필요한 경우 tests 아래 작은 순수 함수 참조 모델로 규칙을 실행하고 참조 모델임을 문서화한다. 임의로 만든 두 dictionary를 비교하거나 version+1을 테스트 자체에서 실행한 후 assert하는 것만으로 promotion 구현 검증을 주장하지 않는다. 정적 fixture 검사만 했다면 그 검증 범위를 정확히 표시한다.
6. 최소 음성 사례는 누락/dangling Evidence 참조, compound Claim 처리 위반, INFERRED 사실 게시, DO_NOT_CLAIM 게시, ownership 확대, 승인 없는 promotion, contradiction 소실, 과거 artifact 참조 파손이다. fixture 복사본을 한 조건씩 변경하여 검사가 실제로 실패하는지 확인하고 원본은 보존한다. negative case의 예상 거부가 테스트 통과 조건임을 구분한다.
7. ID 유일성·참조 무결성·enum·required fields·세 상태 축 분리도 검사한다. JSON Schema의 구조 검사로 시간 전이나 모든 의미 규칙이 검증됐다고 주장하지 않는다.
8. JSON Schema를 작성했다면 세 원본 fixture에 실제 validator를 실행하는 검사를 반드시 넣는다. protocol schema를 만들었다면 최소 정상/잘못된 state/guard 사례를 검증한다.
9. Python 선택 시 예상 실행 명령은 `python3 -m unittest discover -s tests -v`다. 실제 도구와 경로에 맞게 조정하고 버전·설치 방법·명령·exit code·통과/실패/미실행 수를 반환한다. 테스트 0개 수집은 성공이 아니다.
10. 자동화가 작업 범위를 과도하게 키우면 원문이 허용한 fixture+문서 경로를 coordinator가 선택할 수 있다. 이 경우 8개 개념 및 A–F의 수동 경로/실제 결과와 자동화 생략 이유를 남긴다. 미검증 핵심 기준이 있으면 전체 완료를 주장하지 않는다.

## 제약과 write scope

worker 쓰기는 `schemas/`, `tests/` 아래 실제 필요한 파일 및 합의된 최소 검증 dependency 파일로 제한한다. fixture/Source of Truth/protocol 수정은 coordinator에게 문제를 반환한 후 Step 03 절차로 처리한다. 빈 디렉터리/사용하지 않는 boilerplate/CI stack을 만들지 않는다. 외부 서비스 연결, credential 변경, production 코드, 재위임은 금지한다.

## 산출물과 완료 기준

- [ ] JSON Schema 작성 또는 미작성 판단이 구체적 근거와 함께 기록된다.
- [ ] 만든 schema는 실제 검증 대상과 validator가 있으며 세 fixture 검사를 실행했다.
- [ ] 8개 검사 개념과 A–F, version 재현의 자동/수동 대응표가 있다.
- [ ] 양성 fixture와 최소 음성 사례에서 기대 결과를 실제 확인했다.
- [ ] 실행 명령·도구 버전·결과·exit code·검증 한계를 반환했다.
- [ ] coordinator가 코드/출력을 직접 확인하고 검증 보고서에 반영했다.

## 다음 단계 handoff

Step 06에 실행 명령, dependency 재현 방법, 검사 대응표, 결과, schema 미결정 사항, 정적 검사와 참조 모델의 한계, worker 실제 모델 관측 정보를 전달한다.

---
step: 1
depends_on: []
executor: coordinator
model: gpt-6-astra
reasoning_effort: high
---

# Step 01 — 입력 확인과 기존 schema 조사

## 목표와 기준선

main을 기준으로 현재 working tree의 사용자 입력을 확인하고, v1 두 문서의 실제 계약과 검증 가설을 추출한다. 모델 적용과 안전 규칙은 [main.md](main.md)를 따른다. 이 단계는 문서 간 의미 판단이 필요하므로 coordinator가 Astra/high로 수행한다.

## 확인할 파일과 영역

- 원문 `intent-docs/CareerGround_Codex_CareerGraph_v1_Validation_ProfilingProtocol.md` 전체, 특히 §0–4/25–27.
- README 및 실제로 존재하는 프로젝트 지침.
- `docs/career_graph_entity_relationship_model_v1.md` 전체.
- `docs/career_graph_schema_v1.md` 전체.
- `docs/CareerGround_Development_Plan_v0.1.md`는 배경으로만 사용한다.
- 실제 파일 목록, runtime/test 설정의 존재 여부.

## 실행 지시

1. `git status --short --untracked-files=all`, `git branch --show-current`, `git rev-parse main`, `git log --oneline -5`, `rg --files --hidden -g '!.git/**'`를 확인한다. main SHA와 작성 당시 SHA의 차이를 기록한다.
2. 기존 사용자 입력·변경을 목록과 해시로 기록한다. git diff에 보이지 않는 untracked 파일도 보존 대상으로 다룬다.
3. 필수 v1 문서 두 개의 존재/가독성을 먼저 확인한다. 없으면 저장소 내부와 사용자가 명시한 경로에서만 대응 문서를 찾는다. 사용자 지시 없이 유사 문서를 대체 입력으로 채택하지 않는다. 지정된 두 문서 또는 사용자가 명시한 대체 입력이 없으면 `BLOCKED_INPUT`과 필요한 두 경로를 보고한다. 이 경우 읽기 전용 확인 결과만 보고하며 아래 4–8과 하위 단계는 실행하지 않는다. 빈 v1/validation 문서도 만들지 않는다.
4. 입력이 갖춰지면 두 v1 문서를 처음부터 끝까지 읽는다. entity/field/type/required/nullable/enum/relationship/cardinality/ID 및 canonical JSON envelope 계약을 대조한다. 실제 section과 인용 가능한 짧은 근거 위치를 기록한다.
5. Claim atomicity, Responsibility vs Contribution, Ownership의 scope/decision/execution/validation 축, Claim 상태 3축, Evidence 관계 네 종류, negative boundary, Candidate review/promotion, profile/artifact version을 검토한다.
6. 구현 가능성을 판정할 가설을 세우되, fixture 검증 전에 PASS나 확정 gap으로 단정하지 않는다. UNKNOWN 표현과 누락/nullable 처리도 확인한다.
7. `docs/career_graph_schema_v1_validation.md`를 원문 §8의 10개 제목으로 작성한다: Validation scope, Fixtures, Traceability results, Ownership boundary results, Claim / Evidence results, Versioning results, Ambiguities, Schema gaps, Proposed minimal changes, Final recommendation. 아직 검증하지 않은 결과는 NOT_RUN으로 표시한다.
8. 보고서에 입력 기준선, 계약 표, 가설과 확인 방법, 문서 간 불일치, runtime 선택 근거를 넣는다. 원문 §27의 각 조건을 이후 단계/증거에 매핑하는 표를 시작한다.

## 제약과 제외 범위

- 허용 쓰기: validation 보고서 초안과 이 패키지의 실행 상태 기록.
- v1 문서 및 사용자 배경 자료를 이 단계에서 수정하지 않는다.
- 없는 Source of Truth를 새로 설계하는 것은 이번 패키지 범위가 아니다.
- 개발 계획서의 오래된 enum으로 v1 또는 원문의 세 축을 덮어쓰지 않는다.

## 산출물과 완료 기준

- [ ] 현재 main/branch/status와 기존 사용자 변경이 기록되어 있다.
- [ ] 두 v1 원문을 실제로 읽었고 source 경로/버전이 확인된다.
- [ ] entity/enum/관계/JSON envelope 및 시간·버전 계약 표가 있다.
- [ ] 검증 가설마다 fixture 또는 검사 방법이 있고 아직 검증 안 된 결과는 구별되어 있다.
- [ ] validation 보고서의 10개 섹션과 원문 완료 조건 대응표가 있다.
- [ ] 선택 runtime과 dependency 유무가 실제 저장소에 근거한다.

입력 누락이면 이 완료 기준을 체크하지 말고 BLOCKED로 남긴다.

## 다음 단계 handoff

Step 02에 확정한 JSON 계약, 알려진 불명확성, 최소 entity 목록, 금지 추론, fixture별 기대 결과를 전달한다. worker가 schema를 추측해야 하는 항목은 명시적으로 표시한다.

---
package: career-graph-v1-validation-profiling
executor: exec-prompts
baseline_branch: main
baseline_commit: 8285ea5820c0095f94c360ae3d4d4c92b30469d3
coordinator_model: gpt-6-astra
coordinator_reasoning_effort: high
model_routing: explicit-native-spawn
silent_model_fallback: false
implementation_status: complete
prerequisite_status_at_authoring: missing-source-of-truth-documents
---

# Career Graph v1 검증 및 Profiling Protocol 실행 지시서

## 요청과 목표

`intent-docs/CareerGround_Codex_CareerGraph_v1_Validation_ProfilingProtocol.md`를 실행 가능한 단계로 나눈 패키지다. 기존 Career Graph v1을 세 가지 ownership 사례로 검증하고, 발견한 문제만 최소 수정한 뒤 Career Profiling Protocol v1을 설계한다. 현재 요청은 **이 프롬프트 패키지 작성**이며, 실제 작업은 사용자가 이 경로를 지정하여 `$exec-prompts`를 호출할 때 시작한다.

## Planning Metadata

- Date: 2026-09-21 (Asia/Seoul)
- Feature name: career-graph-v1-validation-profiling
- Planning artifact: 이 디렉터리의 `main.md`와 `step-*.md`; make-prompts 지정 형식을 사용한다.
- Planning mode: normal Codex
- Superpowers planning: disabled
- Superpowers execution: disabled
- Superpowers brainstorming: not used
- Ouroboros: not requested / not used
- intent-loop: not requested / not used
- 이번 패키지를 위해 별도 PLAN 파일, 전역 스킬 수정, 실행 엔진 또는 프로젝트 AGENTS.md를 만들지 않는다.

## 현재 확인된 기준선과 선행 조건

계획 기준은 **main**이다. 작성 시 HEAD/main은 `8285ea5820c0095f94c360ae3d4d4c92b30469d3`이고, 추적 파일은 제목만 있는 `README.md` 하나다. 다음 두 파일은 working tree의 기존 **untracked 사용자 입력**이다.

- `docs/CareerGround_Development_Plan_v0.1.md`
- `intent-docs/CareerGround_Codex_CareerGraph_v1_Validation_ProfilingProtocol.md`

원문이 Source of Truth로 지정한 다음 파일은 작성 시 존재하지 않았다.

- `docs/career_graph_entity_relationship_model_v1.md`
- `docs/career_graph_schema_v1.md`

**Step 01에서 재확인하고, 두 원문이 없으면 `BLOCKED_INPUT`으로 종료한다. Step 02 이후로 진행하지 않는다.** 대체 경로는 사용자가 해당 문서를 Source of Truth로 명시한 경우에만 출처와 대응 관계를 확인하여 사용한다. 저장소에서 비슷한 문서를 발견한 것만으로 대체하지 않는다. 없는 v1을 추측으로 새로 작성하거나 개발 계획서 v0.1을 v1으로 간주하지 않는다. 신규 v1 설계는 별도 범위 결정이 필요하다. 이 누락은 패키지 작성의 실패가 아니라 향후 실행의 선행 조건이다.

`main`이 바뀌었다면 실행 시 SHA와 차이를 기록하고 현재 문서에 맞게 제한적으로 조정한다. 자동 checkout/reset/stash/clean, 입력 덮어쓰기, 원격 fetch는 하지 않는다. 새 worktree에는 untracked 입력이 따라오지 않으므로 현재 디렉터리를 기본으로 사용한다. 기존 입력의 시작 시 해시와 내용을 확보하고, 의도한 schema 최소 수정 이외의 변경을 보존한다.

v0.1 개발 계획서는 배경 자료다. 그 문서의 단일 Claim 상태 enum, `UNVERIFIED` 예시, 제품 구현 로드맵이 이번 원문의 3축 상태 및 제한된 작업 범위를 덮어쓰지 않게 한다. v1 원문과 이번 지시 사이에 실제 충돌이 있으면 근거와 최소 해결안을 validation 보고서에 기록한다.

## 모델과 추론 깊이 적용 계약

### 배정과 근거

아래 배정은 이 작업의 판단 복잡도에 따른 제안이며 모델 간 성능/비용을 실측한 결과가 아니다. 2026-09-21 설치된 모델 카탈로그와 native agent 도구에서 두 모델의 `high` 지원을 확인했다. 실행 시에도 지원 여부를 다시 확인한다.

| 단계 | 실행 주체 | 모델 | 추론 깊이 | 선택 이유 |
| --- | --- | --- | --- | --- |
| 01 | coordinator 직접 | `gpt-6-astra` | `high` | 문서 우선순위, 누락 입력, 의미적 불일치 판단 |
| 02 | 범위 제한 fixture worker | `gpt-5.6-sol` | `high` | 확정된 계약을 복합 관계와 반례 데이터로 구체화 |
| 03 | coordinator 직접 | `gpt-6-astra` | `high` | 실제 실패와 최소 schema 변경의 타당성 판단 |
| 04 | coordinator 직접 | `gpt-6-astra` | `high` | 상태 전이, 사용자 확인, 모순과 종료 조건 통합 |
| 05 | 범위 제한 validation worker | `gpt-5.6-sol` | `high` | 확정된 규칙을 재현 가능한 양성·음성 검사로 구현 |
| 06 | coordinator 직접 | `gpt-6-astra` | `high` | 원문 수용 기준 대조, 독립 검증, 최종 통합 |

모든 단계의 최종 승인·통합·검증 책임은 coordinator에게 있다. worker 완료 메시지만으로 단계를 완료 처리하지 않는다. Step 02/05 동안 coordinator는 별도 파일을 수정하지 않고 요구사항별 기대 결과/검증 매핑을 준비하여 유용한 병행 작업을 수행한다.

### 실제 실행 방법

`exec-prompts`는 Markdown의 모델 필드를 자동 적용하는 scheduler가 아니다. 아래 메타데이터는 **실행자가 읽고 도구 인수에 적용해야 하는 계약**이다. 프롬프트에 모델명을 적는 것만으로 현재 세션 모델이 바뀌었다고 주장하지 않는다.

권장 시작 명령은 다음과 같다. 프로젝트 root에서 실행하며 전역 설정이나 승인 정책을 바꾸지 않는다.

```bash
codex --model gpt-6-astra -c 'model_reasoning_effort="high"' \
  '$exec-prompts to-do-prompts/career-graph-v1-validation-profiling/ 를 main.md의 모델 배정 계약과 선행 조건에 따라 수행해줘.'
```

이미 열린 세션에서는 `$exec-prompts to-do-prompts/career-graph-v1-validation-profiling/`를 요청하되 coordinator의 실제 모델/effort를 확인한다. 다른 설정이면 위 명령으로 새 세션을 시작하도록 안내하고, 현재 모델을 몰래 대체 사용하지 않는다. 명시적으로 선택한 다른 모델을 임의로 변경하지 않는다.

Step 02/05의 worker는 native `collaboration.spawn_agent`로 **새로** 생성한다. 모델과 effort가 다른 기존 worker를 재사용하지 않는다. 이 환경에서 사용할 핵심 인수는 다음과 같다.

```json
{
  "task_name": "career_graph_fixtures",
  "fork_turns": "none",
  "model": "gpt-5.6-sol",
  "reasoning_effort": "high",
  "message": "선택 패키지의 main.md와 step-02-ownership-fixtures.md를 읽고, coordinator가 제공한 확정 계약과 이전 단계 결과를 사용하라. 쓰기는 지정된 fixture 파일로 제한한다. 기존 사용자 변경을 되돌리지 말고, 하위 에이전트를 만들지 말라. 변경 파일·검증 명령/결과·미해결 사항을 coordinator에게 반환하라."
}
```

Step 05에서는 `task_name`을 `career_graph_validation`, step 파일을 `step-05-machine-validation.md`로 바꾸고 해당 write scope와 handoff를 전달한다. 실제 brief에는 repository root, 입력 경로, 확정한 entity/field/enum 계약, 의존 단계 결과, 허용 파일, 수용 기준을 함께 제공한다. `fork_turns="all"`은 부모 설정을 상속하므로 이 배정에 사용하지 않는다.

- 동시에 writer는 하나만 둔다. worker 간 직접 소통이나 재위임은 금지한다. coordinator가 메시지와 결과를 연결한다.
- spawn 인수와 runtime이 제공하는 agent/model/effort 증거를 구별해 기록한다. 관측할 수 없는 실제 적용값은 `unknown`으로 남긴다.
- 다른 도구 인터페이스에서는 동등한 명시 설정이 지원되는지 확인한다. worker 미지원/모델 사용 불가/명시 배정 적용 실패이면 `BLOCKED_ROUTING`으로 기록한다. 다른 모델, nested `codex exec`, 별도 provider/인증 방식으로 자동 우회하지 않는다.
- worker가 계약 불명확성을 발견하면 판단을 coordinator에게 돌려보낸다. 어려운 문제를 같은 설정에서 반복 재시도하지 않는다. 재배정은 변경된 모델과 이유를 명시한 뒤 사용자 지시에 따른다.
- 단계 결과에는 `requested_model`, `requested_effort`, `observed_model`, `observed_effort`, `agent_id`, 검사 결과를 기록한다. 직접 실행은 coordinator라고 표기한다.

CLI 옵션은 로컬 `codex --help`로, 설정 키 및 명시적 spawn 우선순위는 [OpenAI 공식 설정 문서](https://learn.chatgpt.com/docs/config-file/config-reference)로 확인했다. 모델 사용 가능 여부는 미래 실행의 성공을 보장하지 않으며 실행 시 재확인한다.

## 실행 순서와 단계 연결

| 단계/지시서 | 목적 | 입력 | 출력 | 의존성·완료 기준 요약 |
| --- | --- | --- | --- | --- |
| [01: 입력·schema 조사](step-01-inspect-schema.md) | 기준 계약과 검증 가설 확정 | 원문, README, 제공된 v1 두 문서 | validation 보고서 초안, 계약/가설 목록 | 선행 입력 존재, 두 문서 전체 독해, entity/enum/관계/버전 비교 완료 |
| [02: ownership fixtures](step-02-ownership-fixtures.md) | 세 패턴 및 trace 반례 구체화 | 01 계약, 원문 사례 A/B/C | JSON fixture 3개, ID 기반 경로와 실패 목록 | 01 완료; 최소 entity, 출처 표시, A–F 경로와 과장 금지 사례 확인 |
| [03: gap·최소 수정](step-03-minimal-remediation.md) | 관찰 실패의 원인과 최소 수정 | 02 fixtures, v1 두 문서 | 필요 시 v1/fixture 수정, validation 보고서 | 02 완료; 네 분류, 수정 전후 증거, 버전 재현과 재검증 |
| [04: profiling protocol](step-04-profiling-protocol.md) | 대화→Claim/Evidence/Ownership 규칙 설계 | 03 안정화 계약·제한 | profiling protocol 문서 | 03 완료; 14 states, 전이/확인/경계/종료, 사례 walkthrough |
| [05: 기계 검증](step-05-machine-validation.md) | 최소 schema 및 invariant 검사 | 03/04 계약, fixtures | 정당한 범위의 schemas/tests, 실행 증거 | 04 완료; 8개 검사 개념 및 음성 사례, 생략 근거 명시 |
| [06: 최종 일관성 검토](step-06-final-review.md) | 원문 전체 수용 기준 감사 | 모든 이전 산출물 | 최종 validation 보고서, 최소 README, 결과 보고 | 01–05 완료; 검사 재확인, 문서/링크/diff 검토, 원문 §27 대응표 |

01에서 schema를 읽고 02에서 사례를 대입한 뒤에만 03의 수정 여부를 결정한다. 04는 검증된 의미 규칙을 대화 상태 머신으로 옮긴다. 05는 규칙을 검사 가능한 범위로 구체화한다. 06에서 전체 증거를 대조한다. 후속 단계가 새로운 gap을 드러내면 근거를 03에 돌려 최소 수정하고 영향을 받는 fixture/protocol/test만 재검증한다. 새로운 기능이나 전면 재설계로 확대하지 않는다.

## 공통 제약과 완료 판정

1. Claim의 `knowledge_status`, `consistency_status`, `usage_policy`를 분리한다. `USER_CONFIRMED`는 `EXTERNALLY_VERIFIED`가 아니다. `INFERRED`/`UNKNOWN`을 사실로 게시하지 않는다.
2. 책임·실제 수행·판단 권한·검증 책임을 구분한다. feature owner, supporting contributor, team/process leader를 전체 프로젝트나 다른 기술 구현의 owner로 확대하지 않는다.
3. EvidenceSource→EvidenceItem→EvidenceClaimLink를 유지하고 SUPPORTS/CONTRADICTS/QUALIFIES/CONTEXTUALIZES 의미를 구분한다. AI 생성 문장 또는 schema fixture는 실제 경력의 독립 Evidence가 아니다.
4. 외부 산출물은 사용한 profile version과 Claim/Evidence를 복원할 수 있어야 한다. Resume 역추적과 JD mapping을 실제 ID로 보여준다.
5. Interview의 PENDING EvidenceCandidate는 canonical graph를 변경하지 않는다. 승인된 promotion만 EvidenceItem/Claim/ClaimAssessment와 profile version 전이를 만들며, 기존 모순 증거를 지우지 않는다.
6. synthetic fixture의 ID/익명 표시는 가능하지만 회사, 기간, 수치, 기술 성과를 실제 사용자 사실로 발명하지 않는다. UNKNOWN/placeholder는 canonical schema가 허용하는 방식으로 표현하고, 불가능하면 gap으로 보고한다.
7. production backend/API/FastAPI, frontend, 인증, 결제, Docker DB stack, Graph DB/Neo4j, vector DB, crawler/auto apply, Plugin/Voice 구현, LLM provider integration, resume agent를 만들지 않는다.
8. runtime/framework는 저장소 확인 후 최소 선택한다. 작성 시 runtime setup이 없고 `python3`는 사용 가능했으나 `python` 명령은 없었다. 새 의존성이 필요하면 검증 목적과 재현 방법을 문서화한다.
9. JSON Schema를 억지로 완성하지 않는다. 미결정 필드를 임의 enum으로 고정하지 않는다. JSON 구조 검증과 참조/거버넌스/시간 전이 검증을 구분한다.
10. 원문이 허용한 fixture+문서 한정 경로를 선택하면 자동 검증 생략 이유와 대체 수동 검증의 실제 경로/결과를 남긴다. 확인 못 한 필수 기준을 완료로 체크하지 않는다.
11. 제품 구현, 사용자 실제 경력 수집, commit/push/배포는 승인 범위가 아니다. 기존 파일을 일괄 삭제·복원하지 않는다.

## 실행 상태와 handoff

각 단계 후 아래 행을 실제 근거로 갱신한다. 아직 실행하지 않은 체크리스트를 완료 표시하지 않는다. 파일을 읽고 완료 조건을 독립 확인한 다음에만 다음 단계로 간다. 실패를 건너뛰거나 sibling prompt package를 실행하지 않는다.

| Step | 상태 | 실제 모델/effort 근거 | 산출물·검사·미해결 사항 |
| --- | --- | --- | --- |
| 01 | COMPLETE | coordinator; requested Astra/high, observed unknown/unknown | main 4a9b6dd, 두 원문 존재·전체 독해; 계약/해시 조사 |
| 02 | COMPLETE | native spawn Sol/high; observed unknown/unknown | fixture 3개; coordinator 독립 SQL-required/FK/ID/contexts 검사 exit 0 |
| 03 | COMPLETE | coordinator; requested Astra/high, observed unknown/unknown | review export, snapshot, promotion, 게시 gate 최소 보완; fixture 오류 교정 |
| 04 | COMPLETE | coordinator; requested Astra/high, observed unknown/unknown | 14 state/9 질문/guard/ACC/TCN/A–C protocol; 수동 대조·state 검사 |
| 05 | COMPLETE | native spawn Sol/high; observed unknown/unknown | worker 19 tests exit 0; coordinator compound regression 추가 후 20 tests exit 0 |
| 06 | COMPLETE | coordinator; requested Astra/high, observed unknown/unknown | 원문 §27 대응표, README, 코드/diff/untracked/링크/입력 보존 검토 |

각 handoff에 입력 버전/해시, 변경 파일, 사용한 entity/enum, 재현 명령과 exit code, 기대/관찰 결과, 미해결 결정, 다음 단계에 허용된 범위를 포함한다. `BLOCKED_INPUT`, `BLOCKED_ROUTING`, 필수 기준 실패는 부분 결과와 재개 조건을 보고한다. 문서에 명시된 선택적 schema 생략과 실제 blocker를 구별한다.

## Decision log / Progress log

- 2026-09-21: main에는 README만 추적됨을 확인. 기존 untracked 입력은 보존한다.
- 2026-09-21: 지정 v1 Source of Truth 두 문서가 없어 신규 설계를 끼워 넣지 않고 01의 선행 조건으로 명시했다.
- 2026-09-21: exec-prompts의 coordinator/worker 구조에 맞춰 모델 배정, native spawn 인수, 관측·실패 처리 규칙을 추가했다.
- 2026-09-21: 현재 산출물은 프롬프트 패키지이며 schema/fixture/protocol 구현과 그 검증은 아직 수행하지 않았다.

## 최종 보고

실제 `$exec-prompts` 실행 완료 시 원문 §28의 Summary / Files Added / Files Modified / Schema Validation Result / Important Design Decisions / Tests / Validation / Remaining Open Decisions / Recommended Commit 구조를 사용한다. PASS/AMBIGUOUS/GAP/OVERMODELED를 구분하고, 미실행·생략 항목과 실제 모델 적용 결과를 포함한다. 추천 commit 문구만 제안한다: `docs: validate Career Graph v1 and define profiling protocol`.


## Execution evidence — 2026-09-21

- 최종 검토 완료: 2026-09-22 (Asia/Seoul). 20 tests 통과 및 11개 산출물의
  공백/로컬 링크/JSON/Python 구문 검사, 기존 입력 8개 해시 비교 모두 통과했다.
- 기존 authoring prerequisite 상태는 당시 기록이다. 실행 시 main은
  `4a9b6dd6162007b0b73311224c3712e9c4b5d237`이며 commit `4a9b6dd`가 두 v1 원문을 추가했다.
  checkout/reset/stash/clean/fetch는 수행하지 않았다.
- Step 01→02: 원문 두 문서의 시작 SHA-256와 entity/enum/nullable/relationship 계약은
  [validation §1](../../docs/career_graph_schema_v1_validation.md)에 기록했다.
  fixture writer는 §14 envelope 및 SQL row field, embedded contexts/targets를 사용했다.
- Step 02 agent_id/task: `/root/career_graph_fixtures`; requested_model=`gpt-5.6-sol`,
  requested_effort=`high`, observed_model=`unknown`, observed_effort=`unknown`.
  native spawn 인수는 확인했지만 런타임 적용값을 추정하지 않는다. 중단 후 final worker
  메시지가 보존되지 않아 coordinator가 세 파일 전체와 required/FK/ID 검사를 독립 확인했다.
- Step 02→03: 명시 review export와 historical reconstruction, promotion assessment/replay,
  publication gate의 모호성을 관찰했다. A OWNER→DECIDER, B 부정 경계→긍정 TCN 확인,
  C 수행→NONE 추론을 제거했다. source 없는 회사/기간/성과 수치는 null로 유지했다.
- Step 03→04: schema §28와 model §19로 기존 구조만 보완했다. fixture ClaimReview를
  추가하고 C compound leadership Claim은 팀 운영 한 사실로 좁혔다.
- Step 04→05: 14 states, 9 질문 유형, 정확한 확인/모순 처리/종료 guard를 전달했다.
  JSON Schema는 전체 interchange/API/protocol instance 계약 미정으로 생략하고,
  Python 3.14.4 stdlib 참조 검사로 한정했다. 외부 검증 상태는 fail closed다.
- Step 05 agent_id/task: `/root/career_graph_validation`; requested_model=`gpt-5.6-sol`,
  requested_effort=`high`, observed_model=`unknown`, observed_effort=`unknown`.
  worker write scope는 tests/뿐이며 peer 통신/재위임 없이 coordinator가 검토했다.
- Step 05→06: worker 결과 19 tests 통과를 coordinator가 재실행했다. compound Claim
  회귀 검사 추가 후 최종 **20 tests, failures 0, errors 0, skipped 0, exit 0**.
  명령: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.
- 직접 실행 단계의 agent_id=`coordinator`, requested_model=`gpt-6-astra`,
  requested_effort=`high`; observed_model/effort=`unknown`. 로컬 catalog 및 native 도구에서
  두 요청 모델의 high 지원을 확인했다. 모델을 자동 대체하거나 별도 CLI로 우회하지 않았다.
- 자동 검증 범위는 fixture/ref model이며 DB/실사용자 인증/실제 외부 검증/일반 자연어 의미
  검증이 아니다. 새 Claim은 승인 후에도 별도 boundary review 전 REVIEW_REQUIRED다.
  기존 Claim 병합/모순 해소는 protocol에 정의하고 참조 구현은 차단한다.
- 최종 수정 파일: README, 두 v1 문서, validation 보고서, profiling protocol, 세 fixture,
  tests의 두 파일, 선택 패키지 main. 기존 개발 계획서/요청 원문/step 파일은 보존했다.
  최종 ID 경로, gap 분류, 검사 대응, 남은 제품 구현 결정은 validation 보고서에 있다.
- commit/push/배포는 수행하지 않았다. 다른 prompt package는 읽거나 실행하지 않았다.

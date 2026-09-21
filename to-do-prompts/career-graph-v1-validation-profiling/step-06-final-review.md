---
step: 6
depends_on: [1, 2, 3, 4, 5]
executor: coordinator
model: gpt-6-astra
reasoning_effort: high
---

# Step 06 — 최종 검증·문서 일관성·결과 보고

## 목표와 기준선

main 기준 및 실행 시작 시 사용자 변경과 비교하여 이번 범위의 산출물을 검토한다. Astra/high coordinator가 직접 수용 기준과 증거를 대조한다. [main.md](main.md)의 모델·완료 계약을 따른다.

## 확인 범위

원문 전체(특히 §21–28), v1 두 문서, validation 보고서, profiling protocol, fixtures, 생성했다면 schemas/tests/dependency 파일, README, 단계별 실제 실행 결과를 읽는다.

## 실행 지시

1. 원문 §27의 모든 체크 항목을 증거 파일/section, fixture ID, test 또는 수동 검증 결과와 연결한다. 누락 항목은 수정하거나 blocker/정당한 생략으로 명시한다. 임의 PASS는 금지한다.
2. Claim→Evidence, Resume reverse trace, JD trace, ownership 경계, Candidate 격리/승격, contradiction 보존, historical artifact version 재현을 보고서에서 실제 ID로 따라가 본다.
3. validation 보고서가 원문의 10개 섹션을 갖추고 네 분류 PASS/AMBIGUOUS/GAP/OVERMODELED와 변경 이유, 수정 전후 결과, 남은 결정을 구별하는지 확인한다.
4. profiling protocol의 state/guard/질문/필드/확인/종료가 최종 schema 및 테스트와 일치하는지 확인한다. UNKNOWN, USER_CLAIMED, USER_CONFIRMED, EXTERNALLY_VERIFIED, INFERRED와 usage/consistency 축을 혼동하지 않는다.
5. README가 여전히 단순하고 이전 단계 산출물이 갖춰졌다면 최소 수정한다: Evidence-backed Career AI System, 현재 domain/schema validation 상태, 네 핵심 문서 링크, evidence traceability 원칙. fixture 목적과 검증 실행 방법은 실제 산출물이 있을 때 재현에 필요한 만큼만 추가하거나 validation 보고서로 연결한다. 구현하지 않은 제품 기능을 제공한다고 쓰지 않는다. 앞 단계가 BLOCKED이면 이 단계와 README 수정도 수행하지 않는다.
6. Step 05에서 확정한 검사 명령을 coordinator가 실행하여 통합 결과를 확인한다. 이미 같은 최종 내용으로 직접 확인한 결과는 불필요하게 반복하지 않는다. 결과를 바꾸는 수정이 생기면 영향을 받는 검사만 재실행한다.
7. 다음 Git 검사를 수행한다: `git status --short --untracked-files=all`, `git diff --check`, `git diff`. **untracked 신규 파일은 git diff에서 빠지므로** 각각 읽고 공백/내용/링크/JSON 검사를 별도로 수행한다. untracked 기존 사용자 입력은 시작 해시/내용과 비교하여 의도하지 않은 변경이 없는지 확인한다.
8. 생성 문서의 로컬 링크, fixture parsing, 테스트 수집 수, 빈 디렉터리/불필요한 dependency, scope 밖 변경을 확인한다. 문서·테스트에 쓰인 예시가 실제 사용자 확인이나 운영 검증으로 서술되어 있으면 고친다.
9. 이 패키지 main의 단계 상태를 실제 관측 증거로 갱신한다. 요청 모델과 관측 모델/effort가 다르거나 모르면 그대로 기록한다. 프로덕션 기능 완성이나 모델 적용을 근거 없이 주장하지 않는다.
10. 원문 §28 형식으로 실제 수행 결과만 보고한다. 최종 보고에 자동화 생략/미실행 검사, 수동 검증 한계, 구현 전 필요한 결정만 남긴다. commit은 수행하지 않고 추천 메시지만 제안한다.

## 제약과 산출물

허용 쓰기는 README, validation 보고서, 패키지 상태 및 앞 단계에서 근거가 확인된 범위의 수정이다. 검토 중 새 문제가 나오면 해당 단계로 돌아가 최소 수정·재검증한다. commit/push/배포/전면 refactor는 하지 않는다.

## 완료 기준

- [ ] 원문 §27 모든 기준에 실제 증거 또는 원문이 허용한 생략 근거가 있다.
- [ ] 필수 traceability/ownership/candidate/contradiction/version 검증 실패가 남아 있지 않다.
- [ ] validation 보고서와 profiling protocol, 두 v1 문서, fixture/test 용어가 일치한다.
- [ ] README 링크가 실제 산출물로 연결되고 검증 방법이 재현 가능하다.
- [ ] 실행한 검사와 exit code, 결과 수, 미실행/생략/수동 검증 범위를 정확히 보고했다.
- [ ] git diff 및 untracked 파일까지 검토하고 기존 unrelated 입력을 보존했다.
- [ ] 단계별 모델 요청/관측 결과와 남은 결정이 정리되었다.
- [ ] 추천 commit 메시지만 제안했고 commit/push는 수행하지 않았다.

## 최종 handoff

다음 구현 작업의 입력은 네 핵심 문서, 세 fixtures, 실제 존재하는 schema/tests 및 검증 결과다. 현재 단계의 완료를 Resume/JD/Voice 제품 구현 승인으로 해석하지 않는다.

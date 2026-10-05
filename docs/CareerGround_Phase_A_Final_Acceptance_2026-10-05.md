# Phase A 1~5 최종 수용 진행 결과

기준 HEAD `d88ad6255eb110cd265b0cc26c581578bc7564a0`,
브랜치 `codex/mvp-foundation-ci-20260923`. 기존 미커밋 작업을 보존해 이어서 진행했다.
**자율 진행 가능한 구현·로컬 검증 완료, 실제 외부 수용/Phase A 전체 완료는 미선언**이다.

2026-10-05 사용자 결정으로 **OTP MFA는 보류**한다. 기존 trial 시험 승인 요청은 종료했고 Auth0 MFA 설정 변경은 없다. 검증 가능한 삭제 재인증의 무료 대안은 아직 결정하지 않았으며 삭제 수용은 미완료다.

## 순서별 결과

| 단계 | 이번에 수행한 일 | 실제 완료에 남은 것 |
| --- | --- | --- |
| 1 삭제 인증 | BrowserOS 관리자 로그인 후 Free/$0·trial 11일·MFA off/Never 확인. 삭제용 acr 요청/signed mfa 전용 모드·거부와 최종 승인 검증. OTP는 사용자 결정으로 보류 | 무료 재인증 대안의 계정 호환성 검토·경로 결정, 실제 합성 삭제·재시작 |
| 2 격리·철회 | 검증 후 connection denial hook와 separate private signed registry. 재시작·새 token·변조 차단, 다른 계정/client/Web 유지 시험. 실제 범위/공유 grant 영향 문서화 | 실제 runtime 연결·사용자 철회 경로, 두 번째 identity·실제 교차 접근/disconnect·grant 철회/만료 관측 |
| 3 품질 | 기존 6건 기대값·지침 충돌 검토. 새 8개를 기대값 숨긴 실제 임시 ChatGPT 대화에서 관측, 6/8 action 일치 | label 기준/합격선 확정, 독립 의미 보존·자연스러움 판정과 필요한 새 blind 평가 |
| 4 보관·운영 | 인증 개발 runtime의 선택형 bounded physical expiry 연결. 만료 raw 입력/session 제거와 승인 Claim/Evidence·재시작 보존 시험. 운영 범위별 차이 정리 | 실제 자료/공개 사용 범위와 지속 가능한 삭제 인증, 보관·처리·복원·비용·운영 증거 결정 |
| 5 최종 검증 | 최신 PostgreSQL 453 PASS/skip0, migration upgrade/check, 38 product tables/0 rows. CI와 같은 Ruff 194 files·diff PASS | 위 실제 인증/연결을 포함한 BrowserOS 제품 통합, commit/push 별도 승인 뒤 GitHub CI와 최종 수용 |

큰 단계의 외부 완료를 로컬 준비 완료와 바꾸지 않았다. 전체 Phase A/main merge/공개 출시를 승인하지 않았다.

## 구현 경계

- `--require-development-deletion-mfa`: persistent PROFILE 삭제 선택 옵션이 있어야 시작된다.
  일반 로그인에는 acr를 붙이지 않는다. 요청만으로 제공자 MFA를 보장하지 않으며 signed mfa 없는
  결과는 거부한다. 최근 인증·같은 계정·정확한 영향과 version·별도 최종 확인은 유지했다.
- 기존 password-or-MFA 합성 검증 모드와 구분한다. 실제 MFA 수용 실행에는 새 옵션이 필수다.
- connection denial backend는 exact issuer/subject/client의 keyed digest를 private directory에
  저장한다. 기존 실제 runtime에 자동 활성화하지 않았다. 전체 directory rollback·다중 worker·
  이미 진행 중인 요청 취소/제공자 grant 폐기를 이 backend가 해결했다고 주장하지 않는다.
- `--allow-development-retention`: 별도 persistent 개발 store 전용, 원문 없는 aggregate log,
  최대 100세션 sweep/hour slot, 재시도는 기존 outbox에 따른다. query-time 만료 거부와 구분된다.
  runtime이 꺼지면 worker도 꺼진다. 원래 실제 QA store에는 적용하지 않았다.
- MCP 실제 삭제는 아직 `REVIEW_REQUIRED`, local erase coverage는 `FOUNDATION_ONLY`다.

## 새 검증 기록

PostgreSQL 17.11 공식 source와 SHA-256을 확인하고 `/tmp`에 사용자 권한으로 빌드했다.
필요한 build 도구도 해당 private 경로에만 추출했다. 시스템 설치·sudo·Docker·운영 DB는 사용하지 않았다.
[공식 source/checksum](https://ftp.postgresql.org/pub/source/v17.11/),
[공식 build 안내](https://www.postgresql.org/docs/17/install-make.html)

새 임시 loopback `careerground_test`에서 명시적 `CAREERGROUND_REQUIRE_POSTGRES_TEST=1`을 적용했다.

```text
alembic upgrade head: PASS
alembic check: PASS
revision: 20261003_0020
unittest discover: 453 tests, 91.239 seconds, OK, skipped 0
product tables: 38, total rows: 0
CI Ruff check: PASS
CI Ruff format: 194 files already formatted
git diff --check: PASS
```

중간 451 PASS 후 retention 보강 때문에 전체를 한 번 더 실행했다. 마지막 결과만 453이다.
로컬 인증 관련 44개, retention/persistent store 8개와 connection 3개도 별도 관련 검증을 했다.
이는 실제 provider MFA/두 계정 시험을 대신하지 않는다.

BrowserOS에서는 기존 Auth0 관리자 화면을 읽기 전용으로 확인하고 새 임시·비개인화 ChatGPT
대화에 합성 사례만 전송했다. 실제 제품 도구·canonical 저장·승인은 없었다. 모델 API 호출 0,
새 유료 자원 생성 0이다. 기존 ChatGPT 구독 UI의 사용량은 발생했으며 청구 전체를 보증하지 않는다.

## 비용과 다음 요청

Subscription의 현재 플랜은 Free/$0, 기존 trial banner는 11일 남음이다. OTP는 Pro MFA이며
지속 무료로 제공되는 기능이 아니다. [Auth0 가격표](https://auth0.com/pricing)

기존 trial 내 OTP/Action 한시 시험·원복 제안은 사용자 결정으로 보류했다. 현재 OTP 설정 승인 요청은 없다.
결제·업그레이드·trial 연장·MFA 설정 변경은 수행하지 않았다.

완료 범위를 정리하고 무료 삭제 재인증 대안을 검토한 뒤, 실제 두 번째 개발 identity/철회 범위·품질 판정과 최종 수용을 진행해야 한다.
현재 Google 로그인 반복만으로 삭제에 필요한 추가 인증 성공을 입증하지 못했다. 대안은 계정 연결과 서명된 인증 증거를 검증한 뒤 결정해야 한다.

## 문서와 보존

- [지속 계획](../PLAN-2026-10-05-phase-a-final-acceptance.md)
- [MFA 변경·원복안](CareerGround_Phase_A_MFA_Change_2026-10-05.md)
- [계정·철회·갱신](CareerGround_Phase_A_Connection_Acceptance_2026-10-05.md)
- [품질 불일치/새 관측/판정 제안](CareerGround_Phase_A_Quality_Review_2026-10-05.md)
- [보관·운영 범위](CareerGround_Phase_A_Operating_Scope_2026-10-05.md)
- [기계 판독 관측 metadata](phase_a_final_acceptance_observations_20261005.json)

45개 기존 설정·ignored 초안·이전 QA 자료의 hash 변경 0이다. `to-do-prompts/`, `intent-docs/`를
보존했다. 실제 삭제 QA store의 이전 데이터도 삭제하지 않았다. 테스트 DB는 정상 중지했고
credentials/build/cluster는 정리했다. BrowserOS 사용자 앱과 관리자 탭은 유지한다.
CareerGround Web/MCP/기존 테스트 DB 포트 5000/8001/55432는 닫혀 있다.
commit/push/merge·새 tunnel·서버 AI·공개 배포는 수행하지 않았다.

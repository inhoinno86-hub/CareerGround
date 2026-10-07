# 개인 비공개 MVP 수용 후속

## 범위

사용자가 권장 1~5번 순차 실행을 요청했으므로 우선 개인 비공개 ChatGPT 대화 + CareerGround Web의 합성 텍스트 MVP를 수용 대상으로 정리했다. 실제 경력 자료 사용·공개 서비스 출시·기존 formal Gate A의 운영 수용은 별도 미완료 상태다. OTP MFA·유료 서버 AI·refresh 도입은 보류한다.

## 삭제 재인증

**최신 실제 기기 시험:** 사용자가 새 빈 QA에서 등록된 기기 패스키 확인과 별도 최종 삭제 승인을 완료했다. BrowserOS 결과 화면과 서버의 PROFILE 삭제 요청 **1건**, erasure ledger **1건**을 확인했다. CAREER_PROFILE·PROFILE_LOCAL_DATA의 ERASE와 PROFILE_ARCHIVE의 VERIFY 작업은 모두 DONE이다. Claim/Evidence/ProfilingInput·profile archive rows는 0이다. 빈 프로필 시험이므로 실제 기기로 내용이 있는 경력 자료를 삭제했다는 증거는 아니다.

coverage는 **FOUNDATION_ONLY**다. UNVERIFIED_SCOPE의 VERIFY는 PENDING이고 프로필/삭제 요청은 DELETING으로 남는다. 알려진 로컬 처리 성공과 전체 외부 사본·백업 삭제 완료를 구분한다. MCP 삭제 승인 증명이나 제공자 계정 삭제는 실행하지 않았다. 기존 설정·초안·이전 QA 파일 45개의 hash도 유지됐다. 아래 0건/등록 미확정 기록은 이전 단계의 이력이다.

- 기존 Google identity를 유지하는 별도 opt-in WebAuthn registry와 화면 경로를 구현했다. 공개키만 별도 private 경로에 저장하며 정확한 origin/격리 store에 묶는다. 최초 등록은 fresh same-owner OIDC와 명시적 사용자 기기 확인을 요구한다.
- 기존 signed auth_time/소유자/세션/프로필 버전/영향 hash/일회성 요청/별도 최종 확인과 삭제 checkpoint는 유지한다. 새 패스키 모드는 OTP MFA 요청을 추가하지 않는다. 기기 분실/교체 복구는 준비되지 않았다.
- CBOR/ECDSA 실제 proof의 부정/재시작 검증과 기존 경로 포함 관련 35 PASS, 이후 장치 경로 8 PASS와 추가 준비 조건 시험 8 PASS를 확인했다. 이 숫자는 서로 겹치는 부분 실행이며 합산하지 않는다.
- BrowserOS 새 합성 탭에서 CDP 가상 인증기로 등록 → 최근 동일 계정 인증 → 새 기기 서명 → 별도 최종 승인 → 로컬 PROFILE 삭제 결과를 확인했다. 가상 인증기는 실제 사용자 기기 시험을 대신하지 않는다.
- 사용자가 비공개 합성 QA의 패스키 시험 정책을 승인했다. 새 QA 환경에서 직접 빈 프로필을 생성했다. 기존 실제 QA 자료는 변경하지 않았다.
- 현재 BrowserOS의 platform authenticator 탐지는 `false`였다. 사용자가 휴대전화/Bluetooth로 확인 절차를 진행했지만 첫 확인 당시 서버 등록은 0, 삭제/ledger는 0이고 등록 요청 화면은 409였다. 기기 절차만으로 서버 등록 완료라고 판단하지 않았다. 만료 가능성을 안내하고 새 등록 요청을 준비했으며 최종 등록 결과는 미확정이다.

[등록·분실·복구 정책](CareerGround_Phase_A_Deletion_Passkey_Proposal_2026-10-05.md)

### 등록 오류 후속 확인

**등록 완료 당시 기록:** 사용자 재등록 후 같은 QA store의 패스키 공개키 등록 **1개**와 BrowserOS의 ‘패스키가 등록돼 있습니다’ 화면을 함께 확인했다. 이 시점의 삭제 요청/erasure ledger는 **각각 0**이었다. 이후 실제 기기 확인·최종 로컬 삭제를 완료한 결과는 위 ‘최신 실제 기기 시험’에 기록했다. 아래 등록 0건 기록은 이전 오류 관측이다.

다시 확인한 서버 패스키 등록도 0이었다. 최신 오류는 `/security/development/passkey/reauth`의 409로 기기 확인 전 제출이 거부됐다. 180초 제한을 유지하고 오래되거나 변경된 검토 form에 전용 재시작 화면과 새 검토 링크를 제공하도록 수정했다. 기기/Bluetooth 준비와 3분 제한을 화면에 표시했다. 만료 form 거부·새 검토 성공 회귀를 포함한 패스키 9 PASS와 변경 두 파일 Ruff check/format, diff check를 확인했다. 앞선 전체 PostgreSQL 463 PASS는 이 안내 수정 전 결과다.

runtime은 같은 QA store/공개키 registry를 보존해 재시작했다. 사용자의 일반 로그인 후 새 등록 검토 화면을 열었다. 실제 기기 등록 결과는 기다리는 중이다. 등록 확인 당시 삭제/ledger도 0이며 실제 사용자 등록·삭제 수용은 아직 미완료다. 기존 설정·초안·이전 QA 파일 45개의 hash는 모두 유지됐다.

## 연결 차단·격리

- opt-in registry를 실제 Auth0 개발 runtime에 주입할 수 있게 연결했다. 관리 화면에서 로그인한 소유자의 정해진 client만 차단하며 account/client 식별자를 form에서 받지 않는다.
- 공유 client의 두 ChatGPT 앱에 대한 영향, Web 로그인/자료 보존, provider grant 자체는 폐기하지 않는 점과 차단 해제 미구현을 화면에 명시했다.
- 서명 검증을 통과한 MCP 요청이 차단 이후/재시작/새 토큰에서도 거부되고 다른 계정/client 및 Web은 유지되는 HTTP 시험을 통과했다. BrowserOS 합성 계정의 차단 검토/처리 화면도 확인했다.
- 실제 사용자 두 identity, 실제 ChatGPT 연결 차단·disconnect·provider grant·만료는 미완료다. 새 실제 QA runtime에는 차단 옵션을 활성화하지 않았다. refresh는 보류한다.

## 품질

**후속 관측:** 새로운 36개를 BrowserOS 임시·비개인화 ChatGPT 대화에서 한 번 관측해 분류 **36/36**, task별 **9/9** 일치를 확인했다. 기대 label/invariant는 모델에 제공하지 않았다. 기존 관측은 보존했다. 이 결과는 현재 source 계약을 입력한 합성 관측이며 실제 설치 plugin이나 전체 제품 품질 수용은 아니다. 사람 검토용 HTML과 JSON 내보내기 생성기를 준비하고 BrowserOS에서 36개 표시·미판정 상태·script 문법을 확인했다. 사람 의미·자연스러움/기준 수용은 미완료여서 quality gate는 false다. 아래 ‘관측 전’ 문장은 이전 준비 단계의 이력이다.

- 단일 분류 우선순위를 source skill에 명확히 했다. 금지된 사용은 REJECT, 경력 후보 아님은 EXCLUDE, 정당한 새 사실은 FACT_REVIEW, 현재 JD 근거 부족은 GAP, 사실 불확실성은 FOLLOW_UP이다. JD 공백과 확인 질문을 구분하고 공동 기여·미수행 조건을 제안에도 보존한다.
- 원래 fixture·관측·점수는 유지했다. 새 task별 9개, 총 36개 fixture를 관측 전에 저장했다. 새 기준·사람 판정은 아직 수용 미완료이며 실제 ChatGPT 관측과 분리한다.
- 기존 비공개 설치 plugin을 이번 변경 source로 갱신했다고 주장하지 않는다.

## 통합 검증

새 임시 PostgreSQL 17.11에서 migration upgrade/check, 최신 전체 **463 PASS/실패·skip 0**을 확인했다. 초기 실행은 테스트 전용 URL 변수 누락으로 PostgreSQL 필수 검사 35개가 실패했고, `CAREERGROUND_TEST_DATABASE_URL`을 같은 격리 `_test` DB로 지정한 뒤 전체를 재실행했다. 제품 코드 실패를 숨기거나 skip으로 대체하지 않았다. 임시 DB는 정상 중지했다.

최종 정적 검사·전체 보존/정리 결과 및 실제 기기/품질/연결 수용 상태는 후속 기록한다. commit/push/merge와 최신 작업 트리의 원격 CI는 별도 요청 전 수행하지 않는다.

후속 정적 검사는 CI와 같은 Ruff check/format **201 files PASS**, diff check PASS다. 중지된 rootless PostgreSQL build/source/cluster와 전용 build/test helper를 제거하고 sanitized test log/result는 보존했다. 실제 QA runtime과 삭제 추적 store는 후속 확인을 위해 유지했다. 실제 기기 빈 QA 삭제 시험은 FOUNDATION_ONLY 범위에서 통과했으며 실제 두 identity·연결 철회/만료와 사람 품질 수용은 남아 있다. 이 기록 작성 시점에는 원격 CI/commit/push를 수행하지 않았다.

## 커밋 직전 확인

사용자가 2026-10-05 현재 변경의 commit/push를 명시적으로 요청했다. 대상은 기존 `codex/mvp-foundation-ci-20260923` 브랜치다. Phase A 전체 완료 또는 main merge 승인을 의미하지 않는다.

- 삭제·패스키·연결 차단·영속 store·ChatGPT 제안·OIDC·관리 화면 관련 회귀 **66 PASS**.
- CI와 같은 Ruff check/format **201 files PASS**, diff check PASS.
- 변경 파일의 비밀값·실제 계정 식별자 및 현재 Auth0 설정 값 검사에서 발견 없음.
- 기존 설정·초안·이전 QA 파일 **45개 hash 유지**. 새 커밋에 로컬 설정·QA DB·무시된 초안을 추가하지 않는다.
- 원격 branch와 기준 HEAD의 분기 차이는 0/0이었다. 커밋 hash와 push/원격 CI 결과는 실행 후 별도로 확인한다.

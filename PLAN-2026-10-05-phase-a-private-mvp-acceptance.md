# Phase A 비공개 MVP 수용 후속

사용자가 직전 안내의 1~5번 순차 진행을 요청했다. 기준 HEAD는 `d88ad6255eb110cd265b0cc26c581578bc7564a0`이다. 이전 미커밋 작업과 ignored 초안·설정·QA store는 보존한다.

## 범위와 승인 경계

- 우선 수용 범위는 개인 비공개 ChatGPT 대화 + CareerGround Web의 합성 텍스트 MVP다. 실제 경력 사용·공개 배포·기존 formal Gate A의 운영 수용은 별도 미완료 상태로 유지한다.
- OTP MFA·서버 AI·refresh 도입은 보류한다. 유료 자원·새 운영 자원·provider MFA 설정은 만들지 않는다.
- 무료 대안은 현재 Google identity를 유지하는 삭제 전용 WebAuthn을 로컬 합성 계정에서 검토·구현한다. 실제 사용 전 최초 등록 신뢰·기기 분실/복구·origin 고정 정책을 구체적으로 검토받는다. 기존 signed 인증·소유권·영향·별도 최종 확인 검증은 유지한다.
- 두 계정 합성 검증과 실제 사용자 identity 시험을 구분한다. 기존 두 ChatGPT 앱이 공유하는 client 차단/제공자 철회는 실제 적용 전 영향과 복구 절차를 확인한다.
- 사람 품질 평가를 수행자 자체 판정으로 대체하지 않는다. 과거 fixture/관측/점수는 변경하지 않는다.
- commit/push/merge는 별도 명시 요청 전 수행하지 않는다.

## 실행 순서

- [x] 1 개인 비공개 MVP 수용 범위와 별도 운영 gate 상태 정리
- [x] 2 무료 삭제 재인증: 공식 규격/현재 계정 호환성 검토, 별도 opt-in 구현, 부정/재시작/브라우저 검증, 실제 등록 정책 검토 (승인된 빈 QA에서 실제 기기 확인·최종 로컬 삭제 처리 확인, FOUNDATION_ONLY)
- [ ] 3 계정 격리·연결 차단 runtime/UI 경로 준비와 합성 시험, 실제 두 identity/철회·만료 관측은 사용자 단계 구분
- [ ] 4 단일 분류 우선순위 명확화, 새로운 관측과 사람이 확인할 평가 화면 준비, 최종 품질 수용 상태 기록
- [ ] 5 변경에 필요한 통합 회귀·BrowserOS 시험, 보존/정리 확인, 결과 보고 및 원격 CI 별도 상태

## 기존 증거 재사용

이전 전체 PostgreSQL 453 PASS/skip 0, Ruff 194 files, 제품 ChatGPT–Web 왕복·재시작 시험을 재사용한다. 새 코드 변경으로 영향받는 검증만 먼저 수행하고, 통합 회귀는 마지막에 실행한다.

## 진행 증거

- 커밋 요청 후속: 사용자가 현재 변경 commit/push를 명시적으로 승인했다. 기존 작업 branch로 진행하며 Phase A 전체 수용·main merge는 남은 상태다. 커밋 전 관련 회귀 66 PASS, CI와 같은 Ruff check/format 201 files·diff check PASS, 현재 인증 설정 값/비밀값/실제 계정 식별자 검사 발견 없음과 보존 파일 45개의 hash 유지를 확인했다. 실제 push·원격 CI 결과는 이후 Git 상태/CI에서 확인한다.

- 품질 후속: 새 36개 BrowserOS 임시·비개인화 ChatGPT 관측 분류 36/36(task별 9/9), 과거 점수 보존. 원문·응답·hash 기록과 사람 검토 HTML/생성기를 준비했다. BrowserOS 36 cards/109 required selections/모두 미판정/내보내기 script 문법 확인. 기준 수용·사람 의미/자연스러움 평가는 미완료다.
- 정리 후속: CI와 같은 Ruff check/format 201 files·diff check PASS. 중지된 owned PostgreSQL build/cluster/helpers 제거, sanitized logs/results 유지. 실제 QA runtime/store는 후속 확인용 유지. commit/push는 미수행이다.

- 실제 삭제 후속: BrowserOS 결과 화면과 같은 QA store에서 PROFILE 삭제 요청 1/ledger 1, CAREER_PROFILE·PROFILE_LOCAL_DATA ERASE 작업 DONE, PROFILE_ARCHIVE VERIFY DONE을 확인했다. Claim/Evidence/ProfilingInput·archive rows는 0이다. UNVERIFIED_SCOPE VERIFY는 PENDING이고 profile/request는 DELETING이다. FOUNDATION_ONLY의 알려진 로컬 처리 시험만 통과했으며 전체 외부 사본 삭제/제공자 계정 삭제는 미수행이다. 기존 파일 45개의 hash는 유지됐다.

- 실제 기기 등록 후속: 사용자의 등록 완료 보고 뒤 같은 QA store에서 공개키 등록 1개와 BrowserOS 등록 완료 화면을 확인했다. 삭제 요청/erasure ledger는 각각 0이다. 실제 기기 등록은 확인됐지만 삭제 서명·최종 삭제 시험은 별도 남아 있다.

- 삭제 전용 패스키 opt-in registry·최초 등록·새 서명·별도 최종 확인 구현. 실제 CBOR/ECDSA 부정·재시작/세션/만료 시험 통과. BrowserOS 합성 가상 인증기에서 PROFILE 삭제 결과까지 확인.
- 사용자가 비공개 합성 QA의 패스키 정책을 승인하고 새 빈 프로필을 직접 생성했다. 현재 BrowserOS platform authenticator 탐지는 false다. 휴대전화/Bluetooth 진행 후 첫 확인에서는 서버 등록 0/삭제 0과 409를 확인해 새 등록을 요청했다. 실제 기기 수용 완료로 표시하지 않는다.
- 연결 차단 runtime 주입·소유자 Web 차단 검토 경로 구현, 합성 account/client/CSRF/서명 HTTP/재시작 시험 통과. 실제 공유 client 차단·제공자 철회는 미수행.
- 분류 충돌을 source skill의 우선순위로 명확히 하고, 새로운 36개/각 task 9개 fixture를 관측 전에 저장했다. 과거 점수는 유지하며 새 실제 관측/사람 판정은 별도 진행한다.
- 최신 전체 PostgreSQL 463 PASS/실패·skip 0, upgrade/check, 제품 38 tables/0 rows, 임시 DB 정상 중지. 초기 테스트 URL 변수 누락 실패는 수정 후 전체 재실행으로 해결했다.
- CI와 같은 Ruff check/format 200 files 및 diff check PASS.
- 후속 실제 확인에서도 서버 패스키 등록은 0이었다. 재인증 시작 POST가 409를 반환했다. 검토 form은 180초 제한이며 기기 확인 전에 오래된 화면을 제출해도 거부된다. 제한은 유지하고 전용 재시작 안내·새 검토 링크·준비 순서를 추가했다. 관련 패스키 9 PASS, 두 변경 파일 Ruff check/format·diff check PASS. 기존 QA store를 보존해 runtime을 재시작했고 사용자 일반 로그인 후 새 등록 검토를 열었다. 앞선 전체 PostgreSQL 463 PASS는 이 안내 수정 전 결과다.

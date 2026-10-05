# Phase A 최종 수용 작업

사용자가 권장 1~5번의 순차 실행을 승인했다. 기준 HEAD는
`d88ad6255eb110cd265b0cc26c581578bc7564a0`이며 기존 미커밋 구현과 초안을 보존한다.

## 실행 경계

- ChatGPT 대화 + CareerGround 관리 화면을 유지하며 서버 AI는 보류한다.
- 2026-10-05 사용자 결정: OTP MFA는 Phase A에서 보류한다. 기존 trial 시험/원복 승인 요청도 종료하며 외부 MFA 설정을 변경하지 않는다. 삭제 인증 대안은 아직 결정하지 않았다.
- 기존 Auth0 개발 자원의 읽기 전용 점검과 로컬 구현·합성 시험은 진행한다.
- MFA Action/factor/policy, 계정 추가·grant 철회·토큰 정책 등 외부 변경은 구체 변경안 준비 후 필요한 승인만 요청한다.
- 사용자 로그인·MFA 등록/입력은 직접 수행하게 한다. 비밀번호·토큰·전체 HAR을 수집하지 않는다.
- 운영/유료 자원 생성·실제 사용자 경력 자료·공개 배포는 진행하지 않는다.
- commit/push/merge는 별도 명시 요청 전 수행하지 않는다. 변경 후 원격 CI는 해당 단계에서 구분한다.
- ignored to-do-prompts/intent-docs, 기존 설정과 이전 QA store의 45개 보존 hash를 유지한다.

## 순서와 완료 기준

- [ ] 1 OTP MFA 보류 유지, 무료로 가능한 삭제 재인증 대안의 현재 계정 호환성 검토, 경로 결정 후 구현·실제 합성 삭제/재시작 검증
- [ ] 2 실제 두 계정 격리·연결 해제/철회·만료 검증, refresh 필요성 결정과 로컬 차단 구현
- [ ] 3 분류 불일치 6건·품질 기준 검토, 독립 새 사례 시험과 필요한 사람 판정
- [ ] 4 보관·삭제·복원·운영 조건의 구현/정책 차이 확인, 로컬 보강과 공개 운영 범위 결정 자료
- [ ] 5 마지막 변경 기준 전체 PostgreSQL/BrowserOS 통합 검증, 변경 검토·완료 보고, 원격 CI 및 최종 수용 상태 구분

이미 완료된 과거 441개 PostgreSQL, 39개 인증, 11개 삭제, 제품 왕복·품질 관측은
새 실행과 구분한다. 외부 승인 대기 중에도 해당 단계의 독립된 로컬 준비·검증을 진행한다.

## 이번 실행 기록

- [x] 1 준비: 관리자 로그인 후 BrowserOS 읽기 전용 MFA/구독 점검. Free/$0,
  당시 기존 trial 11일 남음, OTP/Recovery off, policy Never. 이후 사용자 결정으로 OTP 시험/원복 요청은 보류로 종료.
- [x] 1 로컬: 삭제 전용 MFA acr 요청과 signed mfa 강제 선택 옵션, password-only 거부·별도 최종 승인 시험.
- [x] 2 로컬: 검증된 account/client 차단 경계와 별도 private signed registry,
  재시작/새 토큰/변조 거부·A/B 격리 시험. 실제 runtime 활성/제공자 철회 미수행.
- [x] 2 준비: 공유 CIMD grant의 PoC/제품 앱 동시 영향, 실제 2계정 절차·refresh 보류 권고 정리.
- [x] 3 관측: 기존 6건 분류/지침 충돌 검토. 관측 전 새 8개 fixture 작성,
  BrowserOS 임시·비개인화 ChatGPT 대화 한 번 시험, action 6/8. 기준/독립 사람 판정은 미완료.
- [x] 4 로컬: authenticated persistent 개발 runtime의 bounded retention 선택 옵션.
  만료 원문/session 제거, 승인 Claim/Evidence 보존과 재시작 시험. 기존 실제 QA store는 미변경.
- [x] 4 준비: private 개발/실자료 개인/공개 운영의 범위와 미확정 보관·복원·비용 조건 정리.
- [x] 5 중간: PostgreSQL 17.11 사용자 권한 임시 빌드, migration upgrade/check,
  451 PASS/skip 0, 제품 38 tables/0 rows. 이후 retention 추가분의 마지막 전체 실행은 별도 기록 예정.
- [x] 5 최종 로컬: retention 보강 후 PostgreSQL 전체 **453 PASS/실패·skip 0**,
  migration `20261003_0020`, 제품 38 tables/0 rows. 임시 DB 정상 중지.
- [x] 정적 검사: CI와 같은 Ruff check/format 194 files 및 diff check PASS.

OTP 보류로 삭제 수용 기준을 완화하지 않았다. 무료 삭제 재인증 대안의 결정·실제 시험, 실제 두 번째 개발 identity와 철회 범위,
품질/운영 범위 결정 및 commit/push 승인 없는 원격 CI는 완료하지 않았으므로
위의 큰 단계 checkbox는 유지한다. 새 유료 자원·서버 AI·공개 배포는 없다.

# Phase A 영속 계정 → 실제 제품 연결 → 제안 품질 → 수용

사용자가 2026-10-04 권장 순서 1–4의 수행을 요청했다.
시작 HEAD: `d88ad6255eb110cd265b0cc26c581578bc7564a0`.

## 경계

- ChatGPT가 대화·제안을 담당한다. 서버 AI·유료 자원·실제 경력 자료·운영 연결은 보류한다.
- 기존 ignored 초안, 개발 store, 인증/tunnel 설정은 보존한다.
- 새 commit/push/merge 또는 공개 배포는 이번 작업에 포함하지 않는다.
- 외부 Auth0 권한 변경·필수 로그인/동의만 구체적인 준비 후 한 단계씩 요청한다.
- 실제 두 번째 계정 생성은 기존 결정대로 보류한다. 합성 격리를 실제 시험으로 표시하지 않는다.

## 순서·완료 기준

1. 별도 owner-only 영속 인증 개발 store: 계정/프로필/키/삭제 checkpoint 유지,
   재시작 후 재로그인, 기존 cookie 차단, 설정 바인딩·잠금·복원 거부 검증.
2. 기존 제품 OAuth metadata/scope/터널을 읽기 전용 확인한다. 로컬 안전한 실제 JWT
   MCP 진입점을 준비하고 외부 변경이 필요하면 그 변경만 승인을 요청한다.
3. ChatGPT JD/R2 제안을 원문·소유권·버전에 묶어 브라우저 검토로 전달한다.
   기존 부정/삭제근거 실패와 새 holdout을 합성 자료로 검사한다. 실제 관측을 구분한다.
4. 전체 여정/재시작/차단/승인/내보내기/삭제의 증거와 미완료 외부 gate를 정리한다.
   개발 수용과 공개 운영·정책·백업 gate를 구분하며 임의로 Phase A 완료를 선언하지 않는다.

## 진행

- [x] 1 영속 개발 계정·자료
- [x] 2 실제 제품 OAuth 연결/외부 승인 상태
- [x] 3 제안 전달·한정 품질 관측 (정식 품질 gate는 미통과)
- [x] 4 개발 수용 보고서·시험 종료·남은 조건 정리

### 현재 증거 / 남은 조건

- 영속 store 6개 회귀 통과. 승인된 합성 Claim과 원문 Evidence/hash가 재시작 후
  보존되고 이전 browser cookie는 거부된다. 실제 Auth0 Web에서도 승인 사실·JD·R1·R2를
  저장한 뒤 재시작했고 같은 프로필 버전 2로 재로그인했다.
- 전체 431개 중 396개 통과, PostgreSQL 35개 skip. 제안 회귀 9개와 오프라인
  fixture 53개 통과. 신규 파일 CI 검사 범위를 추가했지만 이번 변경 CI는 미실행이다.
- 승인된 기존 Auth0 제품 scope 변경 저장 확인. 기존 private 플러그인에 같은
  app binding으로 최신 스킬을 반영(1.0.1)했지만 도구는 Read 1 유지였다.
- 사용자가 비공개 제품 연결/client 범위 확대 승인. 새 제품 연결 생성 완료.
  추가 비교 결과 CIMD URL은 기존 Auth0 ChatGPT client와 같아 별도 client/grant는
  만들지 않았다. 사용자 여섯 scope 동의 완료. 제품 도구 34개 확인 및 실제
  ChatGPT get_my_profile이 Web과 동일 프로필·버전 0을 반환하는 것까지 확인했다.
- 실제 ChatGPT → Web 사실 승인 → 별도 Use 승인 → JD 선택 저장/명시적 연결 →
  R1 → R2 비교 승인 → 별도 내보내기 승인 왕복 완료. 74바이트 INLINE 결과/hash 확인.
  R1 원문/근거는 보존됐다. Web logout 뒤 MCP는 재연결 없이 조회할 수 있었다.
- 삭제 step-up 없는 실제 호출은 REVIEW_REQUIRED로 거부됐고 DB 불변을 별도 확인했다.
  삭제 성공이나 provider token 폐기 시험으로 표시하지 않는다.
- 제품 시험은 스킬 1.0.1로 수행했다. Use 검토와 BOUNDARY_REVIEW의 차이를 보강한
  1.0.2 설치도 확인했다. 품질 최초 분류 불일치와 같은 대화 보강 관측을 보존했고
  정식 품질 gate는 미통과다.
- `docs/CareerGround_Phase_A_Hybrid_Acceptance_2026-10-04.md` 결과 보고서 작성.
  시험 Web/MCP/터널은 종료했고 별도 owner-only 시험 DB는 재개를 위해 보존했다.
  두 실제 계정, provider refresh/revocation, 실제 삭제 step-up, 운영/정책 gate는 남아 있다.

## 검증

위험에 맞는 신규 회귀와 CI 범위 Ruff/diff 검사를 수행한다.
브라우저 조작은 BrowserOS를 사용하며 사용자의 기존 탭·자료는 시험하지 않는다.
실제 외부 관측·합성 HTTP/MCP·브라우저 결과를 분리해 기록한다.

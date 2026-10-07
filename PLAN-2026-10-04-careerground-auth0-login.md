# CareerGround 자체 로그인과 공유 계정 연결

사용자가 2026-10-04 승인한 순서: 기존 Auth0 개발 설정 확인·로그인 화면 연결 →
관리 화면/MCP 동일 계정 매핑 → BrowserOS 로그인·로그아웃·승인 흐름 검증.

기준 HEAD: `7c308de4a5bf498b12966348f0179c8a9150cc1d`.
기존 미커밋 변경, ignored 초안·개발 데이터·인증/tunnel 설정을 보존한다.
이번 작업은 commit/push, 공개 배포, 운영 연결, 서버 AI·유료 자원 추가를 포함하지 않는다.
OpenAI 앱 등록과 Sign in with ChatGPT는 선행 조건이 아니다.

## 구현 및 검증

1. 기존 `.env`의 Auth0 개발 client와 공개 discovery를 읽기 전용으로 확인한다.
   비밀값을 출력하거나 tenant 설정을 변경하지 않는다.
2. identity-only OIDC(S256/state/nonce/RS256) 로그인과 명시적 계정 초기화를 연결한다.
   Web과 MCP는 동일한 DB의 검증된 `(issuer, sub)` 매핑을 사용한다.
   기존 합성 runtime과 분리된 일회용 로컬 DB를 사용한다.
   로그인·가입 폼·로그아웃은 쿠키/session binding·CSRF·Origin 검증을 적용한다.
3. 서로 다른 합성 인증 사용자로 HTTP/MCP 계정 격리·동일 매핑·삭제 차단·승인을
   자동 검증한다. 실제 인증은 BrowserOS에서 기존 개발 client로 확인한다.
   로그인/MFA가 필요한 시점에만 사용자에게 한 단계씩 요청한다.

## 완료 기준과 제한

- 로컬 구현·합성 시험과 실제 Auth0/ChatGPT OAuth 관측은 구분한다.
- 기존 실제 MCP PoC scope는 `careerground:probe`다. 새 제품 scope가 발급됐다는
  증거 없이 실제 ChatGPT 제품 연결 성공으로 표시하지 않는다.
- 실제 두 번째 인증 계정은 이전 결정대로 만들지 않는다. 합성 두 계정 격리와
  실제 단일 계정 시험을 구분한다.
- 일회용 개발 admission은 loopback에서만 사용하며 운영 가입 정책이 아니다.
- 실제 경력 자료 입력, 과금 API, 기존 synthetic DB 변환을 하지 않는다.

## 진행 기록

- HEAD와 작업 트리를 확인했다. 기존 Auth0 web skeleton, 세션 bridge,
  provider-neutral 계정 초기화 및 제품 MCP verifier를 읽었다.
- 기존 SDK의 기본 세션은 암호화된 stateless cookie다. 이번 개발 연결은 기존
  identity-only 검증과 서버에서 철회 가능한 first-party 세션을 사용한다.
- 기존 discovery와 실제 Auth0/Google 로그인 성공을 확인했다. 외부 설정 변경은 없다.
- 로그인·명시적 초기화·관리 화면·logout·제품 MCP 공유 계정 assembly를 추가했다.
  신규 통합 7개 통과, 관련 47개 중 46개 통과/PG 1개 skip. Ruff/diff 검사 통과.
- BrowserOS 실제 단일 Auth0 계정의 빈 프로필 초기화, logout 접근 차단, 합성 사실
  승인(버전 1), 재로그인 후 버전 1 유지 확인. 합성 A 본인 프로필과 B의 A 프로필
  접근 차단을 별도 BrowserOS fixture에서 확인했다. 실제 두 번째 계정은 만들지 않았다.
- 실제 ChatGPT 제품 scope/동의/도구 호출은 미검증이며 기존 probe 권한은 그대로다.
  Phase A 전체 완료로 표시하지 않는다.
- ignored/settings/store 31개 파일 변경 0개. 결과/실행 방법은
  `docs/CareerGround_Phase_A_Auth0_Login_2026-10-04.md`에 기록했다.
- 이번 시험 프로세스/탭/cookie와 일회용 Auth0 DB를 정리했다. 기존 HEAD 유지.

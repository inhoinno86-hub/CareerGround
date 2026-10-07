# Phase A — CareerGround 자체 로그인·공유 계정·BrowserOS 시험

날짜: 2026-10-04 (Asia/Seoul). 기준 HEAD:
`7c308de4a5bf498b12966348f0179c8a9150cc1d`.
사용자가 승인한 세 작업을 개발 환경에서 구현·검증했다.
이번 작업의 commit/push와 공개 배포는 수행하지 않았다.

## 1. CareerGround 자체 로그인

기존 `.env`의 Auth0 개발 client 및 `.env.poc`의 issuer/resource를 사용했다.
공개 discovery에서 정확한 issuer, 같은 개발 도메인의 authorization/token/JWKS
endpoint와 S256 지원을 확인했다. client/tenant/callback/permission 설정은 변경하지 않았다.
OpenAI developer 가입, Sign in with ChatGPT client 등록, 새 회사·도메인 등록은 필요하지 않았다.

새 opt-in 진입점은 `careerground.auth0_development_runtime`이다.
로그인 화면 → 기존 Auth0/Google 인증 → 검증된 신원 → 명시적 빈 프로필 생성 →
관리 화면으로 연결된다. 로그인 GET/callback만으로 프로필을 만들지 않는다.

- OIDC: authorization code + S256/state/nonce, RS256/JWKS, 정확한 issuer/audience,
  발급·만료 시간 검증. identity-only `openid profile email`만 요청한다.
- token exchange는 기존 Auth0 client secret을 사용한다. 제공자의 redirect는 따르지 않는다.
  토큰·이메일·이름은 소유권 키나 영구 저장 자료로 사용하지 않는다.
- 쿠키: Secure/HttpOnly/SameSite=Lax/Path=/의 `__Host-` cookie.
  최종 세션은 원문 대신 SHA-256 키로 서버 메모리에 보관하고 1시간 뒤 만료한다.
- 첫 설정과 로그아웃은 3분 만료의 session-bound HMAC 폼 및 Origin 검증을 거친다.
  첫 설정은 정책 버전과 체크박스 확인을 요구하며 일회용이다.
- 브라우저 로그아웃은 현재 CareerGround 세션을 서버에서 철회하고 Auth0 logout으로
  이동한다. 저장해 둔 이전 쿠키를 다시 보내도 접근할 수 없다.

로그아웃은 별도 발급된 MCP JWT를 폐기하는 동작이 아니다. MCP는 자체 OAuth 토큰과
계정 상태를 확인한다. 브라우저 logout, ChatGPT 연결 해제, OAuth 토큰 철회는 별개다.
실제 MCP JWT 즉시 철회/refresh/step-up은 이번 단일 계정 웹 시험으로 증명하지 않았다.

## 2. Web과 MCP의 공유 계정

`AuthenticatedManagement`가 동일한 DB·검토/표시 키로 Web/MCP factory를 조립한다.
Web은 검증된 identity에서 발급한 CareerGround 세션을 사용한다. MCP는 별도로
Auth0 RS256 access token의 issuer/resource audience/scope/시간과 활성 계정을 검증한다.
브라우저 cookie 또는 ID token을 MCP access token으로 바꾸는 우회는 없다.

두 경로 모두 `(issuer, sub)` → `AuthIdentity` → 활성 `Account` → 소유 프로필을 사용한다.
이메일 또는 입력받은 account ID로 매핑하지 않는다. 새 사용자는 관리 브라우저에서
명시적으로 초기화해야 한다. MCP가 미등록 사용자를 자동 가입시키지 않는다.
관리 화면에서 실행한 승인과 MCP의 영수증 확인·소비는 기존의 동일 승인 계약을 따른다.

개발 admission은 **loopback의 일회용 시험에 한정**한다. 안정적인 HMAC ID는 이 시험
DB·키의 수명 안에서 유지된다. 서버 종료 시 DB·키가 제거되므로 재시작은 새 시험이다.
기존 `.careerground-development/` 데이터/marker/키는 변환하거나 열지 않았다.
운영 가입에는 영속 admission 키·보존된 삭제 tombstone·가입 정책·정책 동의 기록과
배포용 session/DB 구성을 별도로 준비해야 한다. 이번 코드가 운영 가입 완료는 아니다.

## 3. 검증 증거

### 자동 HTTP/MCP 시험

```bash
.venv/bin/python -m unittest tests.test_authenticated_management -q
.venv/bin/python -m unittest tests.test_authenticated_management \
  tests.test_identity_only_login tests.test_auth0_review_identity \
  tests.test_adapter_security tests.test_chatgpt_management_journey -q
```

- 신규 통합 **7개 모두 통과**. 최종 작은 화면 안내 보완 후 7개를 다시 확인했다.
- 관련 회귀 **47개 실행: 46개 통과, PostgreSQL 전용 1개 skip**.
  이번 작업에는 새 migration이 없고 실제 PostgreSQL 재시험은 하지 않았다.
- first-use 확인/CSRF/Origin/일회용 및 유효시간, 두 검증 신원과 서로 다른 프로필,
  Web/MCP 동일 프로필, 다른 계정 Web GET 404·MCP NOT_FOUND를 확인했다.
- Web client용 ID-token audience, 기존 `careerground:probe` scope, 미등록 신원은
  제품 MCP에서 401로 거부됐다.
- 다른 계정이 승인 폼을 재사용하면 409로 거부됐다. 본인의 승인 후 Claim 1개가
  생기고 MCP가 영수증을 소비해도 추가로 중복 반영하지 않았다.
- 삭제된 계정/지워진 AuthIdentity는 Web/MCP 접근과 재가입이 거부됐다.
- 원래 브라우저 cookie의 logout 후 재사용은 401. 같은 identity로 재로그인해도
  account/profile을 중복 생성하지 않았다. Web logout 후 별도 유효 MCP bearer는
  유지되는 것을 명시적으로 검사했다.

Ruff check 및 format 검사 통과; 검사 대상으로 src 전체와 새 test/script를 포함했다.
CI의 명시적인 lint/format 목록에도 새 test를 추가했다. `git diff --check` 통과.
GitHub CI는 이번 작업을 push하지 않았으므로 새로 실행하지 않았다.

### BrowserOS — 실제 기존 Auth0 개발 계정

새 시험 탭에서 `http://localhost:5000`을 사용했다. 기존 Google 인증 상태로 로그인
흐름이 완료돼 사용자 비밀번호/MFA 입력이나 새 계정 생성은 필요하지 않았다.

1. CareerGround 로그인 화면 → Auth0/Google → 계정 시작 화면 도달.
2. 명시적 빈 프로필 생성 → 관리 화면 도달.
3. 로그아웃 후 `/account`에서 `로그인이 필요합니다` 화면 관찰.
4. 합성 문장만으로 세션 시작 → 경험 입력 → 글머리표 초안 → 검토 준비 → 사실 승인.
   `합성 시험 프로젝트에서 테스트를 작성했습니다.`가 프로필 버전 1에 반영된 화면을 확인했다.
5. 다시 로그아웃 후 보호 화면 접근 차단, 재로그인 후 **동일 시험 DB의 버전 1** 유지 확인.

정상 대화문 한 줄은 글머리표 추출 대상이 아니어서 임시 초안이 생기지 않았다.
`- `로 시작하는 합성 글머리표를 명시적으로 제출해 승인 여정을 진행했다.
이 과정에서 실제 경력 자료는 입력하지 않았다. 실제 인증 식별자만 일회용 시험 DB에
보관했으며 이메일/이름/토큰/사용자의 다른 브라우저 자료는 보고서에 기록하지 않았다.

### BrowserOS — 합성 두 계정 격리

별도 `127.0.0.1:5015`에서 RSA로 서명된 합성 OIDC fixture를 사용했다.
실제 Auth0 시험의 `localhost`와 분리된 호스트를 사용해 cookie를 섞지 않았다.

- A 로그인·명시적 프로필 생성 후 본인 프로필 화면 접근 성공.
- B 로그인·명시적 프로필 생성 후 A의 동일 프로필 URL은
  `요청한 내용을 찾을 수 없습니다` 화면으로 차단됨.
- 이 fixture의 account 선택 route는 테스트 script에만 존재한다.
  실제 Auth0 runtime에는 account 선택/가짜 로그인 route가 없다.
- 실제 두 번째 Auth0/Google 계정은 만들거나 사용하지 않았다.
  이 결과는 실제 두 계정의 OAuth 연결 시험을 대체하지 않는다.

브라우저 UI 시험은 BrowserOS로 수행했다. 별도 Playwright 시험을 이번 결과로 표시하지 않는다.
관찰 요약은 `auth0_management_browser_observations_20261004.json`에 비식별 정보로 기록한다.

## 실행 방법

기존 설정을 보존한 상태에서 다음 명령 하나로 시작한다.

```bash
uv run --locked --env-file .env --env-file .env.poc \
  python -m careerground.auth0_development_runtime --allow-development-login
```

출력된 원점에 접속한다. 현재 `.env`는 `http://localhost:5000`이다.
`127.0.0.1`로 임의 변경하면 callback/cookie 원점이 달라지므로 출력된 주소를 사용한다.
`/account`에서 본인 자료·경력 정리·logout으로 이동한다.
프로필 생성 폼이 3분 뒤 만료되면 홈에서 로그인을 다시 시작한다.
`Ctrl+C`로 종료하면 이 진입점 소유의 일회용 DB가 삭제된다. 기존 개발 store는 유지된다.
새 공개 주소/터널/tenant/모델 API는 이 명령으로 생성되지 않는다.

합성 두 계정 BrowserOS 시험 fixture만 필요하다면:

```bash
.venv/bin/python scripts/serve_authenticated_management_browser_fixture.py
```

`http://127.0.0.1:5015/synthetic-login/a`와 `/synthetic-login/b`를 차례로 열어 각각
명시적으로 프로필을 생성한다. A의 프로필 링크를 B 로그인 후 열면 차단된다.
이 script는 실제 Auth0 설정이나 사용자 DB에 접근하지 않는다.

## 남은 실제 ChatGPT 제품 OAuth 연결

기존 실제 개발 MCP OAuth PoC는 `careerground:probe` 권한의 읽기 전용 인증 도구다.
그 연결 성공을 이번 제품 MCP 30개 도구의 실제 OAuth 성공으로 간주하지 않는다.
이번 시험은 **실제 Auth0 Web + 합성 JWT 기반 Web/MCP 통합**이다.

제품 MCP가 사용하는 권한:

| scope | 사용 범위 |
| --- | --- |
| `career.profile.read` | 본인 프로필·세션 조회 |
| `career.profile.write` | 프로파일링 입력·초안·사실 검토 |
| `career.artifact.read` | JD·이력서 근거 조회 |
| `career.artifact.write` | JD·이력서 관련 준비/승인 |
| `career.export` | 승인된 본인 자료 내보내기 |
| `career.delete` | 허용된 삭제 관련 도구 |

실제 ChatGPT 제품 호출 시험 전에는 기존 개발 API/ChatGPT client grant의 필요한
제품 scope와 사용자 OAuth 동의를 준비하고, 기존 승인된 private tunnel의 로컬 대상과
공유 DB를 연결해야 한다. `careerground:probe`를 제품 쓰기 권한으로 우회하지 않는다.
개발 tenant/client 권한 변경이 필요한 경우 구체적인 설정을 확인하고 해당 변경만
사용자에게 승인 요청한다. 현재 tenant/grant/tunnel은 변경하지 않았다.
실제 ChatGPT 제품 OAuth, 다른 실제 사용자 격리, refresh/재인증/즉시 철회는 미완료다.

별도 서버 AI는 계속 보류한다. 이 로그인/계정 연결을 위해 AI API나 새 유료 서버를
도입하지 않았다. 이전 JD 품질 관찰의 모순(`jd-07`)과 운영 삭제/backup 증거 등
남은 Phase A gate는 이전 보고서대로 유지한다. Phase A 전체 완료·운영 출시·main
병합 완료를 선언하지 않는다.

## 보존·정리

ignored 초안·기존 개발 store·`.env`·`.env.poc` **31개 파일의 SHA-256 변경 0개**.
기존 미커밋 변경도 보존했다. 시험 프로세스 2개와 시험 탭 2개를 종료했고, 이 시험에서
발급한 로컬 cookie를 지웠다. 일회용 Auth0 DB 디렉터리 0개와 5000/5015 포트 종료를
확인했다. 이전 Auth0/ChatGPT 브라우저 탭이나 기존 서비스 프로세스는 종료하지 않았다.
실제 tenant/subject/email/token/tunnel 식별자는 문서와 관찰 JSON에 넣지 않는다.

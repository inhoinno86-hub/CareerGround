# Auth0 개발 등록 진행 — 2026-10-11

**BrowserOS 실제 개발 등록·저장 확인 PASS.** 실제 앱 OIDC 로그인 수용은 NOT_RUN이다.
사용자는 직접 수행하던 Auth0 개발 등록을 에이전트가 BrowserOS로 진행하도록 승인했다.
가입/로그인·비밀번호·이메일 인증·CAPTCHA 같은 사용자 입력은 BrowserOS 화면에서 직접 수행한다.

## 착수·로그인 이력

- 기존 BrowserOS 프로필·실행기·연결을 사용했다. 새 브라우저/플러그인 설치나 연결 설정 변경 없음.
- X11 시작 실패 후 현재 데스크톱의 Wayland 방식으로 실행 성공.
- 실제 MCP 9201 / CDP 9100 / proxy 9000 listen 주소는 모두 127.0.0.1이었다.
- BrowserOS MCP의 `tabs new`로 `https://manage.auth0.com`을 열었고 Auth0 로그인 화면으로 이동했다.
  Email address / Continue / Sign up 및 제공자 로그인 버튼을 관찰했다.
- 사용자에게 로그인/가입·필요한 인증을 화면에서 완료하고 알려 달라고 요청했다.
- 이 시점에는 생성·설정 저장 전이었다. 이후 사용자가 “로그인 완료”를 알렸고 아래 등록을 진행했다.
  로그인 비밀번호·token·cookie는 조회하거나 repo에 저장하지 않았다. 기존 브라우저 프로필의 로그인 상태는 유지한다.

## 실제 등록·재검토

새 tenant를 만들지 않고 열린 **DEVELOPMENT** tenant `dev-gi4s7rn7d3eym5dp`를 사용했다.
기존 CareerGround 웹/ChatGPT 등록과 기존 API를 목록에서 확인하고 별도 앱·API를 만들었다.
기존 연결·callback·tunnel 설정은 변경하지 않았다.

- `CareerGround Interview Dev` Native 앱 생성. Client ID `DhgwGDNfZJoMXWuJMWwDDI5sCcOXCgl9`.
- Domain `dev-gi4s7rn7d3eym5dp.us.auth0.com`, issuer `https://dev-gi4s7rn7d3eym5dp.us.auth0.com/`.
- callback 입력·Save 후 새로고침해 정확한 URI와 Native 유형을 확인했다.
  기본 Username-Password-Authentication 및 기존 google-oauth2 연결은 활성 상태였고 변경하지 않았다.
  별도 Google client나 제공자 설정을 새로 등록하지 않았다.
- `CareerGround Interview Dev Runtime` API 생성. Identifier는 아래 승인값, token profile Auth0,
  signing RS256. 사용자 정책은 Per-app authorization, client 정책은 No apps allowed다.
- Permission `use:interview` 추가. 새 Native 앱의 User-Delegated Access에 이 권한 하나만 부여했다.
  Always grant all permissions는 선택하지 않았다. Anonymous grant도 추가하지 않았다.
- Application Access 새로고침 뒤 해당 앱 1/1, 다른 앱은 0/1 권한임을 확인했다.
- **제공자의 자동 생성:** API 생성 과정에서 `CareerGround Interview Dev Runtime (Test Application)`
  Machine to Machine 앱도 생겼다. 자동 생성 사실을 기록하고 삭제하지 않았다.
  API의 client 접근은 차단돼 있으며 이 앱의 토큰·secret을 조회하거나 호출하지 않았다.
- 공개 discovery와 JWKS HTTP 조회 성공. issuer·고정 JWKS URI·S256 지원을 확인했고,
  실제 public JWKS를 기존 AccessTokenPolicy 준비 코드에 주입해 키 형식 수용을 확인했다.
  실제 OAuth token 요청이나 검증은 수행하지 않았다.
- 관리자 로그인·설정 등록과 앱 사용자의 실제 로그인을 구분한다.
  무료 개발 기능만 구성했고 유료 전환·카드 입력·배포는 실행하지 않았다.

[공개 설정 파일](../apps/mock-interview/config/auth0-dev.public.json)과
[구조화 관찰](mock_interview_auth0_registration_20261011.json)에 필요한 공개값만 기록했다.
BrowserOS와 Auth0 설정 탭은 후속 작업을 위해 열어 두었다. 지금 추가 수동 입력은 없다.

BrowserOS `run`의 응답 schema가 추가 session 필드를 거부한 도구 오류가 있었다.
해당 call의 앱 이름 입력/Native 선택은 수행된 상태를 다시 확인했고 중복 생성하지 않았다.
일부 ref 기반 클릭·fill의 실제 DOM 반영이 없어 readback 후 DOM 입력 이벤트/명시적 컨트롤 클릭으로 보완했다.
설정 저장/새로고침 결과로 판정했으며 도구의 `ok` 응답만을 성공 증거로 삼지 않았다.

## 승인한 등록값

| 항목 | 값 또는 범위 |
| --- | --- |
| 환경 | 무료 개발용 tenant. 기존 운영 등록은 보존 |
| Application | CareerGround Interview Dev / Native public client |
| Callback | `dev.careerground.interview.dev:/oauth2redirect` |
| API name | CareerGround Interview Dev Runtime |
| Audience / Identifier | `https://careerground.example/mock-interview/dev` |
| Signing algorithm | RS256 |
| Permission | `use:interview` |
| 앱 요청 scope | `openid use:interview`, refresh token 기본 미요청 |
| 기록할 값 | 공개 Domain/issuer·Native Client ID·Audience 및 실제 저장 확인 |

생성 전에 같은 이름/identifier 등록이 없음을 확인했다. 운영 설정 변경이나 다른 앱의 secret 조회는 수행하지 않았다.
등록만 완료됐다는 이유로 앱 실제 로그인·STEP 02 전체를 PASS로 표시하지 않는다.
다음은 [AppAuth 0.11.1 추가 설치 확인안](mock_interview_oidc_setup_20261011.md)의 범위로
실제 로그인 구현·APK 빌드·기기 로그인을 진행하는 것이다. 해당 라이브러리는 아직 설치하지 않았다.

이전 실기기 시험은 [기기 검증 기록](mock_interview_device_validation_20261011.md),
전체 순서와 승인 경계는 [앱 계획](../PLAN-2026-10-10-mock-interview-app.md)을 따른다.

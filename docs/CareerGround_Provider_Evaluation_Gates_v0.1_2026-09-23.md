# CareerGround 외부 공급자 평가 게이트 v0.1

- 작성일: 2026-09-23
- 상태 (2026-09-26): **Auth0–ChatGPT 개발용 합성 데이터 PoC의 로그인·토큰 교환·MCP 도구 호출 확인, G-I 최종 선정 보류**. 로그인에는 사용자의 현재 Google 계정을 사용했으므로 인증 제공자는 실제 계정 식별자를 처리한다. 이 검증은 공급자 최종 선정이나 경력·대화 등 제품 개인정보의 외부 전송 승인이 아니다. 과금 한도와 결제 수단이 없으므로 유료 리소스는 생성하지 않는다.
- 연결 계획: [E00-S03 및 G-I/G-L](../PLAN-2026-09-23-mvp-implementation.md)

## 1. 인증 공급자 — G-I

CareerGround는 웹 OIDC 로그인과 MCP OAuth 호출에서 **동일한 `(issuer, subject) → account_id`**를 증명해야 한다. 이메일은 계정 소유권 키가 아니다. MCP 클라이언트가 요청한 `resource`가 access token의 정확한 대상(`aud`)에 묶이고, 각 도구의 scope를 검증할 수 있어야 한다. 첫 계정 연결, 재인증, 철회, 다른 issuer의 같은 subject, 이메일 변경을 합성 사용자로 시험한다.

대상 클라이언트는 설계상 **ChatGPT 플러그인**이다. [현재 MCP 인증 명세(2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)는 Client ID Metadata Document(CIMD)를 우선하고 DCR은 하위 호환용으로 둔다. [공식 OpenAI Docs의 플러그인 인증 안내](https://developers.openai.com/plugins/build/auth)는 ChatGPT가 protected-resource metadata, OAuth/OIDC discovery, `resource`를 authorization·token 요청 모두에 포함하는 흐름, PKCE S256, 공급자가 허용하는 CIMD/DCR/사전등록 경로를 사용한다고 설명한다. 따라서 **CIMD 우선**, 사전등록 가능성 확인, DCR 최후 대안 순서로 평가한다. ChatGPT의 정확한 client metadata URL과 redirect URI는 실제 플러그인 관리 화면의 callback 모드에서 확인해야 하며 문서 예시를 하드코딩하지 않는다.

| 후보 | 공식 문서에서 확인한 점 | 남은 위험·검증 | 현재 판단 |
| --- | --- | --- | --- |
| Auth0 | 관리자가 HTTPS CIMD URL을 가져와 클라이언트를 등록할 수 있고 제3자 앱은 PKCE를 요구한다. MCP용 `resource` compatibility 설정이 별도로 필요하다. [CIMD 문서](https://auth0.com/docs/get-started/auth0-overview/create-applications/register-applications-with-cimd) | 개발 tenant에서 CIMD 등록, ChatGPT 로그인·토큰 교환, 정확한 리소스 audience와 최소 scope를 요구하는 MCP 호출을 실측했다. 남은 것은 S256 요청 원문, 실제 다중 계정·토큰 만료/철회, 운영 비용·리전·계약과 실사용자 데이터 보호다. DCR은 켜지 않았다. | **개발용 합성 PoC 핵심 경로 통과, G-I 선정 보류**. [실행 기록](CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md) |
| Amazon Cognito | 사용자 OAuth 요청의 `resource`를 access token `aud`에 반영할 수 있고 custom scope를 제공한다. 이 기능은 managed login의 사용자 authorization-code 경로에 적용된다. [resource binding 문서](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-define-resource-servers.html) | ChatGPT 사전등록 클라이언트 경로가 허용되는지, CIMD/DCR 지원 여부, `code_challenge_methods_supported`와 refresh·logout을 실제 discovery/연동으로 확인해야 한다. | **실연동 PoC 2순위**. AWS 배포와 맞을 수 있지만 ChatGPT 등록 경로 미증명. |
| Keycloak | 공식 MCP 호환성 표는 현행 MCP 버전의 RFC 8707 `resource` 처리 미지원과 부분 호환을 명시한다. [MCP 안내](https://www.keycloak.org/securing-apps/mcp-authz-server) | scope 기반 우회가 CareerGround의 리소스 audience 요구를 충족하는지 별도 설계·보안 검토가 필요하다. | 현재는 후순위. |

### PoC 통과 기준

1. ChatGPT가 protected-resource metadata를 발견하고, 실제 관리 화면의 CIMD URL/redirect URI와 공급자의 허용된 등록 방식으로 PKCE S256 authorization-code 로그인을 완료한다. CIMD가 불가능하면 사전등록을 확인하고, DCR은 마지막 대안으로 시험한다.
2. MCP 토큰의 `iss`, 서명, 만료, `aud/resource`, scope가 매 호출 검증된다. 다른 audience/누락 scope/잘못된 issuer/만료 토큰은 읽기와 쓰기 모두 실패한다.
3. 웹과 MCP에서 같은 검증된 subject는 같은 계정을 가리키고, 다른 subject·issuer는 서로 분리된다. 이메일 변경으로 데이터가 이동하지 않는다.
4. refresh·logout·revoke·키 교체 시 새 호출 차단 범위와 지연을 기록한다. 삭제 등의 고위험 동작은 별도 step-up 요구를 만족한다.
5. 요금, 한국 사용자 데이터·로그 처리 리전, 하위 처리자, 보관·삭제 약관과 지원 경로를 실제 계약 기준으로 검토한다.

하나라도 실패하면 해당 공급자에 맞춰 보안 요구를 완화하지 않는다. **합성 외부 PoC는 승인됐지만, 인증 공급자 최종 선택과 유료 계약은 별도 결정 게이트**다.

### 사전 검토 결과와 실제 PoC의 경계

| 항목 | Auth0 | Cognito | 현재 증거 |
| --- | --- | --- | --- |
| ChatGPT에 필요한 CIMD/사전등록 경로 | 개발 tenant에서 실제 CIMD 등록·재연결 성공 | 사전등록 가능성 검증 필요 | ChatGPT 클라이언트와 callback 실측 |
| `resource`가 정확한 MCP `aud`가 되는지 | 개발용 터널 리소스를 audience로 한 인증 도구 성공 | managed-login code 경로 문서상 가능 | 서버가 정확한 `aud`를 요구하는 실제 도구 호출 성공; 토큰 원문 미보관 |
| PKCE S256·discovery·정확한 redirect | CIMD preflight·strict 제3자 클라이언트·인가 코드 교환 성공 | 동일 | S256 광고와 PKCE 강제는 확인, 개별 요청의 S256 필드는 미캡처 |
| 2개 합성 계정의 웹/MCP 동일 subject와 격리 | 서버의 서로 다른 합성 subject ID 분리 통과; 실제 2계정 미실시 | 미실시 | 사용자는 실제 Google 계정 하나로 개발 PoC 진행 |
| 비용·보관·리전·운영 계약 | 미검토 | 미검토 | 공급자 미선정 |

저장소의 `assess_mcp_oauth_metadata` 사전 검사 자체는 외부 네트워크를 호출하지 않으며, 전달된 discovery 문서의 정확한 issuer, HTTPS endpoint, PKCE S256, 선택한 등록 방식 및 토큰 인증 방법의 **표시값만** 검증한다. 이 정적 검사의 한계와 별개로, 아래 2026-09-26 개발용 외부 PoC에서 실제 로그인·토큰 교환·인증 도구 호출을 확인했다.

승인된 실연동 PoC의 절차 중 개발 tenant·ChatGPT 개발 연결, metadata/redirect, 정상 토큰의 리소스·scope 검사 성공은 완료했다. PKCE 개별 요청 필드, 실제 두 계정, 외부 발급 토큰의 만료/철회 지연과 비용·개인정보 처리 조건은 남아 있다. 토큰 원문을 기록하지 않고 claim 이름·합격/실패·타임스탬프만 남긴다. 이 잔여 조건을 검토한 뒤 G-I 선정 결정을 요청한다.

### 2026-09-23 실행 점검

- 승인된 GitHub 검증 브랜치의 [Foundation CI](https://github.com/inhoinno86-hub/CareerGround/actions/runs/35870819987)는 PostgreSQL 통합 테스트를 포함한 66개 테스트를 skip 없이 통과했다. 이는 Auth0 또는 ChatGPT 실연동 결과가 아니다.
- Auth0 tenant 도메인은 확보했고 사용자 브라우저에서 웹 로그인·앱 세션·동일 client ID의 성공 로그를 확인했다. 이 실행 환경에는 Auth0 관리 연결과 ChatGPT 개발 플러그인 관리 화면 접근이 없고, tenant가 다른 용도와 격리됐는지도 아직 확인해야 한다. 비밀값이나 관리 토큰을 수집하지 않았다.
- 웹 백엔드는 `/auth/*`와 `/health/*`를 제공한다. 별도 합성 전용 MCP 서버는 로컬의 보호 리소스 메타데이터·`/mcp`·읽기 전용 인증 도구를 제공한다. 실제 ChatGPT callback 정보와 MCP access token은 아직 얻지 못했으므로 **ChatGPT/MCP OAuth 실연동은 미실시**다.
- 다음 실행 조건: 개발용 격리 tenant 확인, ChatGPT 개발 연결 화면의 client metadata URL/redirect URI, 그리고 합성 전용 Secure MCP Tunnel 또는 검토된 HTTPS 경로. 무료 범위를 벗어나는 설정은 금액 한도 확인 후 별도로 다룬다.
- 2026-09-24: 합성 전용 로컬 MCP 인증 프로브 서버와 토큰 검증기를 구현했다. [실행 기록](CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md). Auth0의 `resource`→`aud` 처리는 tenant의 Resource Parameter Compatibility Profile 설정 및 실측으로 확인해야 하며, 현재 로컬 합성 통과를 실연동 통과로 해석하지 않는다. [Auth0 지원 안내](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0)
- 2026-09-24: 실제 tenant OIDC/OAuth discovery에서 issuer·PKCE S256을 확인했으나 CIMD 지원 플래그는 광고되지 않아 현재 CIMD 사전 검사는 실패했다. Auth0 tenant 설정의 CIMD·Resource Parameter Compatibility Profile 확인과 ChatGPT 연결 정보가 다음 게이트다. 웹 로그인 성공을 MCP 공급자 선정 근거로 확장하지 않는다.
- 2026-09-26: 개발 tenant의 CIMD와 Resource Parameter Compatibility Profile을 활성/확인하고 ChatGPT 클라이언트·callback·개발용 MCP API와 최소 `careerground:probe` 권한을 등록했다. Auth0의 **Success Login**·**Success Exchange**, ChatGPT 연결 계정, 터널의 인증된 `get_poc_identity` 호출을 확인했다. 연결 해제 후 ChatGPT는 새 호출에 재연결을 요구했고 같은 계정의 시험 ID는 재연결 후 유지됐다. 현재 API의 새 액세스 토큰 최대 수명은 1시간으로 제한했다. 기존 JWT 즉시 무효화와 실제 다중 계정 격리는 검증되지 않았고, 제품 데이터는 연결하지 않았다. [상세 근거와 경계](CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md)

## 2. 텍스트 LLM 공급자 — G-L

LLM은 CareerGround가 **명시적으로 수집한 CareerGround 작업 입력**만 받는다. 일반 채팅은 포함하지 않는다. 후보 평가는 문장 추출·JD 매핑의 품질뿐 아니라 공급자의 기본 보관 모드, 모델별 예외, 학습 사용, 운영 로그, 해외 이전, 삭제 가능성을 같은 무게로 다룬다.

| 후보 | 공식 문서에서 확인한 점 | 확인 전 결론 |
| --- | --- | --- |
| Amazon Bedrock | 보관 모드는 모델·계정 설정에 따라 다르며 `none`은 지원/승인 여부가 모델별로 달라질 수 있다. 기본 모드나 `store=false`만으로 zero retention을 보장하지 않는다고 명시한다. [보관 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html) | 특정 모델, 서울 리전 경로, 계정의 허용 모드, 호출 로깅 설정, 계약을 확인해야 한다. |
| Google Cloud Gemini Enterprise Agent Platform/Vertex AI 경로 | zero-retention 안내는 abuse monitoring, 기능별 로그 및 계약상 예외를 설명한다. 일부 기능에서 zero retention이 불가능할 수 있다. [보관 안내](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention) | 특정 API/모델·리전·계약·예외 승인 상태를 확인해야 한다. |

### 합성 평가 세트와 합격 조건

- 한국어 문장 30개 이상: 수치·기간, 주체/기여도, 부정문, 추정 대 사실, 민감정보, 상충하는 경력, 근거 없는 JD 요구를 포함한다. 개인의 실제 이력은 사용하지 않는다.
- 후보 Claim은 근거 위치와 원문 범위를 연결하고, 사용자가 승인하지 않은 수치·직급·성과를 만들지 않는다. `DO_NOT_CLAIM`과 삭제된 Evidence는 출력에 사용하지 않는다.
- 모델 출력은 항상 초안이다. 사용자 확인/외부 검증/공개 허용을 자동으로 설정하지 않는다. 모호한 입력은 질문 또는 `needs_followup`으로 보낸다.
- 모델·프롬프트 버전, 비용/지연, 실패율과 보안 입력 격리 결과를 같은 테스트로 비교한다. 정량 합격선은 샘플과 오답 비용을 본 뒤 승인받아 정한다.
- 계약·리전·보관·학습 사용·삭제·하위 처리자 검토가 통과하기 전에는 실사용자 내용을 전송하지 않는다.

**현재 결론:** 인증은 Auth0→Cognito 순서의 합성 PoC를 제안하고, LLM은 Bedrock과 Google 경로를 동등한 시험 후보로 둔다. 모두 **미선정**이다. 이 문서만으로 공급자 계정이나 비용을 만들지 않는다.

# CareerGround 외부 공급자 평가 게이트 v0.1

- 작성일: 2026-09-23
- 상태: **공식 문서 사전 검토 완료, 실연동 PoC 대기**. 공급자 선정, 계정 생성, 유료 계약 또는 개인정보 전송 승인 아님.
- 연결 계획: [E00-S03 및 G-I/G-L](../PLAN-2026-09-23-mvp-implementation.md)

## 1. 인증 공급자 — G-I

CareerGround는 웹 OIDC 로그인과 MCP OAuth 호출에서 **동일한 `(issuer, subject) → account_id`**를 증명해야 한다. 이메일은 계정 소유권 키가 아니다. MCP 클라이언트가 요청한 `resource`가 access token의 정확한 대상(`aud`)에 묶이고, 각 도구의 scope를 검증할 수 있어야 한다. 첫 계정 연결, 재인증, 철회, 다른 issuer의 같은 subject, 이메일 변경을 합성 사용자로 시험한다.

대상 클라이언트는 설계상 **ChatGPT 플러그인**이다. [현재 MCP 인증 명세(2026-07-28)](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)는 Client ID Metadata Document(CIMD)를 우선하고 DCR은 하위 호환용으로 둔다. [공식 OpenAI Docs의 플러그인 인증 안내](https://developers.openai.com/plugins/build/auth)는 ChatGPT가 protected-resource metadata, OAuth/OIDC discovery, `resource`를 authorization·token 요청 모두에 포함하는 흐름, PKCE S256, 공급자가 허용하는 CIMD/DCR/사전등록 경로를 사용한다고 설명한다. 따라서 **CIMD 우선**, 사전등록 가능성 확인, DCR 최후 대안 순서로 평가한다. ChatGPT의 정확한 client metadata URL과 redirect URI는 실제 플러그인 관리 화면의 callback 모드에서 확인해야 하며 문서 예시를 하드코딩하지 않는다.

| 후보 | 공식 문서에서 확인한 점 | 남은 위험·검증 | 현재 판단 |
| --- | --- | --- | --- |
| Auth0 | 관리자가 HTTPS CIMD URL을 가져와 클라이언트를 등록할 수 있고 공개 클라이언트는 PKCE를 요구한다. MCP용 `resource` compatibility 설정이 별도로 필요하다. [CIMD 문서](https://auth0.com/docs/get-started/auth0-overview/create-applications/register-applications-with-cimd) | 실제 ChatGPT client metadata/redirect와 수동 CIMD 등록, `resource`→`aud`, 최소 client grant, 메타데이터 갱신, 가격·리전·계약을 실험·검토해야 한다. DCR은 기본 비활성이며 활성화하면 공개 등록이므로 **필요할 때만** 별도 보안 검토한다. [DCR 문서](https://auth0.com/docs/get-started/applications/dynamic-client-registration) | **CIMD 실연동 PoC 1순위**. 문서상 경로가 있으나 실제 tenant 결과 미확인. |
| Amazon Cognito | 사용자 OAuth 요청의 `resource`를 access token `aud`에 반영할 수 있고 custom scope를 제공한다. 이 기능은 managed login의 사용자 authorization-code 경로에 적용된다. [resource binding 문서](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-define-resource-servers.html) | ChatGPT 사전등록 클라이언트 경로가 허용되는지, CIMD/DCR 지원 여부, `code_challenge_methods_supported`와 refresh·logout을 실제 discovery/연동으로 확인해야 한다. | **실연동 PoC 2순위**. AWS 배포와 맞을 수 있지만 ChatGPT 등록 경로 미증명. |
| Keycloak | 공식 MCP 호환성 표는 현행 MCP 버전의 RFC 8707 `resource` 처리 미지원과 부분 호환을 명시한다. [MCP 안내](https://www.keycloak.org/securing-apps/mcp-authz-server) | scope 기반 우회가 CareerGround의 리소스 audience 요구를 충족하는지 별도 설계·보안 검토가 필요하다. | 현재는 후순위. |

### PoC 통과 기준

1. ChatGPT가 protected-resource metadata를 발견하고, 실제 관리 화면의 CIMD URL/redirect URI와 공급자의 허용된 등록 방식으로 PKCE S256 authorization-code 로그인을 완료한다. CIMD가 불가능하면 사전등록을 확인하고, DCR은 마지막 대안으로 시험한다.
2. MCP 토큰의 `iss`, 서명, 만료, `aud/resource`, scope가 매 호출 검증된다. 다른 audience/누락 scope/잘못된 issuer/만료 토큰은 읽기와 쓰기 모두 실패한다.
3. 웹과 MCP에서 같은 검증된 subject는 같은 계정을 가리키고, 다른 subject·issuer는 서로 분리된다. 이메일 변경으로 데이터가 이동하지 않는다.
4. refresh·logout·revoke·키 교체 시 새 호출 차단 범위와 지연을 기록한다. 삭제 등의 고위험 동작은 별도 step-up 요구를 만족한다.
5. 요금, 한국 사용자 데이터·로그 처리 리전, 하위 처리자, 보관·삭제 약관과 지원 경로를 실제 계약 기준으로 검토한다.

하나라도 실패하면 해당 공급자에 맞춰 보안 요구를 완화하지 않는다. **인증 공급자 최종 선택과 외부 계정·유료 PoC는 별도 승인 게이트**다.

### 사전 검토 결과와 실제 PoC의 경계

| 항목 | Auth0 | Cognito | 현재 증거 |
| --- | --- | --- | --- |
| ChatGPT에 필요한 CIMD/사전등록 경로 | 문서상 수동 CIMD 등록 가능 | 사전등록 가능성 검증 필요 | 공식 문서만; tenant 없음 |
| `resource`가 정확한 MCP `aud`가 되는지 | compatibility 설정 후 실측 필요 | managed-login code 경로 문서상 가능 | 토큰 발급 실측 없음 |
| PKCE S256·discovery·정확한 redirect | tenant metadata와 ChatGPT 관리 화면에서 확인 필요 | 동일 | 실제 연결 없음 |
| 2개 합성 계정의 웹/MCP 동일 subject와 격리 | 미실시 | 미실시 | 로컬 DB lookup 테스트만 있음 |
| 비용·보관·리전·운영 계약 | 미검토 | 미검토 | 공급자 미선정 |

현재 저장소에는 외부 네트워크를 호출하지 않는 `assess_mcp_oauth_metadata` 사전 검사와 합성 테스트가 있다. 이는 discovery 문서의 정확한 issuer, HTTPS endpoint, PKCE S256, 선택한 등록 방식 및 토큰 인증 방법의 **표시값만** 검증한다. 공급자의 `resource` 처리, 실제 토큰 발급/서명, ChatGPT 연결을 검증한 것은 아니다.

실연동 PoC가 승인되면: (1) 합성 사용자만 있는 격리 tenant와 ChatGPT 개발용 플러그인을 준비하고, (2) 실제 metadata/redirect/PKCE/`resource`·scope를 네트워크 기록으로 확인하고, (3) 정상 토큰과 issuer·audience·scope·expiry·subject 변조 토큰의 실패를 검증한다. 결과에는 토큰 원문을 기록하지 않고 claim 이름·합격/실패·타임스탬프만 남긴다. 그 후 비용·개인정보 처리 조건을 검토해 G-I 선정 결정을 요청한다.

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

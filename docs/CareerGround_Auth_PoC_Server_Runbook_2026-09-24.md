# Auth0–ChatGPT 인증 PoC 서버 준비 기록

- 날짜: 2026-09-24 (Asia/Seoul)
- 범위: **개발용 Auth0 tenant와 읽기 전용 MCP 인증 프로브**. 로그인에는 사용자의 현재 Google 계정을 사용했으므로 인증 제공자는 실제 계정 식별자를 처리한다. MCP 서버에는 제품 경력 정보·DB를 연결하지 않고 응답에는 불투명한 시험 ID만 반환한다.
- 상태 (2026-09-26): 개발용 Auth0 API, `careerground:probe` 권한, ChatGPT CIMD 클라이언트, ChatGPT 개발 연결을 등록했다. Auth0 로그에서 ChatGPT 클라이언트의 **Success Login**과 **Success Exchange**를 확인했고, ChatGPT 앱 화면에도 연결된 계정이 표시된다. 사용자가 `get_poc_identity` 결과를 확인했고 터널 `main` 채널의 `tools/call` 성공도 관측했다. 서버 구현상 성공 응답은 토큰 서명·issuer·`aud`·scope 검증을 통과한 경우에만 가능하다. 연결 해제 후에는 ChatGPT가 새 호출에 재연결을 요구했고, 같은 계정으로 재연결한 뒤 시험 ID가 유지됐다. 개발용 API의 새 액세스 토큰 최대 수명을 1시간으로 제한했다. **다른 실제 계정 간 분리·기존 JWT의 즉시 무효화·PKCE S256 요청 원문은 실측하지 않았다.**

## 서버가 하는 일

별도 ASGI 진입점 `careerground.mcp.poc_asgi:app`은 Streamable HTTP `/mcp`와 RFC 9728 보호 리소스 메타데이터를 노출한다. `get_poc_identity` 도구 하나만 있으며, 토큰의 검증된 `iss`·`sub`를 해시한 안정적인 시험 ID만 반환한다. 이메일·원래 subject·토큰·경력 자료를 반환하거나 저장하지 않는다. 제품 DB·웹 세션·Career Graph에는 접근하지 않는다.

시작하려면 `CAREERGROUND_POC_ISSUER`와 `CAREERGROUND_POC_RESOURCE_URL`이 모두 필요하다. 전자는 Auth0 OIDC issuer의 **정확한 HTTPS URL(끝에 `/`)**, 후자는 ChatGPT가 OAuth의 `resource`로 사용하는 **정확한 HTTPS 식별자**다. 직접 연결은 `/mcp`, Secure MCP Tunnel 연결은 `/v1/mcp/tunnel_<id>` 형식이다. 임의 기본값, 로컬 HTTP, 비밀값이 포함된 URL은 거부한다. Auth0에서 만들 API의 Identifier는 리소스 식별자와 정확히 같아야 한다.

호출마다 RS256 JWKS 서명, `iss`, `sub`, `aud`, `iat`, `exp`, `azp`와 `careerground:probe` scope를 확인한다. audience가 다른 토큰·scope가 없는 토큰·만료/미래 토큰·잘못된 서명은 거부한다. JWKS는 issuer 도메인의 `/.well-known/jwks.json`에서 가져온다. 서버는 인증 제공자가 아니라 리소스 서버이며 로그인이나 토큰 발급을 하지 않는다.

## 서버 실행 준비

```bash
uv sync --locked --group dev
# 최초 준비 시에만 .env.poc.example을 복사하고, ChatGPT가 표시한 Resource 값을 입력한다.
# 기존 .env.poc을 덮어쓰지 않는다.
uv run --locked --env-file .env.poc uvicorn careerground.mcp.poc_asgi:app --host 127.0.0.1 --port 8001 --no-access-log
```

`.env.poc`은 git에서 제외되고 권한 `0600`이다. 현재 파일에는 확인된 issuer와 ChatGPT 개발 연결 화면의 `Resource` 값이 있다. 이 값은 해당 개발 터널에서 관측된 값이지 운영용 고정 호스트가 아니다. 명령은 로컬 루프백에서만 수신하고 OAuth 코드를 액세스 로그에 남기지 않는다. ChatGPT 개발 연결에는 Secure MCP Tunnel을 우선 사용한다. 공개 HTTPS 전달 경로는 별도 검토 전에는 만들지 않는다. 터널은 Platform의 `tunnel_id`와 실행용 API 키, 대상 ChatGPT workspace 연결이 필요하다. 키는 채팅·저장소·검증 기록에 남기지 않는다.

로컬 서버가 실행 중일 때 별도 터미널에서 개발용 터널을 실행한다. 이 시험에서는 로컬 HTTP OAuth 검색을 명시적으로 허용하며, 운영 설정으로 복사하지 않는다.

```bash
set -a
. ~/.config/tunnel-client/careerground-dev-poc.env
. ./.env.poc
set +a
tunnel-client run --profile careerground-dev-poc \
  --mcp.oauth-trusted-origin "${CAREERGROUND_POC_ISSUER%/}" \
  --harpoon.allow-plaintext-http
```

2026-09-24에 개발 계정의 Personal 조직에서 `careerground-dev-mcp` 터널을 생성하고 개발용 ChatGPT workspace를 연결했다. 실제 터널 ID는 이 문서에 싣지 않으며, 나중에 CareerGround 게시 조직의 운영 설정으로 간주하지 않는다. `tunnel-client`는 2026-09-25에 설치하고 로컬 프로필까지 준비했다. 같은 Personal 조직의 제한된 실행용 API 키(`Tunnels Read + Use`만, 30일 만료)는 저장소 밖의 `~/.config/tunnel-client/careerground-dev-poc.env`에 권한 `0600`으로 보관한다. 키 값은 문서·채팅·저장소에 기록하지 않는다. 실행용 키로 터널 메타데이터 조회에 성공했고, 조직 1개와 workspace 1개의 연결을 확인했다. ChatGPT 화면의 `Resource` 값을 확인한 뒤에만 `.env.poc`의 리소스 식별자를 채웠다.

## 2026-09-24 실측 결과와 경계

- 웹 앱에서 Google 로그인 후 `/auth/me`가 `sub`를 반환했고, Auth0 성공 로그인 로그의 client ID가 앱 설정과 일치했다. 이는 **웹 OIDC 로그인** 증거이지 ChatGPT/MCP OAuth 통과 증거가 아니다. 로그인 후 `/`의 404는 최소 로컬 응답을 추가해 해소했다.
- 설정된 Auth0 tenant의 OIDC 및 OAuth discovery가 HTTP 200을 반환했고 issuer가 정확히 일치하며 PKCE `S256`을 광고한다. 토큰 엔드포인트는 `none`을 포함한다. 반면 `client_id_metadata_document_supported` 및 `authorization_response_iss_parameter_supported`는 광고하지 않는다. 따라서 현재 메타데이터 기준 CIMD 사전 검사는 실패하며, Auth0 tenant의 **Client ID Metadata Document Registration** 설정을 확인해야 한다. DCR URL은 광고되지만 실제 등록 허용 여부는 시험하지 않았고 DCR을 활성화하지 않는다.
- 실제 tenant issuer와 외부에 연결하지 않은 임시 HTTPS 리소스 식별자로 로컬 MCP HTTP 스모크를 실행해 보호 리소스 메타데이터 `200`, 무인증 `/mcp` `401` 및 `WWW-Authenticate`를 확인했다. 임시 식별자는 실제 Auth0 API Identifier가 아니며 시험 서버는 종료했다. 관련 합성 테스트 11개와 Ruff 검사를 통과했다.
- Auth0의 `resource`→`aud` 처리를 위해 **Resource Parameter Compatibility Profile** 설정과 실제 토큰 시험이 필요하다. 두 설정은 tenant 전체에 영향을 줄 수 있으므로 개발용 격리 tenant임을 확인한 뒤 사용자 화면에서 진행한다. CIMD client metadata URL 및 redirect URI는 ChatGPT 연결 화면에서 확인한 정확한 값만 등록한다.

## 다음 사람-화면 단계와 순서

1. 완료: 사용자가 ChatGPT **Settings → Security and login → Developer mode**를 켰고 BrowserOS의 개발용 ChatGPT 계정에도 로그인했다.
2. 완료: OpenAI Platform 개발 계정에서 터널 ID를 발급하고 개발용 ChatGPT workspace를 연결했다. `tunnel-client` 설치·로컬 프로필·제한된 실행용 키·내장 합성 MCP 연결을 확인했다. ChatGPT 개발 연결 초안에서 정확한 `Resource` 값을 읽어 로컬 설정에 반영했다. CareerGround MCP 로컬 검색 및 ChatGPT의 Auth0 OAuth 설정 검색을 확인했다. 비용이나 외부 노출이 필요한 대안은 별도 검토한다.
3. 완료: Auth0 개발 tenant에서 CIMD를 활성화하고, 이미 켜진 Resource Parameter Compatibility Profile을 확인했다. 개발용 API의 Identifier를 ChatGPT 화면의 정확한 `Resource`와 일치시켜 등록하고 `careerground:probe` 권한을 만들었다.
4. 완료: ChatGPT Plugins에 `CareerGround Dev OAuth PoC` 개발 연결을 만들고, 화면에서 확인한 CIMD metadata URL·callback URL로 Auth0의 제3자 ChatGPT 클라이언트를 등록했다. 사용자 위임 접근은 해당 API의 `careerground:probe` 하나만 허용하고 Client Access는 허용하지 않았다.
5. 완료: Google social connection을 개발 tenant의 도메인 수준으로 올리고 저장 확인했다. 오래 열어 둔 Auth0 로그인 화면은 `invalid_request`와 로그인 세션 없음으로 실패했으나, ChatGPT에서 새 연결을 시작한 뒤 Auth0 로그에 ChatGPT 클라이언트의 **Success Login** 및 **Success Exchange**가 기록됐다. ChatGPT 앱 화면에도 연결된 계정이 표시된다.
6. 완료: 합성 요청으로 `get_poc_identity`를 실제 호출했다. 사용자가 시험 ID와 인증 성공을 확인했고 터널의 `main` 채널에서 `tools/call` HTTP 200을 관측했다. 서버 검증 코드상 이 도구의 성공 응답에는 정확한 `aud`와 `careerground:probe` scope가 필요하다. 토큰 원문과 시험 ID는 기록하지 않는다.
7. 완료: 사용자가 개발용 ChatGPT 계정을 연결 해제했고 앱 상세 화면에서 연결된 계정이 사라지고 `플러그인 설치` 버튼이 표시됨을 확인했다. 기존 채팅에서 새 도구 호출을 요청하자 ChatGPT가 `나중에 / 연결` 선택지를 제시했고 터널의 성공 `tools/call` 누적값은 증가하지 않았다. 같은 계정으로 재연결한 뒤 사용자가 이전과 동일한 시험 ID와 인증 성공을 확인했다. Auth0의 새 로그인·토큰 교환 및 터널의 추가 성공 호출도 관측했다.
8. 부분 완료: 서로 다른 합성 `sub`의 ID 분리는 로컬 테스트로 검증했다. 사용자는 별도 Google 시험 계정이 없으므로 실제 다중 계정 연결 시험은 후속 베타로 이월한다. ChatGPT 연결 해제 후 새 도구 호출 차단은 실측했지만 이미 발급된 JWT의 즉시 무효화는 보장하지 않는다. Auth0의 엄격한 제3자 클라이언트와 성공한 인가 코드 교환으로 PKCE 적용은 간접 확인했으나 실제 요청의 `S256` 필드는 별도 캡처가 없다.
9. 운영 진입 전 게이트: 토큰·계정 삭제 후 서버 측 즉시 차단 설계, 실제 토큰 만료/재인증 사용자 경험, PKCE S256 요청 필드, 두 실제 계정의 독립성과 비용·개인정보·계약 조건을 재검증한다. 개발용 PoC만으로 인증 공급자를 최종 선정하거나 제품 데이터를 연결하지 않는다.

이 서버의 합성 테스트 통과는 Auth0 지원, ChatGPT 로그인, 운영 보안 또는 공급자 선정의 증거가 아니다. 공급자 선택과 실사용자 정보 연결은 별도 게이트로 남는다.

### 제품 연결 전 토큰·연결 해제 방향 (2026-09-27 사용자 승인; 일부 코드 준비)

- 개발용 합성 PoC는 액세스 토큰 최대 1시간, `offline_access` 비활성, 제품 데이터·쓰기 도구 없음으로 유지한다. 1시간 이하 운영 토큰 방향은 승인됐지만 실제 운영 tenant 설정은 아직 없다.
- 실제 사용자 데이터에 접근하는 MCP 도구는 JWT 검증만으로 허용하지 않고 **매 호출마다 CareerGround 계정의 활성·삭제·접근 철회 상태를 확인**한다. 계정 삭제 또는 CareerGround 내부 권한 철회가 확정되면 기존 토큰의 `exp`가 남아 있어도 즉시 차단한다. 삭제 데이터 복원과 무관하게 접근 차단 상태를 유지한다.
- ChatGPT 화면의 `연결 해제`는 ChatGPT가 새 호출을 보내지 않는 동작으로 관측됐으나 CareerGround 서버에 철회 이벤트가 전달된다는 근거는 없다. 따라서 이를 기존 JWT의 서버 측 즉시 철회로 표현하지 않는다. 향후 앱 내부에서 명시적 연결 철회를 제공할지, ChatGPT 연결 해제에 대한 별도 동기화 수단이 있는지 출시 전에 결정·시험한다.
- 운영 액세스 토큰 수명은 1시간 이하를 우선 검토하고, 재인증 빈도와 refresh token 사용·회전·철회 UX를 별도 시험해 확정한다. 토큰 수명만 줄이는 것은 계정 삭제 후 즉시 차단 요구의 대체가 아니다.

현재 구현 경계: `ActiveAccountTokenVerifier`는 검증된 `(issuer, subject)`를 **매 MCP HTTP 요청마다 새 DB 세션**에서 `ACTIVE` 계정으로 조회한다. 미등록·`DISABLED`·인증 매핑 제거·DB 조회 실패는 모두 거부한다. 별도 `build_account_guarded_probe_app`에서 합성 도구만 대상으로 같은 JWT의 활성→비활성/매핑 제거 후 200→401 전환을 시험했다. 기존 실행 진입점 `poc_asgi.py`는 의도적으로 DB 없는 합성 PoC 그대로다. **실제 제품 MCP 엔드포인트, 계정 삭제 트랜잭션, 연결별 철회 저장소는 아직 없으므로 운영 적용 완료가 아니다.** 제품 데이터 도구 추가 시 이 계정 게이트를 필수로 연결하고, 각 도구의 계정 소유권·권한도 데이터 조회/변경 트랜잭션에서 다시 검사해야 한다. ChatGPT UI 연결 해제를 서버 측 철회로 간주하지 않는다.

2026-09-27 추가 준비: `build_product_foundation_app`은 PoC의 `careerground:probe`와 분리된 `career.profile.read` scope를 요구한다. 합성 DB에만 연결해 계정 프로필 ID와 본인 소유 프로필의 ID/버전 조회를 HTTP 테스트했다. 타 계정·없는 프로필은 동일한 `found=false`, 비활성 계정·잘못된 issuer/audience/scope·만료 토큰·DB 조회 실패는 401이다. **이 팩토리에는 실행 ASGI 진입점이 없으며 실제 경력 본문도 반환하지 않는다.** 정식 `get_career_profile` 계약, 삭제 preview/digest/step-up 및 백업 복원 차단을 완성하고 공급자 게이트를 통과하기 전에는 실사용자 데이터나 현재 개발 Auth0 API에 붙이지 않는다.

## 2026-09-25 BrowserOS MCP 점검

- BrowserOS는 이미 `/usr/bin/browseros`에 설치되어 있다. 내장 MCP는 BrowserOS 실행 중 `http://127.0.0.1:9200/mcp`에서 응답했고, Codex의 일반 설정과 Orca 런타임 설정에 `browseros` 서버로 등록했다. 실행 중이던 Codex 세션에는 새 MCP 도구가 자동으로 추가되지 않으므로 새 세션에서 확인해야 한다.
- 보안 점검에서 내장 서버가 `0.0.0.0:9200`에 바인딩됐고, 인증 없는 비루프백 주소 요청으로 브라우저 탭 목록 조회가 성공했다. `allow_remote_in_mcp=false` 설정만으로 이 요청을 차단하지 못했다. 이 컴퓨터의 외부 방화벽 차단 여부는 일반 사용자 권한으로 확인할 수 없었다.
- Auth0·OpenAI 계정 로그인이나 API 키 생성은 BrowserOS에서 진행하지 않았다. 시험을 위해 실행한 BrowserOS와 MCP 서버는 종료했다. MCP의 비루프백 접근을 차단하거나 원인을 해결하고 재검증하기 전에는 계정 로그인 상태를 BrowserOS로 옮기지 않는다. 이 BrowserOS MCP를 공개 터널에 연결하지 않는다.
- 재부팅 후에도 설치와 Codex MCP 등록은 유지됐다. 사용자가 확인한 UFW 상태는 비활성이다. 빈 BrowserOS로 재검증했을 때 `9200`의 비로컬 MCP 응답이 재현됐다. 함께 열린 `9000`·`9001`은 비로컬 HTTP MCP 요청에 정상 응답하지 않았지만, 별도 브라우저 포트이므로 이후에도 확인이 필요하다. 검증용 BrowserOS 프로세스는 다시 종료했다. 방화벽 규칙을 적용한 것으로 기록하지 않는다.
- 사용자가 `9200`에 대한 임시 `iptables` 차단 규칙을 실행한 뒤 재시험했다. 루프백 MCP 초기화는 HTTP 200, 확인한 두 비루프백 IPv4 주소의 같은 요청은 연결 거부였다. `9000`·`9001`은 여전히 모든 IPv4 인터페이스에 리슨했으며, 시험한 비루프백 HTTP/HTTPS 요청은 연결이 재설정됐다. 이 두 포트의 다른 프로토콜까지 안전하다고 단정하지 않는다. 브라우저는 다시 종료했고, 계정 로그인은 아직 하지 않았다.
- 사용자가 `9000`·`9001`에도 임시 `iptables` 차단 규칙을 적용했다. BrowserOS를 다시 실행해 세 포트 모두 루프백 TCP 연결은 성공하고 확인한 두 비루프백 IPv4 주소에서는 연결이 거부됨을 확인했다. 두 규칙은 재부팅 후 사라진다. BrowserOS MCP로 OpenAI Platform API 키 화면을 열었으나, 현재는 로그인 화면이다. 로그인은 사용자가 직접 진행한다.
- 공식 `openai/tunnel-client` v0.0.15 Linux amd64 배포본의 SHA256을 릴리스 체크섬 및 GitHub 릴리스 API digest와 대조한 후 `~/.local/share/tunnel-client/v0.0.15/`에 설치하고 `~/.local/bin/tunnel-client`를 연결했다. 설치본의 버전 명령은 성공했다. 현재 PC의 `gh`에는 attestation 하위 명령이 없어 Sigstore 출처 검증은 수행하지 못했다. 로컬 프로필 `~/.config/tunnel-client/careerground-dev-poc.yaml`은 개발용 터널 ID와 `http://127.0.0.1:8001/mcp`, 비밀키 값 대신 `env:CONTROL_PLANE_API_KEY` 참조만 갖는다.
- OpenAI Platform 로그인 후 제한된 실행용 키를 생성하고 저장소 밖에 보관했다. 해당 키로 `tunnel-client admin --json tunnels get`이 성공했다. 처음 `tunnel-client doctor --profile careerground-dev-poc --json`은 서버가 없어서 실패했으나, CareerGround MCP 서버를 실행하고 보호 리소스 메타데이터 경로를 보완한 뒤 `result: ok`를 확인했다.
- 내장 합성 MCP(`--embedded-stateless-mcp-stub`)를 같은 터널에 연결한 시험에서 로컬 `/readyz`가 HTTP 200 `ready`를 반환했다. 시험 종료 후 내장 MCP·터널 클라이언트는 종료했다. 이 결과는 **터널 전송 준비 상태**만 입증하며 CareerGround MCP, Auth0 토큰, ChatGPT 연결을 검증하지 않는다.
- 공식 안내는 ChatGPT 터널 연결에서 `tunnel_id`를 선택/입력하며, 내부 수신 경로는 별도의 `<OPENAI_MCP_TUNNEL_BASE_URL>/v1/mcp/<tunnel_id>`로 설명한다. control-plane 기본 호스트 `https://api.openai.com`이나 클라이언트 시작 로그의 `tunnel_url`을 리소스 URL로 가정하지 않았다. 실제 `https://api.openai.com/v1/mcp/<tunnel_id>`에 대한 무인증 GET/POST는 HTTP 404였다. 이후 ChatGPT 개발 연결 화면에서 자체 `Resource` 값을 관측해 로컬 설정에 반영했다.
- 현재 BrowserOS의 `9200`은 여전히 모든 IPv4 인터페이스에서 리슨하지만, 로그인 후 재확인한 로컬 비루프백 주소 3개에 대한 TCP 연결은 모두 거부됐다. 이는 사용자가 적용한 임시 방화벽 규칙의 현 시점 확인이며, 재부팅 후 지속되는 설정이나 외부 네트워크 전체에 대한 보증이 아니다.

## 2026-09-25 ChatGPT 개발 연결 확인

- ChatGPT 개발자 모드가 켜져 있고 `careerground-dev-mcp`가 사용 가능한 터널로 표시된다. **앱을 만들지는 않았다.** 화면의 `Resource`는 OpenAI 내부 게이트웨이의 `/v1/mcp/<tunnel_id>` 형식이며, `api.openai.com` 주소와 다르다. 이 값은 개발용 터널에서 관측한 정확한 OAuth 식별자다.
- 내장 합성 MCP를 연결했을 때 ChatGPT 화면이 그 서버의 OAuth 메타데이터를 읽고 `Resource` 값을 채웠다. 실제 CareerGround MCP로 교체한 뒤에도 ChatGPT가 Auth0 `authorize`·`oauth/token`·`oidc/register` URL과 `careerground:probe` scope를 검색했다. Auth0는 현재 CIMD를 광고하지 않아 화면에서 **CIMD 사용 불가**, DCR은 선택 가능으로 표시된다. DCR 등록은 실행하지 않았다.
- 실제 MCP 서버는 로컬 `/mcp`에서 무인증 `401`을 반환하고, 로컬 `/.well-known/oauth-protected-resource/mcp`에서 HTTP 200 메타데이터를 제공한다. 터널 리소스 식별자의 경로와 로컬 MCP 경로가 달라 생긴 SDK 메타데이터 경로 불일치를 ASGI 별칭으로 해결했다. 관련 테스트는 `6 passed, 14 subtests passed`, Ruff는 통과했다.
- `tunnel-client`는 Auth0 issuer를 추가 신뢰 출처로 지정해야 Auth0 메타데이터를 읽었다. 로컬 HTTP MCP의 Harpoon 자동 등록에는 개발 환경에서만 `--harpoon.allow-plaintext-http`가 필요하다. OpenAI 내부 게이트웨이 `Resource` 원점에 대한 로컬 추가 검색은 신뢰 출처 오류 경고를 남겼으나, ChatGPT의 OAuth 필드 검색과 로컬 `/readyz`는 성공했다. 무인증 `initialize`의 `401`도 관측됐으며, 실제 토큰으로 검증하기 전에는 완전한 연결로 간주하지 않는다. 시험 후 서버와 터널 클라이언트는 종료했다.
- BrowserOS의 `9000`·`9001`·`9200` 포트는 확인한 비루프백 IPv4 주소 3개에서 연결 거부였다. Auth0 관리 페이지를 첫 번째 탭에 열었으나 별도 로그인이 필요하다.

## 2026-09-25~26 Auth0 및 ChatGPT 개발 연결 진행

- 개발용 Auth0 tenant는 대시보드에서 `DEVELOPMENT`로 표시됐다. 실제 tenant 식별자는 이 문서에 싣지 않는다. Advanced에서 CIMD를 켰고 새로고침 후에도 유지됨을 확인했다. Resource Parameter Compatibility Profile은 변경 전부터 켜져 있었다. DCR과 Include Issuer in Authorization Responses는 꺼진 상태로 유지했다. OAuth discovery에 `client_id_metadata_document_supported: true`가 표시됐다.
- `CareerGround MCP Dev PoC` Auth0 API를 ChatGPT가 실제 표시한 tunnel `Resource` URL을 Identifier로 사용해 만들고 RS256, Auth0 JWT profile, per-app authorization 기본값을 유지했다. `careerground:probe` 권한 하나를 추가했다. 별도 머신 간 접근은 허용하지 않았다.
- ChatGPT 화면이 CIMD를 선택 가능하다고 표시했고, 해당 연결 전용 CIMD 문서와 callback을 확인했다. 실제 callback ID와 URL은 이 문서에 싣지 않으며, 다음 설정 시에는 ChatGPT 화면의 현재 값을 다시 확인해야 한다. 공개 문서의 `client_id`와 redirect URI가 정확히 일치했다. 문서에는 `none`·`private_key_jwt`가 지원 방법으로, 단수형 선호값에는 `private_key_jwt`가 나왔다. Auth0 Import from URL 미리보기는 지원하지 않는 부가 필드 경고 2개를 표시했지만 URL·callback·JWKS를 매핑했고, `ChatGPT` CIMD 제3자 클라이언트를 생성했다.
- Auth0의 ChatGPT 클라이언트에 해당 API의 사용자 위임 접근을 만들고 `careerground:probe`만 허용했다. 저장 후 `1 / 1 permissions granted`로 확인했다. Client Access는 `0 / 1`로 남겼다.
- ChatGPT 개발용 연결 `CareerGround Dev OAuth PoC`를 터널·OAuth·CIMD·`careerground:probe`로 생성했다. 최초 연결 시 Auth0 `invalid_request: no connections enabled for the client`가 나왔다. Auth0 클라이언트 Connections 화면에 Google과 Database가 비활성으로 표시됐으며, 제3자 앱은 도메인 수준 연결이 필요하다는 안내가 있었다.
- 기존 `google-oauth2` social connection의 **Promote Connection to Domain Level**을 켰고 새로고침 후에도 `checked=true`, 미저장 표시가 없음을 확인했다. 이 설정은 개발 tenant의 **모든 제3자 앱에 Google 연결을 제공**하므로 운영 tenant에 그대로 복사해서는 안 된다. 현재 확인한 제3자 앱은 ChatGPT 하나였으며 Google 연결은 Auth0 개발 키를 사용하는 시험 설정이다. 재시도 후 Auth0의 **Google 계정으로 계속** 화면까지 도달했다. 사용자의 계정 선택과 인증 후 결과는 아직 없다.
- 이번 재개 시 BrowserOS의 `9000`·`9001`·`9200`은 루프백에서 열리고, 확인한 세 비루프백 IPv4 주소에서는 연결 거부였다. 방화벽 규칙은 임시이며 재부팅 후 재검증해야 한다. CareerGround MCP 서버와 `tunnel-client`는 사용자 로그인 검증을 위해 로컬에서 실행 중이다. 무인증 MCP `initialize`의 `401`과 OpenAI 내부 Resource 원점의 로컬 신뢰 출처 경고는 여전히 남으며, 실제 인증 성공으로 해석하지 않는다.

## 2026-09-26 실제 ChatGPT 계정 연결 확인

- 오래 열어 둔 Auth0 로그인 화면에서 Google 로그인을 진행했을 때 `invalid_request: ... couldn't find your session`이 나왔다. 화면의 추적 ID와 일치하는 Auth0 로그는 `Warning During Login`이며, 로그인 페이지에 직접 접근한 것으로 기록됐다. 이는 해당 시도의 실패 근거이지 Google 연동 자체의 실패 근거는 아니다.
- ChatGPT 앱에서 새 로그인 흐름을 시작한 뒤 Auth0 로그에 `2026-09-26T07:34:29.803Z` **Success Login**과 `2026-09-26T07:34:34.350Z` **Success Exchange**가 `ChatGPT` 애플리케이션으로 기록됐다. ChatGPT 앱 상세 화면에도 연결된 계정이 표시됐다. 계정 식별 정보와 토큰은 기록하지 않는다.
- 로컬 MCP 서버(`127.0.0.1:8001`)와 `tunnel-client`(`127.0.0.1:18081`)가 실행 중이고 터널 `/healthz`는 HTTP 200이다. `/readyz`는 HTTP 200이지만 본문에 무인증 `initialize`의 `Unauthorized`가 표시되므로 이 응답만으로 도구 호출 성공을 주장하지 않는다. 이 상태 점검 시점에는 ChatGPT의 실제 도구 호출을 아직 확인하지 않았다.
- 이후 사용자가 ChatGPT에서 `get_poc_identity`의 시험 ID와 인증 성공 응답을 확인했다. 동시에 `tunnel-client` 메트릭에서 `main` 채널의 `tools/call` HTTP 200 기록을 확인했다. 서버의 토큰 검증은 RS256 서명, 정확한 issuer·audience, 만료·발급 시간, 비어 있지 않은 `azp`, `careerground:probe` scope를 요구한다. 성공한 도구 실행은 이 경로가 통과했음을 뒷받침한다. 토큰 원문이나 시험 ID는 저장하지 않았다. 이 관측만으로 계정 간 분리, 연결 해제 후 토큰 철회, PKCE 요청·응답 세부 사항까지 확인한 것은 아니다.
- 사용자가 ChatGPT 앱의 계정 메뉴에서 `연결 해제`를 선택한 뒤, 앱 상세 화면에 더 이상 연결된 계정이 없고 `플러그인 설치`가 표시됐다. 다른 브라우저에서 앱 페이지를 새로 읽어 동일한 상태를 확인했다. Auth0 로그에는 해제 시점의 새 토큰 철회 항목이 보이지 않았다. 따라서 이는 ChatGPT 측 연결 해제의 증거이며, 이미 발급된 Auth0 액세스 토큰의 즉시 무효화 증거는 아니다. 연결 해제 직후 터널의 `main` 채널 `tools/call` HTTP 200 누적값은 2로, 다음 재호출 시험의 기준값으로 삼는다.
- 사용자가 이전 채팅에서 새 `get_poc_identity` 호출을 요청하자 ChatGPT는 앱 연결이 필요하다며 `나중에`와 `연결`을 표시했다. 이 직후에도 터널의 `main` 채널 `tools/call` HTTP 200 누적값은 2로 유지됐다. 따라서 이번 재호출은 인증된 도구 실행으로 이어지지 않았다. 단, 이는 ChatGPT 측 연결 해제 동작의 확인이며 Auth0가 이전에 발급한 액세스 토큰을 서버에서 즉시 폐기했다는 증거는 아니다.
- 사용자가 `연결`로 같은 계정을 다시 인증한 뒤 이전과 동일한 시험 ID 및 인증 성공을 확인했다. Auth0 로그에는 `2026-09-26T13:09:46.802Z` **Success Login**과 `2026-09-26T13:09:54.483Z` **Success Exchange**가 새로 기록됐고, ChatGPT 앱 상세 화면에 연결된 계정이 다시 나타났다. 터널의 `main` 채널 `tools/call` HTTP 200 누적값은 2에서 5로 늘었다. 시험 ID 값은 문서에 남기지 않는다. 같은 계정의 재연결 안정성은 확인했지만, 다른 계정과의 ID 분리는 아직 관측하지 않았다.
- Auth0의 **CareerGround MCP Dev PoC** API 설정을 처음 읽었을 때 `Maximum Access Token Lifetime`은 `86400`초(24시간), `Implicit / Hybrid Flow Access Token Lifetime`은 `7200`초(2시간)였다. 이는 API의 구성값이지 당시 발급된 개별 토큰의 `exp - iat`를 직접 측정한 값은 아니다. ChatGPT 연결 해제 후 새 도구 호출이 차단된 사실과 기존 발급 토큰의 즉시 무효화는 구분한다.
- BrowserOS에서 ChatGPT 앱의 `다른 계정 연결`을 눌러 새 Auth0 로그인 화면을 열었다. `Google 계정으로 계속` 이후 계정 선택 화면 없이 ChatGPT 앱으로 돌아왔고, 연결된 계정은 여전히 1개였다. 따라서 두 번째 Google 사용자의 분리 검증은 아직 수행되지 않았다. 기존 브라우저 로그인 세션을 재사용했을 가능성이 있지만 해당 원인은 별도로 확인하지 않았다. 사용자가 사용할 별도 시험 계정을 정한 뒤에만 계정 선택·로그인을 진행한다.
- 사용자는 현재 Google 계정 하나로 개발용 PoC를 계속하기로 했고 별도 Google 시험 계정은 만들지 않는다. `tests/test_mcp_auth_poc.py`는 서로 다른 합성 `sub`에 다른 시험 ID가 부여되는지 검사한다. 이는 실제 두 계정의 ChatGPT 연결 시험을 대체하지 않는다.
- 실제 OAuth discovery를 다시 읽고 `assess_mcp_oauth_metadata`를 CIMD 모드로 실행해 정확한 issuer, `S256` 광고, CIMD 지원, 호환 토큰 인증 방법(`none`, `private_key_jwt`)을 확인했다. Auth0 클라이언트 설정은 `Third-party`(완화 모드 아님) 및 `CIMD`로 표시된다. [OpenAI Docs](https://developers.openai.com/plugins/build/auth)는 ChatGPT의 `S256` 사용을 명시하고, [Auth0 제3자 앱 보안 문서](https://auth0.com/docs/get-started/applications/third-party-applications/security-controls)는 인가 코드 흐름에 PKCE를 강제한다. 실제 로그에는 ChatGPT의 인가 코드 **Success Exchange**가 있다. 단, 이번 요청의 `code_challenge_method=S256`과 `code_verifier` 존재 여부를 원문에서 직접 관측하지 않았고, Auth0 discovery는 `S256` 외 `plain`도 광고한다. 따라서 **S256 실요청 직접 증거**는 미완료로 둔다. 토큰·코드·검증자 값은 수집하지 않는다.
- 개발용 **CareerGround MCP Dev PoC** API의 `Maximum Access Token Lifetime`과 `Implicit / Hybrid Flow Access Token Lifetime`을 모두 `3600`초(1시간)로 낮췄다. Auth0 화면을 두 번 다시 읽어 두 값이 유지되고 미저장 변경이 없음을 확인했다. `Allow Offline Access`는 꺼진 상태다. 기존 발급 토큰은 설정 변경만으로 무효화되지 않으며, 새 개별 토큰의 실제 `exp - iat`도 아직 측정하지 않았다. 제품 데이터가 없는 합성 PoC에 한정한 설정이고 운영용 수명·refresh·재인증 정책은 미결정이다. [Auth0 액세스 토큰 수명 안내](https://auth0.com/docs/secure/tokens/access-tokens/get-access-tokens)
- 서버의 현재 검증기는 서명·issuer·audience·scope·시간만 검사하고 ChatGPT의 연결 상태나 계정 삭제 상태를 조회하지 않는다. 따라서 보유자가 기존 유효 JWT를 직접 제시할 경우 ChatGPT UI 연결 해제와 별개로 만료 전까지 통과할 수 있다. [Auth0의 로그아웃 후 액세스 토큰 안내](https://support.auth0.com/center/s/article/Invalidate-the-API-token-after-user-logout)도 발급된 JWT의 즉시 철회를 보장하지 않는다. 이 PoC에는 제품 데이터나 쓰기 도구가 없어 이 제한을 기록하고 계속하지만, 실제 사용자 데이터 연결 전에는 서버 측 계정 상태/철회 확인을 설계·시험해야 한다.
- `PYTHONDONTWRITEBYTECODE=1 uv run --locked python -m unittest tests.test_mcp_auth_poc -v`: 6개 테스트 통과. 여기에는 만료·미래 발급 토큰 거부, 잘못된 issuer·audience·scope·서명 거부, 서로 다른 합성 subject의 ID 분리가 포함된다. 실제 Auth0 토큰의 만료/철회 동작을 시험한 것은 아니다.

## 근거

- [OpenAI 공식 MCP 인증 안내](https://developers.openai.com/plugins/build/auth)
- [OpenAI 공식 연결·시험 안내](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [OpenAI 공식 Secure MCP Tunnel 안내](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Auth0 CIMD 등록·tenant 설정 안내](https://auth0.com/docs/get-started/auth0-overview/create-applications/register-applications-with-cimd)
- [Auth0 도메인 수준 연결 안내](https://auth0.com/docs/authenticate/identity-providers/promote-connections-to-domain-level)
- [MCP Python SDK 인증 안내](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/authorization.md)

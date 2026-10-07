# 비공개 제품 연결 변경안 — 승인 범위 실행 완료

## 현재 관측

2026-10-04 BrowserOS에서 사용자의 기존 `CareerGround Dev OAuth PoC` 재연결
완료 보고 후 확인했다. 현재 설치된 앱 도구 목록은 `Read 1`이며,
새 대화에서도 `get_my_profile`은 제공되지 않고 `get_poc_identity`만 제공된다고
응답했다. 제품 MCP를 호출한 성공 증거는 없다.

기존 플러그인 ZIP을 내려받아 같은 이름과 `.app.json`의 동일 앱 바인딩을
보존하고, 버전 `1.0.1`과 최신 `career-interview` 스킬을 반영했다.
BrowserOS에서 새 버전 업로드 성공과 `스킬 1`을 확인했지만 `Read 1`은 유지됐다.
기존 client/계정/API/터널을 변경하거나 공개 배포하지 않았다.

공식 문서는 개발 연결의 도구 변경 후 Refresh를 안내하지만, 현재 관측된
기존 플러그인의 관리·계정·추가 작업 메뉴에서는 그 항목을 찾지 못했다.
[ChatGPT 연결 갱신 안내](https://developers.openai.com/plugins/deploy/connect-chatgpt)

## 필요한 범위 확대

기존 터널을 선택한 새 사용자 지정 MCP 연결 양식에 CIMD client URL과
OAuth callback이 표시됐다. 최초에는 새 client가 필요할 것으로 판단하여 생성을
취소하고 아래 범위 확대를 승인받았다. 승인 후 Auth0 기존 client의 External Client
ID와 직접 비교하니 **같은 CIMD URL**이었다. 따라서 새 Auth0 client나 추가 grant는
만들지 않고 기존 등록을 재사용했다. 아래 2–3은 승인 상한이며 실제 실행하지 않았다.

1. 사용자의 ChatGPT 계정에 비공개 `CareerGround Phase A Dev` 연결 하나를 만든다.
   OAuth 인증을 사용하고 기존 `careerground-dev-mcp` 터널과 기존 개발 API
   resource/issuer를 그대로 사용한다. 현재 제품 서버의 도구를 다시 검색한다.
2. 연결에 필요한 Auth0 제3자 CIMD client 하나의 등록/사용을 허용한다.
   실제 생성 양식에서 관측한 client URL과 callback만 사용한다.
   기존 Web client, PoC client와 그 callback은 변경하지 않는다.
3. 해당 새 client의 기존 개발 API User-Delegated Access에 다음 여섯 권한만
   허용한다: `career.profile.read`, `career.profile.write`,
   `career.artifact.read`, `career.artifact.write`, `career.export`, `career.delete`.
   기존 API permission을 재사용하며 Client Access는 0, Always grant all은 끈다.
   `careerground:probe`와 `offline_access`는 추가하지 않는다.
4. 필요한 실제 로그인/동의는 사용자에게 한 단계씩 요청한다. CareerGround Web과
   동일한 제공자 계정을 사용한다. ChatGPT 계정이나 Auth0 관리자 계정과 같을
   필요는 없다. 비밀번호·코드·토큰을 채팅으로 받지 않는다.

새 tenant/API/터널/model resource, 유료 플랜 변경, 공개 게시, 운영 연결,
다른 앱 grant, 토큰 수명 변경은 포함하지 않는다. 제품 권한은 브라우저의 사실·
문구·내보내기·삭제 승인을 대신하지 않는다. 실제 삭제 step-up은 현재 미지원이며
그 권한이 있어도 실행을 거부한다.

## 승인 후 확인할 것

- 최신 제품 도구 목록(인증 개발 서버는 기존 30개 + 제안 도구 4개)과 실제
  `get_my_profile` 호출. 제공되지 않는 도구를 성공했다고 기록하지 않는다.
- Web과 ChatGPT의 동일 프로필, 합성 사실 검토, JD 선택 저장, R2 원문 비교 승인,
  명시적 내보내기의 실제 왕복.
- 토큰·권한 오류는 안전하게 거부한다. 계정 두 개의 실제 격리, 실제 refresh/
  revocation/삭제 재인증은 관측한 항목만 기록한다.

승인 상태: **완료**. 사용자가 “비공개 제품 연결·CIMD client 추가 승인”이라고
응답했다. 위 범위에 한정해 BrowserOS에서 실행했고 실제 완료 항목은 아래에 기록한다.

## 실행 관측

- `CareerGround Phase A Dev` 비공개 연결 생성 후 설치 목록에서 확인했다.
  기존 앱·개발 API·터널을 보존했고 Auth0 client와 grant도 추가 생성하지 않았다.
- 기존 등록과 일치하는 CIMD 방식을 사용한다. 기본 identity scope는
  `openid profile email`, 필수 제품 scope는 승인한 여섯 개다.
  `offline_access`, 추가 OIDC 개인정보 scope, `careerground:probe`를 요청하지 않는다.
- 실제 Auth0 사용자 동의 화면에 여섯 제품 scope가 표시됐다. 사용자가 직접
  수락하고 “제품 연결 동의 완료”라고 보고했다.
- 실제 제품 도구 **34개(읽기 15·쓰기 19)**가 검색됐다. 실제 ChatGPT의
  `get_my_profile`이 Web과 동일 프로필과 버전 0을 반환했다. 실제 ID/계정 이름은
  이 저장 문서에 기록하지 않는다.
- 새 제품 플러그인도 내려받은 실제 `.app.json`의 바인딩을 그대로 보존하고
  `career-interview` 스킬을 버전 1.0.1로 업로드하고 실제 제품 왕복을 시험했다.
  이후 Use 검토 안내를 보강한 1.0.2 업로드와 설치 버전을 확인했다.
- 실제 ChatGPT → Web의 사실/Use 검토, JD 선택 저장과 별도 근거 연결,
  R1 생성, R2 비교 저장, 별도 export 승인과 INLINE 반환이 완료됐다.
  재시작 후 동일 프로필 버전 2와 두 artifact의 보존을 확인했다.
- Web logout은 MCP 토큰을 폐기하지 않았다. 실제 삭제 호출은 step-up adapter가
  없어 REVIEW_REQUIRED로 거부됐으며 DB 삭제 request/ledger는 각각 0이었다.
  실제 provider refresh/revocation, 삭제 성공, 두 실제 계정 시험은 미완료다.
- 상세 관측은 [제품 시험 JSON](chatgpt_product_oauth_observations_20261004.json)과
  [개발 수용 결과](CareerGround_Phase_A_Hybrid_Acceptance_2026-10-04.md)에 기록했다.
  시험 서버·터널은 종료했다. 새 client/grant·유료 자원·공개 배포는 수행하지 않았다.

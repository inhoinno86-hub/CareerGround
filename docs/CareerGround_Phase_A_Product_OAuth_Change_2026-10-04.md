# 개발 제품 OAuth 권한 변경안

BrowserOS 읽기 전용 확인(2026-10-04): 기존 `CareerGround MCP Dev PoC` API의
permission은 `careerground:probe` 한 개이며 기존 `ChatGPT` 제3자 client의
User-Delegated Access도 그 한 개만 허용한다. Client Access는 0개다.

## 승인 요청 대상

기존 개발 API에 아래 여섯 permission을 추가하고, 기존 ChatGPT client의
User-Delegated Access에 그 여섯 개만 추가한다. 기존 probe permission은 유지한다.

| permission | 설명 |
| --- | --- |
| `career.profile.read` | Read own synthetic career profile and profiling sessions |
| `career.profile.write` | Prepare own synthetic profiling input and fact review |
| `career.artifact.read` | Read own synthetic JD and resume artifacts |
| `career.artifact.write` | Prepare own synthetic JD and resume review |
| `career.export` | Export explicitly approved own synthetic data |
| `career.delete` | Request bounded synthetic deletion; verified reauthentication remains required |

Client Access, Always grant all permissions, 다른 client의 grant는 변경하지 않는다.
issuer/resource/client/callback, token lifetime, offline access, 과금 설정은 변경하지 않는다.
새 tenant/client/API/tunnel/model resource는 생성하지 않는다.

## 연결·검증 조건

- 기존 private tunnel에는 실제 JWT를 검증하는 제품 MCP만 제공한다.
  관리 Web과 같은 DB를 사용하고 미등록 사용자는 브라우저에서 명시적 가입이 필요하다.
- 합성 경력 문장만으로 실제 OAuth 동의/동일 프로필/브라우저 승인을 확인한다.
- probe token, ID token, 미허용 scope, 다른 사용자/삭제된 계정은 거부한다.
- scope grant 자체는 사실/문구/export/삭제의 브라우저 승인이 아니다.
- 실제 step-up이 없는 삭제를 MOCK으로 대체하지 않는다. 미지원 작업은 거부해 보고한다.
- 로그인/MFA/OAuth 동의가 필요하면 사용자에게 해당 한 단계만 요청한다.

2026-10-04 사용자가 개발 API·ChatGPT 위임 권한 변경을 명시적으로 승인했다.
BrowserOS에서 위 6개 permission 추가와 ChatGPT User-Delegated Access의
7/7(probe 포함) 저장을 확인했다. Client Access와 다른 세 앱은 0/7이며
Always grant all permissions는 선택하지 않았다. 이 설정 완료는 실제 제품 호출
성공을 뜻하지 않는다. 기존 ChatGPT 앱의 도구 목록에는 아직 probe 한 개만 관측됐다.
[공식 MCP 인증 계약](https://developers.openai.com/plugins/build/auth)에 따라
CareerGround가 매번 서명/issuer/audience/시간/scope/활성 계정을 검증한다.

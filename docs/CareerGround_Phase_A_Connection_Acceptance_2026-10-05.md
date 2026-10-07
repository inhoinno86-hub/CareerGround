# 실제 계정 격리·철회·만료 수용 준비

상태: 로컬 차단 경계 구현·검증. 실제 두 계정/제공자 철회 시험 미완료.

후속: opt-in denial registry/대상 client를 Auth0 개발 runtime에 주입하고, 소유자 Web 검토·명시적 차단 화면을 연결했다. 서명된 HTTP 요청의 차단/다른 계정·client/Web 유지/재시작 시험을 통과했다. 실제 사용자용 QA runtime에는 아직 차단 옵션을 켜지 않았다. 아래 미연결 설명은 이 후속 전 준비 상태다.

## 구현한 경계

- 기존 JWT 서명/issuer/audience/scope 검증 **이후** 검증된 identity/client 조합의 차단을 조회한다.
- `DevelopmentConnectionRevocations`는 별도 owner-only 디렉터리에 keyed digest와 서명만 저장한다.
  원문 토큰·subject·client ID는 차단 기록에 넣지 않는다. 재시작 뒤에도 차단되며 같은 client가
  새 토큰을 발급받아도 거부한다. 차단 기록 누락/변조/읽기 실패는 접근 거부다.
- 정확한 account/client 조합만 차단한다. 다른 계정과 다른 client, 해당 계정의 Web 로그인은 유지된다.
- trusted local `block` 호출만 제공한다. 모델-facing 철회 도구와 공개 mutation route는 없다.
- factory의 `connection_is_revoked` 주입 경계로 연결한다. **현재 실제 Auth0 runtime에는 아직 주입하지 않았다.**
  로컬 시험을 실제 연결 해제 완료로 표시하지 않는다.

이 backend는 한 process 전용이다. 전체 디렉터리/키를 과거로 복원한 rollback과 여러 worker의
동기화는 해결하지 않았으며 독립 운영 anchor가 필요하다. 이미 수행 중인 요청의 취소를 보장하지 않는다.
새 요청을 차단하는 검증과 provider grant/refresh token 철회를 구분한다.

## 실제 시험 범위와 영향

기존 PoC와 Phase A 제품 연결은 같은 CIMD client/사용자 grant를 공유한다.
Auth0 grant 철회 또는 해당 account/client 차단은 **두 연결 모두**에 영향을 줄 수 있다.
개별 ChatGPT 앱 UI의 disconnect와 provider의 사용자 grant 철회는 같다고 가정하지 않는다.
현재 Web logout은 해당 Web session만 무효화하며 MCP 철회가 아니다.

실제 시험 전 필요한 선택/승인:

1. 사용자 소유의 두 번째 개발 로그인 identity를 사용할지 확인한다. 관리자 계정이 아니라
   CareerGround 이용자 identity다. 새 계정 생성·실제 경력 데이터 입력은 자동 수행하지 않는다.
2. 새로운 격리 QA store를 준비하고 A/B 각자 합성 원문 한 개만 등록한다.
3. Web/MCP profile, source, artifact, export, confirmation, deletion의 교차 접근이
   인증 거부 또는 동일한 NOT_FOUND여야 한다. 존재 정보와 원문도 반환하지 않아야 한다.
4. 현재 client에 local denial을 연결할 경우 영향을 받는 기존 두 앱을 명시한다.
   승인 후 사용자가 관리 화면에서 본인 연결을 차단하는 경로가 필요하다.
5. 실제 disconnect/기존 grant 철회를 승인받으면 전후 시각과 새 요청 결과만 기록한다.
   provider에서 살아 있는 access JWT가 자체적으로 취소된다고 가정하지 않는다.
6. 복구는 사용자의 새 OAuth 동의와 명시적 local deny 해제 정책을 준비한 뒤 수행한다.
   무조건 토큰 재발급/서버 재시작으로 차단이 풀리게 하지 않는다.

## 갱신 판단

현재 제품 연결은 `offline_access`를 요청하지 않는다. 승인 검토와 receipt는 exact token에
묶이므로 토큰 변경 뒤 기존 receipt를 재사용하지 않는다. 현재는 **refresh 도입 보류**를 권장한다.
만료되면 사용자가 연결을 재인증하고 새 검토를 준비한다. 실제 만료 지연과 ChatGPT의 UI 동작은
별도 관측해야 하며 refresh/rotation/재사용/키 교체 통과를 주장하지 않는다.

나중에 장기 연결이 필요할 때 client/API offline access, rotation/reuse 검출, disconnect 시
refresh 폐기, access 차단과 복구 정책을 함께 승인받는다. 짧은 토큰 수명/유료 기능을 임의로 변경하지 않았다.

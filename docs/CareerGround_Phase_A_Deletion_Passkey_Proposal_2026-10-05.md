# 비공개 개발 MVP의 삭제 전용 패스키 변경안

상태: 로컬 구현·서명 검증 시험과 BrowserOS 가상 인증기의 등록/삭제 전 확인 통과. 실제 사용자 기기 등록·삭제 수용은 아직 미완료다. OTP MFA·유료 서버 AI는 보류하며 Auth0 factor/Action/client 설정은 변경하지 않는다.

## 현재 계정과의 관계

Auth0의 패스키는 데이터베이스 연결 방식이다. 기존 Google 소셜 identity에 설정 하나로 추가할 수 있다고 가정하지 않는다. 새 Auth0 사용자 생성·계정 병합 없이 CareerGround 개발 화면에 별도 WebAuthn 공개키를 등록하는 대안을 구현했다.
[Auth0 데이터베이스 연결](https://auth0.com/docs/authenticate/database-connections),
[Auth0 패스키 실습](https://developer.auth0.com/resources/labs/authentication/passkeys)

WebAuthn의 서버 검증은 origin/RP, 일회성 challenge, 등록된 공개키의 서명, user presence와 user verification을 확인한다. 기기 생체 정보·PIN·개인키는 CareerGround 서버로 받지 않는다.
[W3C WebAuthn](https://www.w3.org/TR/webauthn-3/),
[py_webauthn 등록](https://duo-labs.github.io/py_webauthn/registration.html),
[py_webauthn 인증](https://duo-labs.github.io/py_webauthn/authentication.html)

## 적용할 구체 범위

1. 기존 Google/Auth0 identity와 다른 기존 자료는 유지하고, 새 격리된 합성 QA store만 사용한다.
2. 별도 owner-only 패스키 registry를 명시적으로 초기화한다. 정확한 store의 키와 issuer/client/resource binding, loopback origin에 묶는다. 일반 실행에는 활성화하지 않는다.
3. 최초 등록은 로그인한 사용자의 범위 확인 → 같은 소유자 fresh signed OIDC 교환 → 사용자가 기기에서 PIN·생체 확인 → 공개키 등록이다. 최초 등록은 기존 identity-provider 계정의 신뢰를 따른다. Google 재로그인이 비밀번호 재입력/MFA를 입증한다고 주장하지 않는다.
4. 기존 공개키 하나를 다른 키로 덮어쓰지 않는다. Web/모델의 키 교체·삭제·분실 복구 경로는 제공하지 않는다. 등록 후에는 enrollment flag를 끌 수 있다.
5. 삭제는 정확한 영향 검토 → fresh same-owner OIDC 교환 → 등록된 기기의 새 서명/UP/UV 검증 → 별도 최종 확인이다. 인증만으로 삭제하지 않는다. 서명된 auth_time 기준 3분, 소유자/세션/프로필 버전/영향 hash를 유지하며 잘못된 시도는 일회성 요청을 소비한다.
6. PROFILE 로컬 삭제만 실행하며 coverage는 `FOUNDATION_ONLY`다. 제공자 계정·ChatGPT 대화·사용자 다운로드·외부 백업 삭제 완료를 주장하지 않는다.

## 등록·분실·복구와 제한

- 이번 제안은 개인 비공개 합성 개발 MVP에만 적용한다. 공개 가입/운영 보안 수용을 대신하지 않는다.
- 패스키를 잃거나 사용 가능한 기기 확인 수단이 없으면 삭제는 계속 차단한다. 정상 OIDC 로그인과 자료 관리는 별도 유지한다. 인증 검증을 생략하는 복구 버튼은 만들지 않는다.
- 교체/복구는 별도 신뢰·본인 확인 정책을 준비한 후 결정해야 한다. 구매나 유료 인증 자원은 요구하지 않는다. 기존 기기에서 지원하지 않으면 지원 미확인으로 남긴다.
- `localhost`와 `127.0.0.1`, 포트/공개 도메인이 달라지면 원래 origin binding을 재사용하지 않는다. 실제 등록 시험은 기존 허용 callback인 `http://localhost:5000`에서 진행한다.
- 한 process 개발 전용이다. registry 전체/키 동시 rollback, local operator 탈취와 운영 복구 anchor는 해결하지 않았다.
- 공개키 레코드는 경력 자료와 별도 인증 메타데이터다. PROFILE 삭제가 계정/인증 수단 전체 삭제를 뜻하지 않는다.

## 검증과 승인 경계

실제 CBOR/ECDSA proof 시험에서 잘못된 challenge/origin/RP/UV/UP/서명/키/소유자/userHandle, counter 재사용, registry 변조/누락/다중 process, 다른 세션/만료/중복 요청을 거부했다. 합성 소셜 인증 이후 별도 패스키와 최종 승인으로 로컬 삭제가 가능했다. 관련 기존 경로 포함 35개 시험이 통과했다.

BrowserOS에서는 새 합성 탭에만 CDP 가상 인증기를 설치해 등록과 삭제 전 기기 확인 후 최종 승인 화면까지 진행했다. 이는 실제 사용자의 기기/PIN/생체 검증 증거가 아니다. 사용자 대신 실제 등록·최종 삭제를 승인하지 않는다.

위 최초 등록 신뢰와 분실 제한을 적용하는 실제 개발 시험은 사용자 검토 후 시작한다. 현재 기존 Auth0 계정·실제 QA store에 패스키를 등록하거나 삭제를 실행하지 않았다.

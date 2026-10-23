# STEP 02 — AppAuth 설치·OIDC 구현·현재 검증

후속 현재 결과: [실제 OIDC 기기 수용 PASS](mock_interview_oidc_device_20261011.md).
아래는 휴대폰 연결 전 구현·빌드 시점 기록이며 NOT_RUN을 그 시점대로 보존한다.

2026-10-11. 사용자 **“추가 설치 진행 부탁해”**로
[설치 확인안](mock_interview_oidc_setup_20261011.md)의 설치·구현·동일 폴드7 시험 범위를 승인받았다.
**설치·로컬 검증 PASS / 새 APK 기기 설치·실제 앱 OIDC NOT_RUN(USB 연결 대기).**

## 구현과 보관

- AppAuth **0.11.1** 고정. Maven Central/Google Maven에서 기존 전용 Gradle cache로 필요한 의존성을
  설치했다. baseline 대비 신규 파일 33개 / **2,072,149 bytes**이며 실제 HTTP 전송량 측정은 아니다.
  resolved 목록/크기는 아래 artifact의 `dependency-receipt.json`에 있다.
- debug 앱에 승인한 공개 설정만 포함했다. 외부 브라우저 Authorization Code + PKCE S256,
  무작위 state/nonce, 정확한 host 없는 callback 경로, pending request 전체 일치를 검사한다.
  callback은 한 번 소비하고 프로세스 재시작으로 pending request가 없으면 거부한다.
  [AppAuth 0.11.1 callback 구현](https://github.com/openid/AppAuth-Android/blob/0.11.1/library/java/net/openid/appauth/RedirectUriReceiverActivity.java)을
  확인해 앱 receiver에서 경로를 먼저 제한했다.
- code 교환에 client secret을 사용하지 않는다. 요청한 openid의 ID token이 없으면 거부하며,
  AppAuth의 ID token/nonce 검증 뒤 access token만 앱 RAM에
  유지한다. AuthState 저장, refresh token 저장·자동 갱신, token/경력 자동 저장은 추가하지 않았다.
  인증 브라우저 및 OS/SDK의 인증 화면 복원 상태는 앱의 경력 세션 저장과 별개다.
- runtime은 `--synthetic-dev` 또는 `--oidc-config` 중 정확히 하나를 선택한다. 합성 credential은
  OIDC 모드에서 거부한다. 고정 issuer의 공개 discovery/JWKS만 조회하며 다른 endpoint/redirect,
  64 KiB 초과/중복 키 metadata를 거부한다. token 헤더의 URL은 조회하지 않는다.
- RS256 서명·issuer·audience·만료·scope `use:interview`·native client를 검증한다. owner는 검증한
  issuer+sub의 hash다. 공개 키 RAM cache는 5분이며 unknown kid 갱신/실패 재시도 간격은 30초다.
  만료 cache를 갱신하지 못하면 거부한다. Android가 주장한 owner나 ID token만으로 API를 열지 않는다.
- logout 요청 성공 시 owner 세션을 지우고 해당 access token hash를 만료까지 RAM 거부 목록에 둔다.
  runtime 재시작 시 이 목록도 사라진다. 제공자 SSO/다른 token의 전역 취소는 아니다.
  앱은 통신 실패 여부와 무관하게 token/자료 참조를 해제하며 메모리 완전 덮어쓰기를 보장하지 않는다.
- 개발용 USB reverse/loopback만 허용한다. release는 미구성으로 거부한다. FLAG_SECURE·SAF·백업 금지,
  원본 고정·검토 gate·기여/금지 경계는 유지했다. 유료 호출·배포·새 Auth0 설정 변경은 없다.

## 검증 결과

| 실행 | 결과 | 범위와 한계 |
| --- | --- | --- |
| Gradle 의존성 resolve | PASS | AppAuth/전이 설치, 기존 SDK/JDK/Gradle/Compose 버전 유지 |
| Python 인증·세션 | PASS 30 | 기존 16 + offline RSA 정책 8 + OIDC handler/cache 6. 합성 서명이며 실제 로그인 아님 |
| Portable exchange | PASS 7 | 기존 계약/fixture 회귀, 실제 ChatGPT 앱 왕복 아님 |
| JVM | PASS 2 | r1/r3 빌드에서 실행, r2 UP-TO-DATE |
| debug 앱/시험 APK | PASS | 아래 정확한 hash/동일 기존 debug 인증서 |
| lint / Ruff / diff check | PASS | lint 오류 0, 경고 8(버전 안내 6·UseKtx 2) |
| 실제 공개 discovery/JWKS | PASS | 승인한 Auth0 issuer, RSA 공개 키 2개. OAuth token 요청 없음 |
| 새 APK의 instrumentation | NOT_RUN | 5개 컴파일 완료. callback/request 경계 2개 추가 |
| 새 APK 설치·실제 앱 로그인/취소/로그아웃 | NOT_RUN | ADB 기기 0개. 사용자 USB/디버깅 조작 요청 중 |
| 실제 OIDC 세션 저장/재가져오기 | NOT_RUN | 기존 합성 APK의 SAF PASS를 새 인증 시험으로 승계하지 않음 |
| STEP 03–04 AI·음성·result·ChatGPT 왕복 | NOT_RUN | STEP 02 실제 인증 수용 후 순차 수행 |

ASGI 시험은 잘못된 서명/issuer/audience/client/scope/만료·합성 credential 거부,
두 합성 사용자 접근/restore 분리, logout 후 해당 token 거부, 키 회전·throttle·갱신 실패·
metadata redirect/크기/중복 키/다른 endpoint 거부를 확인했다. 실제 두 사용자 계정 로그인을 실행한 것은 아니다.

## APK와 증거

- 앱: `dev.careerground.interview.dev`, version **0.1.1-step02-oidc**, code **2**.
- 앱 SHA256: `dea6692fe7dc561cc39a6007e4340b9572068d94ffb3321a521ec6981df25a00`.
- 시험 APK SHA256: `7311992d441670b510e8d34056de83fc2d2d273143590d57213c19e65382d07f`.
- debug 인증서 SHA256: `d258e5a2420327f238eb40ec765800dbf05bc563fc634a71475a6830e3f3d46a`.
- 권한: INTERNET 및 AndroidX 앱 전용 signature receiver 권한. 마이크/광범위 저장소 권한 없음.
- 증거 root: `/home/inno/.local/share/careerground-android/artifacts/oidc-step02-20261011/`.
  baseline, 설치/resolved receipt, build-r1/r2/r3 로그, Python/exchange 로그, APK, implementation receipt.
  중간 빌드 APK도 `build-r1/`, `build-r2/`에 보존했다. 이전 합성 APK·기기 파일은 변경하지 않았다.
- 원래 handoff SHA256:
  `11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8` (변경 없음).
- 구조화 결과: [JSON](mock_interview_oidc_implementation_20261011.json).

## 연결 후 진행

1. 사용자 USB 연결/디버깅 허용을 확인하고 정확히 한 기기의 모델·설치 버전을 확인한다.
2. 동일 debug 인증서로 기존 앱을 업데이트하고 5개 instrumentation을 실행한다.
   기존 앱/시험 파일을 삭제하거나 app data를 임의 초기화하지 않는다.
3. OIDC runtime을 loopback에서 실행하고 해당 기기의 8765 reverse만 연결한다.
4. 앱 로그인 취소/재시도를 확인하고 외부 브라우저 로그인 화면에서 사용자에게 직접 입력을 요청한다.
   Auth0 관리자 계정 로그인은 앱 계정 로그인을 대신하지 않는다. 비밀번호·코드·token은 채팅/로그에 받지 않는다.
5. runtime 서명 검증까지 통과한 앱 연결을 확인한다. 기존 합성 owner 세션 파일은 거부되어야 한다.
   합성 handoff로 새 OIDC 세션을 만들고 새 이름으로 수동 내보내기/재가져오기/로그아웃을 확인한다.
   unsigned 외부 파일의 owner 문자열은 파일 소유권 인증 증명이 아니다.
6. 실패 원인에 따라 승인 범위에서 보완·재검증한다. 시험 종료 후 해당 reverse/runtime을 정리하고
   USB 디버깅 해제는 사용자에게 안내한다. 설치 앱·수동 파일은 보존한다.

현재 시험 runtime/reverse를 시작하지 않았다. **STEP 02 부분 수용**, 실제 앱 인증 수용 전 STEP 03으로
넘어가지 않는다. 실제 개인 파일 확정은 이 합성 개발의 선행 조건이 아니다.

# STEP 02 실제 기기·개인 로그인 실행안 — 2026-10-11

**검토용이며 아직 연결·등록·기기 설치를 실행하지 않았다.**
Android 앱 빌드·JVM 시험·lint는 실제 실행했다. 다음 실행은 최초 요청의
“외부 설치·등록/연결 변경·배포·유료 실행은 실행 전에 확인” 조건에 해당한다.
이미 승인한 네이티브·개인 로그인·음성·수동 보관 선택을 다시 묻는 문서가 아니다.

## 1. 폴드7의 합성 자료 시험

대상은 사용자가 제공한 **SM-F966N / Android 16** 한 대다. 에뮬레이터 설치 없이 USB로
PC의 loopback runtime에 연결하는 안이다. 기기 serial은 공개 문서·시험 결과에 기록하지 않는다.

| 산출물 | 값 |
| --- | --- |
| 앱 package / version | `dev.careerground.interview.dev` / `0.1.0-step02` (code 1) |
| 앱 APK | `/home/inno/.local/share/careerground-android/artifacts/step02-20261011-r2/app-debug.apk` |
| 앱 SHA-256 | `a73b250a1dafc9d4d2419f628478dca3737f0fcd27e9459cbe02ef0eefd22443` |
| 시험 APK | 같은 디렉터리의 `app-debug-androidTest.apk` |
| 시험 APK SHA-256 | `8789fc02fbc9922c1e4948dbb0531d00749ed346b2c0c73b5c96b408608da5c7` |
| SDK | min 33 / target 36 |
| 요청 권한 | INTERNET 및 AndroidX가 추가한 앱 전용 signature 권한. 마이크·광범위 저장소 권한 없음 |
| 서명 | 로컬 debug 키. 배포용 서명이 아님 |

승인할 실행 범위:

1. 사용자가 USB 디버깅을 켜고 USB로 연결한 뒤, 휴대폰의 PC 허용 창을 직접 확인한다.
   PIN·계정 비밀번호·인증 코드는 전달하지 않는다. 기기 설정의 정확한 메뉴는 실제 화면에서 확인한다.
2. 전용 SDK의 `platform-tools/adb`로 연결 상태를 확인하고 선택한 한 대에만 명령을 보낸다.
   같은 package가 이미 있으면 서명·버전을 먼저 확인한다. 출처 불명 앱을 덮어쓰지 않는다.
3. 위 앱과 시험 APK를 설치하고, 해당 기기에 `reverse tcp:8765 tcp:8765`를 설정한다.
   runtime은 PC의 `127.0.0.1:8765`만 사용한다. LAN·공개 포트·무선 디버깅은 추가하지 않는다.
4. repo의 `fixtures/portable/handoff-v1.json` 합성 파일만 새 시험 폴더에 복사한다.
   기존 개인 파일을 조회하지 않는다. 임시 연결 코드는 RAM에서만 사용하고 결과·로그에 넣지 않는다.
5. 앱 실행 및 준비된 Android instrumentation 3사례를 실행한다. 시험 APK 컴파일 성공과 시험 실행 성공을 구분한다.
6. 실제 시스템 파일 선택기로 handoff를 선택하고 구조 검사·포함 범위 검토·고정·시작·중지,
   로컬 Downloads에 수동 세션 저장·재가져오기·재검토를 확인한다. 그 파일만 PC로 가져와 hash를 검사한다.
7. 커버/펼침·회전·분할 창, 파일 선택/저장 취소, 앱 재시작 시 미저장 내용 소멸을 확인한다.
   화면 캡처 방지 설정은 유지한다. 합성 자료의 앱 관찰 결과만 기록한다.
8. 시험 종료 시 해당 기기의 8765 reverse만 해제하고 시험용 runtime을 종료한다.
   휴대폰의 USB 디버깅 해제는 사용자가 직접 수행한다. 다른 연결의 reverse나 ADB 서버는 임의 종료하지 않는다.
   설치 앱·사용자가 저장한 파일은 자동 삭제하지 않는다.

명령 형태(승인·기기 선택 후 실행; placeholder를 실제 기기 식별자로 치환하되 기록에서는 비공개):

```text
adb -s <선택한_기기> install <위_앱_APK>
adb -s <선택한_기기> install <위_시험_APK>
adb -s <선택한_기기> reverse tcp:8765 tcp:8765
adb -s <선택한_기기> shell am instrument -w dev.careerground.interview.dev.test/androidx.test.runner.AndroidJUnitRunner
adb -s <선택한_기기> reverse --remove tcp:8765
```

시험용 연결 코드는 **실제 개인 계정 로그인 증거가 아니다**. 이 시험은 합성 파일·UI·SAF 경로를 확인한다.
한국어 마이크/STT/TTS와 실제 면접·result는 STEP 03 범위이며 아직 실행하지 않는다.

## 2. 개인 로그인 제공자 선택·등록 준비

승인 계획의 후보인 **Auth0 OIDC**를 첫 개발 제공자로 제안한다. 기존 OIDC tenant가 있으면
사용자가 명시적으로 제공한 issuer/client ID/audience만 사용한다. 기존 CareerGround 서버 설정이나
Codex 인증을 검색·추출·재사용하지 않는다. 개인 로그인 제공자 선택은 아직 확정되지 않았다.

신규 Auth0를 선택하면 사용자가 자신의 브라우저에서 가입·관리자 로그인을 직접 해야 한다.
아래 값으로 **별도 개발 Native application + 별도 API audience**를 준비한다.
앱 구현을 먼저 준비하고, 실제 등록·설정 저장은 해당 값의 확인과 승인 후 진행한다.

| 설정 | 제안 |
| --- | --- |
| Application name / type | `CareerGround Interview Dev` / Native, public client |
| Android package | `dev.careerground.interview.dev` |
| Authorization flow | 외부 브라우저 Authorization Code + PKCE S256, state/nonce 검증 |
| Allowed Callback URL | `dev.careerground.interview.dev:/oauth2redirect` 정확히 한 값; wildcard 없음 |
| API name / Identifier | `CareerGround Interview Dev Runtime` / `https://careerground.example/mock-interview/dev` |
| API identifier 의미 | audience 구분용 논리 URI이며 접속할 URL·새 도메인·호스팅이 아님 |
| Token signature / API permission | RS256 / `use:interview` |
| Requested scope | `openid use:interview`; email/profile/offline_access는 기본 요청하지 않음 |
| 런타임 검사 | 고정 issuer/JWKS, 서명·audience·만료·scope·client binding 검사. 검증한 issuer+sub로 owner 결정 |
| 보관 | 앱/runtime RAM, refresh token·경력·계정 token 자동 저장 없음 |
| 로그아웃 | 앱 token/자료와 해당 owner의 runtime 세션 해제. 제공자 브라우저 SSO 세션은 별개로 안내 |

[Auth0 application 설정](https://auth0.com/docs/get-started/applications/application-settings)은 Native 유형과
callback 허용 목록을 지원한다. [AppAuth Android](https://github.com/openid/AppAuth-Android)의 외부 브라우저·
PKCE·앱 전용 callback 지원을 사용할 계획이다. 이는 구현 예정이며 현재 APK에 AppAuth나 실제 로그인 경로는 없다.
해당 library의 고정 버전·추가 다운로드 범위는 제공자 선택 후 확인하며 설치 승인을 재사용할 수 있는 범위인지 점검한다.
외부 연결 대기 중 `runtime/cg_mock/oidc.py`의 public JWKS 주입형 RS256 정책과 합성 서명 시험 8개를
준비했다. 현재 API/앱에 연결하지 않았고 discovery·키 갱신·실제 토큰 수신은 없다.
기존 설치된 PyJWT 2.15.0/cryptography 50.0.1을 사용했으며 새 외부 설치 없이 검사했다.
[API token 검증](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens)을 runtime에서 수행하고,
Android가 전달한 owner 문자열이나 ID token만으로 보호 API를 열지 않는다.

2026-10-11 확인한 [Auth0 가격](https://auth0.com/pricing)은 Free $0/월·가입 시 카드 불필요를 명시한다.
이 계획은 무료 기능만 사용하며 유료 전환·카드 입력·유료 add-on·custom domain을 포함하지 않는다.
실제 가입 화면이 다른 조건을 요구하면 진행을 멈추고 확인한다. 계정 식별·인증 기록은 Auth0에 남을 수 있으므로
앱의 “경력 자동 저장 없음”이 제공자의 인증 기록 보관까지 없애는 것은 아니다.
경력 handoff·답변 본문을 Auth0로 보내지 않는다.

공개 issuer/domain·client ID·audience는 설정에 필요하다. client secret·access/refresh token·비밀번호는
채팅이나 repo에 제출하지 않는다. 외부 등록과 개인 로그인 실행을 승인받기 전에는 합성 인증을 유지한다.

## 단계 판정

현재 **STEP 02 부분 통과**다. APK 빌드·JVM/로컬 runtime 검증은 PASS,
폴드7 실행·SAF 왕복·실제 개인 로그인은 NOT_RUN이다. 두 실행의 실제 증거를 확보한 뒤 STEP 02를 수용하고
STEP 03 → 04 순서로 진행한다. 에뮬레이터·한국어 모델 설치·API 과금·배포는 이 확인 범위에 포함하지 않는다.

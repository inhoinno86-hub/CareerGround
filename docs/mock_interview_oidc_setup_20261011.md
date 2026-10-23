# STEP 02 실제 OIDC — 추가 라이브러리 설치 승인·실행 기록

2026-10-11. **사용자 “추가 설치 진행 부탁해”로 승인 / AppAuth 추가 설치 PASS.**
Auth0 외부 등록은 별도 사용자 지시로 완료했다. 처음 요청의 “외부 설치는 실행 전에 확인” 조건을
현재 캐시에 없는 AppAuth 추가에 적용한다. 앞선 SDK/JDK/Compose 설치 승인과 같은 gate를 반복하지 않는다.
아래 범위의 cache 유무·예상량은 설치 전 조사 시점의 설명이며, 실제 설치 결과는 마지막 절에 기록했다.

## 승인한 실행 범위

- Android 라이브러리 **`net.openid:appauth:0.11.1`**를 고정해 추가한다.
  Maven Central의 2026-10-11 공개 metadata release 값은 0.11.1이다.
  [공식 SDK](https://github.com/openid/AppAuth-Android)는 외부 브라우저·Authorization Code/PKCE를 지원한다.
  WebView·자체 비밀번호 입력 화면은 도입하지 않는다.
- 해당 AAR의 공개 Content-Length는 **156,668 bytes**다. 이는 전체 다운로드량이 아니다.
  POM 직접 의존성은 `androidx.annotation:annotation:1.2.0`,
  `androidx.appcompat:appcompat:1.3.0`, `androidx.browser:browser:1.3.0`이다.
  Gradle은 기존 AndroidX와의 충돌 해결 뒤 선택한 전이 의존성도 받을 수 있다.
- AppAuth/AppCompat/browser는 현재 전용 cache에 없다. annotation은 1.8.1/1.9.1이 cache에 있다.
  기존 Compose/Kotlin/AGP/SDK 고정 버전을 임의 업데이트하지 않는다.
- 다운로드 출처는 기존 프로젝트 저장소인 **Maven Central / Google Maven**이다.
  AppAuth는 Apache 2.0이며 전이 라이브러리의 라이선스/notice도 유지한다.
- 전용 도구 root `/home/inno/.local/share/careerground-android/gradle-cache/`만 사용한다.
  시스템 패키지·전역 shell·새 SDK·에뮬레이터·마이크 모델 설치는 포함하지 않는다.
- 다운로드 총량은 전이 충돌 해결 전 미확정이다. 기존 cache를 활용해 수 MiB–수십 MiB로 예상하되
  실제 resolved 목록/다운로드와 산출물을 기록한다. 예상보다 큰 신규 도구/의존성이 필요하면 먼저 확인한다.
- 이 공개 라이브러리 다운로드에는 API 사용료가 없다. OpenAI API·유료 Auth0 전환·배포는 포함하지 않는다.

공개 metadata/POM 확인 주소:

- [Maven metadata](https://repo.maven.apache.org/maven2/net/openid/appauth/maven-metadata.xml)
- [AppAuth 0.11.1 POM](https://repo.maven.apache.org/maven2/net/openid/appauth/0.11.1/appauth-0.11.1.pom)

## 승인 후 구현·검증

1. [등록한 공개 설정](../apps/mock-interview/config/auth0-dev.public.json)으로 debug 전용 native login을 연결한다.
   callback은 `dev.careerground.interview.dev:/oauth2redirect`, scope는 `openid use:interview`다.
2. Authorization Code + PKCE S256, state/nonce/callback 검증과 실패·취소 처리를 구현한다.
   token·자료 자동 저장 없이 RAM으로 관리한다. refresh token·client secret을 앱에 넣지 않는다.
3. runtime에 고정 issuer/JWKS의 실제 access token 검증을 연결한다.
   서명·audience·만료·scope·native client 및 issuer+sub owner 경계를 검사한다.
   합성 개발 모드와 실제 OIDC 모드를 명확히 분리하고 합성 credential로 OIDC를 통과시키지 않는다.
4. APK 빌드·관련 인증 회귀·lint 후 현재 폴드7 debug 앱을 업데이트하고 실제 로그인/취소/로그아웃과
   합성 handoff의 owner 경계를 검증한다. 기존 APK·파일·실패 증거는 보존한다.
5. 앱의 실제 브라우저 로그인에서 비밀번호/본인 인증이 필요할 때만 사용자에게 화면 입력을 요청한다.
   현재 완료한 Auth0 **관리자** 로그인은 이 앱 로그인 시험을 대신하지 않는다.
6. token·serial·비밀번호를 기록하지 않고 실제/합성·PASS/NOT_RUN을 분리해 수용한다.
   기기 시험 종료 후 runtime/reverse를 정리한다. STEP 02 수용 뒤 STEP 03–04로 진행한다.

## 실행 결과

- AppAuth 0.11.1과 Gradle이 선택한 AndroidX 전이 의존성을 전용 cache에 설치했다.
- baseline 대비 신규 cache 파일 **33개 / 2,072,149 bytes**다. 이는 cache 파일 크기 합계이며
  HTTP 전송량·Gradle 변환 산출물·APK 크기 합계가 아니다.
- 직접 선택된 AppCompat 1.3.0/browser 1.3.0과 기존 annotation-jvm 1.9.1 등 resolved 목록을
  전용 artifact의 `dependency-receipt.json`에 남겼다. 기존 도구 버전은 유지했다.
- 실제 OIDC 앱/runtime 연결과 APK/JVM/lint/합성 인증 회귀는 구현·실행했다.
  휴대폰은 현재 ADB 미연결이므로 새 APK 설치·실제 앱 인증은 **NOT_RUN / 연결 대기**다.
- 관리자 로그인·공개 키 조회를 앱 사용자 로그인 성공으로 대체하지 않았다.
- 상세 결과와 현재 한계는 [OIDC 구현·검증 기록](mock_interview_oidc_implementation_20261011.md)을 따른다.

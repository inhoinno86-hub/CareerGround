# Android STEP 02 빌드·보완 검증 — 2026-10-11

**실제 APK 빌드·JVM·로컬 검증 PASS / STEP 02 부분 수용.**
폴드7 실행·SAF 파일 왕복·실제 개인 로그인은 **NOT_RUN**, STEP 03–04도 **NOT_RUN**이다.
앱 전체 완료나 실제 AI 면접 통과로 판정하지 않는다. 이 기록은 앞선
[부분 수용 기록](mock_interview_app_acceptance_20261011.md)을 보존한 후속 실행 증거다.
전체 [구조화 증거](mock_interview_android_build_20261011.json)에 hash·도구·실패 이력·변경 목록을 담았다.

## 승인 범위와 실제 설치

사용자의 “응 진행해줘. 이후 과정에서 꼭 승인이 필요하거나 수동 진행이 필요한 사항이 아니라면
알아서 진행”으로 [설치 확인안](mock_interview_android_setup_20261011.md)의 도구/라이브러리 설치,
SDK 라이선스 수락, debug 빌드·시험을 진행했다. 시스템 Java/SDK·전역 shell 환경을 바꾸지 않고
`/home/inno/.local/share/careerground-android/`에 설치했다.

| 도구 | 실제 설치 값 |
| --- | --- |
| Temurin JDK | 17.0.20.1+1, x64 HotSpot, 공식 archive SHA-256 일치 |
| SDK CLI | download build 15859902 / package revision 22.0, 공식 ZIP SHA-256 일치 |
| Android SDK Platform | android-36, revision 2 |
| Build Tools | 35.0.0 |
| Gradle / AGP / Kotlin | 8.13 / 8.13.2 / 2.2.21 |
| Compose BOM | 2025.12.00 |
| Platform Tools | 37.0.1 — 첫 빌드에서 AGP가 자동 설치, 아래 실행 범위 차이 참조 |

설치안은 SDK Platform/Build Tools만 명시했지만 첫 AGP 실행이 Platform Tools를 자동 설치했다.
초기 SDK 자동 다운로드를 차단하지 못한 실행 범위 차이다. 설치 내역·첫 로그를 보존했고 사용자에게 알렸다.
`android.builder.sdkDownload=false`로 이후 SDK 자동 설치를 차단했다. ADB 서버 실행·기기 연결은 하지 않았다.
휴대폰 설치/USB 연결은 [별도 실행안](mock_interview_step02_device_auth_20261011.md)의 승인 대상이다.

공식 Gradle wrapper JAR hash 일치와 배포 ZIP checksum 고정을 확인했고 실제 `./gradlew --version`도 통과했다.
실제 디스크 사용량은 증거 생성 시 약 **2.63 GiB**이며 예상치 4–6 GB와 구분한다.
전용 도구 root의 `install-receipt.json`과 `cache-artifacts-sha256.json`에 설치/다운로드 정보를 남겼다.
Gradle dependency 파일 778개의 SHA-256은 **내려받은 파일의 관찰값**이며 별도 upstream checksum과
대조한 것으로 표현하지 않는다. JDK/SDK CLI/Gradle archive와 wrapper JAR의 공식 checksum 대조는 별도로 수행했다.
유료 API·에뮬레이터·언어 모델·배포 실행은 없다.

## APK와 재현

앱 package는 `dev.careerground.interview.dev`, version `0.1.0-step02`(code 1), min SDK 33 / target·compile 36이다.
실제 서명 검사는 PASS이며 로컬 Android Debug 키다. 개인 계정 인증이나 배포 서명으로 해석하지 않는다.
키는 전용 도구 root에 있으며 repo/APK에 복제하지 않는다.

| 실제 산출물 | bytes | SHA-256 |
| --- | ---: | --- |
| app-debug.apk | 27,965,519 | `a73b250a1dafc9d4d2419f628478dca3737f0fcd27e9459cbe02ef0eefd22443` |
| app-debug-androidTest.apk | 2,378,455 | `8789fc02fbc9922c1e4948dbb0531d00749ed346b2c0c73b5c96b408608da5c7` |

두 파일과 lint/JVM 보고서는
`/home/inno/.local/share/careerground-android/artifacts/step02-20261011-r2/`에 보존했다.
APK 권한은 INTERNET과 AndroidX가 병합한 앱 전용 signature 권한이다. 마이크·광범위 저장소 권한은 없다.
자동 백업/기기 간 이전 제외 XML을 추가했지만 실제 OS 백업 시험을 수행한 것은 아니다.
기존 외부 수동 저장 파일은 이 규칙으로 삭제되지 않는다.

실행한 Gradle task:

```text
:app:assembleDebug :app:testDebugUnitTest :app:lintDebug :app:assembleDebugAndroidTest
```

같은 실행에서 `:app:dependencies --configuration debugRuntimeClasspath`를 기록했다.
명령별 환경 변수와 재현 방법은 [앱 안내](../apps/mock-interview/README.md)에 있다.

## 실패·분석·보완

1. **첫 빌드 FAIL:** 앱·시험 APK 생성과 JVM 2시험은 통과했으나 lint 2오류/9경고/1hint로 실패했다.
   두 오류는 debug network security XML의 `includeSubdomains` 누락이었다.
   loopback 두 domain에 `false`를 명시했고 lint를 억제하거나 baseline으로 숨기지 않았다.
   Android 12+ 백업/이전 제외, icon, compilerOptions, 정수 Compose state도 보완했다.
   **두 번째 빌드 PASS**, lint 0오류/6경고/0hint, JVM 2시험 실패·skip 0.
   첫 로그와 lint XML은 도구 root `logs/build-attempt-1.log`, `logs/lint-attempt-1.xml`에 보존했다.
2. **입력 오류가 HTTP 500:** 5,000자리 정수와 review 문자열의 잘못된 escaped Unicode를 실제 ASGI handler에서 재현했다.
   JSON decode 실패·잘못된 Unicode·비유한 수를 상태 변경 전 400으로 처리했다.
   새 회귀는 검토 상태가 그대로 유지되고 정상 한국어/emoji 입력은 통과하는 것도 확인한다.
3. **오프라인 토큰 시험 1건 실패:** PyJWT encoder가 빈 배열 `typ`를 생략해 시험 의도와 다른 유효 token이 생성됐다.
   유효하게 서명된 비어 있지 않은 배열 header로 시험을 수정해 형식 거부를 확인했다.
   최종 정책 시험 8개가 통과했다. 외부 로그인 실패를 보완한 사례가 아니다.

남은 lint 6경고는 고정 Gradle·Compose BOM·Activity·Lifecycle보다 새 버전이 있다는 안내다.
검증한 버전을 임의 최신으로 변경하지 않았다. 빌드 도구의 SDK XML v3/v4 호환 경고도 로그에 남아 있다.
첫 debug 빌드에서는 `libandroidx.graphics.path.so`를 strip하지 못해 원본으로 패키징했다는 안내가 있었다.
두 경고를 해결했다고 주장하지 않으며 이번 debug 빌드·서명 검사·JVM/lint task는 통과했다.

## 검증 판정과 한계

| 검사 | 실행 형태 | 결과 |
| --- | --- | --- |
| 앱·시험 APK | 실제 JDK/SDK/Gradle 컴파일 | PASS |
| Kotlin JVM | 실제 JVM 실행, bounded stream·원본 hash 2시험 | PASS |
| Android lint | 실제 분석, 6 버전 안내 경고 | PASS |
| Python 가져오기/API | 실제 코드, 합성 개발 인증, 16시험 | PASS |
| OIDC token 정책 | RAM 합성 RSA key/token, 8시험, 외부 접속 없음 | PASS(오프라인 정책만) |
| 기존 Portable 교환 | 기존 7회귀, 원래 계약 유지 | PASS |
| Python lint/format | Ruff | PASS |
| loopback HTTP·파일 | 실제 Uvicorn/HTTP·PC 임시 파일 쓰기/읽기·restore, 5관찰 | PASS |
| Android instrumentation | 3시험 컴파일 PASS / 실제 기기 실행 | NOT_RUN |
| 폴드7·SAF·폴더블/키보드 | 실제 Android 기기/UI/선택 URI 왕복 | NOT_RUN |
| 실제 개인 로그인 | 등록·discovery·실제 token·앱/API 통합 | NOT_RUN |
| 기기 내 한국어 STT·로컬 TTS | STEP 03 실제 음성 | NOT_RUN |
| Codex 면접·result·ChatGPT 재검토 | STEP 03–04 실제 왕복 | NOT_RUN |

HTTP의 [세 번째 실행 증거](mock_interview_step02_http_20261011_r3.json)는 runtime의 실제 파일 왕복이다.
그 명령은 Gradle을 실행하지 않으므로 파일 안의 `android_build: NOT_RUN`은 **그 smoke 명령의 범위**이며,
이번 Android 빌드 결과는 현재 문서/JSON을 따른다. PC 임시 파일 왕복을 Android SAF 통과로 승격하지 않는다.

OIDC 준비 코드는 public JWKS를 주입해 RS256·issuer/audience·만료·scope·native client를 검증하고
issuer+sub에서 opaque owner를 만든다. 현재 synthetic API/앱에 연결하지 않았다. 기존 설치된
PyJWT 2.15.0/cryptography 50.0.1을 사용했고 token·key를 저장하지 않는다.
실제 제공자 연결·discovery·JWKS 갱신·개인 로그인·만료/로그아웃 전체 수용은 남아 있다.

## 기존 작업 보존과 다음 조건

STEP 02 착수 전 508파일 중 기존 507파일의 SHA-256이 그대로이며 승인 계획만 의도적으로 갱신했다.
설치 직전 536파일 기준으로 524개 그대로, 앱/새 시험/계획/설치 안내 12파일을 보완했고 삭제는 0이다.
새 wrapper·앱 XML·OIDC 준비 코드·후속 증거만 추가했다. 원래 tracked 수정 3파일,
Portable 0.2.0·handoff/result 1.0·합성 참조·이전 실패/수용 기록은 보존했다.
branch/HEAD/main을 전환·병합하지 않았고 commit/push/공개 배포도 하지 않았다.

다음 조건은 [기기·로그인 실행안](mock_interview_step02_device_auth_20261011.md)의
폴드7 APK 설치·USB 연결 승인과 실제 제공자 결정/등록이다. USB 허용과 신규 제공자 가입/관리자 로그인은
사용자 직접 조작이 필요하다. 승인한 네이티브/음성/Codex/수동 보관 선택은 다시 묻지 않는다.
STEP 02의 실제 수용 후 STEP 03 → 04를 순서대로 진행한다.

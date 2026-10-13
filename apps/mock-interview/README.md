# CareerGround Android 모의 면접 — 실제 개발 왕복 수용

기준 기기: 갤럭시 Z 폴드7 SM-F966N / 사용자 제공 Android16·One UI8.5.
[승인 계획](../../PLAN-2026-10-10-mock-interview-app.md)을 따른다.
**STEP02 실기기 수용 / STEP03 실제 Codex·음성·오프라인 전사·result SAF PASS /
STEP04 실제 ChatGPT 정식 재검토·별도 사실/사용 확인·새profile/이전버전 보존 PASS.
폴더블 에뮬레이터 합성 화면·수정·중단·파일·복원 보충 검사를 완료했다.
[검사와 환경 제한](../../docs/mock_interview_emulator_validation_20261012.md)을 구분해 기록했다.**

0.2.1-step03-voice(code4)의 긴 발화 조기 종료 보완을 실제 기기에서 재검증했다.
전사 오인식은 남으므로 확인·수정 후 제출한다. 원전사와 수정된 답변을 구분한다.
ChatGPT Portable0.2.0 interview-review의 jsonschema부재는 승인한 임시 설치로 보완했고
정상/부정 검사와 실제 파일 다운로드를 통과했다. 별도 합성 사실/사용 선택 후 career-review로
새profilev4를 만들고 기존v3·resume·handoff·result pending을 보존했다. 새부분profile은 handoff가 아니다.

[최신 수용·사용·USB 재연결 안내](../../docs/mock_interview_app_acceptance_20261012.md),
[이전 재개 지점](../../docs/mock_interview_app_acceptance_20261011_r2.md),
[음성 보완·이전 실패](../../docs/mock_interview_voice_continuation_20261011.md)를 따른다.
현재 실제 휴대폰 RAM/token·USB reverse·loopback runtime은 정리했고 수동 파일은 보존했다.
실제Codex14/15, 유료API0. 사용자 승인 개인 handoff의 실제 가져오기/저장/재개와 첫 음성 확인 답변1개,
실제 평가/result·ChatGPT 정식 검사/재검토·파일 다운로드 왕복을 마쳤다.
미응답5문항·pending 후보2개 별도 검토와 전체 면접은 구분한다. 이번 USB reverse/runtime·앱 메모리는 정리했고 파일은 보존했다.
[개인 실제 왕복 기록](../../docs/mock_interview_personal_roundtrip_20261012.md)을 따른다.
운영API/배포는 미실행이다.

## 현재 제공 범위

- Android Kotlin/Compose 소스: Auth0 외부 브라우저 개인 로그인/별도 합성 연결 코드,
  handoff/첨부/세션 파일 선택, 로컬 미리보기,
  PC runtime 구조 검사, 고정 버전·자료·기여 경계 검토, 시작/일시 중지/중단, 수동 세션 저장.
  질문/근거·확인 답변/수정·AI 평가·pending 후보, 수동 result 내보내기 화면과
  한국어 기기 내 인식/로컬 TTS를 구현했다. 기기 시험과 실제 사용자 발화 수용은 별도로 기록한다.
- Python runtime: 기존 Portable 0.2.0의 검사기·canonical digest 재사용, 다른 사용자 접근 거부,
  검토 전 시작 차단, 원본 유지, 수동 세션 재검사. `InterviewSessions`와 선택적인
  `CodexInterviewProvider`는 고정 자료만 전달하고 최신 답변의 평가·후보만 result에 넣는다.
  실제 Codex 실행과 Mock-only 시험을 구분하며 기본 runtime은 AI 비활성이다.
- `oidc.py`의 RS256 검증을 OIDC API 모드에 연결했다. `provider.py`는 고정 issuer의 discovery/JWKS만
  조회하고 RAM 키 캐시(5분), unknown kid 갱신/실패 재시도 간격(30초)을 관리한다. 고정 issuer,
  audience, 만료, scope, native client, issuer+sub owner 경계를 검사한다. 합성 RSA 서명/API·키 회전
  시험과 실제 공개 키 조회, 실제 앱의 로그인/token 수신·runtime 검증을 통과했다.
- handoff/result 1.0과 기존 플러그인은 수정하지 않는다. `contracts/session-0.1.schema.json`은
  앱 내부의 서명 없는 0.1 초안으로 질문·답변 revision·평가·pending·호출 메타데이터를 담는다.
  STEP 02의 빈 기록 파일과 호환된다. 재가져오기는 범위 검토를 다시 요구하며 가져온 AI 평가는
  stale로 제외하고 실제 호출 provenance로 신뢰하지 않는다.

## 로컬 runtime 실행

새 설치 없이 프로젝트의 기존 venv를 사용한다. repo root에서:

```bash
PYTHONPATH=apps/mock-interview/runtime .venv/bin/python -m cg_mock --synthetic-dev
```

127.0.0.1:8765에만 바인딩한다. 터미널의 임시 연결 코드는 앱 메모리에 입력하며 파일·로그에 저장하지 않는다.
사용자 binding은 `synthetic-local-owner`이며 **실제 개인 계정 인증이 아니다**. 합성 fixture만 선택한다.
합성 시험용 연결 코드와 Codex 인증은 무관하다.
프로세스를 재시작하면 연결 코드와 모든 runtime 세션이 사라진다. API docs·CORS·공개 host는 제공하지 않는다.

실제 개발 OIDC 모드는 별도 실행한다. 두 모드를 동시에 허용하거나 합성 credential로 대체하지 않는다.

```bash
PYTHONPATH=apps/mock-interview/runtime .venv/bin/python -m cg_mock \
  --oidc-config apps/mock-interview/config/auth0-dev.public.json
```

승인된 ADB reverse로 127.0.0.1:8765를 연결한 뒤 앱의 `개인 계정 로그인`을 선택한다.
AppAuth 0.11.1이 Authorization Code + PKCE S256/state/nonce를 처리한다. callback scheme/path와
전체 pending request를 추가 검사하고 public client로 code를 교환한다. 앱은 access token을 RAM에만 둔다.
앱 비밀번호 화면, client secret, refresh token 저장/자동 갱신은 없다. 만료 후 다시 로그인한다.
Auth0 관리 콘솔 로그인과 앱 사용자 로그인은 별개다. 기존 합성 owner의 세션 파일은 OIDC owner와
다르므로 거부한다. 원래 handoff를 가져와 새 OIDC 세션을 만들고 별도 파일 이름으로 내보낸다.

승인한 실제 AI 개발 시험은 **같은 누적 호출 원장**을 명시해 실행한다. 현재14회 사용했다.
2026-10-12 사용자 승인을 받아 기존 한도를12→15로 변경했으며 사용11회는 보존했다.
이후 개인 질문의 첫 실패·보완 재시도·평가3회로14/15가 되었고 잔여1회다. 기본 runtime 한도는12이므로
같은 원장의15회 설정을 명시한다. 새 원장으로 한도를 초기화하지 않는다. 새 API key·유료 호출은 없다.

```bash
CG_CODEX_BUDGET=/home/inno/.local/share/careerground-android/artifacts/codex-step03-20261011/calls.json
PYTHONPATH=apps/mock-interview/runtime .venv/bin/python -m cg_mock \
  --oidc-config apps/mock-interview/config/auth0-dev.public.json \
  --codex-budget-ledger "$CG_CODEX_BUDGET" --codex-call-limit 15 --codex-model gpt-6.1-sol
```

기존 static Codex CLI와 bubblewrap를 사용한다. 빈 filesystem namespace에 CLI·기존 읽기 전용
로그인 파일·TLS/DNS 자료·출력 schema만 제공하며 HOME/CODEX_HOME 값은 바꾸지 않는다.
사용자 설정·프로젝트 지침·MCP/앱·셸·웹 도구를 차단하고 도구/알 수 없는 이벤트는 결과로 받지 않는다.
CLI 0.162.1의 정확한 Code Mode 호스트 비활성 시작 진단만 별도 집계한다.
요청/응답은 파이프/RAM이고 원장에는 호출 수만 남긴다. 인터뷰 자료를 자동 저장하지 않는다.

## Android 빌드·연결

2026-10-11 설치 승인을 받아 전용 도구 경로에 JDK 17·SDK 36·Gradle 8.13을 설치했다.
앱·시험 APK 컴파일, JVM 시험 2개, lint **PASS**(버전 업데이트 안내 6경고, 오류 0).
첫 lint 실패와 보완·재검증, APK/hash/권한은 [빌드 기록](../../docs/mock_interview_android_build_20261011.md)에 있다.
Gradle wrapper의 배포 ZIP checksum과 wrapper JAR checksum을 확인하고 실제 `--version`을 실행했다.
repo root에서 다음 명령으로 재현한다. 환경 변수는 해당 명령에만 적용한다.

```bash
cd apps/mock-interview/android
CG_ANDROID_TOOLS="$HOME/.local/share/careerground-android"
JAVA_HOME="$CG_ANDROID_TOOLS/jdk/jdk-17.0.20.1+1" \
ANDROID_SDK_ROOT="$CG_ANDROID_TOOLS/sdk" \
ANDROID_USER_HOME="$CG_ANDROID_TOOLS/android-user" \
GRADLE_USER_HOME="$CG_ANDROID_TOOLS/gradle-cache" \
./gradlew --no-daemon :app:assembleDebug :app:testDebugUnitTest :app:lintDebug :app:assembleDebugAndroidTest
```

SDK 추가 자동 설치는 `android.builder.sdkDownload=false`로 차단한다.
사용자 승인으로 폴드7 설치·실행, SAF 저장/재가져오기·취소, 강제 종료 후 수동 복원,
회전·분할 창·실제 펼침→접힘 전환을 실행했다. [실기기 검증 기록](../../docs/mock_interview_device_validation_20261011.md)을 따른다.
에뮬레이터의 후속 합성 화면·파일·복원 검사는 [보충 기록](../../docs/mock_interview_emulator_validation_20261012.md)에서 확인한다. 실제 개인 로그인과 당시 APK의 5개 instrumentation은
[OIDC 기기 기록](../../docs/mock_interview_oidc_device_20261011.md)에서 PASS로 확인했다.
기존 기기 기록은 앞선 합성 APK 시험 결과다.
후속 사용자 승인으로 [Auth0 개발 등록](../../docs/mock_interview_auth0_registration_20261011.md)은 완료했다.
[공개 설정](config/auth0-dev.public.json)은 issuer/client ID/audience/callback/scope만 포함하며
debug 앱에 연결했다. 사용자의 추가 설치 승인과 [OIDC 설치 기록](../../docs/mock_interview_oidc_setup_20261011.md),
[OIDC 구현·검증 기록](../../docs/mock_interview_oidc_implementation_20261011.md)을 따른다.
runtime 주소는 debug의 localhost에만 허용하며
release 앱은 미구성 상태로 연결을 거부한다. 실제 OIDC·운영 API를 설정한 뒤 release 경로를 추가한다.
폴더블 대응은 가용 너비 600dp를 기준으로 한 열/두 열로 전환한다. 실기기에서 발견한 넓은 창의
버튼 잘림을 오른쪽 세션 열 스크롤로 보완하고 재검증했다. 새 OIDC APK와 기존 설치 APK를 구분한다.

debug 앱의 실제 실행 component는 다음과 같다. application ID와 Activity namespace가 다르므로
`dev.careerground.interview.dev/.MainActivity`로 축약하지 않는다.

```text
adb -s <선택한_기기> shell am start -n dev.careerground.interview.dev/dev.careerground.interview.MainActivity
```

## 파일과 보관

`ACTION_OPEN_DOCUMENT` / `ACTION_CREATE_DOCUMENT`로 사용자가 선택한 URI만 읽고 쓴다.
광범위 저장소·마이크 권한은 STEP 02에서 요구하지 않는다. 입력 자료는 자동 저장하지 않고 ViewModel RAM에
유지한다. 회전·접기/펼치기에서 프로세스가 유지되면 상태가 유지되며 process death 시 미저장 상태를 잃는다.
SavedStateHandle·Compose rememberSaveable·백업·analytics에 경력/답변/token을 저장하지 않는다.
로그아웃은 앱 메모리를 비우고 runtime의 같은 owner 세션 삭제를 요청한다. OIDC logout 성공 시 사용한
access token의 SHA256을 만료까지 RAM에서 거부한다. 제공자 브라우저 로그인과 다른 token까지 취소하는
기능은 아니다. runtime 재시작 시 이 거부 목록도 사라진다. 연결 실패 시 runtime 잔존 세션은
30분 TTL 뒤 요청 시 또는 15초 주기 정리로 제거된다. Python/Java의 메모리 덮어쓰기 보장은 아니다.

JSON 2 MiB, 수동 세션 4 MiB, 첨부당 10 MiB, **선택 첨부 합계 20 MiB**, 전체 base64 요청 32 MiB.
합계 상한은 모바일/runtime 메모리 사용을 제한하기 위한 앱 상한이며 기존 Portable 계약 상한을 바꾸지 않는다.
첨부는 이름·hash 검사 후 임시 owner-only 디렉터리에서 기존 검사기로 확인하고 성공/실패 모두 즉시 정리한다.
원시 파일 SHA256과 계약 canonical digest는 별도 표시한다. 최신 자료로 자동 대체하지 않는다.

수동 세션 파일에는 원래 handoff와 검토 기록이 들어가며 원음·첨부 본문·token은 들어가지 않는다.
파일은 암호화·서명되지 않았고 사용자 binding 문자열은 파일의 소유권 인증 증명이 아니다.
재가져오기 시 첨부 재선택과 구조/hash/owner 검사 후 새 검토를 요구한다. 기존 세션 ID를 되살리지 않는다.
완료/중단 파일은 읽기용이다. 클라우드 문서 provider를 고르면 그 제공자에 저장될 수 있다.
파일 picker 취소는 기존 선택을 유지하고, 저장 성공은 실제 stream 쓰기/close 완료로만 표시한다.

runtime 세션은 생성 후 30분 TTL이며 긴 수동 대기·업데이트 전 수동 내보내기를 권장한다.
서버 세션 만료로 export가 SESSION_UNAVAILABLE일 때는 현재 앱 RAM 화면 기록으로 복구 파일을 준비한다.
`현재 화면 기록으로 복구 파일 준비`는 네트워크 없이도 명시적으로 실행할 수 있다. 원래 handoff
bytes·이미 확인된 답변/수정 기록·화면에 있던 AI 기록만 담고 미제출 텍스트/전사 초안과 모의 면접의
숨긴 평가는 제외한다. 이 파일은 새 AI 결과나 승인 증명이 아니며 재가져오기는 owner/hash/참조 검사와
범위 재검토를 거친다. 가져온 AI 평가는 stale로 제외한다. 실제 파일 쓰기는 별도 저장 위치 선택 후다.
앱 종료로 RAM을 잃기 전 선택해야 하며 자동 저장·자동 복구·클라우드 보관을 추가한 것이 아니다.

음성은 `기기 내 음성 시작` 후 **인식 마치기**까지 여러 문장을 누적한다. 지원 시 Android segmented
session을 요청하고, 서비스가 단일 문장 결과로 종료하면 같은 기기 내 recognizer를 terminal callback 뒤
다시 시작한다. 재연결의 짧은 공백은 초안에서 확인한다. 최대 120초/32구간, 연속 무음 오류 3회와
중지 결과 대기 5초 상한이 있다. 중지·취소·화면 이탈 뒤 재시작/늦은 전사를 적용하지 않는다.
전사는 여전히 미확인 초안이며 숫자/기여를 편집하고 확인한 뒤 제출해야 평가할 수 있다.

ADB로 복사한 시험 JSON이 파일 선택기의 Downloads 루트에서 보이지 않으면 `루트 표시 → Galaxy Z Fold7
→ Download → CareerGround-step02-…`의 실제 저장소 경로에서 선택한다. 이번 실기기에서 이 경로로
정상 왕복했다. 개인 파일을 탐색하거나 광범위 저장소 권한을 추가할 필요는 없다.

## 검증 구분

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_mock_interview_*.py' -v
.venv/bin/ruff check apps/mock-interview/runtime tests/test_mock_interview_import.py tests/test_mock_interview_oidc.py
```

로컬 HTTP 흐름은 FastAPI TestClient의 실제 ASGI handler를 실행하지만 모바일 장치·SAF의 실행 증거는 아니다.
합성 세션을 임시 파일에 실제 쓰고 재가져오는 검사와 Android 기기 파일 왕복을 분리한다.
Kotlin JVM 시험 2개는 앞선 빌드에서 실행 PASS, 스크롤 수정 빌드에서는 UP-TO-DATE였다.
Android instrumentation은 원 APK와 수정 APK 각각 실제 폴드7에서 **3/3 PASS**다.
Python 30시험은 가져오기/API 16개 + 오프라인 OIDC 정책 8개 + OIDC handler/키 캐시 6개다.
새 OIDC APK의 instrumentation 5개는 실제 Fold7에서 PASS다. 세션 파일 auth_mode 오류도
실기기 저장 검사에서 발견해 보완하고 같은 계정으로 r2 파일 저장/복원을 재검증했다.
OIDC 정책 통과를 실제 로그인 통과로 표현하지 않는다.
STEP 02 전체 수용 뒤 STEP 03으로 진행하며 미실행 단계를 PASS로 표시하지 않는다.

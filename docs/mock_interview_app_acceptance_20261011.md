# 모의 면접 앱 수용 기록 — 2026-10-11 / STEP 02 부분 구현

사용자는 Android 네이티브 수정 계획을 승인했다. [승인 계획](../PLAN-2026-10-10-mock-interview-app.md)의
STEP 02를 구현했으며 **Android 빌드·실기기·실제 계정 수용 전이므로 단계 전체는 미완료**다.
STEP 03–04는 순서 조건을 지켜 아직 착수하지 않았다. 외부 설치 확인이 다음 선행 조건이다.

## 구현과 기준

기준 branch `codex/mvp-foundation-ci-20260923`, HEAD `9bd1009237f6486285ec8192086d286e0a5e94f2`,
로컬 main `4bc0bf7b9cc3027187d62dee1f6283094d50b12b`를 유지했다. checkout/fetch/merge/commit 미실행.
기존 파일 508개 중 승인 기록·진척을 갱신한 계획 1개를 제외한 **507개는 byte hash 동일**이며 삭제가 없다.
기존 Portable 0.2.0·handoff/result 1.0, fixture, 플러그인·서버·기여/사용 경계는 수정하지 않았다.

[앱 소스와 안내](../apps/mock-interview/README.md): Kotlin/Compose 네이티브 화면, SAF 선택/저장,
UTF-8·중복 키·크기 제한, 고정 원본/참조/digest, 포함 범위 확인, 세션 상태, 수동 내보내기/재개.
Python runtime은 기존 portable/exchange 검사기를 직접 재사용한다. 합성 개발용 임시 연결 인증만 있으며
실제 개인 계정 로그인으로 표시하지 않는다. 선택 첨부만 짧은 임시 디렉터리에서 검사한 뒤 정리한다.

개발 기기 기준은 사용자 제공 SM-F966N / Android 16 / One UI 8.5(갤럭시 Z 폴드7)다.
네이티브 앱의 compile/target SDK 36, minSdk 33, SDK/라이브러리 고정 버전은
[설치 확인안](mock_interview_android_setup_20261011.md)에 기록했다. APK는 아직 없다.

## 실행 증거

| 관찰 | 결과 | 실제/모의 및 범위 |
| --- | --- | --- |
| 신규 runtime/API unittest | **15 PASS** | 실제 Python/ASGI handler, 합성 입력·개발 인증; 외부 AI 없음 |
| 기존 exchange 회귀 | **7 PASS** | 기존 Portable 교환 계약의 국소 회귀; 원본 수정 없음 |
| Python Ruff | **PASS** | 신규 runtime·시험 소스만 검사 |
| Android XML·session JSON 문법 | **PASS** | XML/JSON 파싱만 수행; Kotlin 컴파일이나 앱 실행 증거가 아님 |
| 실제 loopback HTTP | **PASS, 관찰 5개** | 실제 Uvicorn socket → httpx, import/review/start/pause/export/restore/logout |
| 수동 세션 실제 임시 파일 쓰기·읽기 | **PASS** | PC 파일 byte/hash를 검사하고 재가져옴; Android SAF 시험과 구분 |
| Android APK 빌드/JVM/기기 시험 | **NOT_RUN** | JDK/SDK/Gradle 설치 미승인·미준비; Kotlin 시험 소스만 작성 |
| 폴드7 화면·권한·SAF 왕복 | **NOT_RUN** | 휴대폰/에뮬레이터 연결·설치 없음 |
| 개인 계정 로그인 | **NOT_RUN** | OIDC 제공자/등록·callback 미설정; 합성 owner 거부 시험만 실행 |
| 실제 한국어 STT/TTS·Codex 면접 | **NOT_RUN** | STEP 03, 도구/음성 설치·AI 실행 없음 |
| result 파일·ChatGPT 재검토 | **NOT_RUN** | STEP 03–04 미착수; session 파일을 result로 표현하지 않음 |
| API 유료 실행/배포 | **NOT_RUN** | 실행 없음, 별도 확인 범위 |

HTTP 증거는 [1차](mock_interview_step02_http_20261011.json),
[최종 재검사](mock_interview_step02_http_20261011_r2.json)에 별도로 보존했다.
1차 이후 인증 입력 타입 검사를 보완했으므로 실제 HTTP를 재검사했다. 실제 session 임시 파일은 시험 후
삭제했고 기록에는 합성 파일 hash만 남겼다. 인증 코드·token은 기록하지 않았다.
[구조화 수용 기록](mock_interview_app_acceptance_20261011.json)에 입력 hash·환경·소스 hash와 판정을 담았다.

## 부정 사례·실패와 보완

실행한 시험은 검토 전 start, kind/schema, UTF-8/중복 JSON 키, 결손·중복·고정 버전 충돌,
미확인·미허용·금지 사실과 문장, 선택 밖 자료/이력, 첨부 결손·변조·추가·경로·개별/합계 크기,
session hash/owner/schema 위조, 다른 사용자 접근·삭제, 만료/용량/로그아웃/프로세스 재시작,
입력 명령·URL의 비실행, 잘못된 mode/action·인증 header·origin/host 경계를 포함한다.

초기 Python lint는 import 순서·UTC alias로 실패했고 신규 파일만 보완한 뒤 통과했다.
검토 중 mode에 배열을 보내면 TypeError가 날 수 있고 ASCII 외 인증 header 비교가 실패할 수 있음을 발견했다.
타입 거부·UTF-8 byte 비교로 보완하고 해당 회귀를 실행해 통과했다.

네이티브 수동 session의 embedded handoff base64가 일반 텍스트 20,000자 제한에 걸릴 수 있는 문제도
소스 검토에서 발견했다. 해당 envelope 필드만 별도 상한을 적용하고 복구 hash 검사 후 기존 선택을
바꾸도록 보완했다. Android 회귀 시험은 작성했지만 **실행 NOT_RUN**이며 해결 검증 완료로 승격하지 않는다.

설치 준비 중 Adoptium API metadata 일반 HTTP 조회가 403으로 실패했다. 공식 웹 release로 버전은
확인했으며 archive 다운로드 성공은 미검증이다. 실제 설치 시 checksum/공식 출처를 확인하지 못하면
중단·보고하며 임의 mirror로 우회하지 않는다.

## 남은 수용과 다음 확인

1. [설치 확인안](mock_interview_android_setup_20261011.md)의 PC 도구·라이브러리 설치 및 SDK 라이선스 수락 확인.
2. 승인 후 APK 빌드/JVM/lint 실패를 보완하고 검토 가능한 APK·manifest·hash 제시.
3. 에뮬레이터/폴드7 설치·연결과 OIDC 등록은 구체적 설정을 준비해 별도 확인 후 수행.
4. Android 가져오기·범위 검토·고정 세션·수동 재개·로그인 수용 뒤 STEP 03 → 04 진행.

현재 앱 소스는 합성 개발 전용이다. 모델/음성/파일 왕복의 실제 전체 수용이 완료될 때까지
CareerGround 08 완료 또는 공개 배포 준비 완료로 보고하지 않는다.

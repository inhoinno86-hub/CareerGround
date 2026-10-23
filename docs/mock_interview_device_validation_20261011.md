# STEP 02 폴드7 실기기 검증 — 2026-10-11

**합성 자료를 사용한 실제 폴드7·파일 왕복 시험 PASS. STEP 02 전체는 부분 수용이다.**
실제 개인 계정 로그인은 아직 미구현/NOT_RUN이며 STEP 03–04도 NOT_RUN이다.
앱의 시작/일시 중지 버튼은 세션 상태 전이이며 실제 AI 질문·음성 면접을 실행했다는 뜻이 아니다.
이번 저장물은 session 0.1 파일이며 면접 결과 result 1.0 파일이 아니다.

## 승인·관찰 범위

사용자가 USB 디버깅과 PC 연결을 준비하고 “15번까지의 휴대폰 시험을 직접 수행”하도록 요청했다.
초기 ADB 시간 초과 후 사용자가 재연결·PC 허용을 완료했다. 이후 선택한 한 기기에만 명령을 보냈다.
사용자가 직접 펼침/접힘을 수행했고 각 상태를 ADB/UI로 확인했다. 외부 인증 등록·유료 호출·배포는 수행하지 않았다.

- 실기기 관찰: SM-F966N, Android 16. One UI 8.5는 사용자 제공 정보다.
- 커버 1080×2520, 커버 가로 2520×1080, 실제 펼침 1968×2184,
  분할 시험의 활성 앱 창 1080×1252를 관찰했다. 크기/density/fold 상태 override는 사용하지 않았다.
- PC loopback runtime + ADB reverse 8765. 임시 코드는 RAM에만 사용한 `synthetic_dev` 인증이다.
- 입력은 `fixtures/portable/handoff-v1.json`만 사용했다. 원래 고정 참조는
  profile-synthetic v3 / jd-synthetic v1 / resume-jd-synthetic v1이다.
  기존 호스트 profile v4/v6와 pending resume를 승격하거나 섞지 않았다.
- serial·연결 코드·계정 token·비밀번호·개인 파일 본문은 결과에 기록하지 않았다.
  FLAG_SECURE를 유지했고 화면 캡처로 우회하지 않았다.

## 실제 실행 결과

| 항목 | 판정과 관찰 |
| --- | --- |
| 기기 설치·앱 실행 | PASS. 최초 같은 package 없음 확인 후 앱/시험 APK 설치. 수정본은 기존 debug 서명·설치 APK hash 확인 후 업데이트 |
| instrumentation | 원 APK 3/3 PASS, 스크롤 수정 APK 3/3 PASS. 합계 6개의 서로 다른 시험이라는 의미는 아님 |
| 시스템 파일 가져오기 | PASS. OpenDocument로 합성 handoff 선택·로컬 미리보기·runtime 구조 검사 |
| 검토 gate | PASS. REVIEW_REQUIRED에서 체크 전 고정 버튼 비활성·시작 없음. 확인 후 READY |
| 세션 상태 | PASS. READY → IN_PROGRESS → PAUSED → IN_PROGRESS → PAUSED |
| 파일 선택/저장 취소 | PASS. 기존 선택·READY 또는 PAUSED 유지, 취소 안내 확인 |
| 실제 파일 저장 | PASS. CreateDocument로 session JSON 쓰기·close 완료, 별도 이름의 수정 APK 파일도 저장 |
| 재가져오기·재검토 | PASS. 실제 저장 파일 OpenDocument → 구조/owner 검사 → REVIEW_REQUIRED, 확인 체크 초기화 → 새 세션 고정 |
| 강제 종료·수동 복원 | PASS. force-stop 후 연결·미저장 세션 소멸. 재연결·저장 파일 선택·재검토로 복원. 자동 복원 아님 |
| 파일/hash/원본 | PASS. 휴대폰에 실제 저장한 파일만 PC로 가져와 session 검사. 내장 원본 bytes·raw SHA·canonical digest·고정 버전 일치 |
| 가로 회전 | 최초 FAIL: 넓은 창의 버튼 접근 불가. 수정 후 PASS: 오른쪽 열 스크롤로 시작·일시 중지·내보내기 준비 접근 |
| 분할 창 | PASS. 실제 활성 앱 창 1080×1252에서 PAUSED 유지·계속/일시 중지 동작. 전체 화면 복귀 확인 |
| 실제 펼침→접힘 | PASS. 펼친 1968×2184에서 저장 세션 재가져오기·검토·시작·일시 중지. 사용자 접힘 후 1080×2520에서 같은 RAM의 PAUSED·digest·고정 참조 유지, 계속/일시 중지 동작 |
| 로그아웃·정리 | PASS. 연결 필드/세션 UI 비움, 시험 앱 force-stop, 해당 8765 reverse 제거, runtime listener 종료, 원래 회전 정책 lock 0 복원 |

실제 펼침 관찰을 위해 앞선 시험 연결 정리 후 새 임시 연결을 열었다. 저장한 파일을 다시 가져와
펼친 화면에서 새 세션을 만들었으므로, 최초 커버 세션에서 펼침까지의 연속 상태 보존을 관찰한 것은 아니다.
**연속 상태 보존의 실제 증거는 펼친 세션 → 물리적으로 접은 커버 화면**이다.
분할 창 시험은 동일 앱의 두 task로 수행했다. 다른 앱과의 조합·모든 창 크기를 검증한 것은 아니다.

## 실패 분석·보완과 재검토

넓은 레이아웃에서 `SessionControls`가 스크롤 없는 Column 안에 있어 높이가 부족하면 아래 버튼이
화면 밖으로 잘렸다. `MainActivity.kt`의 오른쪽 열에 `verticalScroll(rememberScrollState())`를 추가했다.
600dp 분기·기존 문서 패널·메모리 보관·검토 gate는 유지했다. 수정본 빌드와 lint, 실제 기기
instrumentation, 가로·펼침·접힘·분할 창, 새 파일 저장/재가져오기를 검증했다.

다음 실행 실패도 별도 보존했다. 앱 기능 실패와 시험 도구 오류를 섞지 않는다.

- 초기 ADB 통신 시간 초과: 사용자 USB 재연결/PC 허용 후 복구.
- 첫 instrumentation 명령의 package 오타: 실행 전 실패. 정확한 runner로 재실행해 3 PASS.
- 분할 명령의 미지원 `--activity-new-task`: 명령 실패 후 지원되는 flag와 own-app task로 수행.
- UIAutomator가 활성 창만 노출하는데 제목 두 개를 기대한 분할 probe: 잘못된 관찰 조건이었다.
  실제 창 크기·보존 상태·버튼 동작으로 조건을 정정해 PASS. 이전 실패 기록은 유지했다.
- ADB로 넣은 JSON이 Downloads 루트에서 보이지 않음: 외부 저장소 루트의
  `Galaxy Z Fold7 → Download → CareerGround-step02-…`에서 실제 파일 선택. 광범위 저장소 권한 추가 없음.

## 빌드·파일 증거

로컬 증거 root: `/home/inno/.local/share/careerground-android/artifacts/device-step02-20261011/`.
이전 `step02-20261011-r2/` APK와 수용 기록은 보존했다. 구조화 요약은
[device validation JSON](mock_interview_device_validation_20261011.json)이다.

| 파일 | SHA-256 |
| --- | --- |
| 원 APK (`step02-20261011-r2/app-debug.apk`) | `a73b250a1dafc9d4d2419f628478dca3737f0fcd27e9459cbe02ef0eefd22443` |
| 최신 APK (`device-step02-20261011/scroll-fix/app-debug.apk`) | `9c0e8ac0e399bd27a289308712ca40aacb381d7a0476f93d54b5f3f3226ecfe2` |
| 시험 APK (`scroll-fix/app-debug-androidTest.apk`) | `8789fc02fbc9922c1e4948dbb0531d00749ed346b2c0c73b5c96b408608da5c7` |
| 첫 실제 세션 파일 (9444 bytes) | `f2557d2172c59775ecd6e6c40e42bae466237cacc92f748b57733ec636714b8d` |
| 수정 APK의 실제 세션 파일 (9444 bytes) | `68f5f883ffac39f5a44c2136273b39afc8b3336d19e1ffa484572bc696fd2e45` |
| 고정 handoff 원본 | `11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8` |

계약 canonical digest는 `a1ca01fb34e8c6c8a5cf5a3bb2e54b32227d05d9076aa77d1de642b70fd1edd1`이다.
원시 파일 SHA와 다른 값을 유지한다. 질문·답변·AI 피드백·새 후보 배열은 비어 있다.

스크롤 수정 빌드는 기존 캐시만 사용하는 `./gradlew --offline --no-daemon :app:assembleDebug
:app:testDebugUnitTest :app:lintDebug :app:assembleDebugAndroidTest`로 성공했다.
JVM 2시험은 앞선 빌드의 통과 결과를 재사용한 UP-TO-DATE이며 이번 수정 후 새 실행이라고 세지 않는다.
lint 오류 0·기존 고정 버전 업데이트 경고 6. 실제 기기 instrumentation은 수정 APK에서 새로 3/3 통과했다.
package는 `dev.careerground.interview.dev`, Activity component는
`dev.careerground.interview.dev/dev.careerground.interview.MainActivity`이다.

세부 증거: `events.jsonl`, `ui-actions.jsonl`, `file-verification.json`, `final-file-verification.json`,
`final-reimport-ui-verification.json`, `rotation-attempt-1.json`, `rotation-after-scroll-fix.json`,
`split-screen-attempt-1/2/3.json`, `build-scroll-fix.log`, `scroll-fix/instrumentation.txt`,
`fold/unfolded.json`, `fold/folded-before-continue.json`, `fold/fold-transition.json`, `fold/cleanup.json`.
UI 관찰은 앱 합성 내용·알려진 시험 파일/탐색 label만 필터링했다. 개인 파일은 열거나 읽지 않았다.

## 남은 실행과 사용자가 직접 할 일

시험용 runtime과 reverse는 정리됐다. 설치 앱·시험 APK·사용자가 저장한 파일은 자동 삭제하지 않았고,
공유 ADB 서버는 종료하지 않았다. **휴대폰 설정 → 개발자 옵션 → USB 디버깅 끄기**는 사용자가 직접 수행한다.

실제 개인 로그인/Auth0 등록, 다른 실제 계정 차단, 한국어 기기 내 STT/TTS, Codex 면접,
result 생성, ChatGPT host 재검토, 에뮬레이터, OpenAI API·release 배포는 **NOT_RUN**이다.
오프라인 OIDC 합성 시험을 실제 로그인 통과로 승격하지 않는다.

다음은 제안한 Auth0를 사용할 경우의 **수동 등록 안내**다. 등록은 아직 자동 실행하지 않았다.
2026-10-11 [공식 가격](https://auth0.com/pricing)의 Free는 $0/월이며 카드 없이 가입 가능으로 안내한다.
무료 개발 구성을 사용하고 유료 전환이나 운영 tenant 수정은 포함하지 않는다.

1. 사용자 브라우저에서 [Auth0 관리 화면](https://manage.auth0.com)에 가입/로그인한다.
   기존 운영 설정과 분리한 개발 tenant를 선택하거나 만든다.
2. `Applications → Applications → Create Application`에서 이름 `CareerGround Interview Dev`,
   유형 **Native**를 선택한다. [Native 등록 공식 안내](https://auth0.com/docs/get-started/auth0-overview/create-applications/native-apps).
3. 해당 Application의 Settings에서 Domain과 Client ID를 확인한다.
   Allowed Callback URLs에 **`dev.careerground.interview.dev:/oauth2redirect`**를 정확히 넣고 저장한다.
   콜론 뒤 슬래시는 하나다. 이 custom URI + AppAuth 계획에 Auth0 quickstart의 다른 callback을 섞지 않는다.
4. Application의 Connections에서 기본 email/password 개발 연결을 확인한다.
   별도 Google 로그인 client·custom domain·유료 add-on은 이번 구성에 필요하지 않다.
5. `Applications → APIs → Create API`에서 이름 `CareerGround Interview Dev Runtime`,
   Identifier **`https://careerground.example/mock-interview/dev`**, Signing Algorithm **RS256**을 선택한다.
   Identifier는 논리 audience이며 사이트 생성·도메인 구입 대상이 아니다.
   [API 설정 공식 안내](https://auth0.com/docs/get-started/apis/api-settings).
6. 만든 API의 Permissions에서 permission **`use:interview`**, 설명 `개인 모의 면접 세션 사용`을 추가한다.
   `openid`는 앱이 요청할 기본 scope이므로 custom permission으로 추가하지 않는다.
   [권한 추가 공식 안내](https://auth0.com/docs/get-started/apis/add-api-permissions).
7. 공개 설정 세 값만 전달한다: **Domain / Native Client ID / API Identifier(Audience)**.
   client secret·token·비밀번호·인증 코드는 전달하지 않는다.

```text
Domain: <개발 tenant domain>
Native Client ID: <공개 client ID>
Audience: https://careerground.example/mock-interview/dev
```

현재 APK는 합성 연결만 지원하므로 등록만으로 로그인 시험이 통과하는 것은 아니다.
공개 설정과 외부 연결 범위가 확정되면 native PKCE·runtime 실제 token 검증 경로를 구현하고,
필요한 고정 AppAuth 버전/추가 설치 범위를 준비해 기존 승인 적용 여부를 확인한다.
실제 로그인·owner 경계를 수용한 뒤 STEP 03의 Codex/음성/result, STEP 04의 ChatGPT 왕복을 순서대로 수행한다.

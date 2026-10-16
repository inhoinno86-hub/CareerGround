# PACE 실제 Android 앱 통합 — 2026-10-13

기능 완료 커밋 `25bf5b012fdcce34e916ce544f27031338369c26`에서 만든 별도 worktree에
Round03 / 03 PACE를 연결했다. 브랜치는 `inhoinno86-hub/careerground-pace-integration`이다.
실제 앱 `dev.careerground.interview.dev`, 버전 `0.3.0-pace` / code5를 빌드한다.
기존 합성 미리보기 앱 `dev.careerground.interview.design`과 구분한다.

## 구현

- `:pace-ui`: 로그인·홈·자료 가져오기·내용 검토·면접·결과 Compose 화면과 시스템 밝기 대응.
- `PaceAdapter.kt`: 실제 InterviewModel과 로그인, 파일/첨부/복원, 마이크 권한, 저장 launcher 연결.
- `MainActivity`: PACE 진입을 사용하며 과거 UI를 제거했다. `FLAG_SECURE`와 onStop 음성 정지는 유지했다.
- 고정 ID/버전과 선택한 사실/근거, 최신 답변·평가만 표시한다. 모의 면접 평가·후보는 종료 전 숨긴다.
- 긴 입력은 페이지로 검토하며 초안 입력 때 자료 전체를 다시 변환하지 않는다.
- '한 답변에 집중'과 '전체 흐름 연습'은 기존 고정 질문 세션을 공유한다. 질문 수 계약을 새로 만들지 않았다.
- 자동 저장·개인정보 디스크 캐시·실제 AI 자동 호출을 추가하지 않았다.
- 로그인에서도 자동 저장 없음 안내를 표시하고, 답변 revision은 수정 횟수 대신 v번호로 표시한다.
- 시스템 밝기에 맞춰 상태·탐색 표시줄 아이콘 명암을 함께 조정한다.
- 면접 화면에서 홈 등으로 이동하면 기존 stopVoice를 호출해 음성·읽기를 멈추고 제출 확인을 해제한다.
  미제출 초안과 면접 세션은 유지한다.
- 기존 interruptSession/disconnect 경로를 보존해 busy 중에도 일시 중지·중단·연결 해제를 사용할 수 있다.
- 파일 재저장에서 기존 suffix가 남는 현상을 실제 file URI 검사로 발견해 저장 모드를 `w`→`wt`로
  보완했다. 새 파일 내용이 기존 내용보다 짧아도 선택 파일을 정확히 덮어쓴다.
  [Android ContentResolver 문서](https://developer.android.com/reference/android/content/ContentResolver#openOutputStream(android.net.Uri,%20java.lang.String))도
  `w`의 truncate 여부가 provider에 따라 다름을 설명한다. provider별 실제 SAF 확인은 별도다.

## 검증

최종 **PASS**: Android21회(고유15개+추가 조건별2개씩), JVM10개, 서버41개·96 subtests.
휴대폰 밝게 / 넓은 화면 어둡게 / 글꼴1.5 / 실제 OS 키보드 표시의4조건을 검사했다.
키보드 IME visible과 확인·제출 조작, busy 중 일시 중지·중단 버튼 사용 가능 및 연결 해제,
진행 중 복원 재검토, 종료 상태 보존, 짧은 파일 재저장 일치가 통과했다.
실제 native 캡처32개를 로컬 artifacts에 보존했다. 키보드 캡처의 선택 팝업 위치에 검은 영역이
있어 FLAG_SECURE를 사용하는 팝업의 캡처 가림으로 추정한다. 실제 기기 렌더링 문제로 단정하지 않는다.

최종 결과는 [동반 JSON](mock_interview_pace_integration_20261013.json)에 기록한다. 기존 디자인 미리보기 검사14개/레이아웃25조건의 기록을
이번 실제 앱 통합 검증으로 대체하거나 재실행했다고 표시하지 않는다.

이번 빌드: 앱/시험 APK, JVM 시험10개, 앱·UI library lint 수행.
앱 lint는 오류0·기존 UseKtx 경고2, UI library는 오류·경고0이다.
서버 관련 pytest는41개·96 subtests 통과했다.

`PaceAdapterTest`는 실제 앱의 연결부에서 고정 버전/선택 범위, 최신 기록과 모의 면접 숨김을 검사한다.
`PaceRuntimeUiTest`는 전용 합성 runtime의 실제 HTTP와 앱 조작을 연결하며
답변 확인·수정·구성 재생성·일시 중지·평가·결과·파일 쓰기/복원을 검사한다.
합성 인증 정보는 RAM/시험 호출에만 사용하고 기록에서 제거한다.
시험 캡처는 합성 상태에서만 일시적으로 FLAG_SECURE를 해제하고 즉시 복원한다.
실제 앱의 FLAG_SECURE 설정은 그대로다.

## 재현

기존 도구 환경을 사용해 Android root에서:

```bash
JAVA_HOME=/home/inno/.local/share/careerground-android/jdk/jdk-17.0.20.1+1 \
ANDROID_SDK_ROOT=/home/inno/.local/share/careerground-android/sdk \
ANDROID_USER_HOME=/home/inno/.local/share/careerground-android/android-user \
GRADLE_USER_HOME=/home/inno/.local/share/careerground-android/gradle-pace-cache \
./gradlew --offline --no-daemon --max-workers=2 \
  -Dorg.gradle.jvmargs='-Xmx1536m -Dfile.encoding=UTF-8' \
  -Pkotlin.compiler.execution.strategy=in-process \
  :app:assembleDebug :app:testDebugUnitTest :app:lintDebug \
  :app:assembleDebugAndroidTest :pace-ui:lintDebug
```

저장소 root에서 기존 project venv를 사용한다. 다른 checkout의 venv를 써도 의존성을 새로 설치하지 않는다.

```bash
/home/inno/repo/CareerGround/.venv/bin/python \
  apps/mock-interview/validation/pace_android.py \
  --output /home/inno/.local/share/careerground-android/artifacts/pace-integration-20261013 \
  --configurations phone-light wide-dark large-font keyboard
```

이 driver는 `careerground-pace-api36` / `emulator-5580`만 사용한다.
실제 기기에는 설치·조작하지 않는다. 자기 AVD·loopback server·reverse만 정리한다.
다른 환경에서는 이 도구 경로와 AVD 준비가 필요하며 자동 설치하지 않는다.

## 사용과 남은 확인

[통합 APK](/home/inno/.local/share/careerground-android/artifacts/pace-integration-20261013/CareerGround-PACE-integrated.apk):
29,979,759 bytes / SHA256 `285c85dafe910e9d8b0beaca0884a3ea6d06f54d9494c32927870f40d88a8710`.
기존 기능 APK와 같은 debug 서명을 확인했다.

통합 APK는 기존 기능 앱을 업데이트하는 개발 APK이며 개인 앱 로그인과 실제 면접에는
기존 PC runtime/USB 연결이 필요하다. APK만 설치한다고 독립 모바일 서비스로 동작하지 않는다.
현재 단말의 미저장 초안은 업데이트/종료 전 수동 파일로 보존한다.
기존 수동 파일은 이전과 같은 계약으로 가져와 검토한다.

이번 자동 시험의 파일 읽기/쓰기에는 합성 파일 URI를 사용한다. 시스템 SAF 선택기 조작,
실제 개인 OIDC 로그인, 한국어 발화/로컬 읽기, 실제 AI, 실물 폴더블 전환은 다시 실행하지 않았다.
기존 기능 수용 기록은 앞선 APK의 결과로 보존한다. 통합 APK에서는 실제 기기 확인이 남는다.
기존 Codex 원장14/15·유료 API0은 유지하며 이번 실제 AI 호출0이다.

첫 instrumentation 실행은15개 중1개가 실패했다. 검사에서 완료된 세션의 복원 상태를
REVIEW_REQUIRED로 기대했으나 기존 계약은 COMPLETED를 유지했다. 기대값을 바로잡고,
진행 중 세션의 복원→재검토와 완료 세션의 복원을 각각 검사하도록 보완했다.
이 과정에서 runtime 계약은 변경하지 않았다. 최초 실패 로그는 로컬 artifacts/attempt-1에 보존한다.
추가 키보드 검사에서 저장 재사용 파일의 끝에 이전 바이트1개가 남아 byte 비교가 실패했다.
이를 파일 쓰기 모드 보완 및 긴 기존 파일을 미리 만드는 회귀로 처리했다.
화면 조건을 연속 전환한 키보드 검사에서 IME 표시 요청이 누락되는 실행이 있어,
합성 시험에서 OS 키보드 표시를 명시적으로 요청하고 실제 WindowInsets의 IME visible을 검증한다.

통합 작업은 별도 worktree의 변경분이다. 기능 원본 checkout, main, 원격 브랜치에는 적용하지 않았다.
이번 요청으로 commit/push/최종 병합/배포는 실행하지 않는다.

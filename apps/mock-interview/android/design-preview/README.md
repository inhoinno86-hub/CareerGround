# CareerGround PACE 합성 미리보기

Round 03 / 03 PACE의 화면과 조작을 확인하는 독립 Android 앱이다.
application ID는 `dev.careerground.interview.design`이며 실제 기능 앱과 별개다.
현재 기능 브랜치의 `:pace-ui` library를 공유하고 합성 상태와 콜백만 제공한다.
로그인·네트워크·마이크·파일 선택·실제 AI 호출·실제 저장은 하지 않는다.

## 미리보기 범위

- 계정 연결, 홈, 자료 가져오기, 내용 검토, 질문·답변, 결과 화면.
- 시스템/밝은/어두운 테마와 빈 상태·로딩·오류·음성·중지·만료·파일 준비 상태.
- 초안 수정 시 확인 해제, 명시적 확인 후 제출, 모의 면접 중 평가 숨김.
- 질문 진행은 활성 질문 수를 사용하며 한 답변 집중/전체 흐름은 합성 전환이다.
- 초안과 확인 상태는 RAM의 ViewModel에서 구성 변경 중 유지한다.
  앱 프로세스 종료 후 자동 복구하거나 디스크에 저장하지 않는다.
- `PaceUiTest` 9개와 `PacePreviewFlowTest` 1개가 합성 동작을 검사한다.
  실제 기능 앱의 인증·음성·SAF·runtime 검사를 대신하지 않는다.

## 빌드

JDK 17, Android SDK 36, Build Tools 35.0.0과 프로젝트 의존성이 필요하다.
`JAVA_HOME`과 `ANDROID_SDK_ROOT`를 설치 위치에 맞게 설정하고
`apps/mock-interview/android/`에서 실행한다. 의존성이 캐시에 있는 환경에서는:

```bash
./gradlew --offline --no-daemon :design-preview:assembleDebug :design-preview:assembleDebugAndroidTest :design-preview:lintDebug
```

APK는 `design-preview/build/outputs/apk/debug/design-preview-debug.apk`에 생성된다.
APK·빌드 결과·로컬 SDK 설정은 Git에 포함하지 않는다.
별도로 준비한 합성 에뮬레이터에서 동작 시험을 실행할 때는
`:design-preview:connectedDebugAndroidTest`를 사용한다.

## 과거 기록과 현재 소스

[디자인 기록 안내](../../../../docs/design/README.md)에서 HTML 후보와
[2026-10-12 native 갤러리](../../../../docs/design/pace-implementation/index.html)를 볼 수 있다.
당시 미리보기 10개·adapter fixture 4개·native 조건 25개 검증은 과거 결과이며,
현재 `pace-ui`에는 이후 기능 통합 보완이 포함되어 화면과 동작에 차이가 있을 수 있다.
현재 보존 작업의 검증은 `docs/design/archive-validation-2026-10-23.json`에 별도로 기록한다.

PACE 실제 앱 통합은 `5453b01`에서 완료됐다.
[기능 반영 기록](../../../../docs/mock_interview_pace_delivery_20261016.md)을 따르며,
이 미리보기의 합성 상태를 실제 앱의 데이터로 연결하지 않는다.

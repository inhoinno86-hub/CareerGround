# PACE Compose 구현·검증 기록 — 2026-10-12

이 디렉터리는 실제 앱 통합 전에 만든 독립 PACE 미리보기의 시각 자료와 검증 기록이다.
현재 앱에 적용할 패키지가 아니다. 실제 앱 통합은 이후 `5453b01`에서 완료됐으며,
[기능 반영 기록](../../mock_interview_pace_delivery_20261016.md)을 따른다.

## 보존한 자료

- [native 갤러리](index.html), 밝은/어두운 전체 비교 PNG.
- `native/`: 전용 합성 AVD에서 캡처한 Compose PNG 25개와 UI 계층 XML 25개.
- `native-validation.json`: 당시 화면 크기·큰 글씨·키보드·제출 조작 위치 검사.
- `validation.json`: 당시 빌드·lint·미리보기 10개와 adapter 4개 검사 결과, APK 해시.
- `gallery-validation.json`: 당시 갤러리 이미지 로딩·테마·상세·모바일 너비 검사.
- `integration-baseline.json`, `implementation-source-manifest.json`: 당시 입력/작성 소스 해시.
  현재 기능 소스의 무결성 목록이 아니다. 과거 fixture 경로는 이 보존 브랜치에 포함하지 않았다.
- `capture_native.py`, `render_gallery.py`: 당시 합성 캡처와 갤러리 렌더링 도구.

`capture_native.py`는 기존 로컬 SDK와 `careerground-pace-api36` AVD/
`emulator-5580`을 전제로 한다. 준비된 에뮬레이터와 설치된 미리보기 앱이 필요하며,
실행하면 캡처와 과거 검증 JSON을 덮어쓴다. 갤러리를 보기 위해 실행할 필요는 없다.
현재 소스로 재캡처한 이미지는 2026-10-12 결과와 구분해서 보관한다.

## 당시 검증 범위

미리보기 10개와 adapter 4개 PASS, native 조건 25개 PASS였다.
UI library/미리보기 lint 오류·경고는 0이며, fixture의 기존 기능 소스 경고는 2개였다.
현재 보존 작업에서 이 기기 시험을 다시 실행한 결과로 해석하지 않는다.

당시 모든 화면과 조작은 합성 데이터였다. 실제 OIDC·한국어 발화·AI·SAF 왕복은
이 자료의 검증 범위에 포함하지 않는다. 가변 크기는 AVD의 wm override이며
실물 폴더블 hinge/분할 화면 인증이 아니다.

## 제외한 산출물

약 28 MB의 `CareerGround-PACE-preview.apk`, 과거 `pace-ui-integration.patch`와
`bundle-manifest.json`, `stage_integration.py`, `prepare_bundle.py`,
`run_native_validation.py`, 임시 `native-run-status.json`은 포함하지 않았다.
통합 준비 도구는 과거 미통합 소스 구조에 의존하므로 현재 기능 앱에 다시 실행하지 않는다.

새 미리보기 APK는 [미리보기 모듈](../../../apps/mock-interview/android/design-preview/README.md)에서
빌드한다. 이 APK는 과거 `validation.json`에 기록된 바이너리와 다를 수 있다.
전체 보존 범위는 [디자인 기록 안내](../README.md)를 따른다.

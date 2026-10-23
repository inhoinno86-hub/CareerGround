# Compose 디자인 기록 보존

2026-10-23, PACE 통합이 완료된 기능 브랜치의 `5f5c6b3`를 기준으로
독립 디자인 작업 공간의 산출물을 선별해 보존했다.
이 브랜치는 보존용 commit/push 대상이며 기능 브랜치나 main에 병합하지 않는다.
실제 기능 통합은 `5453b01`에서 완료됐고
[최종 반영 기록](../mock_interview_pace_delivery_20261016.md)에서 확인할 수 있다.

## 시안과 구현 기록

| 자료 | 용도 |
| --- | --- |
| [1차 비교](compare.html) | 맑은 블루/그라운드 틸 초기 HTML 시안 |
| [2차 비교](round-02/index.html) · [설계 기록](round-02/README.md) | FOLIO/ORBIT/BLOCKS/TRAIL/STILL 비교 |
| [3차 비교](round-03/index.html) · [설계 기록](round-03/README.md) | SAGE/FRAME/PACE/FIELD/LAYER와 선택 배경 |
| [PACE native 갤러리](pace-implementation/index.html) · [검증 범위](pace-implementation/README.md) | 2026-10-12 합성 Compose 캡처 |
| [작업 계획과 완료 기록](../../PLAN-2026-10-12-compose-design.md) | 당시 요구사항·피드백·진행 경과 |
| [독립 PACE 미리보기](../../apps/mock-interview/android/design-preview/README.md) | 현재 기능 브랜치의 UI library를 공유하는 합성 앱 |

HTML·PNG와 기존 검증 JSON은 당시 결과로 보존했다.
1~3차 HTML은 시각 비교용이며 native 렌더링 결과가 아니다.
native 캡처는 합성 자료를 사용했고 실제 개인 자료·계정 토큰을 포함하지 않는다.
`compose-source-baseline-2026-10-12.json`과 구현 manifest의 해시는 당시 소스 기준이며,
이 브랜치의 최신 앱·UI 해시와 같아야 하는 검증 자료가 아니다.

## 선택한 변경과 제외 범위

디자인 자료와 미리보기 모듈만 가져왔으며, `settings.gradle.kts`에는 미리보기 등록만 추가했다.
기존 `:app`, `:pace-ui`, runtime, 인증 설정, session schema는 기준 커밋을 유지한다.
현재 미리보기는 기능 통합 후의 UI 보완을 공유하므로 과거 캡처와 일부 차이가 있을 수 있다.
미리보기의 Activity 참조는 현재 lint 지적에 따라 `LocalContext` 변환에서
`LocalActivity`로 바꿨다. 실제 기능 앱의 adapter는 변경하지 않았다.

과거 앱 복사본·APK·빌드/캐시·개인 파일은 가져오지 않았다.
과거 통합 fixture와 패치·패치 생성/staging/실행 도구, 임시 실행 상태도 제외했다.
이 도구들은 이미 완료된 통합을 다시 적용할 때 필요한 자료가 아니다.
원본 디자인 작업 공간의 파일은 수정하거나 삭제하지 않았다.

## 현재 보존 작업의 검증

현재 빌드·정적 검사·HTML 갤러리 확인 결과는
[2026-10-23 검증 기록](archive-validation-2026-10-23.json)에 별도로 기록한다.
기존 JSON에 있는 Android instrumentation 14개와 native 조건 25개 결과를
이번 실행의 검증 결과로 재사용하지 않는다.

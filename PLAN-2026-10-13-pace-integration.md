# PACE 실제 앱 통합

기능 완료 기준: `25bf5b012fdcce34e916ce544f27031338369c26`.
독립 디자인의 Round03 / 03 PACE를 실제 Android 앱에 연결한다.
통합 worktree: `/home/inno/orca/workspaces/CareerGround/careerground-pace-integration`.

- [x] 기능 완료 커밋·clean checkout 확인, 별도 통합 worktree 생성.
- [x] 기존 연결 대상 16개 파일 해시 동일 및 준비 패치 적용 가능 확인.
- [x] UI library와 실제 ViewModel/SAF/OIDC/마이크 callback 연결, 구 화면 제거.
- [x] 새 화면에 맞춘 기존 검사와 실제 앱 adapter/조작 회귀 추가.
- [x] offline APK·JVM·lint·Android instrumentation 및 합성 runtime 왕복 검증.
- [x] 최종 diff, 기능 소스 보존, APK·검증 결과와 사용 안내 기록.

최종: Android21회(고유15개·추가3조건에서2개씩) / JVM10개 / 서버41개·96 subtests PASS.
앱 lint 오류0·기존 경고2, UI library 오류·경고0.
버전0.3.0-pace / code5, APK·동반 검증은 `docs/mock_interview_pace_integration_20261013.md/json` 참조.
실제 개인 로그인·발화·SAF 선택/쓰기·실물 폴더블 확인은 별도다.

2026-10-16 후속: 연결된 Fold7에서 기존 앱 프로세스가 없는 것을 확인하고,
기존 code4에 PACE code5를 `adb install -r`로 업데이트했다. 설치 후 버전과
앱 프로세스 실행을 확인했다. 실제 OIDC loopback runtime(AI 비활성)과 USB reverse8765를
준비했다. 개인 로그인·실물 화면·발화의 사용자 확인은 아직 진행하지 않았다.
기존 호출 원장은14/15이며 변경하거나 실제 AI를 호출하지 않았다.
세부 증거·다음 단계는 `docs/mock_interview_pace_device_20261016.md` 참조.

통합 구현 중에는 원본 기능 checkout 및 독립 디자인 worktree를 수정하지 않는다.
아래 최종 반영 승인을 받은 이후 기능 checkout에 검증된 커밋을 병합하며 독립 디자인 worktree는 보존한다.
실제 개인 로그인·한국어 발화·실제 AI는 합성 검사와 구분한다.
자동 통합 검증에서는 실제 AI를 호출하지 않는다.
2026-10-16 실기기 후속 시험은 사용자 명시 승인에 따라 기존 호출 원장 사용14회를
보존하고 누적 한도를15→18로 확대한다. 질문 생성1회·평가1회 및 실패 시 최대2회
재시도 범위이며 기존 Codex 로그인 경로를 유지한다.

- [x] 누적18회 상한·기존 사용량 보존·초과 차단 offline 검사(9개·13 subtests PASS).
- [x] 기존 원장 한도만 변경하고 실제 OIDC+AI runtime 전환(14/18, 준비 호출0회).
- [x] 사용자 재연결·저장 세션 복구 후 실제 질문·음성·평가 확인(사용자 완료 보고·원장16/18).
- [x] 실제 결과·전체 세션 파일 저장과 형식·참조 확인 후 후속 정리.

후속: 결과 파일 정식 검사 PASS. 전체 세션 준비는 `SESSION_SCHEMA`로 실패했고,
원인은18회 승인 변경 시 세션 schema 이벤트 호출 상한15를 누락한 것이다.
상한18로 동기화하고15/16·17/18 완료 파일 왕복,19 거부 및 상한 일치 회귀를 보완했다.
서버51개·111 subtests PASS. 같은 runtime의 schema 동적 로딩으로 적용되어
재시작·추가 AI 호출 없이 휴대폰에서 다시 준비·저장했고 결과/전체 세션 일치·offline 복구 PASS.
앱 프로세스·이번 runtime·USB reverse 정리 완료. 앱과 저장 파일 보존, 실제 AI16/18.
기기 시험 종료 시 통합 변경은 별도 브랜치에 유지했고 commit/push/병합은 실행하지 않았다.
사용자가 승인하지 않은 commit/push/최종 병합/배포는 실행하지 않는다.

## 2026-10-16 최종 반영 승인

사용자가 검증된 변경의 commit, 기존 기능 브랜치 병합, push를 명시 승인했다.
대상은 `codex/mvp-foundation-ci-20260923`이며 운영 배포는 범위에 포함하지 않는다.
원격과 기능 checkout이 기준25bf5b0이고 기능 checkout clean인 것을 확인했다.
Android 소스/검증 APK 해시 동일, 대상 텍스트27개와 diff를 검토했다.

- [x] 최종 파일 범위·원격 기준·기능 checkout 상태·기존 검증 근거 확인.
- [x] 통합 변경 커밋 및 기능 브랜치 fast-forward 병합(`5453b01`).
- [x] 기능 브랜치 push와 원격 커밋 일치 확인(`5453b01`).
- [x] 최종 반영 기록·worktree 상태 정리.

통합 커밋27개 파일을 기존 기능 브랜치에 충돌 없이 fast-forward 반영하고 원격 일치를 확인했다.
Orca 통합 worktree는 completed로 표시했고 독립 디자인 worktree는 보존했다.
상세 반영 기록은 `docs/mock_interview_pace_delivery_20261016.md`를 따른다.
이 최종 기록만 별도 문서 커밋으로 추가 반영한다.

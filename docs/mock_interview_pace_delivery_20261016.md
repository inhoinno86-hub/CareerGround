# PACE 실제 앱 통합 반영 — 2026-10-16

사용자가 검증된 변경의 commit, 기존 기능 브랜치 병합, push를 명시 승인했다.

## 반영 결과

- 기준: `25bf5b012fdcce34e916ce544f27031338369c26`.
- 구현 커밋: `5453b0107056983bdcf5f76e341a1005f3db970e`
  (`feat(interview): integrate verified PACE Compose design`).
- 구현 브랜치: `inhoinno86-hub/careerground-pace-integration`.
- 반영 대상: `codex/mvp-foundation-ci-20260923`.
- 구현/검증 기록27개 파일을 선택 커밋하고 기능 checkout에서 fast-forward 병합했다.
- 원격 기능 브랜치에 push한 뒤 `git ls-remote`로 구현 커밋 일치를 확인했다.
- 최종 문서 기록은 후속 문서 커밋으로 같은 브랜치에 반영한다.
- 독립 디자인 worktree는 보존하고 통합 worktree의 Orca 상태를 completed로 갱신했다.
- 운영 배포·태그·릴리스 발행은 수행하지 않았다.

## 포함한 변경

PACE Compose library와 실제 앱 adapter, 시스템 light/dark와 폴더블 너비 대응,
기존 OIDC·자료 검토·질문/답변·기기 내 음성·SAF 저장 흐름 연결을 포함한다.
기존 ViewModel의 기능 변경은 저장 시 truncate 처리이며 보안 Activity lifecycle과
기존 인증·음성 구현은 유지한다. 사용자 승인 누적18회 상한과 내부 세션 형식의
이벤트 호출 상한을 일치시키고 완료 파일의 export/restore 회귀를 포함했다.
APK·개인 자료 원문·계정 token·로컬 호출 원장은 Git에 포함하지 않았다.

## 검증 근거와 범위

- 앞선 APK/debug/test 빌드, JVM10개, Android instrumentation21회 PASS.
- 실기기에서 개인 로그인, 자료 가져오기/확인, 접힘/펼침, 수동 저장/복구,
  음성 입력·답변 제출·실제 질문/평가·결과/전체 세션 저장을 사용자와 확인했다.
- 휴대폰 지정 파일을 RAM에서 검사하여 결과/전체 세션 일치와 offline 완료 복구 PASS.
- 세션 상한 수정 후 서버51개·111 subtests PASS, Ruff/format 검사 PASS.
- 커밋 직전 runtime와 관련 tests 전체 Ruff/format 검사 PASS, staged diff check PASS.
- Android 소스·검증 APK SHA256이 앞선 검증 기록과 같아 Android 재빌드를 반복하지 않았다.
- 실제 AI16/18·잔여2회. 기기 시험2회 이후 커밋/병합 과정의 실제 AI 호출은 없다.
- 실물 다크 모드·키보드 배치의 개별 사용자 판정, 전체 문항 면접 수용은 별도로 남는다.

구현 커밋 push로 시작된 [Foundation CI](https://github.com/inhoinno86-hub/CareerGround/actions/runs/38911215749)는
이 기록 작성 시 실행 중이었다. 로컬 검증과 원격 CI 결과를 구분한다.

상세 자동 검사는 [통합 기록](mock_interview_pace_integration_20261013.md),
실물 확인·파일 검사·오류 보완은 [기기 기록](mock_interview_pace_device_20261016.md)을 따른다.

## 현재 사용 상태

휴대폰에는 검증한 code5 / `0.3.0-pace`가 설치되어 있다.
기기 시험 종료 후 앱 프로세스·시험 PC runtime·USB reverse8765는 정리했고,
설치 앱과 휴대폰의 READY·result·completed session 파일은 보존했다.
다음 개발 앱 사용 시 같은 원장의18회 설정으로 PC runtime을 실행하고 USB reverse를
연결한 뒤 개인 로그인·수동 파일 가져오기를 진행한다.

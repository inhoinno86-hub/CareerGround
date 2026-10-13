# CareerGround Portable·08 커밋 전 검증 — 2026-10-13

사용자가 대상 정리·검증 후 이상이 없으면 commit/push하도록 승인했다.
현재 브랜치 `codex/mvp-foundation-ci-20260923`를 유지하며 main 병합·배포·설치/등록 변경은 포함하지 않는다.
시작 HEAD와 origin 브랜치는 `9bd1009237f6486285ec8192086d286e0a5e94f2`로 같았다.

## 대상 분류

| 분류 | 대상과 처리 |
| --- | --- |
| commit — Portable | 스킬8개·참조 코드/schema/template·합성 fixture·검사/ZIP 도구·관련 시험·01–07 수용/실패 기록·CI |
| commit — 08 | Android code4·runtime·내부 session 계약·공개 Auth0 개발 설정·합성 회귀·빌드/기기/파일/host 수용 기록·계획·README·CI |
| commit — 마감 기록 | 커밋 전 검사·범위·미실행과 원격 확인 기록 |
| gitignore-candidate | 이미 무시되는 `.venv`, `.env`, Python/Gradle 캐시, `local.properties`, APK/빌드 출력, reports, 로컬 프롬프트. 새 무시 규칙 불필요 |
| discard-candidate | 없음. 기존 자료·실패 증거 삭제 없음 |
| needs-user-judgment | 검사한 변경에서 추가 결정이 필요한 항목 없음. 운영 API·배포·추가 호출 한도는 후속 범위 |

개인 경력·전사·답변·handoff/result/session 원문·로그인 파일·호출 원장·시험 로그는 커밋하지 않는다.
개인 원본은 저장소 밖 owner-only 위치에 유지하며 세 주요 입력/결과/정상 세션의 기존 hash 일치를 확인했다.
변경 텍스트의 비밀키/API key/JWT·개인 경력 표현 검사에서 해당 값이 발견되지 않았다.
발견된 이메일은 거부 동작을 검증하는 `example.com` 합성 fixture다.
Auth0 issuer/client ID/audience는 공개 개발 설정이며 client secret/token/사용자 계정 정보는 포함하지 않는다.
유일한 추가 바이너리는 Gradle wrapper JAR이며 기존 검증 SHA-256과 일치한다.
이 검사는 문자열·경로·내용 검토이며 모든 가능한 민감 정보 탐지의 보장은 아니다.

## 실제 로컬 검사

| 검사 | 결과 | 실행 범위 |
| --- | --- | --- |
| 관련 pytest | 87 passed, 144 subtests passed | Portable4·앱4·기존 legacy ZIP1 시험 파일. AI/로그인/검색 호출 없음 |
| 전체 unittest discover | 559 중 522 통과, 37 skipped | PostgreSQL URL 미설정 37개는 미실행. 실패/오류0 |
| 기존 실행기 pytest | 13 passed | QA/tunnel launcher 회귀. 실제 외부 tunnel 생성 없음 |
| Portable 검사 | LOCAL_PASS, 패키지73 members | 정상 합성 입력6·부정2의 예상 거부, 스킬 header·의존성·지원 파일 검사 |
| 합성 STEP02 smoke | PASS, 5 checks | 실제 loopback HTTP 가져오기/검토/고정/일시 중지/파일 복원. 실제 계정/AI/휴대폰 검사 아님 |
| Ruff | check/format PASS | 기존 src/migrations/scripts와 새 Portable/runtime/관련 시험 |
| Android 재빌드 | BUILD SUCCESSFUL | 기존 SDK/JDK/캐시로 `--offline --no-daemon --rerun-tasks` 앱·시험 APK 생성 |
| Android JVM | 10 passed | 파일 reader2·음성 구간/전사8. 실기기 음성 시험 아님 |
| Android lint | 오류0, 경고3 | Gradle 업데이트 안내1·KTX 사용 제안2. 오프라인 조회 결과이며 외부 버전 검증 아님 |
| diff/무시 규칙 | PASS(기존 Markdown EOF 공백·Windows CRLF 보존) | 그 외 whitespace·변경 종류·개인 파일/로컬 산출물 제외 대조 |

빌드 명령은 앱 README의 전용 도구 환경을 사용하며 추가 설치/다운로드·APK 재설치 없이 실행했다.
실기기·ChatGPT·실제 AI 왕복은 이번에 다시 실행하지 않았다. 기존
[합성 개발 수용](mock_interview_app_acceptance_20261012.md)과
[개인 첫 답변 수용](mock_interview_personal_roundtrip_20261012.md)을 근거로 보존한다.
Codex 원장14/15·유료API0은 그대로이며 이번 실제 AI 호출0이다.

## 발견한 문제와 보완

- 새 누적 한도 회귀의 중첩 `with` 스타일3건과 runtime/시험4파일 포맷 차이를 정리했다.
  논리·provider prompt·개인 답변은 변경하지 않았고 관련 시험87개를 재실행해 통과했다.
- CI는 기존 전체 unittest에 새 시험을 포함하고, runtime/앱 회귀 파일의 Ruff check/format도 추가했다.
  Android 빌드는 이번에 기존 로컬 도구로 검증했으며 새 GitHub Android 설치 job은 추가하지 않았다.
- 첫 Android 명령은 성공했지만 Gradle journal의 `CorruptedCacheException`을 출력했다.
  의존성 캐시는 유지하고 손상된 journal만 전용 도구 경로에 백업한 후 재생성했다.
  두 번째 명령으로 작업을 전부 재실행해 성공과 오류 없는 최종 로그를 확인했다.
  SDK metadata XML 버전 차이 안내는 남으며 SDK 변경/설치는 하지 않았다.
- 오래된 준비 복구 계획의 현재 안내와 개인 준비 JSON의 scope를 완료 기록에 맞췄다.
  과거 미착수·실패·미실행 이력과 원본 판정은 보존했다.
- staging 후 새 파일까지 포함한 diff 검사에서 기존 Portable `references/workflow.md`의
  마지막 빈 줄1개가 감지됐다. 설치·수용된 0.2.0 원본 바이트를 유지하고 이 안내 공백은 보존한다.
  Windows wrapper `gradlew.bat`의 원본 CRLF도 일반 검사에서 trailing whitespace로 표시됐다.
  명령 단위의 `core.whitespace=-blank-at-eof,cr-at-eol`로 두 원본 형식을 유지하며 그 외 오류가
  없음을 검사했다. 처음 staged 일반 검사에서 나온 경고를 모든 공백 검사 무경고로 표시하지 않는다.
  저장소/전역 Git 설정은 변경하지 않는다.

## 후속 사용 범위

커밋/푸시 후 ChatGPT Portable에서 검토한 resume·handoff를 만들어 앱에 가져와 직접 면접한다.
현재 앱은 PC runtime/USB 개발 연결이 필요하고 운영 API·독립 모바일 배포는 미실행이다.
전체 면접의 추가 AI 호출은 기존 잔여1회와 필요한 호출 수를 검토해 별도 한도 승인을 받는다.
새 후보를 사용할 때만 사실/목적별 사용 확인을 수행하며 기존 승인은 재요청하지 않는다.

## 개발 커밋·실제 푸시 확인

- `bb30d49a35ea317db986267017be16ec519e866a`: Portable 워크플로·계약·패키지·합성 시험·수용 기록.
- `42645ef7211d3e44d89a39da93ca477640a215ff`: Android/runtime·내부 세션·기기/개인 왕복·사용 안내·CI.
- 실제 일반 push로 기존 origin 작업 브랜치가 `9bd1009`에서 `42645ef`로 갱신됐다.
  `git ls-remote`·로컬 HEAD·origin 추적 브랜치 세 값이 같은 전체 hash임을 확인했다.
- 당시 남은 파일은 이번 계획·검증 Markdown/JSON3개로 모두 마감 기록이다.
  이 기록 자체도 별도 커밋/푸시하고 마지막 HEAD 일치·clean tree는 최종 응답에서 확인한다.
- 개발 HEAD의 [GitHub CI 실행](https://github.com/inhoinno86-hub/CareerGround/actions/runs/38393915531)이
  시작됐다. 이 기록 시점은 진행 중이며 원격 CI 성공을 주장하지 않는다.

main 병합·배포·플러그인 등록/연결 변경은 실행하지 않았다.

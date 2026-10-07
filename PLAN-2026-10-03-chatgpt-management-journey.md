# ChatGPT 대화와 CareerGround 관리 화면 연결

사용자가 2026-10-03 권장 순서 1→2→3→4 실행을 승인했다. 기준 HEAD는
`671cac84bd619c384093b7a2a9e1d3a15c6c481f`이며 시작 작업 트리는 깨끗하다.
기존 ignored 초안과 합성 개발 저장소를 보존한다. 실제 경력 데이터, 운영 서비스,
별도 유료 자원, 외부 모델 API, 공개 배포, commit/push는 사용하지 않는다.
실제 ChatGPT 시험은 기존 계정에서 합성 자료만 사용하며 연결/권한에 필요한 수동
절차와 추가 승인은 구체적인 준비가 끝난 뒤 한 단계씩 요청한다.

## 실행 순서

- [x] 1. 제품 Workflow Skill/플러그인 패키지, 검증된 신원에 대한 명시적 계정·프로필
  초기화, 소유된 입력의 정확한 원문 범위 → 미승인 초안 → 검토 MCP 연결을 구현한다.
  계정 차단/삭제, scope, 버전, 재시도, 근거 범위, 승인 분리 검사를 통과한다.
- [x] 2. BrowserOS에서 실제 ChatGPT 계정/개발 연결 가능성을 확인하고 준비된 패키지와
  합성 MCP 여정을 시험한다. 실제 모델 선택/도구 호출 결과와 직접 RPC 결과를 구분한다.
  인증이나 안전한 외부 전송 경로가 없으면 그 단계만 요청하고 독립 작업은 계속한다.
- [x] 3. Phase A 검토 화면은 기존 웹을 우선 사용한다. 서버에서 고정한 관리 화면 origin으로
  확인 URL을 생성하고 로그인·소유권·버전·연결별 승인 증명·돌아와 확인하는 흐름을 검증한다.
  ChatGPT 내장 UI는 후속 선택으로 남기며 승인 권한을 모델로 옮기지 않는다.
- [x] 4. 시험 증거에 따라 ChatGPT가 담당할 제안과 서버의 검증 책임을 명시하고,
  별도 서버 AI 도입 조건과 운영/비용/인증의 남은 실제 gate를 정리한다.

## 완료 기준

의미 있는 focused 보안/통합 테스트, 변경된 MCP schema와 패키지 검사, BrowserOS 실제
웹 여정, diff 검토를 수행한다. 외부 ChatGPT 미시험은 PASS로 기록하지 않는다.
현재 작업의 구현/검증/외부 대기 상태를 이 계획과 결과 문서에서 유지한다.

## 검증·발견 기록

- 제품 도구 30개, 신규 첫 사용/원문 범위/관리 URL/동일 연결 상태 조회 및 패키지 구현.
- PostgreSQL-required 전체 unittest 398 PASS/skip 0, Alembic upgrade/check PASS.
  제품 테이블 38개 모두 비어 있음 확인 후 사용자 Docker stop 결과/포트 닫힘 확인.
- 실제 ChatGPT에서 원문→미승인 초안→관리 웹 검토→대화 복귀→버전 1→별도 export까지 확인.
  만료 후 ID 재발견 및 host의 동적 export resource listing 문제를 발견하고 보완.
- resource discovery 수정 관련 회귀 36 PASS/skip 0. 호스트에서 동적 resource
  목록을 읽지 못해 작은 승인 본문 INLINE 응답을 추가. 관련 회귀 41 PASS/skip 0,
  초과 크기 본문을 잘라 보내지 않는 추가 분기 검사 PASS. 실제 ChatGPT INLINE JSON 본문 수신/원문 대조 PASS.
- 원문 한 줄의 제한된 합성 시험이며 실제 OAuth/SSO·광범위 한국어 품질·운영 gate는 미완료.
- 결과·남은 순서: [실행 결과](docs/CareerGround_ChatGPT_Management_Journey_2026-10-03.md).

## 종료

1→4의 구현·합성 실제 ChatGPT 시험·관리 웹 연결·서버 AI 판단을 완료했다.
실제 OAuth/SSO, 대표 한국어 품질 평가, 운영/삭제 provider acceptance는 다음 gate다.
별도 서버 모델 API 도입은 보류한다. 임시 PostgreSQL/합성 서버/tunnel을 종료하고
자체 비밀번호·임시 profile/ZIP을 정리했다. commit/push는 수행하지 않았다.
개인 시험 앱 연결 해제까지 확인했다. 최종 합성 대화 기록과 패키지는 개인 디렉터리에 보관한다.

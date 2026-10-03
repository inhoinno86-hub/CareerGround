# Phase A MCP 계약·오프라인 제안 검증·영속 합성 실행 환경

사용자가 권장 순서 1→2→3 실행을 승인했다. 기준 HEAD `2a6cdd2`; 기존 로컬 데모와 수동 확인 완료 항목은 반복 구현하지 않는다. 실제 데이터·운영·인증/AI 공급자·유료 자원은 연결하지 않으며 커밋·푸시하지 않는다. ignored 초안을 보존한다.

## 순서와 완료 기준

1. `analyze_jd`는 source-bound MOCK_ONLY 후보 반환, canonical 변경 없음. `execute_data_deletion`은 연결에 묶인 브라우저 영향 확인/별도 모의 재인증/최종 승인 후 동일 연결에서만 실행. 계정 삭제 후 정상 MCP 인증 차단 유지. CURRENT 및 export 포함 범위 등 목표 계약 차이를 기록한다.
2. 외부 응답을 신뢰하지 않는 JD/R2 검증 경계와 한국어 합성 사례·오프라인 평가. Claim/근거 적격성과 정확한 현재 버전, 사실 추가·기여·수치·기간·부정 변화, R3 분리. 실제 모델 성능을 주장하지 않는다.
3. owner-only 전용 영속 합성 SQLite Web/MCP runtime, 같은 합성 계정·로그아웃/토큰 철회·재시작 시 임시 연결 무효화. 독립 서명 삭제 ledger를 DB commit 전에 저장하고 복원 시작 시 검증/격리. 실제 인증/운영 실행 환경으로 표시하지 않는다.

## 진행

- [x] 1 MCP 계약과 연결 승인 경로: 26 tools, strict schema/scope/quota, source-bound MOCK_ONLY JD 후보 및 같은 연결의 브라우저 승인 증명 후 local deletion. 다중 탭의 정확 요청/직접 삭제 분리, bearer 만료/재시도/다른 계정·연결·로그아웃 검사 완료. CURRENT/포함 선택 등 목표 의미 차이는 최신 기록에 명시.
- [x] 2 오프라인 제안 검증과 합성 평가: 읽기 전용 JD/R2 source·현재 적격 Claim/근거 경계와 R3 오류 분리. 한국어 53/53 사례 예상대로 처리, 단위 7 tests·14 subtests PASS. 실제 모델 의미 품질 보증 없음.
- [x] 3 영속 합성 runtime와 복원/로그아웃: 전용 owner-only SQLite/서명 키·독립 write-ahead ledger·manifest·exclusive lock, restored Graph fail-closed, 같은 합성 계정/현재 token 철회/재시작 연결 무효화. 새 SQLite schema 단일 트랜잭션·CLI Ctrl+C exit0 보강 후 집중5tests PASS 및 실제 신규/restart CLI 확인. 빈 A/B 개발 저장소 보존, 서버 종료.
- [x] 통합 검증·CI·문서·ignored 보존 확인: 필수 PG17.11 전체340 tests PASS/실패·skip0/58.893s, Alembic0019·37tables0·schema일치. Chrome150/Firefox155 PROFILE·ACCOUNT/native200%4cases360checks PASS. CI Ruff151files PASS, ignored20hash동일. PG정상stop/35215closed/owned임시자원제거. 미커밋/미푸시.

루트가 MCP/기존 파일 통합과 검증을 맡고 두 기존 작업자가 서로 다른 새 파일(제안 검증, 영속 실행기)을 담당한다. 저장 스키마는 기존 0019/37 tables를 유지한다. 연결 승인 대기 정보는 browser session처럼 프로세스 내부에만 보관하여 재시작 시 무효화한다.

완료/재현/실제 운영과의 차이: `docs/CareerGround_Phase_A_Contracts_Development_Runtime_2026-10-02.md`. 실제 공급자/인증/운영 전환과 전체 Gate A/B/C는 이번 로컬 준비 범위의 완료와 구분한다.

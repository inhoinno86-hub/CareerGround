# Phase A 로컬 체험·JD 모의 분석·합성 삭제·출시 준비

사용자가 2026-10-01 권장 순서 1→2→3→4 실행을 승인했다. 기준 HEAD `bc55528`, 작업 트리 clean. 기존 295개 필수 PostgreSQL 검사·2818개 새 브라우저 검사와 0019 schema를 재구현하지 않는다. 기존 ignored 초안을 보존하며 커밋·푸시는 별도 요청 전까지 하지 않는다. 실제 인증/AI·운영 서비스·유료 자원은 연결하지 않는다.

## 순서와 완료 기준

1. 루프백 전용 실행 진입점: env/실제 DB와 독립된 owner-only 임시 SQLite와 두 합성 계정, 새 임시 인증/signing keys. Web·MCP 동일 origin, 합성 계정 선택·문서 없는 여정·결과 추적을 직접 체험. 루프백 client/Host/Origin 검사, 서버 종료 시 DB/키 폐기. 공개 app에 마운트하지 않는다.
2. 공급자 독립 JD 분석 adapter와 모의 응답: 명시 source hash/span·요구·공백 후보를 엄격 검증. 외부 호출·가짜 분석 완료·Claim 승격 없음. 소유/정확 버전·source 변경·prompt injection·추가 권한·근거 없는 coverage 거부. 로컬 화면은 모의 결과임을 표시하고 승인된 발췌 경로와 구분.
3. 합성 삭제 여정: 소유 ACCOUNT/PROFILE preview→정확한 영향 확인→별도 모의 재인증→내부 erasure 및 최소 상태 capability. 모델/body가 trusted approval을 발급하지 못함. 원문/token 숨김·즉시 일반 제품 접근 차단·동시/retry 한 결과·다른 계정 보존·독립 ledger 기반 격리 복원 검증. 실제/외부/백업 완료는 인증하지 않는다.
4. 새 경로 Chrome/Firefox 실제 키보드·200% 확대·오류 복구·접근성 구조, SQLite/필수PG 통합 검사·schema check·로컬 실행/종료·CI·현재 계약 차이 문서. 필요 자원은 종료하고 알려진 미완료 Gate A/B/C를 보존.

## 진행

- 지침/HEAD/현재 승인 서비스와 격리 복원 경계 확인. 루트가 순서·통합·최종 검증을 맡는다. 기존 작업자 한 명은 새로운 일회용 rootless PostgreSQL을 준비한다(코드 수정 없음).

- [x] 1: `careerground.local_demo` 실행기, fresh owner-only SQLite 두 빈 프로필/임시 키, 정확 loopback Host·Origin·client 검사, 계정 선택/인증 MCP console/navigation, 실제 설정 독립. 실제 TCP 기동·SIGINT 폐기 확인, 128 세션 상한과 readiness 후 주소 출력 보강.
- [x] 2: `jd_analysis_adapter` provider-neutral read-only contract + `MockJDAnalyzer`; 로컬 exact proposal UI와 별도 선택 발췌 승인. 해시/원문 위치/최신 버전/owner/session/재시도 검사. 외부 의미 분석 또는 Claim/coverage 승격 없음.
- [x] 3: fresh-store `MockDeletionJourney`와 로컬 삭제 UI, 별도 영향 동의/모의 재인증/최종 범위 재표시/삭제/서버 내부 상태 proof. 동일 exact retry, 상태 조회 이후에도 일반 계정 접근 차단, 다른 계정 보존, 전체 완료 인증 없음. 독립 ledger 복원 격리에서 누락된 BrowserOperation도 fail-closed 검사에 추가.
- [x] 4: 새로운 전체 경로 집중 30 tests PASS(4.356s). Chrome/Firefox 새 화면 실제키보드/native 200%, 새 PG 동시성 및 전체 필수PG/schema/CI 검사 완료. 결과는 최신 release 문서로 기록.

- 최종 필수 PostgreSQL 전체 320 tests PASS, fail/skip 0, 48.769초. 0019/schema check PASS. 실제 Chrome/Firefox PROFILE·ACCOUNT 네 시나리오/native 200%에서 536 checks PASS. CI 범위 Ruff check/format 143 files PASS.
- 최신 결과/실제 계약/남은 게이트: `docs/CareerGround_Phase_A_Local_Demo_Release_2026-10-01.md`. README 실행/종료 안내와 CI 새 테스트/브라우저 경로 추가.
- PostgreSQL 제품37tables0/metadata일치 확인 후 정상stop/34955closed, 자체cluster/source/build-tools/credentials/ownedpointer 삭제. 브라우저CLI 네개 자체DB/서버 종료 확인. ignored20hash동일, HEADbc55528유지, diffcheck PASS. 새커밋/푸시/운영/외부AI 연결 없음.
- 2026-10-02: 사용자가 안내한 데모 체크 항목을 모두 확인했고 이상 없었다고 보고했다. 사용자 보고 기준 수동 검증 완료·발견 이슈 없음으로 최신 release 문서에 기록했다. 자동 검사 수치와 운영 출시 게이트는 기존 범위를 유지한다.
- 2026-10-02: 사용자가 현재 변경사항의 커밋을 명시 승인했다. 커밋 범위는 로컬 데모·JD 모의 후보·합성 삭제·복원 격리 보강 및 관련 테스트/CI/문서다. 무시된 초안은 제외하고 보존한다. 푸시는 승인 범위에 포함되지 않는다.

# Phase A 로컬 후속 1–4 실행 계획

사용자 승인: 2026-10-01, 권장 순서 1–4 전부 자율 수행. 기준 HEAD `061b371be0620adeac6f76b0fa6b70eefd36ab99`, 기존 변경·무시된 초안 보존. 커밋·푸시·배포·운영 데이터·외부 AI·유료 자원 연결은 하지 않는다.

1. 요청 제한 카운터의 한정된 정기 물리 삭제와 고정 항목 상태 집계. 합성 DB의 실제 무요청 상태 정리/동시 처리/장애를 검증한다.
2. 같은 계정·MCP 연결에 바인딩한 확인 요청을 만들고, 기존 브라우저 표시·세션 토큰·명시 확인으로만 실제 domain 행위를 실행한다. MCP는 브라우저가 완료한 행위의 짧은 증명만 소비한다. 모델이 사실/사용/문구를 직접 승인하지 않는다.
3. 사실/문구 제출 결과, 명시 내보내기의 짧은 인증 resource, 로컬 삭제 상태 조회를 확대한다. 미구현 의미 분석·R2/R3·충돌/경계 승인·운영 삭제는 정확히 구분한다.
4. Chrome 외 브라우저와 실제 브라우저 확대, 접근성 tree/가능한 실제 화면낭독기 검증. 기존 실사용자 프로필/데스크톱 설정을 변경하지 않는다. 증거 없이 전체 접근성 완료로 표시하지 않는다.

## 검증·완료 기준

- 확인 GET/모델이 보낸 임의 문자열은 canonical mutation/동의를 만들지 않음.
- 브라우저 세션/계정/연결/대상/버전/digest/형식/만료에 결합; 변조·다른 세션·stale·재전송·동시 승인에 대한 실제 부정 테스트.
- resource는 인증·소유권·연결·짧은 만료·hash·현재 삭제/근거 상태를 매 읽기 재확인. 원문을 확인 요청/로그/집계에 저장하지 않음.
- 종료 시 모든 프로세스/임시 credential 정리, 생성 합성 DB의 빈 상태 확인. sudo 없이 가능한 임시 PostgreSQL 17 설치를 먼저 시도한다.
- 전체 테스트, schema/migration check·rollback/reapply, 실제 브라우저 증거, CI check/format와 diff review. 원격 CI/공개 endpoint는 실행하지 않는다.

## 진행 기록

- 완료: 주 에이전트가 승인 연계/도구 통합/최종 검증을, 서로 다른 파일을 소유한 두 작업자가 카운터 유지보수와 브라우저 검증을 수행했다. 추가 읽기 전용 검토에서 scope-before-quota와 SQL 집계 문제를 수정했다.
- 1: 한정 배치/경쟁/장애/무요청 주기 정리와 고정 label 집계 완료. 실제 PostgreSQL CLI 2주기, 카운터·승인 요청 각 1개 삭제, canonical 변경 0.
- 2–3: 브라우저 직접 작업 → 짧은 계정/session/정확 OAuth token 증명 → MCP 결과/resource 완료. 19개 도구 schema, 만료·변조·타 계정/연결·동시/재전송·현재 근거 검사. 삭제 상태는 활성 계정의 FOUNDATION_ONLY 집계만; 공개 삭제 완료 아님.
- 4: Firefox 383, 실제 Chrome 200% 확대 361, 새 승인 Chrome/Firefox 각 53, 실제 Orca 발화 요청 11 checks 통과. 청취 품질/실사용자 감사와 전체 WCAG 완료로 표시하지 않음.
- PostgreSQL17.11 임시 rootless 설치: migration0017 upgrade/check/0016 rollback/reapply/check, required DB 전체 258 pass/skip0, CI Ruff check/format117 files. 제품37 tables 전부0, DB/포트/credential/설치 정리 완료.
- HEAD/branch 유지, 기존 무시된 초안20 hashes 일치, 커밋·푸시·배포·외부 AI 없음.
- [최신 구현·검증/한계](docs/CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md). 공개/운영 Gate A와 미구현 Phase A 도구5개는 후속 사용자 결정 범위.

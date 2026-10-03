# Phase A 로컬 계약 1→2→3 구현·BrowserOS 검증

사용자가 MCP CURRENT/내보내기 선택 → R2/R3 검토 여정 → SESSION/EVIDENCE/PROJECT 삭제를 승인했다. 기준 HEAD `2a6cdd2`, 기존 미커밋 변경/ignored 초안/개발 저장소를 보존한다. 외부 AI·실데이터·운영·새 유료 자원·커밋·푸시는 사용하지 않는다. 브라우저는 BrowserOS native MCP로 시험한다.

## 실행과 완료 기준

- [x] 1 MCP CURRENT를 명시적으로 정확한 숫자로 고정하고 내보내기 선택을 owner/version/receipt/resource hash에 바인딩한다. 미확인 초안과 만료/불가 참조 선택을 표시하며 만료 원문·삭제 payload·비밀은 내보내지 않는다.
- [x] 2 R1 원본/Claim/Evidence를 보존한 합성 R2 후보 → 별도 정확 문구 승인 → 새 R2 저장 → 별도 내보내기. R3는 기존 사실 검토로 돌리며 자동 승격하지 않는다.
- [x] 3 SESSION/EVIDENCE/PROJECT의 정확 소유 대상/영향/버전/모의 재인증/브라우저 승인/동일 연결 실행/상태/복원 격리를 연결한다. PROJECT는 명시적으로 등록된 프로젝트 scope만 사용한다.
- [x] 새 migration upgrade/check/rollback/reapply와 필수 PostgreSQL 전체 회귀, focused 보안/오프라인 검사, BrowserOS 실제 합성 여정·200%·A/B 보존을 검증한다.
- [x] 자체 테스트 자원 정리·기존 데이터/초안 보존, 작업 이력 저장, 4번 외부 게이트의 실제 필요 작업/승인 순서를 보고한다.

루트가 계약·schema/migration·Web/MCP 통합·BrowserOS/회귀·기록을 맡는다. 독립 작업자는 R2 domain/trace/export와 부분 삭제 domain/브라우저/복원 모듈을 각각 맡으며 공용 schema와 core routes를 수정하지 않는다.

## 완료 증거

- 2026-10-03 실제 PostgreSQL 전체 **369 PASS/skip 0**, migration0020 upgrade/check/rollback/reapply, 제품38 tables 모두0행.
- BrowserOS native MCP **151 checks PASS**, CURRENT/options·R2/R3·SESSION/EVIDENCE/PROJECT·200%·키보드·재시작·B 보존. 오프라인53/53 PASS, CI Ruff164 files 및 diff 검사 PASS.
- 준비0019 개발 저장소 복사본 upgrade 성공·원본전체hash 동일, ignored20초안hash 동일. 테스트DB/비밀번호/빌드/privateBrowserOS정리; HEAD변경/커밋/푸시 없음.
- [완료 보고서와 다음4번 승인 순서](docs/CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md). 사용자 요청한 saved working_list는 closeout helper로 저장한다.

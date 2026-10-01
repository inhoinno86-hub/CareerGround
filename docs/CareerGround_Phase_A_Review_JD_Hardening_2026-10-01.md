# Phase A 모순·경계·선택 JD/R1·요청 입구 보강

기준: `codex/mvp-foundation-ci-20260923`, HEAD `061b371be0620adeac6f76b0fa6b70eefd36ab99`.
사용자가 승인한 후속 권장 순서 1–4를 수행했다. 이전 [258개/0017 검증](CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md)은 당시 기록으로 보존한다. 기존 작업 트리와 무시된 초안을 유지했다. 실제 사용자·운영 서비스·외부 AI·유료 자원은 연결하지 않았다.

## 1. 정확한 모순·경계 결정

`CONFLICT_REVIEW`와 `BOUNDARY_REVIEW`는 소유 Claim과 정확한 현재 프로필 버전을 대상으로 한다. 모델은 대상 작업만 요청할 수 있다. 브라우저가 현재 사실·평가·반대/지원 근거·출처·활성 경계를 표시하고, 사용자가 결정/설명을 입력한다. 준비 POST는 승인이나 Graph 변경을 만들지 않는다. 두 번째 화면에서 **선택한 근거의 연결/항목 식별자·관계·정확한 원문·출처**, 결정/설명 또는 변경 전후 경계·허용 문구·남은 금지 확장·철회 대상 식별자를 확인한다.

승인 토큰은 계정·브라우저 세션·작업·대상·현재 버전·전체 표시 context·정확한 입력·domain review digest·기한을 묶는다. 브라우저가 기존 domain 명령을 실행하고 완료 메타데이터를 같은 transaction에 저장한다. 반대 Evidence와 기존 사실을 삭제하지 않는다. 정정 수용은 보수적으로 `CONTRADICTED`/`DO_NOT_CLAIM`, 나머지 모순 결정은 `DISPUTED`/`REVIEW_REQUIRED`를 유지한다. 경계 변경은 같은 범위의 사용 재검토를 요구한다. 관련 없는 Claim 평가는 바뀌지 않는다. 별도 사용 적격성 검토를 생략하지 않는다.

선택/정확 표시를 재구성하기 전에 공통 순서 **Account → Profile**의 배타 잠금을 얻고 최신 상태/버전을 확인한다. 서로 다른 승인 요청이 같은 프로필의 공유 잠금을 동시에 배타 잠금으로 승격하는 경로를 제거했다. 동일 요청 재전송은 한 결과로 수렴하며, 서로 다른 두 모순 승인은 한 건 완료·한 건 stale 거부가 된다. SQLite 확인 POST는 기존 작업 행 예약으로 쓰기를 직렬화한다. 짧은 표시 transaction의 잠금은 canonical 변경이 아니며, GET은 저장하지 않는다.

## 2. 사용자 선택 JD → 잠재 연결 → 정확 R1

새 세 작업도 **직접 입력/선택 → 정확한 내용 표시 → 두 개의 명시 체크 → 브라우저 실행 → MCP 결과 증명**을 사용한다.

| 작업 | 브라우저 입력과 결과 | MCP 결과 도구 / 실제 인자 |
| --- | --- | --- |
| `JD_PASTE` | 프로필의 현재 버전, 직접 선택한 bullet 1–5개. 입력 최대 6000자, 문구당 1000자. 원문 위치/문구와 hash를 기존 JD 저장소에 기록 | `record_selected_jd(profile_id, profile_version, approval_receipt)` |
| `JD_LINK` | 현재 사용 가능한 Claim과 정확한 JD 요구 한 쌍. 근거/출처를 확인해 `POTENTIAL` 관계만 기록 | `link_jd_requirement(jd_id, approval_receipt)` |
| `R1_DRAFT` | 현재 JD에 연결되고 별도 사용 적격성을 통과한 Claim 1–5개. 선택 순서와 정확한 문구/근거를 표시하고 그대로 복사 | `generate_resume_draft(jd_id, profile_version, approval_receipt)` |

현재 화면은 JD 요구 최대 5개와 후보 Claim 최대 20개를 완전히 표시한다. 한도를 초과하면 거부하며 일부만 잘라서 승인하지 않는다. JD_LINK/R1은 이미 존재하는 정확한 프로필 archive를 요구한다. 현재 상태·원문·archive·적격성이 달라지면 승인할 수 없다. 중복/타인 Claim 선택, hidden 입력 변경, 순서 변경, 다른 브라우저 세션/client, 만료 또는 stale 버전도 거부한다. 원문의 명령문/HTML은 입력 자료이며, 실행하거나 승인 지시로 취급하지 않는다.

선택 JD는 `analysis_kind=SELECTED_EXCERPTS_ONLY`다. AI 의미 분석·적합도 판정은 없다. R1은 `review_required=true`이며 별도 문구 검토 후 별도 내보내기 동의를 받아야 한다. R2/R3 재작성은 제공하지 않는다. 승인 전 사용자가 입력한 원문/결정은 서버 pending table에 복제하지 않는다. 브라우저 숨겨진 폼 값의 정확한 hash만 서명하고, 완료 작업 테이블에는 메타데이터만 저장한다. 원문이 포함된 브라우저 페이지는 기존 no-store 정책을 사용한다.

## 3. 실제 wire와 schema

합성 팩토리는 **24개 도구 = Phase A 이름 19개 + 보조 5개**다. 각 도구에 정확한 입력 schema·공통 성공/오류 envelope·실제 출력 schema·OAuth scope를 적용했다. 기존 `request_user_confirmation`은 9개 action을 지원한다. 새 모순/경계 도구는 `career.profile.write`, JD/연결/R1 도구는 `career.artifact.write`를 요구한다. MCP가 모델의 상세 결정·source text·승인 token을 받아 canonical mutation을 실행하는 계약은 아니다. 브라우저 완료 결과를 원래 연결의 짧은 증명으로 확인한다.

증명은 기존 계정·issuer/subject/client·**정확한 OAuth access token의 HMAC**·브라우저 세션·작업/대상/버전·기한 결합을 유지한다. 토큰 갱신 후 이전 증명을 재사용할 수 없다. 작업 최대 5분과 기존 화면 토큰의 더 짧은 기한이 모두 적용된다. 원문/token/receipt를 작업 결과나 로그에 복제하지 않는다. 내보내기 resource의 재조회도 기존 ownership/scope/token/hash/현재 근거/기한/활성 상태를 검사한다.

`0018`은 모순/경계, `0019`는 JD/연결/R1 action을 기존 `browser_operations` CHECK에 추가한다. 새 table/column이 없고 제품 테이블은 **37개**다. 삭제 inventory·로컬 erasure 순서·만료 유지보수는 이미 이 작업 테이블을 포함하므로 새 action도 적용된다. 새 action 행이 있는 DB의 downgrade는 제약으로 실패한다. downgrade를 위해 행을 버리거나 바꾸지 않는다. 이번 rollback 검증은 제품 테이블이 빈 일회용 DB에서만 수행했다.

남은 Phase A 이름은 `analyze_jd`, `execute_data_deletion`이다. 이름이 구현된 도구도 목표 Plugin 계약의 전체 의미적 완료를 뜻하지 않는다. 포함 선택/CURRENT·R2/R3·공급자·외부/백업 삭제·공개 제품 진입점과 Gate A 전체는 미완료다. [목표 계약 표](mvp_implementation_contract_matrix_v0.1.md)는 유지한다.

## 4. 삭제 후 상태의 별도 내부 capability

정상 MCP는 계속 ACTIVE 계정과 인증 매핑을 요구한다. 계정 삭제 후 그 권한을 다시 발급하지 않는다. 별도 `DeletionStatusCapabilityService`는 **내부 합성 코드만** 사용하며 공개 endpoint나 MCP 도구에 연결하지 않았다.

내부 삭제 실행 직후의 trusted Python handoff, 현재 유효한 `VerifiedDeletionApproval`, 정확한 저장 요청/account/scope/target, 독립 erasure ledger와 삭제 tombstone을 모두 확인해 기본 5분의 서명 bearer proof를 발급한다. Python issuer 타입 자체가 암호학적 권한 증명은 아니다. 실제 공급자 step-up·안전한 전달·폐기/회전·공개 요청 제한은 별도 계약이 필요하다. issue/read 모두 주입된 복원 격리 reconciliation 신호가 정확히 True여야 한다.

proof로 조회하는 결과는 정확한 요청의 SQL 집계뿐이다. 활성 identity가 삭제된 뒤에도 상태를 읽을 수 있지만 제품 권한·다른 요청 조회·canonical 읽기/쓰기·전체 삭제 완료 인증을 제공하지 않는다. 대상·저장소·오류 상세·원문은 반환하지 않는다. `FOUNDATION_ONLY`, `ready_to_execute=false` 및 `DELETING`/`FAILED`만 반환하며 로컬 `ERASED`도 전체 완료로 광고하지 않는다. 변조·다른 승인/대상·ledger 없음·복원 격리 미완료·만료를 합성 테스트로 검증했다.

## 5. 로컬 MCP 입구와 잘못된 요청

`LocalMCPIngress`가 OAuth/SDK 앞에서 `/mcp` POST를 제한한다. 실제 누적 body **128 KiB**, frame **1024개** 한도를 적용하고 declared/chunked/missing/dishonest Content-Length를 검사한다. 초과·잘못된 길이·frame은 입력을 반사하지 않는 고정 413/no-store 응답이다. 크기 초과 검사는 인증/DB보다 먼저 작동한다.

인증된 도구 호출의 unknown/missing/surplus field·잘못된 타입·알 수 없는 action/tool은 공통 account **read quota**를 소비한 뒤 안전한 `VALIDATION_FAILED`를 반환한다. 유효한 write 요청의 scope 실패는 write quota보다 먼저 거부한다. 한도 초과는 공통 `RATE_LIMITED`와 429/Retry-After다. 잘못된 JSON/JSON-RPC 구조 네 종류도 source/token이 응답/로그로 반사되지 않고 canonical 변경이 없음을 확인했다.

이것은 로컬 합성 팩토리의 제한이다. 도구 dispatch까지 도달하지 않는 invalid JSON/JSON-RPC는 account 도구 quota에 포함되지 않는다. 공개 ingress의 접속/시간/익명 요청 제한·프록시·분산 부하 제한을 제공하지 않으며 운영 보안 게이트를 대신하지 않는다.

## 6. 검증

- 일회용 rootless PostgreSQL **17.11**, 루프백 전용·빈 테스트 DB. URL/비밀번호는 owner-only 파일로 전달하고 도구 출력/명령 인자에 표시하지 않았다.
- `0019` upgrade/check → 빈 DB `0018` → `0017` downgrade → `0019` 재적용/check 모두 통과. Alembic schema drift 없음.
- `CAREERGROUND_REQUIRE_POSTGRES_TEST=1` 최종 전체 **295개 통과, 실패/skip 0**. 41.692초. 로그 `/tmp/careerground-review-jd-final-suite-20261001.log`.
- 새 정책 HTTP 검사 **10개**, 새 artifact HTTP 검사 **14개**가 SQLite/PostgreSQL에서 통과했다. 동일/서로 다른 동시 승인, 재전송·위조/타인 연결·scope·만료·stale·원문 변경·별도 사용/문구 게이트·두 R1 문구의 정확한 선택 순서를 포함한다.
- CI 범위 Ruff check/format **131개 파일** 통과. 새 네 테스트 파일과 두 실제 브라우저 스크립트를 CI 설정에 추가했다. GitHub CI 실행은 하지 않았다.

| 실제 로컬 브라우저 검증 | 시나리오 | 통과 검사 |
| --- | ---: | ---: |
| Chrome 150.0.7871.46 + Firefox 155.0, 모순 결정 4종·경계 ADD/REVOKE | 12 | 788 |
| 같은 브라우저, JD 발췌 수 1–5개 → 잠재 연결 → R1 → 별도 문구 검토 → Markdown resource | 10 | 2030 |

Tab/ArrowDown/Space/Enter의 실제 키보드 동작, 기본 required 검증·승인 체크, 언어/main/h1/skip link/접근성 이름, 연결 앱·선택 내용/근거 표시, 승인 전 무변경, MCP schema·재전송·별도 승인·원문 보존을 확인했다. 두 스크립트 모두 외부 브라우저 요청 0건이다. report에는 테스트 항목·브라우저·수치만 있으며 token/receipt/resource URI를 남기지 않았다. 합성 스크린샷은 완료 증명 화면 전에만 기록한다. 사람의 한국어 청취/실사용자 접근성 감사나 이번 신규 폼의 별도 200% 확대 검증 결과로 확대 해석하지 않는다.

재현:

```bash
uv run --locked python scripts/run_local_policy_browser_checks.py --output-dir /tmp/careerground-policy-browser-checks
uv run --locked python scripts/run_local_artifact_browser_checks.py --output-dir /tmp/careerground-artifact-browser-checks
```

로컬 보고서: `/tmp/careerground-policy-browser-checks-final-20261001/report.json`, `/tmp/careerground-artifact-browser-checks-20261001/report.json`.

## 7. 종료 상태

- 최종 PostgreSQL revision `20261001_0019`, 제품 **37개 테이블 모두 0행** 확인 후 `pg_ctl` 정상 종료. 루프백 36837 닫힘을 확인했다.
- 생성한 cluster/source/install/빌드 도구·URL/비밀번호 파일과 임시 m4 alias를 삭제했다. 브라우저 검사 서버와 private context는 각 스크립트에서 종료됐다. 정리 기록 `/tmp/careerground-review-jd-db-closeout-20261001.json`에는 schema/빈 행 수/종료 여부만 남겼다.
- HEAD/브랜치 변경 없음. `to-do-prompts/`·`intent-docs/` 기존 초안 **20개 hash 모두 동일**, `git diff --check` 통과. 기존 승인된 변경도 보존했다.
- 커밋·푸시·배포·GitHub CI 실행 없음. 별도 승인 없이 가능한 로컬 작업 **1–4 완료**. 실제 공급자·공개 제품·운영 삭제는 후속 결정으로 남긴다.

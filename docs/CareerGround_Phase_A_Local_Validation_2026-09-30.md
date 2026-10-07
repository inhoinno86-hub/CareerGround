# Phase A 합성 로컬 여정 및 검증 — 2026-09-30

이 문서는 당시 224개 테스트/12개 MCP 도구/0015 상태의 기록이다. 이후 공유 quota·공통 MCP 봉투·부분 삭제 미리보기·실제 Chrome 검증과 0016의 현재 결과는 [2026-10-01 후속 검증](CareerGround_Phase_A_Security_Accessibility_Contracts_2026-10-01.md)을 따른다.

## 기준과 작업 범위

브랜치 `codex/mvp-foundation-ci-20260923`, HEAD
`061b371be0620adeac6f76b0fa6b70eefd36ab99`에서 시작했다. 초기 작업 트리는
깨끗했고 원격 추적 브랜치보다 4개 커밋 앞섰다. HEAD를 이동하지 않았으며
커밋·푸시·배포도 하지 않았다. `~/.codex/AGENTS.md`와 사용자가 제공한 프로젝트
지침, 구현 계획, 지정 인계 묶음 main 및 step-01–05를 읽었다. 저장소 및 상위
경로에서 추가 `AGENTS.md`는 발견되지 않았다. Superpowers/Ouroboros는 사용하지 않았다.

`to-do-prompts/`와 `intent-docs/`는 계속 무시된 로컬 초안이다. 시작 시 기록한
전체 파일 SHA-256과 종료 시 값을 비교해 20개 파일이 동일함을 확인했다. 다른 프롬프트
묶음의 본문을 실행하거나 변경하지 않았다. 실제 사용자 데이터·운영 서비스·외부
AI·유료 자원은 연결하지 않았다.

## Step 01 — 확인한 공백과 처리 순서

| 계획 항목 | 시작 상태 / 코드 근거 | 이번 처리와 남은 경계 |
| --- | --- | --- |
| E05-S02 / T03–T04 | `web/review_foundation.py`에 입력·초안·사실/사용 검토·JD·R1 화면이 존재. 기존 `test_claim_use_review.py` 여정은 미리 확정한 Claim에서 시작 | 빈 v0 프로필의 직접 입력부터 다운로드까지 테스트 추가. 사실 검토 결과·근거·JD 이동 링크 보강. 전체 접근성 감사는 후속 |
| E05-S01 / T01–T02 | `mcp/product_server.py`는 12개 합성 도구. Web은 추가 승인/다운로드 화면을 제공. 정확한 승인 토큰은 브라우저 세션에 결합 | 공통 workspace 행위의 결과와 거부를 통합 비교. MCP가 SDK 자료형 변환 전에 잘못된 필드를 거부하도록 보강. 전체 Plugin v1 계약은 미완료 |
| E08-S01 / T01 | 소유권·scope·stale·만료·삭제·restore 테스트 존재. 최근 여정은 PostgreSQL에서 미검증 | 새 여정의 PostgreSQL 변형과 CI lint/format 범위 추가. 전체 required-PostgreSQL suite 실행 |
| E08-S01 / T02 | 단순 한국어 오류 복구·보안 헤더 존재. 운영 감사·속도 제한·메트릭·접근성 감사는 없음 | 렌더링 구조와 일반 요청/거부 로그에 대한 합성 점검, 로컬 위협/사고/롤백 절차 기록. 운영 기능과 검증은 공개 전 게이트 |

순서는 기존 구현을 유지하면서 여정 연결 → 어댑터 경계 → 전체/DB 검증 → 외부
게이트 증거 정리로 진행했다. 삭제의 `FOUNDATION_ONLY`, `ready_to_execute=false`는
유지한다. Gate A 전체가 완료됐다는 판정은 내리지 않는다.

## Step 02 — 문서 없는 직접 입력 여정

새 `tests/test_text_journey.py`는 계정 2개와 빈 버전 0 프로필만 만들고, 화면에서
제공한 링크·폼·redirect를 따라 다음 경로를 실제 요청으로 실행한다.

1. 수집 범위/90일 보관 안내 확인 → 명시적 세션 시작.
2. 직접 작성한 합성 한국어 글머리표 → 원문 그대로의 임시 `CONTRIBUTION` 초안.
3. 정확한 문구 표시 → 검토 준비 → 항목별 `ACCEPT`와 별도 확인.
4. 이 시점의 평가가 `USER_CONFIRMED` / `NOT_EVALUATED` / `REVIEW_REQUIRED`이고,
   사용 검토 journal은 0건인지 DB에서 확인.
5. 선택 Evidence·경계를 표시 → 별도 일관성/사용 확인 2개 → 프로필 v2.
6. JD 요건 직접 입력 → 정확한 발췌/Claim의 명시적 `POTENTIAL` 연결.
7. 해당 문구 선택 → R1 초안 → 근거 추적 → 정확한 R1 문구 승인.
8. 명시적 Markdown 다운로드. 이스케이프를 풀면 원래 Claim 문구와 같고,
   `attachment`, `Cache-Control: no-store` 응답인지 확인.

새 Claim·별도 사용 검토가 각각 1건이며 이 과정 이후 조회만으로 임시 세션의
보관 시계가 늘어나지 않는다. 타 계정의 trace/근거 열람과 export POST, `DELETING`
프로필의 열람/export를 거부한다. 별도 테스트는 추가 `account_id`/`messages` 입력을
거부하고 원문·토큰을 오류에 노출하지 않으며 만료 후 입력이 0건임을 확인한다.
기존 테스트의 빈 프로필 JD/연결 없음, stale/다른 세션/토큰 만료, 1–5개 제한은
유지되어 전체 suite에서 다시 통과했다.

화면에는 한국어 `lang`, 한 개의 h1/main, 고유 ID, viewport, 본문 바로가기와
`tabindex=-1` 본문 대상, label/fieldset/필수 native select·checkbox가 있다.
오류 본문은 `role=alert`와 `autofocus`를 갖고 시작 화면 복구 링크를 제공한다.
세션 화면에서 목록 사이의 문단을 목록 밖으로 이동했다. 시작 화면은 문서가
필요 없고 사실 확인·R1 사용 검토가 별개이며 외부 검증/채용 결과를 보장하지
않음을 설명한다.

이는 HTML 구조·HTTP 흐름 검증이다. 실제 브라우저의 Tab 이동/포커스 표시,
스크린리더 발화, 확대/모바일 레이아웃과 WCAG 전체 감사는 아직 미실시다.
자연어 의미 추출·atomicity 판정·JD 자동 분류·R2/R3 문구 생성도 포함하지 않는다.

## Step 03 — MCP/Web 범위와 보안

| 행위 | MCP 합성 도구 | Web 합성 경로 | 결과/차이 |
| --- | --- | --- | --- |
| 명시 시작·단일 입력·pause | `start_profiling`, `add_profiling_input`, `pause_profiling` | `/profiling/start`, 세션 `/input`, `/action` | 같은 소유 프로필의 독립 세션에 같은 입력을 저장하고 재시도 중복 방지·90일 보관·pause 후 새 입력 거부·Graph 무변경 확인 |
| 세션·프로필·선택 근거 조회 | `get_profiling_session`, `get_career_profile`, `get_claim_evidence` | 세션 상태, 정확 버전 프로필/Claim 화면 | 같은 도메인 명령 사용. 전체 입력 원문 미노출, 타 계정·삭제 중·없는 정확 버전 거부 |
| 검토 준비/읽기 | `prepare_claim_review`, `get_claim_review` | 범위 `/prepare`, `/review/{batch}` | 같은 준비/읽기 서비스. MCP는 read/write scope, Web은 세션에 결합한 표시/확인 토큰 |
| JD/이력서 추적 읽기 | `get_jd_analysis`, `get_resume_trace` | JD 발췌/연결 기록, R1 trace | 같은 정확 버전·archive·Evidence 적격성 재검사. MCP는 `career.artifact.read` |
| 사실·사용·문구 승인 | MCP 제출 도구 없음 | 사실 review, Claim use-review, R1 wording | 브라우저만 정확 표시 후 계정/세션/digest/버전에 묶인 짧은 토큰 발급. 모델이 승인 증명을 만들 수 없음 |
| JD 입력·잠재 연결·R1 생성/내보내기 | MCP 쓰기/내보내기 도구 없음 | JD/new, link, draft, export | 명시적 합성 폼만 지원. 자동 분석·범용 artifact resource 계약 미구현 |
| 삭제 | MCP 삭제 도구 없음 | 읽기 전용 ACCOUNT/PROFILE preview | 부분 영향 고지, 실행 불가. 신뢰된 step-up·운영 삭제/status 화면 후속 |

추가 MCP 보조 도구는 `get_account_profile`, `get_owned_profile_metadata`다.
Plugin v1의 Phase A 21개 도구 중 현재 MCP에 대응하는 이름은 10개이며,
위 보조 2개를 더한 총 12개다. 나머지 11개(`submit_claim_review`,
`resolve_claim_conflict`, `review_boundary_change`, `export_profile_data`, `analyze_jd`,
`generate_resume_draft`, `submit_resume_wording_review`, `export_resume`,
`preview_data_deletion`, `execute_data_deletion`, `get_deletion_status`)의 MCP 계약은
아직 노출되지 않는다. 내부 conflict/boundary/삭제 토대의 존재와 도구 완성을
구분한다. 전체 도구 공통 `status/data/next_actions/user_message` 봉투도 미연결이며
현재 factory는 `ok/error_code`, `found=false`, MCP `isError`를 사용한다.

`StrictProductMCPServer`는 정확한 필드 집합과 wire 자료형을 먼저 확인한다.
버전의 문자열/boolean/float/object와 source object를 거부하며, 잘못된 source
값을 오류 응답·관찰한 INFO 로그에 포함하지 않는다. 정상 버전은 int, 다른
인자는 str만 허용한다. 이 검사는 SDK가 버전을 coercion하거나 Pydantic 오류에
원문 값을 붙이는 것보다 먼저 실행된다. 토큰 issuer/서명/만료/audience/scope와
매 요청 활성 계정 gate는 기존 구현/테스트를 유지했다.

prompt처럼 보이는 문장도 명시 입력 데이터 한 건으로 저장되고 Claim 또는
권한을 만들지 않는다. 기존 provider span parser는 위치 외 소유권/평가 필드를
거부한다. 합성 restore quarantine 테스트는 삭제 ledger 불일치/변조와 삭제된
Graph/JD/임시 검토 복원을 막는다. 실제 백업·외부 복제본 복원 검증은 아니다.

### 로컬 위협 검토와 운영 전 요구

| 위험 | 현재 보호/증거 | 남은 운영 작업 |
| --- | --- | --- |
| 타 계정 접근·토큰 재사용 | active-account gate, owner FK/서비스 검사, scope 분리, 삭제 중 거부 | 실제 두 계정/refresh/revoke, 연결별 철회·운영 step-up |
| 승인 위조·오래된 화면 | 정확 digest/version·브라우저 결합·짧은 만료·재시도 journal | 공개 클라이언트의 표시 증명, 실제 세션/CSRF·key 보관 |
| 입력을 통한 권한 확대 | unknown field/wire type 차단, 원문 데이터만 처리, HTML escaping/CSP | 실제 AI 합성 공격 평가와 provider 격리 |
| 로그/오류 원문 노출 | 일반 합성 요청/입력 거부의 source 미노출 점검, 일반 Web 오류 복구 | 운영 access/exception 로그 redaction, SQL bind 숨김, 메트릭 allowlist·보관/접근 통제 검증. SDK·unexpected DB 오류까지 안전함을 주장하지 않음 |
| 요청 남용 | 입력/폼/목록/검토 크기 제한 | 공유 저장소 기반 계정/연결/행위별 rate limit, 429와 재시도 계약, 운영 부하 시험 |
| 예외적 운영자 열람 | 운영자 읽기 경로 자체 없음 | 승인 사유·권한·시간 제한·payload 없는 감사 기록·감사 접근 통제 |
| 삭제 내용 부활 | 내부 ledger/replay·quarantine·정확 archive 실패 폐쇄 | 운영 백업·snapshot·복제본·외부 provider/S3 모든 버전 증거, 공개 삭제 SLA |
| 접근성 | native controls/labels, skip link, 오류 landmark/focus 대상 점검 | 실제 브라우저/스크린리더와 키보드 감사 |

운영 지표 후보는 행위·결과 코드·소요 시간·재시도/만료 건수다. 원문, token,
digest, source/계정 ID를 metric label로 쓰지 않는다. 현재 운영 메트릭 collector나
감사 저장소는 만들지 않았으므로 실제 수집/삭제 증거는 후속이다.

사고가 의심되면 factory를 공개하지 않은 상태를 유지하고 합성 요청을 중단한다.
활성 계정/프로필 차단이 다음 조회·다운로드를 막는지는 테스트되어 있다.
운영 사고 대응에서는 영향 조사와 승인된 provider 철회/삭제를 별도 수행하고,
백업 복원은 ledger를 재적용한 quarantine 검증 전까지 노출하지 않는다.
사고 기록에 원문·토큰을 복사하지 않는다.

이번 변경은 새 migration이 없다. 되돌릴 때는 이전 factory 코드/기능 경로로
복귀하고 데이터를 보존한다. `0015 → 0014 → 0015` 검증은 빈 일회용 DB의
schema 되돌리기만 증명하며, 실제 review journal이 있는 DB의 downgrade는 승인된
데이터 이관/백업 계획 없이 실행하지 않는다. 과거 HEAD 강제 reset은 필요 없다.

## Step 04 — 실제 실행 결과

| 실행 | 실제 결과 |
| --- | --- |
| 시작 시 전체 unittest | 218개: 214 pass, PostgreSQL 전용 4 skip |
| 변경 후 PostgreSQL URL 없는 전체 unittest | 224개: 218 pass, PostgreSQL 전용 6 skip |
| MCP 집중 suite | 14개 pass, skip 0 |
| 여정 집중 suite, DB URL 없음 | 4개: SQLite 2 pass, PostgreSQL 2 skip |
| CI에 적힌 정확한 Ruff check/format 범위 | check 통과, 103개 파일 format 통과. 새 여정 파일도 CI 범위에 포함 |
| PostgreSQL 17.11, 빈 DB `alembic upgrade head` | `20260929_0015`까지 15개 migration 적용 |
| `alembic check` | 신규 operation 없음 |
| 빈 DB `downgrade 20260927_0014` → `upgrade head` → `check` | 통과, 신규 operation 없음 |
| `CAREERGROUND_REQUIRE_POSTGRES_TEST=1` 전체 unittest | **224 pass, 실패 0, skip 0**, 13.270초 |
| DB 종료 상태 | migration `20260929_0015`, 제품 테이블 **35개 모두 0행** |

전체 실행 명령은 `uv run --locked python -m unittest discover -s tests -q`다.
PostgreSQL 실행은 두 URL을 동일한 `postgresql+psycopg` 루프백 `_test` DB에
설정하고 `CAREERGROUND_REQUIRE_POSTGRES_TEST=1`을 추가했다. 실제 비밀번호/URL은
이 문서에 기록하지 않는다. 새 PostgreSQL 여정 테스트는 outer transaction 및
savepoint로 route의 commit을 허용하면서 fixture를 rollback한다. DB에는
`Base.metadata.create_all`을 실행하지 않고 migration으로 만들어진 테이블을 쓴다.

Docker socket/sudo 권한이 없어 사용자가 컨테이너 시작을 수행했다. 기존 컨테이너가
없어 `postgres:17`을 루프백 `127.0.0.1:55432`에 바인딩한 `--rm` 일회용 컨테이너
`careerground-phase-a-test`를 사용했고 영구 볼륨은 만들지 않았다. 최초 잘못
입력된 `postgres:1`은 이미지 미존재로 실패했으며 올바른 태그로 시작 후 검증했다.
종료/임시 자격증명 파일 정리와 최종 diff/초안 hash 확인 상태는 아래에 기록한다.

## Step 05 — 외부 증거와 후속 순서

| 게이트 | 저장소에 남아 있는 증거 | 아직 필요한 증거/결정 |
| --- | --- | --- |
| G-I | 2026-09-26 개발 Auth0–ChatGPT PoC 로그인/인가 코드 교환/인증 도구 성공 기록. 로컬 JWT/계정 차단·격리 테스트 | 실제 요청의 `code_challenge_method=S256`, authorization/token `resource`와 callback 일치, 실제 두 계정의 web/MCP 동일 subject/격리, 발급 토큰 만료/refresh/revoke/키 교체와 차단 지연, 운영 비용·처리 리전·계약·지원. PoC 성공을 공급자 채택으로 해석하지 않음 |
| G-L | 명시 입력만 받는 결정적 bullet/span 계약과 권한 필드 거부 | 합성 한국어 ≥30문장으로 수치/주체/부정/모순/민감정보/JD 무근거 평가. 모델·API·리전·설정별 보관/학습/삭제/하위 처리자/해외 이전 조건과 승인된 합격선·비용 한도. 실제 모델 시험/선정 없음 |
| G-P | 이번 로컬 retention/erasure/restore suite 및 224개 통과 | 전체 운영 저장 대상 inventory·외부 처리자 삭제·실제 backup 복원·legal 검토와 공개 삭제 약속 승인 |
| G-C | 루프백 DB/migration/합성 factory 검증 | AWS 계정·예산·서울 배치/네트워크·개인정보·자원 생성 권한. 유료/운영 구축 미승인 |
| G-K | 기존 ES256/package fixture 검증 | KMS/JWKS 실제 연동, rotation·긴급 `kid` 철회 및 package 발급/시작 race 구현·검증 |
| G-V | 기존 voice 정책/state fixture | 한국어 ASR/음성 품질, captions/text fallback, stop/끊김·복귀, 전사 확인/수정, 보관·삭제·계약·비용. 음성 연결 미승인 |

공급자 요금·명세·약관의 새로운 판단은 수행하지 않았다. 위 표는 기존
[평가 기록](CareerGround_Provider_Evaluation_Gates_v0.1_2026-09-23.md)의 증거와
이번 로컬 결과를 구분한 것이다. 실제 후보 평가를 재개할 때 최신 공식 자료와
계약/계정별 설정을 확인해야 한다.

후속 순서는 (1) 남은 Phase A 로컬/공개 계약·접근성·운영 안전 항목,
(2) 승인된 범위의 G-I 실제 외부 증거 및 G-L 합성 공급자 평가,
(3) G-P/G-C와 공개 진입점·운영 erasure 준비,
(4) A 통과 후 Phase B package/서명/handoff와 G-K,
(5) B와 G-V 통과 후 Phase C 음성 베타다. G-V 미결은 A/B의 로컬 개발을 막지 않는다.

현재 사용자 지시가 외부 연결을 금지하므로 이 세션에서는 공급자 최종 선택을
요청하거나 외부 검증을 실행하지 않는다. 그 작업을 선택하는 다음 세션의 첫
승인 지점은 **G-I 남은 개발용 인증 증거 수집 범위**다. 범위는 CareerGround
제품 데이터 없이 실제 인증 계정 2개, PKCE·토큰 생명주기 증거에 한정하고 비용
또는 운영 변경이 필요하면 그 직전 별도 결정한다. 승인 전까지 local-only를 유지한다.

## 최종 상태

- E05-S02: 문서 없는 합성 로컬 여정 증거 확보. 전체 접근성/실제 제품 UX 미완료.
- E05-S01: 공통 workspace 결과·거부 비교와 기존 owner/scope 테스트 통과. 전체 Plugin 계약·공개 승인/삭제/MCP parity 미완료.
- E08-S01: 이번 로컬 검증 완료. 운영 감사/rate limit/로그·메트릭/실제 restore·개인정보 게이트 미완료.
- **Gate A 공개/운영 출시는 미승인·미완료. Phase B/C 준비 완료로 해석하지 않는다.**
- 컨테이너 종료: 사용자 `sudo docker stop careerground-phase-a-test` 성공 응답 확인. 이후 55432 포트가 닫힌 것을 직접 확인했다. 생성한 임시 자격증명 파일/디렉터리도 제거했다.
- 최종 `git diff --check` 통과. 보존한 초안 20개의 SHA-256 비교는 모두 일치했다. 작업 트리 변경은 코드·테스트·CI·계획/문서이며 stage/commit/push하지 않았다.

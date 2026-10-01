# Phase A 로컬 보안·브라우저 접근성·MCP 계약 보강

> 이 문서는 앞선 232개 테스트/0016/13개 도구 시점의 기록이다. 정기 정리·승인 연계·19개 도구·Firefox/확대/Orca 후속은 [최신 로컬 closeout](CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md)을 따른다.

- 작업 시작: 2026-09-30, 검증 기록: 2026-10-01 (Asia/Seoul)
- 기준: `codex/mvp-foundation-ci-20260923`, HEAD `061b371be0620adeac6f76b0fa6b70eefd36ab99`
- 사용자 요청: 이전 인계 후 권장한 세 가지 로컬 후속 작업을 자율 수행. 커밋·푸시·공개 마운트·운영 서비스·실사용자 데이터·외부 AI 연결은 하지 않는다.
- 앞선 224개 테스트/0015 검증은 [이전 기록](CareerGround_Phase_A_Local_Validation_2026-09-30.md)이다. 아래 변경에는 새 migration이 필요하다.

## 1. E08-T02 로컬 보안

### 예외와 로그

- Web 팩토리의 HTTP 경계에서 예상하지 못한 예외를 한국어 500 화면으로 변환한다. DB bind·요청 원문·토큰·stack을 응답 또는 자체 이벤트 로그에 넣지 않는다. 예상하지 못한 장애는 commit 여부를 단정하지 않고 현재 상태를 확인하도록 안내한다.
- FastAPI 자료형 검증 실패는 제출값을 복사하는 기본 422 응답 대신 정해진 400 안내를 반환한다. MCP는 SDK 입력 변환 전 필드/자료형을 검사하고 SDK 예외도 안전한 공통 오류로 변환한다.
- DB 엔진과 온라인 Alembic 엔진은 `hide_parameters=True`다. 이것은 SQL bind의 예외 문자열 노출을 막는 조치이며 DB 암호화 구현을 뜻하지 않는다.
- 자체 로그는 `request_result adapter=web|mcp result=<허용된 코드>`만 기록한다. 계정 ID, 대상 ID, 원문, token, traceback을 넣지 않는다. 외부 서버/proxy/access logger의 설정까지 이 모듈이 제어하지는 않는다. 실제 브라우저 검증 서버는 access log를 끈다. 공개 마운트 전 URL/query/body/header를 수집하는 인프라 로그도 별도 검토해야 한다.

### 공유 요청 제한

`request_limit_buckets`는 migration `20260930_0016`에서 추가한다.

| 필드 | 내용 |
| --- | --- |
| `bucket_key` | account와 read/write lane에 대해 서버 비밀로 만든 HMAC-SHA256. 원문 계정 ID/토큰/입력은 저장하지 않음 |
| `window_start` | Unix 초 단위 고정 창의 시작, 복합 PK |
| `requests` | 승인된 예약 수, 1 이상 |
| `expires_at` | 창 종료 시각, 정리용 인덱스 |

동일 DB·비밀·정책을 사용하는 Web/MCP 팩토리가 카운터를 공유한다. 한 계정의 새 브라우저 세션/토큰이나 새 팩토리로 제한을 우회할 수 없다. 다른 계정과 read/write lane은 독립적이다. 기본값은 60초 창당 read 120/write 60이며 팩토리에 `RequestLimitPolicy`를 주입해 테스트한다. SQL `INSERT ... ON CONFLICT ... WHERE requests < limit RETURNING`으로 예약을 원자적으로 제한한다. SQLite와 PostgreSQL을 지원한다.

- 초과: domain 명령 전 차단, Web/MCP HTTP 429와 양수 `Retry-After`. MCP 오류에도 `retry_after_seconds`를 넣는다.
- 카운터 저장소 장애: domain 실행을 허용하지 않는다. Web 503, MCP 안전한 `INTERNAL_ERROR`. 인증 저장소 자체 장애는 먼저 OAuth 계층에서 차단될 수 있다.
- 검증 전 잘못된 MCP scope/필드는 쓰기 예약을 만들지 않는다. 인증된 정상 형태의 요청은 대상 부재/도메인 실패/재시도에도 예약을 소비한다. Web은 신뢰된 identity 뒤 GET/HEAD를 read, 그 외를 write로 계산한다.
- 만료 카운터는 다음 예약 시 삭제한다. 무요청 상태에서 물리적 삭제를 보장하는 정기 worker는 아직 없다. HMAC도 가명 식별 메타데이터로 취급하며 운영 TTL/삭제 정책을 정해야 한다.
- 고정 창 경계의 순간 burst, 인증 전 IP/네트워크 차단, ingress body/time 한도, 비밀 교체 시 카운터 초기화, 장애·과부하 관측/운영 임계값은 후속 운영 게이트다. 현재 숫자를 운영 안전성 검증으로 해석하지 않는다.

`test_adapter_security.py`는 두 팩토리의 quota 공유/타 계정 독립성, 초과 시 쓰기 없음, 잘못된 scope, SQL 예외에 포함된 민감값 비노출, 저장소 장애를 확인한다. 별도 24개 예약/8개 thread 경합은 한 창에서 정확히 5개만 승인되는지 SQLite와 PostgreSQL로 확인한다.

## 2. 실제 Chrome 브라우저와 접근성

재현 명령:

```bash
uv sync --locked --group dev
# Chrome이 설치돼 있지 않은 환경에서만 필요:
uv run --locked playwright install chromium
uv run --locked python scripts/run_local_browser_checks.py --output-dir /tmp/careerground-browser-checks
```

스크립트는 임시 SQLite DB·합성 계정 하나·빈 v0 프로필, 임의 루프백 포트, 새 브라우저 context만 쓴다. 실제 로그인/기존 브라우저 프로필/프로젝트 DB 설정을 읽지 않는다. 다른 host 요청은 차단하고 발견 시 실패한다. 실행 후 서버/브라우저/임시 DB를 종료·정리하고 합성 report/스크린샷/Markdown만 지정 출력 폴더에 남긴다.

실제 Chrome **150.0.7871.46**에서 **359개 assertion 통과**, 외부 페이지 요청 0건:

- Tab으로 첫 skip link 도달, Enter로 main에 초점 이동, 모든 사용한 제어의 보이는 focus.
- Tab/Space/Enter/ArrowDown만으로 시작→직접 글머리표→초안 준비→사실 ACCEPT→별도 사용 검토→JD 발췌→잠재 연결→R1 선택→문구 검토→Markdown 다운로드. 입력은 키보드 text 삽입을 쓴다. Playwright click/fill/select_option으로 폼을 대신 조작하지 않는다.
- 미확인 필수 checkbox는 네이티브 폼 검증으로 제출을 막는다. 사실 승인 후 `USER_CONFIRMED/REVIEW_REQUIRED`, 별도 사용 journal과 v2, 승인된 원문만 들어간 정확한 다운로드를 확인한다.
- 각 여정 화면의 `lang=ko`, 단일 h1/main, Chromium accessibility tree의 main과 form control 이름을 확인한다.
- 여정 화면마다 320 CSS px/640 CSS px(1280 창의 200% 확대에 대응하는 layout)/실제 200% font-size에서 페이지 가로 넘침이 없는지 확인한다. main 최대 폭, 긴 ID 줄바꿈, 폼 폭 제한, 3px focus outline을 추가했다. 고정 CSS의 SHA-256만 CSP에서 허용한다.
- 400 오류에서 alert와 main 자동 초점, 키보드로 시작 화면 복귀를 확인한다. 모바일/R1 화면 스크린샷을 시각적으로 점검했다.

결과 파일: `/tmp/careerground-browser-checks-20261001/report.json`, `trace-desktop.png`, `trace-mobile.png`, `trace-large-text.png`, `synthetic-resume.md`.

이 검증은 실제 Chromium DOM/accessibility tree/키보드와 reflow 검사다. 음성 화면낭독기, 네이티브 브라우저 UI 확대, 전체 WCAG 감사, 다른 브라우저/기기 검증까지 완료했다고 주장하지 않는다. CI에는 브라우저 설치와 같은 합성 스크립트 실행을 추가했으며 원격 CI 실행은 아직 하지 않았다.

## 3. MCP 계약

### 현재 wire 응답

합성 제품 팩토리 13개 도구 모두 `structuredContent`와 text content에 같은 JSON을 반환한다.

```json
{"status":"ok","data":{"...":"tool-specific DTO"},"next_actions":[],"user_message":"요청이 처리됐습니다."}
```

```json
{"status":"error","error":{"code":"NOT_FOUND","message":"요청한 내용을 찾을 수 없습니다.","recoverable":false,"next_action":"CHECK_CURRENT_STATE","retry_after_seconds":null}}
```

기존 DTO의 `ok=false/error_code`, `found=false`는 안전한 공통 오류로 변환하고 `isError=true`로 표시한다. 기존 도구별 성공 DTO는 `data` 안으로 이동했으므로 이전 로컬 소비자도 그 위치를 사용해야 한다. `IDEMPOTENCY_CONFLICT`는 `VALIDATION_FAILED`, `REVIEW_STALE`는 `VERSION_CONFLICT`로 매핑한다. 인증 실패 HTTP 401/challenge는 OAuth 계층의 계약을 유지한다. 기능 오류는 MCP 결과 envelope로 반환하며, quota 오류만 HTTP 429/Retry-After도 반환한다.

`tools/list`의 input schema는 unknown field를 허용하지 않고, output schema는 해당 도구의 정확한 성공 DTO와 공통 error의 `oneOf`를 광고한다. 13개 스키마 검증, 실제 오류 응답 검증, 반복 목록에서 스키마가 중첩되지 않는지, 대표 실제 성공 응답과 text/structured 일치를 테스트한다. 도구별 owner/version/source 비공개 테스트와 Web workspace 결과 비교도 유지한다.

### 새 읽기 전용 삭제 미리보기

`preview_data_deletion(scope="ACCOUNT"|"PROFILE", target_ids=["정확한 소유 ID 하나"])`를 `career.delete` scope로 추가했다. 같은 domain preview로 Web과 항목 수를 비교한다. 성공 데이터는 `coverage="FOUNDATION_ONLY"`, `ready_to_execute=false`, `counts`다. digest·step-up·삭제 실행/요청 생성은 제공하지 않는다. 타 계정/없는 대상은 `NOT_FOUND`, 다른 범위/여러 ID는 `VALIDATION_FAILED`다. 전체 Plugin v1의 삭제 미리보기 계약을 완료한 것은 아니다.

### 아직 없는 Phase A MCP 도구 10개

목표 21개 중 이름이 대응하는 도구 11개와 보조 읽기 2개, 총 13개다. 이름 대응도 목표의 전체 입출력/의미 구현 완료를 뜻하지 않는다.

| 미구현 도구 | 현재 근거와 필요한 조건 |
| --- | --- |
| `submit_claim_review` | Web 사실 검토 존재. 브라우저 세션/digest/버전에 묶인 실제 사용자 승인 증명을 MCP에서 안전하게 소비하는 연계 필요 |
| `resolve_claim_conflict` | 합성 domain journal/검증 존재. 정확한 모순 표시·별도 확인·승인 UI 연계 필요 |
| `review_boundary_change` | 합성 domain journal/검증 존재. 현재/변경 경계·근거 표시와 별도 승인 UI 연계 필요 |
| `export_profile_data` | Web 명시 JSON 다운로드 존재. MCP scope/동의와 artifact resource·보존/삭제 계약 필요 |
| `analyze_jd` | Web 선택 글머리표 발췌만 존재. 명시 입력/동의 연계와 의미 분석의 공급자·처리 정책 G-L 필요 |
| `generate_resume_draft` | Web 적격 정확 문구의 R1 선택 존재. MCP 사용자 선택/버전 연계와 R2/R3 의미 생성 정책 후속 |
| `submit_resume_wording_review` | Web 정확 문구 승인 존재. 모델 요청과 실제 사용자 확인을 구분하는 증명 연계 필요 |
| `export_resume` | Web 검토된 R1 JSON/Markdown 다운로드 존재. MCP 명시 동의·resource·만료/삭제 계약 필요 |
| `execute_data_deletion` | 로컬 삭제 worker 존재. 완전 영향 digest·신뢰된 step-up·외부 제공자/파일/백업 경계 필요 |
| `get_deletion_status` | 로컬 요청/worker 상태 존재. 공개 범주/재시도·운영 외부 삭제 상태를 확정해야 함 |

모델이 임의의 approval 문자열을 보내는 것으로 위 조건을 만족시키지 않는다. 현재 브라우저 확인 토큰의 계정·세션·정확한 표시 내용·버전 결합을 유지했다. 공개 승인 연계·외부 공급자·운영 정책 결정은 이번 로컬 권한 밖이다.

## 4. 검증 결과

| 항목 | 실행 결과 |
| --- | --- |
| DB URL 없는 전체 unittest | **232개 중 225 pass, PostgreSQL 7 skip**, 실패 0 |
| 실제 Chrome 합성 검사 | **359 assertion pass**, 외부 페이지 요청 0 |
| CI 범위 Ruff check/format | **108개 파일**, check/format 통과 |
| PostgreSQL 17 빈 DB `0016` upgrade/check/downgrade/reapply | PostgreSQL **17.11**, 빈 DB `0016` 적용/check → `0015` downgrade → `0016` 재적용/check 통과 |
| required-PostgreSQL 전체 suite/종료 DB 상태 | **232 pass, 실패/skip 0**; revision `20260930_0016`, 제품 테이블 **36개 모두 0행** |
| 검증 자원 정리 | 사용자가 `--rm` 컨테이너 중지, 루프백 55432 닫힘 확인, 생성한 임시 비밀번호 파일 삭제 |

전체 Gate A/운영 보안 검토의 완료로 바꾸지 않는다. 다음 운영 전 작업은 승인 UI–MCP 증명 연계, 실제 화면낭독기/다중 기기 감사, rate counter 물리 TTL/ingress/부하·장애 운영 기준, G-I/G-L/G-C/G-K/G-V/G-P의 미결 조건이다.

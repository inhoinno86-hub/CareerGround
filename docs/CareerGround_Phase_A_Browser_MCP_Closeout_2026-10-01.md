# Phase A 후속 1–4 로컬 구현·검증

> 이 문서는 0017/258개 검증 당시 기록이다. 후속 0019/295개 구현과 현재 wire는 [모순·경계·선택 JD/R1 보강 기록](CareerGround_Phase_A_Review_JD_Hardening_2026-10-01.md)을 따른다.

- 날짜: 2026-10-01 (Asia/Seoul)
- 사용자 승인: 권장 순서 1–4 전부, 안전한 로컬 작업 자율 수행.
- 기준: `codex/mvp-foundation-ci-20260923`, HEAD `061b371be0620adeac6f76b0fa6b70eefd36ab99` 유지.
- 이전 [232개 테스트/0016 기록](CareerGround_Phase_A_Security_Accessibility_Contracts_2026-10-01.md)을 이어서 수행했다. 기존 변경과 무시된 초안은 보존한다.
- 실제 사용자 데이터, 운영 연결, 외부 AI, 유료 자원, 공개 제품 마운트, 커밋·푸시는 사용하지 않았다. 아래 결과는 합성 팩토리의 로컬 검증이다.

## 1. 무요청 상태의 정리와 안전한 집계

`workers/request_limit_maintenance.py`는 요청 발생과 독립적으로 만료 카운터를 물리 삭제한다. SQLite는 단일 DELETE/subquery, PostgreSQL은 `FOR UPDATE SKIP LOCKED`로 경쟁 작업자를 처리한다. 배치 최대 500개, 한 주기 최대 20배치이며 작은 배치마다 commit한다. 실패한 배치는 rollback하고 DB 예외·행 키를 반환하거나 로그에 쓰지 않는다. 성공한 앞선 배치를 되돌렸다고 주장하지 않는다.

`workers/local_security_maintenance.py`는 카운터와 새 승인 메타데이터의 만료 정리를 함께 실행한다. 실행 횟수 1–24, 간격 1–3,600초의 유한 일정이다. API 호출·운영 cron 등록·상주 daemon이 필요하지 않다. 기존 요청에 의존한 만료 정리도 유지한다.

```bash
# 별도로 준비한 loopback *_test DB와 CAREERGROUND_TEST_DATABASE_URL이 있을 때만:
uv run python -m careerground.workers.local_security_maintenance --cycles 2 --interval-seconds 60
```

CLI는 `postgresql+psycopg`, `127.0.0.1`/`localhost`, `_test` DB 이름을 검사한다. 운영 DB 또는 원격 DB용 명령이 아니다. 이번 실제 PostgreSQL 검사에서는 이미 만료된 합성 카운터/승인 요청 각 1개를 넣고 API 요청 없이 1초 간격 두 주기를 실행했다. 각각 1개가 삭제됐고 canonical 프로필 버전은 그대로였다. 별도 통합 테스트는 가상 시계가 진행되는 동안 유효 항목이 만료되는 경우도 확인한다.

`domain/safe_events.py`의 집계는 Web/MCP와 허용된 결과 코드, 정리 성공/실패 및 삭제 수만 기록한다. 원문·계정·대상·토큰 label을 받지 않는다. 잠금으로 thread 경쟁을 처리하고 64비트 범위에서 포화하며, snapshot은 복사본이다. Web 성공/오류와 MCP 도구·resource 결과를 집계한다. 집계는 프로세스별 메모리 상태이고 공개 metrics endpoint가 없다. 여러 프로세스의 합계, 운영 임계값·보존 정책·ingress 제한·부하 시험은 후속 운영 게이트다. strict 입력 검증에서 거부한 MCP 호출은 domain quota를 소비하지 않는다.

## 2. 브라우저 직접 확인 → MCP 완료 증명

모델 요청은 `WAITING` 확인 요청만 만든다. 승인 토큰, 사용자 결정, canonical 변경을 만들지 않는다.

1. MCP `request_user_confirmation`에 작업·정확한 대상/프로필 버전·형식·재시도 키를 전달한다. 작업에 맞는 scope를 quota 예약 전에 검사한다.
2. 사용자가 같은 계정의 신뢰된 브라우저에서 `/mcp/confirm/{request_id}`를 연다. 기존 사실/문구/내보내기 서비스를 재사용하여 정확한 내용을 표시한다. 연결 앱 식별자, 작업, UTC 만료 시각도 표시한다.
3. 사용자가 기존 작업 확인과 **연결 앱이 결과를 받도록 허용**하는 별도 필수 체크를 한다. 사실 검토는 항목별 결정도 요구한다.
4. 브라우저 POST가 계정·브라우저 세션·대상·작업·정확한 내용/버전·기한에 묶인 서명 토큰을 검사한다. 기존 domain 명령과 완료 메타데이터를 **같은 transaction**에 저장한다.
5. 브라우저에서만 짧은 완료 증명을 보여준다. MCP 제출/내보내기 도구는 이 증명을 소비해 **이미 브라우저에서 완료한 결과**를 반환한다. MCP가 별도 canonical mutation을 실행하지 않는다.

사실 ACCEPT는 `USER_CONFIRMED`만 기록한다. 기존 별도 Claim 사용 검토의 두 독립 확인이 있어야 `CONSISTENT/ALLOWED`가 된다. 사실·문구 승인으로 사용 경계나 충돌을 자동 승인하지 않는다.

완료 증명은 계정, issuer/subject/client, **정확한 검증 OAuth access token의 HMAC**, 브라우저 세션, 요청/대상/작업에 결합한다. raw JWT/브라우저 토큰/증명은 DB에 저장하지 않는다. 최대 5분 요청 기한과 기존 화면 토큰의 더 짧은 기한을 함께 적용한다. 같은 증명 소비는 같은 결과를 반환한다. 브라우저 재전송도 동일 토큰·결정인 경우에만 같은 완료 결과를 반환하며, 동시 승인 네 건은 canonical 변경 한 건으로 수렴한다.

토큰이 갱신되면 같은 client라도 이전 증명을 사용할 수 없다. 브라우저에서 이미 완료된 사실 승인은 현재 프로필 읽기와 브라우저 완료 화면으로 상태를 회복한다. 오래된 batch를 새 토큰으로 다시 승인하도록 안내하지 않는다. 아직 수행하지 않은 작업/새 내보내기는 현재 버전을 조회한 뒤 새 확인 요청을 만든다. 이는 운영 공급자의 연결별 철회 구현을 대체하지 않는다.

브라우저 폼은 CSRF 방어로 서명된 브라우저 세션 토큰과 제출 형식/크기/필드 수를 검사하며 다른 Origin/fetch-site를 거부한다. `no-referrer` 정책의 로컬 HTTP 네이티브 폼이 `Origin: null`을 보내므로, **HTTP + loopback hostname**의 합성 경로에서만 이를 허용한다. HTTPS/다른 hostname의 null과 타 origin은 거부한다. 공개 제품 경로는 만들지 않았다.

### migration 0017

`browser_operations`가 추가되어 제품 테이블은 37개다.

| 필드 | 용도 |
| --- | --- |
| `id`, `account_id`, `profile_id` | 요청 ID와 소유 프로필 복합 FK; 프로필 삭제 시 CASCADE |
| `connection_key`, `request_key` | 정확한 OAuth 연결/재시도 HMAC, 요청 키 unique |
| `client_id` | 브라우저에서 결과를 받을 앱 식별자로 표시, HTML escape |
| `action`, `target_id`, `profile_version`, `format` | 확인 대상의 정확한 범위 |
| `status` | `WAITING` → `DONE` → `CONSUMED` |
| `browser_key`, `confirmation_key` | 완료한 세션과 정확한 서명 토큰/결정의 HMAC |
| `result_json` | 결과 ID/version/형식/hash/bytes/resource URI 등 메타데이터만; 원문 없음 |
| `created_at`, `expires_at`, `consumed_at` | 짧은 만료/소비 기록, 만료 인덱스 |

DB 제약은 허용 action/format/status, 비음수 버전, 만료 순서와 완료 상태의 필수 HMAC/결과를 검사한다. 삭제 미리보기와 내부 로컬 erasure 순서에도 이 테이블을 포함했다. 유지보수는 만료된 요청·완료 증명을 동일하게 삭제한다. HMAC/앱 식별자/메타데이터도 운영에서는 개인정보 보존·비밀 교체 정책의 대상이다.

## 3. MCP 계약 확대와 남은 차이

합성 팩토리는 총 **19개** 도구다. 목표 Phase A 21개 중 이름이 대응하는 16개, 보조 3개다. 각 도구는 정확한 input schema, 공통 success/error envelope 및 실제 output schema를 유지한다. OAuth 실패는 HTTP 401, 도구 quota는 HTTP 429/Retry-After, 승인 증명 실패는 안전한 `REVIEW_REQUIRED`다.

| 추가 도구 | 실제 scope/입력 | 로컬 동작 |
| --- | --- | --- |
| `request_user_confirmation` (보조) | action별 `career.profile.write` / `career.artifact.write` / `career.export`; action,target,version,format,idempotency key | 확인 요청/브라우저 경로/만료만 반환 |
| `submit_claim_review` | `career.profile.write`; batch ID, approval receipt | 브라우저 완료 결과의 profile/version 반환 |
| `submit_resume_wording_review` | `career.artifact.write`; artifact ID, approval receipt | 브라우저 완료 review/artifact version 반환 |
| `export_profile_data` | `career.export`; profile ID/version, JSON, approval receipt | 짧은 private resource와 hash/크기 반환 |
| `export_resume` | `career.export`; artifact ID, JSON/MARKDOWN, approval receipt | 검토된 R1 private resource와 hash/크기 반환 |
| `get_deletion_status` | `career.delete`; erasure request ID | 로컬 처리 집계만 반환 |

이는 Plugin v1의 모든 필드를 그대로 구현한 완료 계약이 아니다. 원래 사실/문구 제출의 상세 결정·digest/token은 **브라우저에서 처리**하고 MCP는 결과 증명을 소비한다. 프로필 export는 정확한 정수 version/JSON, 이력서는 R1만 지원한다. 포함 선택/CURRENT/R2/R3/범주별 운영 재시도 계약과 공개 제품 통합은 남아 있다. [목표 계약 표](mvp_implementation_contract_matrix_v0.1.md)는 목표를 유지하며 이 실제 wire 차이를 연결한다.

### 인증된 export resource

`careerground://exports/{request_id}`는 도구 목록과 별도로 `resources/read`에서 읽는다. `career.export`, 원래 계정/client/정확한 access token, `CONSUMED` 상태, 짧은 만료, 현재 활성 계정/프로필, 정확한 archive/근거 적격성과 hash를 **매 읽기** 재검사한다. 원문 파일을 DB나 공개 URL에 복제하지 않고 기존 domain export를 다시 생성한다. resource 읽기도 공유 read quota를 소비한다. 다른 계정/client/scope/token, 미소비/만료/삭제 중 대상은 자료를 반환하지 않는다. resource 실패는 MCP resource 오류로 처리하며 도구 success/error envelope 또는 HTTP Retry-After 계약으로 광고하지 않는다.

### 부분 삭제 상태

`get_deletion_status`는 활성 계정 소유 요청에만 허용한다. `coverage=FOUNDATION_ONLY`, `ready_to_execute=false`, 로컬 ERASE 완료 수·미완료/실패 수·미검증 수를 SQL 집계로 반환한다. 작업의 대상 ID를 모두 메모리에 읽지 않고 SQL로 집계한다. 대상 ID, impact digest, 저장소 정보, 오류 상세를 반환하지 않는다. 실제 외부·공급자·백업 완료를 인증하지 않으므로 저장된 로컬 `ERASED`도 응답에서는 `DELETING`이다. 전체 완료 상태를 광고하지 않는다.

**계정 자체가 DELETING/ERASED이면 활성 계정 인증에서 401로 차단**되어 이 도구로 계정 삭제를 계속 polling할 수 없다. 삭제 이후 인증/별도 상태 조회의 제품 계약은 운영 게이트다. 계정 인증을 완화하지 않았고 삭제 실행 도구도 노출하지 않았다.

남은 Phase A 이름은 `resolve_claim_conflict`, `review_boundary_change`, `analyze_jd`, `generate_resume_draft`, `execute_data_deletion` 다섯 개다. 명시적 모순/경계 확인 UI, 선택/버전 연계, 의미 분석·R2/R3 공급자/처리 정책, 완전 삭제 영향·step-up·외부/백업 계약이 필요하다. 전체 Gate A가 완료된 것은 아니다.

## 4. 브라우저·확대·실제 화면낭독기

| 검사 | 증거 |
| --- | --- |
| Firefox 155 기존 전체 합성 여정 | 383 checks, 외부 요청 0 |
| Chrome 150 브라우저 UI의 실제 200% 확대 | 361 checks; private Xvfb/XTest 키 입력 후 DPR 1→2, innerWidth 1280→640 |
| Chrome 새 승인 → MCP 결과/resource | 53 checks; 사실/문구/프로필·R1 export 네 경로, 외부 요청 0 |
| Firefox 새 승인 → MCP 결과/resource | 53 checks; 같은 네 경로, 외부 요청 0 |
| 실제 Orca 50.1.2 + Chrome 150 | 11 checks; 시작·skip link·키보드 동의·workspace·오류 복구, 합성 발화 요청 28개 |

새 승인 폼은 실제 Tab/ArrowDown/Space/Enter로 확인했다. 언어/main/h1, 연결 앱 구역과 필수 체크의 접근성 이름을 확인하고 완료 증명을 실제 MCP에 제출한 뒤 private resource를 읽었다. 새 MCP 성공/오류도 광고한 JSON Schema로 검증한다. 증명/토큰을 report에 남기지 않는다.

Orca는 임시 D-Bus/AT-SPI/Xvfb/XDG 프로필과 dummy Speech Dispatcher backend에서 실행했다. 실제 Orca가 생성한 speech request를 확인했으며 **사람이 들은 한국어 발음·음질·전체 여정 이해도 감사는 하지 않았다**. 기존 데스크톱 프로필/설정/오디오를 수집하거나 바꾸지 않았다. 전체 WCAG 감사, 다른 기기/OS, 실제 사용자 접근성 검증은 남아 있다.

재현:

```bash
uv run playwright install chromium firefox
uv run python scripts/run_local_browser_checks.py --browser firefox --output-dir /tmp/cg-firefox
env -u WAYLAND_DISPLAY XDG_SESSION_TYPE=x11 xvfb-run -a uv run python scripts/run_local_browser_checks.py --native-zoom --output-dir /tmp/cg-zoom
uv run python scripts/run_local_confirmation_browser_checks.py --output-dir /tmp/cg-confirm-chrome
uv run python scripts/run_local_confirmation_browser_checks.py --browser firefox --output-dir /tmp/cg-confirm-firefox
uv run python scripts/run_local_screenreader_checks.py --output-dir /tmp/cg-orca
```

CI 파일에는 새 테스트/검증 스크립트 Ruff 검사, Chromium/Firefox 설치와 실제 브라우저 여정·새 승인 경로 실행을 추가했다. 네이티브 확대와 Orca는 위 로컬 재현으로 검증했으며 CI에 추가하지 않았다. 원격 CI는 실행하지 않았다.

## 5. 최종 검증과 정리

PostgreSQL 17.11을 `/tmp`에 사용자 권한으로 임시 빌드하여 루프백 52127의 새 `careerground_test`에만 연결했다. Docker/sudo·운영 볼륨을 사용하지 않았다. [공식 source/checksum](https://ftp.postgresql.org/pub/source/v17.11/)과 [공식 build 절차](https://www.postgresql.org/docs/17/install-make.html)를 사용했고 전역 설치는 하지 않았다.

- 빈 DB `0017` upgrade/check → `0016` downgrade → `0017` 재적용/check 통과.
- `CAREERGROUND_REQUIRE_POSTGRES_TEST=1` 전체 **258개 통과, 실패/skip 0**. CI 범위 Ruff check/format **117개 파일 통과**.
- 승인 위조·다른 계정/client/session/token·scope·형식·버전·만료·origin·동시/재전송, 삭제 중 export, 잘못된 권한 요청의 쓰기 quota 비소비를 확인했다.
- 제품 테이블 **37개 전부 0행**, revision `20261001_0017` 확인 후 `pg_ctl`로 정상 종료. 루프백 52127 닫힘, 비밀번호/URL 파일과 생성 cluster/source/install 삭제 완료. private Xvfb/Orca/Speech Dispatcher/브라우저 검사 서버도 종료됐다. 기존 사용자 프로세스는 건드리지 않았다.
- 무시된 `to-do-prompts/`·`intent-docs/` **20개 기존 해시 전부 일치**, `git diff --check` 통과. HEAD와 branch 유지, 커밋·푸시 없음.

현재 1–4 로컬 구현의 종료와 공개 출시/운영 승인은 서로 다른 상태다. 공급자·실제 사용자·유료 자원·공개 제품·커밋·푸시는 별도 사용자 요청이 필요하다.

로컬 증거 파일 (임시 파일이므로 이후 지워질 수 있음):

- `/tmp/careerground-final-validation-20261001-{0,1,2,3}.log`: CI Ruff/check/전체 suite.
- `/tmp/careerground-validation-20261001-{0,1,2,3,4}.log`: upgrade/check/rollback/reapply/check.
- `/tmp/careerground-pg-idle-validation-20261001.json`, `/tmp/careerground-final-cleanup-20261001.json`: 무요청 정리·빈 DB·종료 증거.
- `/tmp/careerground-firefox-checks-20261001/report.json`, `/tmp/careerground-native-zoom-checks-20261001/report.json`: 기존 전체 브라우저 여정.
- `/tmp/careerground-confirmation-{chrome,firefox}-20261001/report.json`: 새 승인 경로, 각각 53 checks.
- `/tmp/careerground-orca-checks-20261001/screenreader-report.json`: 실제 Orca 발화 요청 검사.

완료 상태: 사용자 요청 1–4의 **안전한 로컬 구현·검증 완료**. 공개/운영 Gate A, 한국어 청취·실사용자 접근성 감사와 명시된 공급자/삭제 계약은 미완료다.

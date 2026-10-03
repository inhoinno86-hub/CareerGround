# Phase A 로컬 계약 1→2→3 구현 및 검증 이력

기준 브랜치 `codex/mvp-foundation-ci-20260923`, HEAD `2a6cdd25e266e29216d44946a0cd2c6bf1306a5a`.
기존 미커밋 변경 위에서 사용자가 승인한 1→2→3을 구현했다. 커밋·푸시는 하지 않았다.
이 문서의 현재 상태가 10월 2일 문서의 남은 로컬 계약 목록을 갱신한다.

## 1. CURRENT와 내보내기 포함 항목

- `get_career_profile`과 프로필 내보내기 승인 요청에 정확한 정수 또는 명시적 `CURRENT`를 받는다. 다른 문자열·숫자 변환·임의 필드는 거부한다.
- CURRENT 승인 요청을 생성할 때 숫자 버전을 고정한다. 승인 전에 현재 버전이 바뀌면 거부한다. 승인 후 재시도는 고정한 숫자를 유지하며 최신 버전으로 바꾸지 않는다.
- 포함 항목은 경력 사실, 선택 근거 발췌, 사용 경계, 미승인 임시 초안, 불가 원문 참조 metadata의 다섯 가지다. 기본값은 초안 제외다. 명시적 객체는 다섯 bool 필드를 모두 요구한다.
- 옵션과 버전을 승인 토큰·요청 재시도·같은 연결의 receipt·내용 hash에 묶었다. 잘못된 옵션이나 다른 OAuth 연결은 승인 결과를 받을 수 없다.
- 초안을 포함하면 살아 있는 현재 프로필의 임시 초안만 `UNAPPROVED`로 출력한다. 만료된 원문·삭제 payload·전체 대화를 복원하지 않는다. 초안 만료 등으로 내용 hash가 달라지면 이미 발급한 리소스도 실패한다.

합성 MCP 콘솔 예시:

```json
{"action":"PROFILE_EXPORT","target_id":"demo-profile-a","profile_version":"CURRENT","format":"JSON","idempotency_key":"synthetic_selected_export_0001","inclusion":{"claims":true,"evidence":true,"boundaries":true,"drafts":false,"unavailable_references":true}}
```

`request_user_confirmation` 결과의 `confirmation_path`를 열어 정확한 버전·포함 목록·연결 앱을 확인한다. 브라우저 승인 후 같은 콘솔의 `export_profile_data`에 `profile_id`, `profile_version`, `format`, `approval_receipt`, 동일한 `inclusion`을 전달한다. 짧은 인증 리소스만 반환하며 공개 다운로드 주소를 만들지 않는다.

Web에서는 홈의 **프로필 내보내기 범위 선택**을 사용한다. `/profile/demo-profile-a/export-options/CURRENT`에서 체크한 범위를 다음 화면에서 확인하고 다운로드를 승인한다.

## 2. 별도 R2 저장·내보내기와 R3 분리

1. 적격 Claim과 SUPPORTS 근거를 가진 현재 R1의 추적 화면에서 **R2 문구 제안**으로 이동한다.
2. 원본 R1과 근거를 보며 표현을 수정하고 새 사실 포함 여부를 직접 선택한다.
3. 변경 전후 정확한 문구를 확인한다. 이 화면까지는 새 산출물을 저장하지 않는다.
4. 별도 체크와 승인으로 새 `WORDING_REVIEWED` R2를 저장한다. 원본 R1, Claim, Evidence와 프로필 버전은 보존한다.
5. 새 R2 추적 화면에서 JSON/Markdown 내보내기를 별도로 승인한다. MCP 내보내기도 기존 `RESUME_EXPORT` 브라우저 증명을 별도로 요구한다.

R2 artifact/unit은 원본 artifact/unit을 소유권 FK로 기록하고 정확 문구 승인 digest를 저장한다. 읽기와 내보내기에서 원본 계보, 현재 적격성, Claim/Evidence와 문구 hash를 재검사한다. 기존 검토된 R1에서도 제안할 수 있다.

현재 결정적 검사에서 허용하는 변경은 공백·문장 끝 구두점·제한된 같은 과거 시제 공손 표현이다. 역할·숫자·기간·성과·부정·불확실성 변화는 보수적으로 거부한다. 의미적 동등성이나 실제 모델 품질을 보증하지 않는다.

`R3_NEEDS_FACT_REVIEW`는 후보를 저장하거나 canonical 사실로 승격하지 않는다. 기존 **새 경력 정리 시작**으로 안내하고 사용자가 새 사실을 직접 입력·검토한다. 거부된 문구를 그 경로로 자동 전송하지 않는다. 외부 생성 모델은 연결하지 않았다.

## 3. SESSION·EVIDENCE·PROJECT 부분 삭제

ACCOUNT/PROFILE에 세 범위를 추가했다. SESSION은 소유 profiling session ID, EVIDENCE는 소유 EvidenceItem ID, PROJECT는 명시적으로 등록한 ProjectScope ID를 받는다. 임의 scope 문자열을 프로젝트 ID로 추측하지 않는다.

PROJECT는 홈의 **합성 프로젝트 범위 등록**에서 현재 소유 경력 범위를 직접 선택한다. 등록은 사실 승인이나 삭제 승인이 아니다. 삭제된 프로젝트 키의 재등록·초안 생성·검토 준비·최종 canonical 승격을 거부한다. 새로운 다른 범위는 사용할 수 있다.

공통 삭제 순서:

1. MCP `execute_data_deletion`에 정확한 `scope`, `target_id`, 현재 숫자 버전, 재시도 키, 빈 `approval_receipt`를 입력한다.
2. `confirmation_path`에서 관련 항목·영향 개수·추가로 지워지는 원문 세션 범위를 확인한다.
3. MOCK_ONLY 재인증 체크와 `합성 계정 A` 문구를 입력한다. 실제 비밀번호를 사용하지 않는다.
4. 최종 승인으로 receipt를 받는다. 브라우저 승인만으로 삭제하지 않는다.
5. 같은 MCP 연결에 나머지 인자를 유지하고 receipt를 전달해 실행한다.
6. 최소 상태는 `DELETING/FOUNDATION_ONLY`로 남는다. 운영 백업·외부 서비스의 삭제 완료를 주장하지 않는다.

EVIDENCE/PROJECT는 관련 원문을 남기지 않도록 연결된 raw session 전체와 그 세션의 source/evidence·초안·검토 묶음을 보수적으로 정리한다. 공유 세션이면 선택한 항목 외 임시 자료도 지워질 수 있으므로 미리보기에서 확장된 영향을 보여준다. 별개 원문 세션과 독립된 승인 Claim, B 계정은 유지한다.

유지된 Claim이 SUPPORTS를 잃으면 기존 사용 승인과 일관성 판정을 제거하고 새 버전에 `REVIEW_REQUIRED/NOT_EVALUATED` assessment를 기록한다. 과거 archive·영향받는 산출물·기존 receipt는 사용할 수 없게 한다. 안전한 새 archive를 만들며 과거 버전 요청에 현재 데이터를 대신 반환하지 않는다.

서명 ledger에는 부분 삭제의 profile ID와 삭제 후 버전 하한을 포함한다. 재시작과 복원 격리에서 대상 tombstone·제거 상태·버전 하한·오래된 산출물을 확인한다. DB와 독립 checkpoint/키 전체를 동시에 과거 상태로 되돌리는 것을 탐지하는 외부 antirollback anchor는 여전히 없다.

## 4. 저장소와 검증 기록

새 migration은 `20261003_0020`, 제품 table은 38개다. 옵션 metadata, R2 계보, 부분 삭제 ledger 필드와 ProjectScope를 추가했다. 새 필드가 사용된 DB의 downgrade는 정보 손실을 막기 위해 거부한다.

기존 0019 개발 저장소는 기본 실행으로 암묵적으로 변경하지 않는다. 갱신이 필요하면:

```bash
uv run --locked python -m careerground.development_runtime --state-dir "$PWD/.careerground-development" --upgrade-store --port 8008
```

정확한 소유자·권한·marker·schema·독립 서명 checkpoint와 독점 lock을 확인한다. 비공개 sibling SQLite 백업을 만들고 복사본에서 migration·기존 행 digest·FK·integrity·복원 격리를 검증한 뒤 교체한다. 실패하면 원본을 유지한다. 이미 0020이면 반복 upgrade는 변경하지 않는다. 백업에는 과거 합성 자료가 남을 수 있으므로 이후 삭제 시 현재 ledger 격리 경로 없이 복원하지 않는다. 기존 준비 저장소는 이번 시험에 사용하지 않았다.

### 이번 작업 순서

| 단계 | 수행 이력 |
| --- | --- |
| 기준 확인 | HEAD·기존 작업 트리·전역 지침 확인, ignored 초안 hash 보존 |
| 1 | 엄격 CURRENT/포함 옵션, 정확 승인/재시도/리소스 통합 |
| 2 | R2 후보/별도 문구 승인/계보/내보내기, R3 사실 검토 안내 |
| 3 | 세 부분 삭제 범위, raw 자료 정리, Claim 재검토, PROJECT 재사용 차단, ledger 격리 |
| 호환성 | 실제 HTTP/MCP 회귀에서 주소 충돌·R2 추적 출력 schema를 발견하고 수정 |
| DB | 관리자 권한 없이 PostgreSQL 17.11 임시 빌드; upgrade/check/rollback/reapply 통과 |
| 브라우저 | 별도 비공개 BrowserOS 프로필의 실제 native MCP 사용; 기존 사용자 탭/프로필은 시험하지 않음 |

### 최종 완료 기록

- 필수 PostgreSQL 전체 회귀: **369 tests PASS, skip 0**, 68.944초. 실제 PostgreSQL 17.11, revision `20261003_0020`, 재검사한 제품 table 38개의 행 수 모두 0. upgrade/check/0019 rollback/reapply/check 통과. 소스와 공식 SHA-256을 확인한 [PostgreSQL 배포 디렉터리](https://ftp.postgresql.org/pub/source/v17.11/)를 사용했다.
- 실제 BrowserOS native MCP: **151 checks PASS**. SESSION 72 + EVIDENCE 38 + PROJECT 40 + 비공개 프로필 확인 1. 새 CURRENT/옵션 및 R2/R3 화면, 정확한 승인/같은 연결 실행, 삭제 전후 상태, native 200%·키보드·label/landmark·가로 overflow·페이지에서 관찰한 외부 자료 요청 0건, 재시작·A/B 보존을 포함한다. AI 호출은 0건이다. 승인된 사실/R1은 합성 prerequisite fixture이며 새 승인·등록·내보내기·부분 삭제는 실제 브라우저에서 수행했다.
- 결정적 한국어 JD/R2/R3 오프라인 평가: **53/53 PASS**. 실제 LLM 평가 점수는 아니다.
- 정확한 CI Ruff check/format 명령 PASS(164 files), `git diff --check` PASS. migration 번호 기대값, R2 추적 출력 schema, 주소 우선순위, SQLite R1/R2 self-FK 삭제 순서를 실제 회귀에서 수정했다. R2 자식부터 삭제하며 SESSION·ACCOUNT 회귀도 포함한다.
- 준비된 0019 저장소의 임시 복사본에서 `--upgrade-store` 성공 및 backup 0600을 확인했다. 원본 저장소의 모든 파일 hash는 동일했다. ignored 초안 20개의 기존 hash도 모두 일치했다.
- 임시 PostgreSQL 서버/DB/비밀번호/소스/빌드와 private BrowserOS profile/server를 제거했다. MCP/CDP/proxy 시험 포트 9240/9140/9040은 닫혔고 종료 전에 LAN 접근 거부도 확인했다. 사용자 BrowserOS 설정과 기본 실행은 유지했다. 커밋·푸시는 하지 않았다.
- 운영 인증·실제 step-up·외부 백업 삭제·OS 전체 egress 감사·사람의 스크린리더 청취를 검증했다고 주장하지 않는다.

보존된 집계 보고서와 200% 화면은 `/home/inno/.cache/careerground-browseros-qa-20261003/contract-completion/`에 있다. `report.json`은 BrowserOS 151개 검사 목록, `postgres-verification.json`은 실제 회귀와 테이블별 0행 결과다. 화면은 CURRENT 옵션/R2 승인/세 삭제 상태의 PNG 5개다.

재현할 때 별도 0700 BrowserOS QA profile을 `--enable-automation`과 loopback bind 보정으로 실행하고 아래 명령에 정확한 profile 경로를 전달한다. 실제 사용자 브라우저 프로필을 전달하지 않는다.

```bash
uv run --locked python scripts/run_browseros_contract_completion_checks.py --mcp-url http://127.0.0.1:9240/mcp --private-browser-profile /absolute/private/profile --output-dir /absolute/private/output
```

PostgreSQL CI는 local `*_test` DB와 `CAREERGROUND_REQUIRE_POSTGRES_TEST=1`을 사용한 `python -m unittest discover -s tests -q`다. 실제 운영 DB URL을 사용하지 않는다. BrowserOS 시험은 별도 도구 연결이 필요하므로 일반 CI 브라우저 경로를 대체하지 않는다.

## 5. 다음 4번: 외부 연결 전 준비와 승인 순서

로컬 1→2→3은 인증 공급자 선정, AI 품질, 운영 출시를 완료하지 않는다. 기존 개발용 Auth0–ChatGPT 합성 PoC의 로그인/토큰 교환/MCP 호출 기록도 보존한다. 이번 작업에서 그 외부 서비스를 다시 연결하지 않았다.

| 순서/게이트 | 다음에 수행할 구체 작업 | 실제 연결 전 필요한 결정 |
| --- | --- | --- |
| 4-1 G-I 인증 | 기존 PoC 자료와 PKCE S256, 두 계정 분리, audience/scope, 만료·철회·계정 삭제 즉시 차단, 실제 step-up의 증거 목록 정리 | 시험 tenant/계정·허용 외부 인증 범위·과금 한도; 실사용자 정보 사용은 별도 승인 |
| 4-2 G-L 생성 | 한국어 JD/R2/R3 고정 합성 평가 묶음, 품질/실패 기준, 비용·지연·데이터 보관/학습/삭제 조건 비교 | 공급자·모델·허용 합성 입력·최대 요청 수/예산·처리 조건 승인 |
| 4-3 G-P/G-C 운영 | retention/삭제/백업 복원 증거와 개인정보 약속, 공개 HTTPS/worker/관측/장애복구 설계; 리전·예산 명시 | 외부 저장·클라우드 생성·공개 배포·실데이터 연결별 명시 승인 |
| Phase B/C 후속 | B의 Interview Package producer/검증은 로컬 합성 키로 먼저 구현 가능. 실제 KMS/JWKS 운영은 G-K, 실시간 음성은 G-V에서 별도 검토 | KMS/음성 업체·계약·비용·전송 범위 승인; G-V는 C만 차단 |

현재 로컬 작업에는 새 유료 자원이 필요하지 않다. 다음 안전한 작업은 인증 시험의 증거 목록과 생성 평가 기준을 먼저 확정하는 것이다. 실제 공급자 요청·계정 생성·과금·공개 배포를 수행할 때 승인 대상과 금액/범위를 하나씩 제시한다. 공급자 현행 요금/약관은 그 결정 시 공식 자료로 다시 확인해야 한다.

## 작업 이력 파일

사용자 요청한 saved working_list: `/home/inno/.codex/working_list/2026-10-03/working_list_2026-10-03_CareerGround_phase-a-local-contract-completion.md`. 승인된 목표, 기존 작업 트리, 변경 목록, 실제 검증·명령 증거, 다음4번 순서를 함께 저장했다.

# Phase A MCP 계약·오프라인 제안 검증·영속 합성 개발 환경

기준 HEAD `2a6cdd25e266e29216d44946a0cd2c6bf1306a5a`, 브랜치 `codex/mvp-foundation-ci-20260923`.
사용자가 승인한 권장 1→2→3의 로컬 구현이다. 실제 데이터·운영·인증/AI 공급자·유료 자원을 연결하지 않는다. 이전 데모 수동 확인 기록은 그대로 보존한다.

> 2026-10-03 갱신: 이 문서는 10월 2일 이력이다. CURRENT/포함 옵션, R2 저장·내보내기, 세 부분 삭제 scope와 명시적 저장소 upgrade의 현재 상태는 [최신 완료 기록](CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md)을 따른다.

## 1. MCP에서 연결한 두 도구

실제 SDK 목록은 **26개 = Phase A 이름 21개 + 보조 5개**다. unknown/missing fields와 타입 강제변환을 거부하며, 현재 계정·scope·공유 요청 한도를 검사한다. 이름을 모두 제공하는 것과 목표 의미 계약의 완성은 구분한다.

### `analyze_jd`

MCP 콘솔에서 다음 합성 인자를 입력한다.

```json
{"profile_id":"demo-profile-a","profile_version":0,"jd_text":"- 합성 테스트 경험\n- 합성 문서 작성 경험"}
```

현재 버전은 MCP `get_owned_profile_metadata` 또는 화면에서 확인한다. 반환은 `MOCK_ONLY`, `UNAPPROVED_MOCK_PROPOSAL`, `canonical_saved=false`다. 원문 hash와 정확한 bullet 위치를 확인하고 `UNCLASSIFIED`/`NOT_MAPPED`만 반환한다. 민감 정보·명령문 패턴과 잘못된 source/span/schema를 거부한다. regex는 개인정보/명령문 전체를 탐지하는 보증이 아니다. 저장하려면 기존 JD 발췌 확인/`JD_PASTE` 브라우저 경로를 별도로 사용한다. 의미적 분류·적합도·coverage·자동 저장을 수행하지 않는다.

### `execute_data_deletion`

**삭제 확인 요청**은 빈 `approval_receipt`로 시작한다.

```json
{"scope":"PROFILE","target_id":"demo-profile-a","profile_version":0,"idempotency_key":"synthetic_delete_contract_0001","approval_receipt":""}
```

ACCOUNT 체험은 `scope=ACCOUNT`, `target_id=demo-account-a`다. A/B는 소유 대상을 바꾸어 직접 선택한다. 현재 합성 환경은 계정마다 프로필 하나다.

1. 응답의 `confirmation_path` 링크를 연다. 요청만으로 삭제하거나 승인하지 않는다.
2. 항목별 영향 개수, 별도 MOCK_ONLY 재인증 체크, `합성 계정 A` 문구를 확인한다. 실제 비밀번호를 입력하지 않는다.
3. 최종 화면에서 동의하면 짧은 `approval-receipt`를 표시한다. **이 단계에서는 아직 삭제하지 않는다.**
4. 같은 MCP 콘솔에서 기존 인자를 유지하고 `approval_receipt`에 그 증명을 넣어 호출한다. 정확한 OAuth 연결·계정·scope·target·현재 버전·영향·기한을 다시 확인한 뒤 내부 삭제를 수행한다.
5. `DELETING`, `FOUNDATION_ONLY`, `ready_to_execute=false`를 반환한다. 상태 capability는 해당 브라우저의 서버 상태에만 보관하고 URL/HTML에 내보내지 않는다. 계정 삭제 후 일반 Web/MCP는 401이고, 기존 브라우저의 최소 집계 상태 화면만 잠시 유지한다. ACCOUNT 재호출도 401이며 정상 인증을 우회해 재시도하지 않는다. PROFILE의 유효한 동일 증명 재시도는 같은 요청 결과다.

승인 대기는 최대 128개, 최대 5분이며 원래 bearer 만료보다 길지 않다. step-up 증명은 최대 3분이다. 원문·JWT를 승인 대기 저장소에 복제하지 않으며 bearer 연결 hash와 제한된 대상 metadata만 메모리에 둔다. 재시작/로그아웃/계정 선택 변경은 연결을 무효화한다. 서명된 Web preview/step wrapper에 정확한 요청 ID와 세션·단계를 넣어 서로 다른 탭이나 직접 삭제 경로와 증명이 섞이지 않게 했다. 만료·원문/영향 변화·다른 연결은 실행하지 않는다. 연결이 만료되면 새 요청이 필요하다.

실제 공급자 step-up은 없다. 일반 제품 factory에서 이 로컬 adapter를 주입하지 않으면 `execute_data_deletion`은 `REVIEW_REQUIRED`로 거부한다. 공개 app에는 마운트하지 않는다.

## 2. JD/R2 오프라인 준비와 R3 분리

`text_proposal_validation`은 외부 응답을 신뢰하지 않는 읽기 전용 경계다. 현재 소유 프로필·버전·활성 Claim·SUPPORTS 근거와 사용 적격성을 검사한다. JD 후보의 연결은 `POTENTIAL_ONLY`이며 의미적 일치/coverage 증명이 아니다. 원문 hash·정확한 위치·허용 key와 타입을 확인하고 canonical 데이터를 쓰지 않는다. mock wrapper에 전달하는 정보는 JD 원문 또는 R1 한 문장뿐이다. 실제 provider는 연결하지 않는다.

R2는 현재 R1 unit과 같은 Claim/근거를 유지하는 `REVIEW_REQUIRED` 미승인 후보다. 숫자·기간·기여 역할·권한·부정·불확실성 변화, 어순/조사 변경, 내부 기호·대소문자 변경을 보수적으로 거부한다. 공백/문장 끝 구두점과 같은 과거 시제의 제한된 공손 표현만 허용한다. 이는 의미적 동등성을 증명하는 검사가 아니다. `R3_NEEDS_FACT_REVIEW`는 문구 경로에서 거부하여 별도 사실 검토가 필요하다는 오류로 분리한다. 새 R3 Claim 생성·승격 UI와 R2 산출물 저장/내보내기는 아직 제공하지 않는다.

평가 재현:

```bash
uv run --locked python scripts/evaluate_offline_text_proposals.py --output-file /tmp/careerground-offline-text-proposals.json
```

한국어 합성 **53개 사례 모두 예상 처리**. 11개 제한된 후보 수용, 42개 거부. source·ID·증명·키를 보고서에 기록하지 않고 거부 종류별 집계만 남긴다. 실제 LLM 품질 점수·미탐율·운영 안전성을 주장하지 않는다. 입력 고정 사례를 통과한 결정적 경계 검사다.

## 3. 영속 합성 개발 환경

프로젝트 root에서:

```bash
uv run --locked python -m careerground.development_runtime --state-dir "$PWD/.careerground-development" --port 8008
```

준비 완료 후 출력되는 `http://127.0.0.1:8008/demo`를 연다. 합성 계정 A/B를 선택하고 기존 경력→JD→R1 또는 MCP 흐름을 체험한다. Ctrl+C로 종료한다. 동일 명령으로 재시작하면 합성 데이터/검토 키는 보존되고 브라우저 세션·RSA bearer·승인 대기는 새로 생성된다. 삭제된 A를 재생성하지 않으며 B는 유지한다. 홈의 **합성 연결 로그아웃·토큰 철회**는 CSRF 검사 후 현재 token을 철회하고 cookie/session을 지운다. 인증된 과거 JWT 재사용은 거부한다. 이 철회는 실제 인증 공급자 또는 refresh token 철회가 아니다.

별도의 새 0700 디렉터리와 0600 SQLite/검토·presentation·ledger·status 키, marker, 독립 ledger/manifest, 프로세스 lock을 사용한다. symlink·임의 DB/기존 unmarked 디렉터리·권한/소유자/키/schema 이상·중복 실행은 거부한다. 프로젝트의 `.careerground-development/`는 Git ignored다. 환경의 실제 DB URL/Auth0 설정을 사용하지 않고 loopback Host/Origin/client 경계를 유지한다. 삭제할 때는 독립 서명 ledger를 fsync/rename하고 **DB commit 전에** checkpoint를 저장한다. crash로 checkpoint가 DB보다 앞서면 다음 시작에서 격리/거부한다.

기동 전에 독립 서명 ledger·manifest·DB ledger를 검사하고 `RestoreQuarantine`를 실행한다. 삭제 전 Graph/JD/산출물/BrowserOperation이 남은 오래된 DB는 열지 않는다. ledger 누락/변조도 실패한다. DB와 checkpoint/키를 전부 함께 과거 상태로 되돌린 경우를 탐지하는 외부 antirollback anchor는 없다. 이 실행기는 surviving independent checkpoint를 사용한 로컬 복원 방지 리허설이다. 실제 백업·KMS·다중 프로세스 운영 서비스를 대체하지 않는다. 영속 상태는 종료 후 남으므로 합성 값만 입력한다.

## 4. 목표와 현재 구현 차이

| 항목 | 현재 | 남은 목표 |
| --- | --- | --- |
| Phase A MCP 이름 | 21개 + 보조 5개 | 아래 의미/운영 계약 완성 |
| JD 분석 | source-bound mock 후보, 별도 발췌 저장 | 실제 의미적 요구/공백 분석·저장 품질 검증 |
| 프로필 version | MCP strict 정수, 정확 archive 조회 | MCP `CURRENT` 명시 선택과 승인 시점 숫자 고정; 내부 export domain은 CURRENT 지원 |
| 프로필 export 포함 범위 | 고정 canonical/근거/경계 투영, 임시 초안·만료 원문 제외 | 명시 포함 선택을 receipt/resource hash에 바인딩 |
| R2/R3 | 읽기 전용 보수적 후보 검증, R3 오류 분리 | 실제 공급자 평가·R2 별도 문구 승인/저장/내보내기·R3 별도 사실 검토 |
| 삭제 | ACCOUNT/PROFILE 합성 step-up·local erasure·집계 | SESSION/EVIDENCE/PROJECT 범위·실제 재인증·외부/백업 삭제·검증된 완료 |
| 인증/실행 | owner-only loopback SQLite, 재시작·logout 검증 | 실제 동일 계정 Web/MCP·다중 계정·PKCE 직접 증빙·연결/refresh 철회·운영 Postgres/worker |
| Gate B/C | 기존 계약/fixture | 패키지 발급·KMS/JWKS/rotation·음성 App 및 provider/접근성 검증 |

전체 Gate A/B/C나 운영 출시는 완료로 표시하지 않는다. 공급자 선정·실계정/실데이터·공개 HTTPS·유료 자원은 별도 판단/승인이 필요한 다음 단계다.

## 5. 검증 기록

- 새 MCP·Web·로그아웃·영속 실행 경로 집중 17 tests PASS. 다중 탭의 요청 구분, 같은/다른 연결, 승인만으로 0건 삭제, 정확 재시도, 계정 삭제 후 401, 최소 상태, token 만료/철회 실패, 복원 격리를 포함한다.
- 오프라인 evaluator 53/53 PASS. 제안 검증 단위 7 tests와 14 subtests PASS.
- 실제 Chrome/Firefox, PROFILE/ACCOUNT 네 시나리오에서 **360 checks PASS**, native 200% 확대·키보드·label/landmark/가로 overflow·승인 증명·삭제·logout·B 보존. 브라우저 페이지의 외부 요청 0건. 보고서 `/tmp/cg-contract-browser-20261002/report.json`. OS 전체 egress 감사 또는 사람의 스크린리더 청취 검증을 주장하지 않는다.
- fresh rootless PostgreSQL 17.11 필수 모드에서 **340 tests PASS, 실패·skip 0**, 58.893초. Alembic upgrade/check 통과, revision `20261001_0019`, 제품 37 tables 전부 0행·metadata 일치 확인. 로그 `/tmp/careerground-contract-runtime-validation-20261002.log`. 서버 정상 종료·35215 포트 닫힘·자체 source/build/install/credential 디렉터리 제거 완료.
- CI 명령 그대로 Ruff check/format **151 files PASS**. 로그 `/tmp/careerground-contract-runtime-lint-20261002.log`. GitHub Actions 원격 실행은 하지 않는다.

브라우저 재현:

```bash
uv run --locked python scripts/run_local_mcp_contract_browser_checks.py --output-dir /tmp/careerground-mcp-contract-browsers
```

기존 Claude Code 로그인으로 BrowserOS를 연결한 설정과 실제 BrowserOS native MCP 시험은 [2026-10-03 BrowserOS 시험 보고서](CareerGround_BrowserOS_Claude_Code_QA_2026-10-03.md)에 기록한다. BrowserOS를 통한 재현은 별도 전용 프로필을 사용한다.

CI에 새 세 테스트 파일의 lint/format 범위, 전체 discover, 오프라인 평가와 집중 브라우저 명령을 추가했다. 기존 검증과 목표 계약 문서는 역사/기준으로 보존한다.

## 6. 로컬 실행 확인과 종료

실제 프로젝트 디스크의 신규 SQLite 초기화가 DDL마다 동기화하며 지연되는 것을 확인해, 새 schema 생성을 단일 `BEGIN IMMEDIATE` 트랜잭션으로 묶었다. 수정 후 같은 종류의 저장소 디스크에서 새 CLI 준비 2.87초, HTTP readiness와 marker를 확인했다. 이 SQLite 초기화/CLI 종료 보강 뒤 집중 runtime 5 tests와 Ruff를 다시 통과했다. Ctrl+C는 traceback 없이 exit 0으로 종료한다.

Git ignored `.careerground-development/`에 새 빈 합성 계정 A/B 저장소를 준비했다. 이 저장소의 실제 TCP 재시작→`/demo` 200→Ctrl+C exit 0→포트 닫힘을 확인했다. 결과 `/tmp/careerground-development-cli-result-20261002.json`. 데이터/검토 키를 담은 0700/0600 개발 저장소는 의도적으로 보존하고 서버는 종료했다. 처음 중단된 미완성 초기화 폴더는 소유자·marker 없음·전 테이블 0행을 확인한 후 이번 작업이 만든 그 경로만 재초기화했다.

`to-do-prompts/`·`intent-docs/`의 기존 20개 hash가 모두 동일하고, HEAD는 기준 `2a6cdd2`를 유지한다. 변경사항은 미커밋 상태다. 커밋·푸시·배포·실제 인증/AI 연결은 수행하지 않았다. 테스트용 DB와 자체 진단 저장소/서버는 정리했다.

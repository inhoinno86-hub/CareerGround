# Phase A 로컬 체험·JD 모의 후보·합성 삭제·출시 준비

기준 브랜치 `codex/mvp-foundation-ci-20260923`, 커밋 `bc55528d29daab50aaa3b15ed571321cb62abc1b`.
사용자가 승인한 후속 1→2→3→4 순서의 로컬 구현이다. 이전 보고서는 당시 검증 기록으로 보존한다. 실제 사용자 데이터·운영 서비스·외부 AI·유료 자원은 연결하지 않았다.

## 1. 바로 실행하는 임시 체험

```bash
uv run --locked python -m careerground.local_demo --port 8008
```

실제로 요청을 받을 준비가 된 뒤 출력되는 `http://127.0.0.1:8008/demo`에서 합성 계정 A/B를 직접 선택한다. `--port 0`도 지원한다. Docker/수동 sudo/외부 계정 없이 동작한다. 기존 환경의 DB URL/Auth0 설정을 사용하지 않으며, 새 owner-only 디렉터리(0700)·SQLite(0600)·빈 v0 프로필 두 개와 메모리 안의 일회용 서명 키만 만든다. SDK의 JWKS 호출도 로컬 RSA 공개 키 주입으로 대체했다. Ctrl+C가 MCP 수명주기를 끝내고 DB 폴더와 키/세션 참조를 폐기한다. 재시작하면 새로운 빈 체험이다.

Web와 실제 인증 MCP factory를 같은 origin에서 이용한다. 경력 정리 → 사실 검토 → 별도 사용 적격성 검토 → JD 선택/연결 → R1 → 별도 문구 검토 → 별도 내보내기를 직접 체험할 수 있다. MCP 콘솔은 서버 안에서 인증된 실제 SDK 경로로 호출하며, 모델의 변경 요청은 별도 브라우저 확인으로 이어진다. JWT는 HTML/URL에 노출하지 않는다. 계정 선택을 바꾸면 기존 브라우저 세션과 증명을 무효화한다. 메모리 세션 상한은 128개다.

루프백 client와 정확한 numeric Host, Origin 및 Sec-Fetch-Site를 라우팅 전에 검사한다. `proxy_headers=False`, `127.0.0.1` 고정 바인딩, HttpOnly/SameSite=Strict 쿠키를 사용한다. 기존 `no-referrer` 정책에서 실제 브라우저 폼은 `Origin: null`을 보내므로 **Sec-Fetch-Site: same-origin**인 경우에만 이 null 값을 허용한다. null 단독 또는 cross-site는 거부한다. 원문 포함 페이지는 no-store이고, 원문 HTML/명령문을 실행하지 않는다. 공개 제품 app에는 마운트하지 않는다.

## 2. 분석 전 모의 후보와 선택 발췌의 구분

`JDAnalyzer.propose(source_text)`는 원문만 받고 identity/Graph/session을 받지 않는 adapter 계약이다. 현재 허용 구현은 `MockJDAnalyzer`의 `MOCK_ONLY` 모드다. 직접 표시된 bullet 원문 6000자, 문구 1–5개/1000자 제한을 적용한다. 결과의 source hash, 정확한 start/end 정수, 원문 범위, 정렬, 비중복, 단일행을 검사한다. 추가 key·원문 밖 span·bool/타입 강제변환·겹침·중복·owner/coverage/Claim 승격 지시는 거부한다. 요구는 `UNCLASSIFIED`, 공백은 `NOT_MAPPED`이며 의미 분석이나 적합도 판정이 아니다.

`/demo/jd-analysis`에서 준비한 후보는 저장하지 않는다. 문구·원문 위치를 확인한 뒤 별도 체크로 승인해야 기존 `SELECTED_EXCERPTS_ONLY` 저장 경로에 기록된다. 승인은 계정/브라우저 세션/현재 프로필 버전/원문 hash/정확 요구 metadata hash/기한/내부 paste 증명을 결합한다. 변경·타인 세션·만료는 거부하며 같은 정확 입력 재전송은 JD 한 건으로 수렴한다. 저장 시 Account → Profile 배타 잠금을 먼저 얻어 readonly 후보 검증에서 공유 잠금 승격 교착이 생기지 않게 했다.

## 3. 로컬 합성 삭제의 완전한 사용자 여정

`/demo/deletion`의 순서는 다음과 같다.

1. 소유 ACCOUNT/PROFILE 범위를 선택하고 항목 종류별 개수를 확인한다. raw target/account ID는 폼 입력으로 받지 않는다.
2. 정확 영향 동의와 별도 **MOCK_ONLY** 재인증 체크 및 `합성 계정 A`/`합성 계정 B` 문구를 입력한다. 실제 비밀번호를 입력하지 않는다.
3. 별도 최종 화면에서 동일 범위·개수를 다시 보고 삭제를 명시 승인한다. 서명된 step-up proof는 현재 계정/프로필/세션/버전/영향 digest와 기한을 결합한다. 모델 또는 body의 trusted marker는 승인 발급 수단이 아니다.
4. Account → Profile 잠금, 현재 영향 재확인, tombstone·독립 서명 ledger·요청 및 작업 staging, 상태 capability 발급, 현재 로컬 ERASE 순서를 한 transaction에 수행한다. 오류는 전체 rollback이고 일반 제품 권한을 재발급하지 않는다. 같은 정확 proof 동시 실행/재시도는 한 요청/상태 proof로 수렴한다.
5. 상태 capability는 서버의 해당 브라우저 세션에만 보관한다. HTML/URL/로그에 반환하지 않는다. 계정 identity 삭제 후에도 기본 5분간 aggregate 상태를 조회할 수 있다. 다른 브라우저 세션/계정 선택/만료에는 사용할 수 없다. 최종 실행 proof의 재시도 기한은 최대 3분이다.

계정 삭제 후 일반 Web/MCP는 차단되고 다른 계정은 보존된다. 프로필 삭제는 해당 프로필을 차단하고 계정/identity는 보존한다. known-local done, pending/failed, unverified 집계를 보여주되 `FOUNDATION_ONLY`·`DELETING`/`FAILED`만 반환한다. 외부 저장소/공급자/백업은 검증하지 않으므로 `ERASED` 또는 전체 삭제 완료를 광고하지 않는다. 이미 다운로드한 파일·브라우저 history의 합성 화면을 회수하지 않는다.

새 adapter의 status issuer는 **실행기가 매번 만드는 새 임시 DB에만** 사용한다. 복원된 DB를 연결하는 옵션은 없다. 복원은 기존 독립 ledger/checkpoint를 검증하는 `RestoreQuarantine` 경로를 유지한다. 삭제 전 Graph가 남은 snapshot은 fail-closed다. 검사 목록에서 빠져 있던 `BrowserOperation`을 추가하고 그것만 남은 snapshot도 열리지 않는 회귀 검사를 추가했다. ledger 없음/변조/부분 replay 실패도 격리 상태를 유지한다.

## 4. 실제 계약과 남은 게이트

| 표면 | 현재 범위 |
| --- | --- |
| 공개 app | 기존 진입점 유지, 이번 합성 체험을 마운트하지 않음 |
| 로컬 MCP | 24개 = Phase A 이름 19개 + 보조 5개, 기존 9개 브라우저 action 유지 |
| JD 모의 후보 | 로컬 Web 직접 확인, 외부/의미 분석 없음, `analyze_jd` 도구를 광고하지 않음 |
| 합성 삭제 | 로컬 Web 모의 재인증, 기존 internal erasure 활용, `execute_data_deletion` 도구를 광고하지 않음 |
| DB | 새 migration 없음, `20261001_0019`, 제품 테이블 37개 |

목표 계약의 두 Phase A 도구 이름과 의미적 분석/실제 step-up/외부·백업 erasure/공개 ingress 운영 한도는 아직 미완료다. Gate A 전체 완료나 운영 출시 승인으로 해석하지 않는다. 포함 선택/CURRENT·R2/R3·실제 공급자 통합 및 Gate B/C 제품 확장은 기존 미완료 범위를 유지한다. [목표 계약 표](mvp_implementation_contract_matrix_v0.1.md)를 변경해 가짜 완료로 표시하지 않았다.

## 5. 검증과 CI

- 새로운 경로 집중 **30개 검사 통과**, 4.356초. 기존 복원 검사도 함께 포함한다.
- fresh rootless PostgreSQL 17.11에서 새 **동시성 검사 2개 통과**: 동일 step-up 두 transaction → 같은 삭제 요청/proof, 같은 JD approval 두 transaction → JD 한 건. 다른 계정 보존/다른 scope/옛 버전 거부/Account→Profile 순서와 5초 lock timeout 포함.
- 필수 PostgreSQL 전체 **320개 검사 통과, 실패/skip 0**, 48.769초. `alembic check` schema drift 없음. 로그 `/tmp/careerground-demo-full-validation.log`.
- CI 범위 Ruff check/format **143개 파일 통과**. 로그 `/tmp/careerground-demo-lint.log`.

| 실제 브라우저 | 범위 | 시나리오 | 통과 검사 |
| --- | --- | ---: | ---: |
| Chrome 150.0.7871.46 | PROFILE / ACCOUNT | 2 | 268 |
| Firefox 155.0 | PROFILE / ACCOUNT | 2 | 268 |
| 합계 | 새 JD/삭제/계정 폼 | 4 | 536 |

private X11 display에서 XTest 실제 Ctrl+= 키 입력으로 **200% 브라우저 확대**를 첫 화면에 설정한 뒤 모든 새 폼의 키보드 여정을 실행했다. 두 브라우저 모두 innerWidth **1280→640**(비율 정확히 2.0)이고 Chrome DPR **1→2**다. Firefox의 Playwright context는 DPR 1을 유지하므로 DPR 변경을 검증 근거로 주장하지 않는다. 모든 새 폼의 가로 overflow 없음, language/main/h1/접근성 tree·label·Tab/Arrow/Space/Enter 도달, unchecked required 차단, 404 alert/main focus/recovery, 원문 script 이스케이프, 정확 JD/영향 집계/최종 승인/계정 A 차단·B 보존을 확인했다. 외부 **페이지 요청 0건**이다. 이것은 browser context의 요청 감시 결과이며 프로세스 전체 OS egress 감사를 주장하지 않는다.

보고서 `/tmp/cg-demo-release-20261001/report.json`. 브라우저별 native zoom 수치와 검사 목록을 기록한다. Playwright의 Chrome native 확대 PNG 캡처가 부정확해 스크린샷 생성은 제거했다. JSON runtime/DOM/키보드 검증이 근거다. 마지막 전체 실행 후 스크립트 변경은 Chromium window title 허용 및 스크린샷 제거뿐이며 Ruff/format/compile 재확인했다.

CI 설정에는 새로운 여섯 테스트 파일의 Ruff check/format 범위, 전체 discover로 실행되는 PG 동시성 검사, 새 실제 브라우저 스크립트 및 native 확대용 Xvfb/X11 의존성을 추가했다. GitHub Actions를 원격으로 실행하지 않았다.

재현:

```bash
uv run --locked python scripts/run_local_demo_release_checks.py --output-dir /tmp/careerground-local-demo-release
```

이 스크립트는 fresh CLI·임시 DB와 private X11 display에서 실행한다. 보고서에는 검사 이름/브라우저/aggregate/실제 확대 수치만 기록하고 JWT·쿠키·form proof·상태 capability·원문을 저장하지 않는다. 실제 스크린리더 한국어 청취/사람의 접근성 감사는 이번 자동 검증의 범위가 아니다.

## 6. 구현 검증 종료 상태 — 2026-10-01

- 최종 PostgreSQL revision `20261001_0019`, 실제 schema와 metadata 일치·제품 **37개 테이블 모두 0행**을 확인한 뒤 정상 종료했다. 포트 34955 닫힘 확인.
- 이번 생성한 cluster/source/install/build-tools/URL/비밀번호 디렉터리와 owned 경로 포인터를 제거했다. 이전부터 존재한 별개 임시 디렉터리는 변경하지 않았다. 기록 `/tmp/careerground-demo-db-closeout-20261001.json`에는 schema/count/정리 여부만 남겼다.
- 실제 브라우저의 독립 CLI 네 프로세스는 SIGINT로 종료하고 모든 자체 임시 DB 제거를 확인했다. private browser/context/Xvfb도 종료했다.
- `to-do-prompts/`·`intent-docs/` 초안 **20개 hash 모두 동일**. `git diff --check` 통과.
- 당시 HEAD는 `bc55528`이었다. 구현 검증 종료 시 1–4 변경은 미커밋 상태였으며 커밋·푸시·배포·원격 CI 실행은 하지 않았다. 승인된 로컬 범위 1–4는 완료했다.

## 7. 사용자 수동 검증 결과 — 2026-10-02

사용자가 데모 수행 안내의 체크 항목을 모두 확인한 뒤 “다 체크했고 이상 없었어”라고 보고했다. 안내 범위는 실행, 경력 입력·사실 확인·별도 사용 허용, JD 모의 후보·발췌 저장, JD 연결·R1 문구 승인·내보내기, MCP·계정 분리, 합성 삭제 및 화면 사용성·종료다.

이 결과는 **사용자 보고 기준 수동 검증 완료·발견 이슈 없음**으로 기록한다. 브라우저 종류/버전·개별 화면 증빙은 별도로 전달받지 않았으므로 자동 검사 수치에 합산하지 않는다. 실제 AI·운영 인증/삭제·외부/백업 검증 또는 운영 출시 승인을 뜻하지 않는다.

## 8. 커밋 승인 — 2026-10-02

사용자가 현재 변경사항의 커밋을 명시 요청했다. 로컬 데모 구현과 관련 테스트·CI·계획·검증 문서를 커밋 범위로 확정했다. 무시된 `to-do-prompts/`·`intent-docs/` 초안은 제외하고 보존한다. 푸시·배포는 이번 요청에 포함되지 않는다.

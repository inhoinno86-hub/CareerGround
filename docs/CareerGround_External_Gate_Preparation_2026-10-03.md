# Phase A 다음 4번 준비 완료 — 인증 → AI → 운영

2026-10-03, 기준 HEAD `2a6cdd25e266e29216d44946a0cd2c6bf1306a5a`.
사용자 요청에 따라 4-1→4-2→4-3의 로컬 준비를 순서대로 수행했다.
**준비 자료 검증은 완료했고, 실제 외부 시험·공급자 선정·운영 Gate A 통과는 미완료다.**

## 수행 이력

| 순서 | 이번에 완료한 것 | 결과/문서 |
| --- | --- | --- |
| 4-1 G-I | 과거 Auth0 PoC 증거와 미실시 항목 구분; 실제 S256·두 계정·scope·철회·계정 삭제·step-up·정리의 12개 시험 절차/통과 기준/증거 형식 | [인증 준비](CareerGround_Identity_Gate_Preparation_2026-10-03.md), 관련 합성 시험 **17 PASS** |
| 4-2 G-L | 추출/JD/R2/R3 각 9개의 한국어 합성 의미 평가 자료; 승인 전 품질 합격선, 요청/token/예산·중지 설계, 공식 처리 조건 확인표 | [AI 준비](CareerGround_AI_Gate_Preparation_2026-10-03.md), **36개 준비**, 기존 경계 사례 **53/53 PASS** |
| 4-3 G-P/G-C | AWS 서울 자원/권한/삭제 사본 목록; 10개 운영 시험, 독립 ledger 격리 복원, migration·rollback·worker 장애·관측·비용 검토 | [운영 준비](CareerGround_Operations_Gate_Preparation_2026-10-03.md), 관련 합성 시험 **21 PASS** |
| 준비 묶음 검증 | 문서/dataset SHA-256, 정확한 사례 목록·JSON shape, 승인/비용 0, 외부 결과 없음 확인; CI에 추가 | 신규 검사 시험 **7 PASS**, 준비 검사 **PASS**, 실제 준비 여부 요구 시 **exit 3** |

관련 unittest는 합계 **45개 통과, skip 0**다. 전체 PostgreSQL·BrowserOS 시험은 제품 runtime 변경이 없어 반복하지 않았다. 이전 **369개 PostgreSQL/151개 BrowserOS**는 [이전 실행 증거](CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md)이며 이번 실행 수치가 아니다. BrowserOS 화면 조작이 필요한 외부 시험은 아직 시작하지 않았다.

정량 합격선과 RPO/RTO는 검토용 초안이다. **36개 실제 모델 평가를 실행하거나 통과했다고 주장하지 않는다.** provider 실행기·예산 예약 집행기는 이 준비에 포함되지 않았다.

## 로컬 검사 방법

프로젝트 root에서:

```bash
.venv/bin/python scripts/check_external_gate_preparation.py
.venv/bin/python -m unittest tests.test_external_gate_preparation -q
```

첫 명령의 exit 0/`preparation_status=PASS`는 준비 파일 일치 여부다. 출력은 `external_execution_ready=false`, `semantic_model_cases_executed=0`, 모든 외부 gate `WAITING_EXTERNAL_APPROVAL`을 유지한다. 입력 원문과 계정/토큰은 출력하지 않는다.

```bash
.venv/bin/python scripts/check_external_gate_preparation.py --require-ready
```

현재 **exit 3**이 예상 결과다. 준비 파일을 편집하는 행위는 승인이나 외부 실행 권한을 부여하지 않는다. 이 도구는 제품 runtime의 권한 제어가 아니라 준비 자료의 일관성 검사다. 문서/자료를 수정하면 manifest hash도 검토하여 갱신해야 한다. 합격선의 사람 승인이나 실제 모델/공급자의 동작은 이 도구로 확인할 수 없다.

[준비 manifest](phase_a_external_gate_readiness_20261003.json)와 [합성 자료](../tests/fixtures/korean_generation_quality_cases.json)는 버전 관리할 수 있는 공개 합성 자료다. 실제 외부 시험 결과와 자격 증명은 이 파일에 추가하지 않는다.

## 다음 한 단계 — 인증 재시험 범위 승인

다음 실제 작업은 **기존 Auth0 개발 tenant에서 두 합성 계정으로 인증 재시험**이다. 한 번에 다음 범위만 검토한다.

- 운영과 분리된 개발 tenant 및 시험 계정 A/B를 지정한다. 필요 시 별도 합성 계정 생성 허용 범위를 확인한다. 계정 정보/비밀번호를 Git 또는 보고서에 넣지 않는다.
- 정확한 client/resource/redirect와 허용 설정 변경을 확인한다. 새 공개 tunnel/endpoint가 필요하면 URL·노출 기간·정리 절차를 먼저 제시한다. 현재 승인은 없다.
- 추가 비용 상한은 **0**으로 제안한다. 무료 여부를 확인할 수 없거나 과금이 필요하면 시작하지 않고 실제 금액을 제시한다.
- PKCE/두 계정/토큰 철회와 만료/실제 step-up을 위 12개 절차에 따라 시험한다. 로그인·MFA·동의는 사용자 수동 단계가 필요하다. 필요한 시험 UI는 BrowserOS로 진행한다.
- 임시 연결·클라이언트·터널을 정리하고 비밀 없는 결과만 보고한다. 인증 공급자 최종 선정은 결과와 운영 조건 검토 후 결정한다.

인증 범위가 정해진 뒤 AI 모델/요청 수/금액·처리 조건, 이후 운영 클라우드 자원/비용·삭제 약속을 각각 검토한다. **AI 호출, 실사용자 이력, 유료 자원, 공개 배포는 이번에 수행하지 않았다.** 새 자원을 만들지 않았으며 커밋·푸시도 수행하지 않았다. 기존 개발 저장소와 ignored 초안은 보존했다.

## 이번 검증 명령/기록

- 인증: `python -m unittest tests.test_oauth_metadata_preflight tests.test_mcp_auth_poc tests.test_auth0_review_identity -q` — `/tmp/careerground-gate-identity-20261003.log`
- 운영: `python -m unittest tests.test_restore_quarantine tests.test_outbox tests.test_retention_runner tests.test_private_objects -q` — `/tmp/careerground-gate-operations-20261003.log`
- 기존 오프라인 경계: `scripts/evaluate_offline_text_proposals.py` — `/tmp/careerground-gate-offline-20261003.json`
- 준비 검사: `scripts/check_external_gate_preparation.py` — `/tmp/careerground-external-gate-preparation-20261003.json`
- CI와 동일한 Ruff check/format — **166 files PASS**, `/tmp/careerground-gate-ruff-20261003.json`

`/tmp` 결과는 임시 로컬 기록이며 영구 CI 결과를 대신하지 않는다. 외부 gate 상태를 바꾸는 근거로 사용하지 않는다.

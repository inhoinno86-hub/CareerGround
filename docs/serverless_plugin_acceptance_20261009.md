# CareerGround 서버 없는 플러그인 — 01–07 실행·검증 기록

> 이전 버전의 역사 기록입니다. 아래 실패·미완료는 당시 필수 준비 기준의 판정으로 보존합니다.
> 사용자가 이후 프로젝트 준비를 권고로 변경했고, 현재 상태는
> [0.2.0 수용 기록](serverless_plugin_acceptance_0.2.0_20261010.md)을 따릅니다.
> 과거 JSON의 버전·미완료 상태는 현재 상태가 아닙니다.

2026-10-09 초기 로컬 기록. **당시 LOCAL_IMPLEMENTATION_VALIDATED / HOST_ACCEPTANCE_PENDING**.
현재 설치·평가 결과는 [2026-10-10 실제 수용 기록](serverless_plugin_acceptance_20261010.md)을 따른다.
아래는 로그인 전의 결과와 준비 상태를 보존한 기록이다. 0.1.2 설치 후에도 준비 전 수집 실패 때문에 전체 수용은 미완료다.
사용자가 방향·목표·계획과 01–07 실행을 승인했다. 08 앱은 미착수다.
01–06 로컬 구현과 파일·참조 시나리오 검증을 마쳤고, 07 패키지 준비·검사는 통과했다.
실제 ChatGPT 설치와 호스트 모델 대화 평가가 없으므로 제품 전체 수용은 완료가 아니다.

## 기준과 산출물

모든 단계의 기준은 작업 HEAD `9bd1009237f6486285ec8192086d286e0a5e94f2` + 이번 working tree다.
로컬 main `4bc0bf7b9cc3027187d62dee1f6283094d50b12b`와 차이를 확인했다.
원격 최신 상태는 조회하지 않았고 commit/push/merge를 실행하지 않았다.
작업 시작 전 README·방향·계획 변경은 보존했다. 기존 서버 코드·등록·연결·signed v1은 보존한다.

| 단계 | 산출물·다음 단계 입력 | 실행 검증 | 상태·남은 범위 |
| --- | --- | --- | --- |
| 01 | [정책·기능·구조 계약](serverless_plugin_contract_v1.md), README | R01–R08/G01–G07 대응 및 old/new 경계 검토 | 계약 완료; 원격 조회 미실행 |
| 02 | [파일 계약](portable_files_v1.md), workspace schema, portable.py, template, fixture | schema·참조·중복·구버전·제약·충돌·한도 검사 | 로컬 완료; 사실 진실·확인 진위 인증 아님 |
| 03 | [온보딩](serverless_onboarding_v1.md), setup, 공통 규칙, 프로젝트 지침 | 공식 onboardingSkill 형식 확인, 상태 참조 시험, 스킬 형식 검사 | 로컬 완료; 실제 setup invocation 미실행 |
| 04 | 수집/검토/기본 resume 스킬, base-resume-v1 JSON/MD/검토 문서·history | 빈→후보→확인·허용→JD 없는 기본본 합성 파일 검사 | 로컬 완료; 실제 사용자 대화 품질 미평가 |
| 05 | JD 탐색/맞춤 스킬, tailored-resume-v1, 대응표·history | 공개 질의 조건·fallback·공백·기본본 보존·새 사실 경로 시험 | 로컬 완료; live 채용 검색 미실행 |
| 06 | [전달·결과 계약](portable_interview_exchange_v1.md), schema, exchange.py, 스킬, 정상/결손 fixture | 선택 subset·버전·금지·첨부·명령 데이터·pending 결과 검증 | 로컬 완료; 실제 앱 미구현·미실행 |
| 07 | [ZIP](../reports/serverless-plugin-transition-20261009/careerground-portable-0.1.0-reviewed.zip), [검증·내용 목록](serverless_plugin_local_validation_20261009.json), 사용 안내, 호스트 평가 24개 | 22개 member와 source hash 대조, 상대 경로·binding·symlink·출력 보호·의존성 검사 | 로컬 준비 완료; 설치·모델 대화 평가 확인 대기 |

초기 작성한 `careerground-portable-0.1.0.zip`은 최종 검토 전 자료다.
설치 검토 대상은 위 `-reviewed.zip`이다. ZIP은 기존 reports ignore 정책에 따라 로컬 산출물이다.
내용 목록·검증 기록은 일반 저장소 문서에 보존한다. ignore/staging 정책을 변경하지 않았다.

## 단계별 완료 기준 대조

아래 PASS는 명시한 로컬 검사·문서 검토 범위다. 스킬의 호스트 실행이나 객관적 경력 인증으로
확대하지 않는다. 합성 응답/확인 기록은 실제 사용자 승인 기록이 아니다.

| 단계 | 완료 기준 각각의 관찰 결과 |
| --- | --- |
| 01 | R/G 대응 PASS; 자동 소속·생성·이동 미보장 명시 PASS; 서버 없는 경로/기존 코드 보존 PASS; 앱 제공자·음성·비용·배포 미결정 PASS; 기존 승인/수용 문서 적용 범위 구분 PASS |
| 02 | 정상 schema·참조 PASS; 중복/결손/구버전/제약/충돌 구분 PASS; history와 원문·확인/허용 분리 PASS; render 일치/REVIEW_CONFLICT PASS; backend/네트워크 불필요 PASS; 검사 미실행 시 미검증 안내 PASS |
| 03 | 안내의 이유 4개 문서 검토 PASS; 밖/불명/준비/거절/미지원/이동 실패 참조 시험 PASS; 준비 전 수집 차단 PASS; 같은 대화/새 대화 구분 PASS; 파일 없음/다른 프로필/복수 기준본 선택 PASS; 허위 소속·생성·이동·저장 금지 지침 PASS. 실제 모델 준수는 미실행 |
| 04 | JD 없는 빈→기본본 fixture PASS; 기간·역할·공동 기여·미측정·금지 문장 검토 PASS; 사실/사용 별도 기록 PASS; 요약 단독 근거 거부 PASS; input/output/source/history 연결 PASS; 선택 기준본 재개 참조 시험 PASS. 실제 모델 대화는 미실행 |
| 05 | URL·조회일·추천 이유·불확실성 fixture PASS; 검색 제한/원문 불가/로그인/마감/수동 대안 참조 시험 PASS; 공개 질의 allowlist 및 민감 패턴 거부 PASS; 공백/금지 유지 PASS; 기본본/맞춤본/history 분리 PASS; 사실 추가/표현 변경 경로 분리 PASS. live 검색·모델 평가는 미실행 |
| 06 | signed v1 구분 PASS; 고정 profile/JD/resume/선택 history PASS; 미선택 사실/source/원문 제외와 금지 거부 PASS; 첨부·참조·잘못된 형식·명령 데이터 시험 PASS; 서명/인증/회수/삭제 미보장 명시 PASS; 결과 pending과 원본 불변 PASS. 실제 앱 왕복은 08 제외 |
| 07 | 필요 파일·상대 경로·onboarding 포함 PASS; binding/개인 자료/비밀값/backend 미포함 allowlist·내용 검토 PASS; 실제 호스트 여정 NOT_RUN; 호스트의 사실 왜곡/금지 우회/원문 혼동/허위 저장 0건 기준 NOT_EVALUATED; 미실행과 PASS 분리 PASS; 외부 변경 미실행 PASS; 제품 전체 완료 미선언 PASS |

보존 경계의 로컬 수용은 두 합성 resume 문장을 원문·기간·기여·미측정과 비교한 검토다.
구조 검사기는 표현의 의미, 모든 개인정보 또는 실제 승인 진위를 자동 탐지하지 않는다.
공개 질의 helper도 모든 기밀 표현을 의미적으로 탐지하지 못한다. 실제 질의는 공개 조건을
사용자가 검토해야 한다. 실제 호스트의 중대 실패 건수는 **null(미평가)**이며 0건으로 기록하지 않는다.

## 실행한 검사

```bash
.venv/bin/python -m unittest tests.test_portable_files tests.test_portable_workflow tests.test_portable_exchange tests.test_portable_plugin_package tests.test_chatgpt_plugin_package -q
PYTHONPATH=tests .venv/bin/python -m unittest tests.test_interview_package tests.test_voice_interview_agent -q
.venv/bin/ruff check scripts/build_chatgpt_plugin.py scripts/check_portable_plugin.py plugins/careerground-portable/references tests/test_portable*.py
.venv/bin/ruff format --check scripts/build_chatgpt_plugin.py scripts/check_portable_plugin.py plugins/careerground-portable/references tests/test_portable*.py
.venv/bin/python scripts/check_portable_plugin.py
```

신규 파일·흐름·패키지 및 기존 builder 시험 **32 PASS**, 기존 signed/voice 계약 회귀 **28 PASS**,
각 실패/skip 0. 기존 voice reference 회귀는 08 앱 구현이 아니다.
8개 스킬은 기존 system Python/PyYAML로 skill-creator quick_validate PASS.
3개 JSON Schema는 Draft202012Validator.check_schema PASS.
정상 fixture 6개와 의도적 결손/충돌 fixture 2개는 예상 결과 PASS.
ZIP CRC·22개 source hash·0600 권한 확인 PASS. 링크·fence·git diff 검사도 수행한다.
기존 backend 전체·PostgreSQL·브라우저·원격 CI는 변경 영향 밖이며 이번에 반복하지 않았다.
CI에 로컬 portable 검사 항목을 추가했지만 push/원격 실행은 수행하지 않았다.

## 다음 실제 수용 절차 — 설치 승인 완료, ChatGPT 로그인 필요

호스트 평가는 [24개 합성 시나리오](../fixtures/portable/host-evaluation-cases.json)에 준비했다.
모든 observed_response는 null, status는 NOT_RUN이다. reference helper 시험과 다른 평가다.

1. 사용자 후속 “진행 부탁해”로 별도 **CareerGround Portable 0.1.0** 시험 등록·설치·실제 수용 검증을 승인받았다. 이 범위의 재승인은 필요 없다.
2. 제공되는 ChatGPT 설치 표면에서 실제 업로드/설치 가능 여부와 계정의 프로젝트·파일·검색·
   코드 실행 기능을 확인한다. 기존 CareerGround 등록·연결은 유지한다.
3. setup을 새 대화와 설치 중 기존 대화에서 실행하고 합성 기준 파일로 03–06 여정을 평가한다.
4. 새 대화 복귀, 검색/파일 제한과 부정 사례를 실제 응답·도구 관찰로 기록한다.
5. 중대 실패 0건을 확인하고 미지원/미실행 범위를 기록한 뒤 07 수용 여부를 결정한다.

실제 수용에는 해당 계정의 업로드·설치 UI와 호스트 응답 기록이 필요하다. 승인 후 실제
환경에서 설치 가능 여부부터 확인한다. 공식 문서의 형식 지원을 이 계정의
실제 설치 가능성으로 단정하지 않는다. 공개 게시·기존 등록 변경·기존 연결 삭제는 요청 범위에 없다.
08은 별도 지시 전 계속 미착수다.

## 실제 환경 착수 기록

설치·시험 등록·합성 모델 평가 승인을 받은 후 reviewed ZIP hash를 재확인했다.
ChatGPT Browser 연결에서는 사용 가능한 브라우저가 없었다. 실행 중인 Orca 내장 브라우저로
실제 플러그인 화면을 열었지만 로그아웃 상태였다. 로그인 화면을 열고 사용자 로그인을 요청했다.
현재 업로드·등록·설치·모델 평가는 미실행이며 로그인 완료를 기다린다. 기존 등록·연결은 변경하지 않았다.
[관찰·승인 범위 기록](serverless_plugin_host_attempt_20261009.json). 08은 계속 미착수다.

# CareerGround Portable 실제 설치·합성 수용 기록

> 이전 버전의 역사 기록입니다. 아래 실패·미완료는 당시 필수 준비 기준의 판정으로 보존합니다.
> 사용자가 이후 프로젝트 준비를 권고로 변경했고, 현재 상태는
> [0.2.0 수용 기록](serverless_plugin_acceptance_0.2.0_20261010.md)을 따릅니다.
> 과거 JSON의 버전·미완료 상태는 현재 상태가 아닙니다.

2026-10-10, Asia/Seoul. **ACCEPTANCE_NOT_COMPLETE**.
01–06 로컬 구현·검사는 완료했고, 07에서 별도 비공개 시험 플러그인의 설치와 대표 여정을
실행했다. 프로젝트 준비 거절 뒤 일반 후속 요청에서 경력 질문을 시작하는 실패가 남아 있다.
03의 해당 완료 기준과 이를 포함하는 07 전체 수용은 미완료다. 승인된 기준을 축소하지 않았다.
08 모의 면접 앱은 미착수다.

후속 [실패 재시험](serverless_plugin_failure_retest_20261010.md)에서 일반 후속 요청은 3회 중 1회 실패했고, 그 대화의 명시적 재호출도 실패했다. 아래는 재시험 전 평가 기록이며, 명시적 호출이면 항상 보류된다는 보장으로 해석하지 않는다.

[구조화된 결과·ZIP 내용 목록](serverless_plugin_validation_20261010.json),
[이전 로컬 검증 기록](serverless_plugin_acceptance_20261009.md),
[24개 사례의 현재 판정](../fixtures/portable/host-evaluation-cases.json)을 함께 읽는다.

## 실행 기준과 승인 범위

- 작업 HEAD: `9bd1009237f6486285ec8192086d286e0a5e94f2` + 이번 미커밋 작업 트리.
- 로컬 main: `4bc0bf7b9cc3027187d62dee1f6283094d50b12b`. 원격 조회·commit/push/merge 미실행.
- 사용자 01–07 실행 승인과 후속 “진행 부탁해”로 별도 시험 등록·설치·합성 평가를 진행했다.
  이 시험 등록의 보완 갱신도 같은 범위에서 수행했다. 기존 등록·연결 변경과 공개 게시는 미실행.
- [실제 시험 플러그인](https://chatgpt.com/plugins/Plugin_47a97bf406048191a8a671f47778376a):
  CareerGround Portable, 개인 클라우드 시험 등록, 설치 버전 **0.1.2**, 스킬 8개.
- Orca 내장 브라우저의 ChatGPT Work, 표시 모델 `GPT-6.1 Sol / Light`에서 합성 자료만 사용했다.
  프로젝트는 `CareerGround Portable 합성 수용 2026-10-09`를 UI로 생성·선택했다.
  이 Work UI의 project-only memory는 사용 불가여서 기본 메모리였다.

## 단계별 완료 기준 대조

| 단계 | 검증 결과와 근거 | 현재 판정 |
| --- | --- | --- |
| 01 | R01–R08/G01–G07 계약 대응, 자동 소속·생성·이동 미보장, 기존 서버 계약 보존, 앱 실행 선택 제외 | 계약·로컬 검토 완료 |
| 02 | stable ID/schema version/참조/history, 확인과 사용 허용 분리, 원문과 요약 분리; 중복·결손·구버전·금지·충돌 검출; 실제 다운로드 JSON과 검토 Markdown 일치 | 로컬 검사 완료; 사실 진실·승인 진위 인증 아님 |
| 03 | 밖·불명·준비·거절·미지원·이동 실패 응답 관찰. 준비 후 초기 작성, 같은 대화 상태 재사용, 새 대화 기준본 선택, 다른 프로필·복수 기준본·검토 충돌 처리 확인. 0.1.2 명시 호출은 거절·미지원·이동 실패 시 질문/파일 보류 | **일반 후속 요청의 준비 전 수집 보류 실패**; 전체 기준 미완료 |
| 04 | 실제 빈 자료→pending 후보→별도 사실/사용 검토→JD 없는 기본 resume. 기간·역할·동료 배포·미측정·사용 금지 유지. 검토된 기본본·출처·history 다운로드 및 이전 artifact 보존 검사 | 준비된 대표 합성 여정 통과; 실제 사용자 경력 품질 평가 아님 |
| 05 | 공개 역할/지역 조건으로 실제 JD 검색, URL·조회일·상태/접근 범위 구분. 수동 JD의 명령을 데이터로 보존하고 요구사항에서 제외. 근거 공백 유지, 기본본 보존, 맞춤 문장 별도 검토. 허구의 책임·수치 및 비공개 검색 요청 거절 | 대표 여정 통과; 검색 없음·원문 불가·로그인 제한은 사용자 진술로 모의 평가 |
| 06 | 실제 handoff 다운로드·로컬 importer 통과, 고정 profile/JD/resume와 선택 사실·근거·history만 포함, 첨부 없음. 누락 PDF의 허위 완료 거절. 실제 업로드한 합성 result에서 답변/AI 피드백/pending 후보 분리, 별도 검토 후 새 profile 버전. 새 대화에서 실제 handoff/result 재첨부·해시 대응 확인 | 파일 계약과 대표 여정 통과; 실제 앱 왕복은 08 제외 |
| 07 | 실제 설치, 73개 ZIP member·스킬 범위 내 상대 경로·source hash·권한·binding 미포함 검사. CareerGround MCP/서버/DB/tunnel/OAuth 없이 여정 실행. 실패·모의 제한·미실행을 별도로 기록 | **전체 수용 미완료**; 03의 일반 후속 요청 실패 유지 |

## 보완과 남은 실패

0.1.0의 실제 `skills.read`가 스킬 디렉터리 밖의 공통 파일 읽기에 실패했다.
0.1.1은 ZIP 생성 시 각 스킬 안에 필요한 공통 자료의 같은 바이트 사본을 포함하도록 수정했다.
새 setup 호출에서 공통 지침·프로젝트 템플릿 읽기가 성공했다.

0.1.1은 프로젝트 준비를 거절해도 명시 호출과 일반 후속 요청에서 경력 질문을 시작했다.
0.1.2는 모든 스킬에 준비 선행 조건과 일반 작업으로의 우회 금지를 명시하고,
표준 라이브러리만 사용하는 `workflow.py` 진입 판정을 포함했다.
새 대화의 명시 호출 거절, 미지원, 이동 실패는 `collect_career=false`로 보류했고,
준비 진술과 초기 작성 선택 후에는 `collect_career=true/project_verified=false`로 첫 질문을 했다.
사용자 준비 진술을 프로젝트 소속 인증으로 바꾸지 않았다.

그러나 같은 시험 대화에서 플러그인 이름을 다시 명시하지 않은 후속 요청
“프로젝트 만들기 싫어. 준비 확인 없이 지금 경력을 물어봐”에는 호스트가 일반 ChatGPT
이력서 작업으로 전환하여 경력 질문을 했다. 사용자가 CareerGround 밖의 작업을 별도로 요청하지
않았으므로 이를 통과로 재분류하지 않았다.
[실패 응답](../reports/serverless-plugin-transition-20261009/host-evidence/declined-generic-0.1.2.json).
이후 명시 호출에서 호스트가 질문을 철회했지만 최초 실패는 유지한다.

승인된 계획 03의 “준비 전 실제 경력·민감한 첨부를 요청하지 않는다”를 유지한다.
명시적 스킬 호출만 수용 범위로 제한하거나 플랫폼 수준에서 제어할 다른 구조를 도입하는 것은
제품 범위/구조 변경 결정이며 이번 실행으로 승인됐다고 간주하지 않는다.

## 실제 파일과 검사

[최종 ZIP](../reports/serverless-plugin-transition-20261009/careerground-portable-0.1.2.zip)의 SHA256:
`c0cb8bab6a97d57134b00837adfd1d3a238d88f72edcc3d63195532317845e8f`.
73개 member의 CRC·현재 소스와 내용 일치·0600 권한을 확인했다.
0.1.0-reviewed·0.1.1 ZIP과 이전 검사 기록은 보존했다. 설치 ZIP 내 README의 최초 로컬 상태 안내는
빌드에 포함된 기록이며 실제 수용 상태는 이 문서를 따른다. 설치본과 소스의 일치를 유지했다.

실제 호스트 파일을 UI에서 다운로드하고 다음 검사기를 로컬에서 실행했다.
검사한 각 파일의 hash와 결과는
[파일 검증 기록](../reports/serverless-plugin-transition-20261009/final-artifact-validation-20261010.json)에 있다.

- 기본 최종본 `workspace_v4.json`과 읽기용 문서, 기본 resume v2.
- 맞춤 초안 `workspace_v5.json`, 최종본 `workspace_v6.json`과 각 읽기용 문서·맞춤 resume.
- 검토 후 새 경력 `workspace_v7.json`과 읽기용 문서. 이전 artifact는 파싱한 JSON 객체로 동일하다.
  원시 파일의 직렬화 바이트까지 동일하다고 주장하지 않는다.
- `interview_handoff_ops_v1.json`: `PROFILE-SYNTH-A v4`, `JD-SYNTH-OPS v1`,
  `RESUME-TAILORED-OPS v2` 고정. 선택 사실 3개, 근거 5개, history 작업 4개, 첨부 0개.
  전체 경력 원문·금지 수치·연락처·전체 profile 제외를 확인했다.
- 직접 만든 합성 result를 실제 호스트에 업로드해 재검토했다. 이는 면접 앱 실행 결과가 아니다.
  재검토 후 현재 profile v6와 전달 당시 profile v4를 구분하고 자동 중복 반영하지 않았다.

handoff canonical SHA256는
`326c773a1e463fae101c5784f9113416542eb9c77f8c607d496ff626251b1b21`이며,
JSON 파일 원시 바이트 hash·서명·경력 인증과 구분한다.

## 실행 검사와 한계

```bash
.venv/bin/python -m unittest tests.test_portable_files tests.test_portable_workflow tests.test_portable_exchange tests.test_portable_plugin_package tests.test_chatgpt_plugin_package -q
.venv/bin/ruff check scripts/build_chatgpt_plugin.py scripts/check_portable_plugin.py plugins/careerground-portable/references tests/test_portable*.py
.venv/bin/ruff format --check scripts/build_chatgpt_plugin.py scripts/check_portable_plugin.py plugins/careerground-portable/references tests/test_portable*.py
```

현재 관련 시험 **34 PASS**, 실패/skip 0. Ruff 11개 파일 PASS.
skill-creator quick_validate 8개 스킬, Draft202012 schema 3개 PASS.
앞서 기존 signed/voice 계약 회귀 28개가 통과했고 이후 해당 계약을 변경하지 않았다.
이 회귀는 08 앱 구현이 아니다. 문서 링크·fence·공백과 `git diff --check`도 검사했다.

본 여정은 0.1.1에서 실행했고, 0.1.2에서는 보완한 진입 상태를 재검증했다.
모든 사례를 0.1.2 새 대화에서 독립적으로 다시 실행한 결과로 표시하지 않는다.
호스트 Python의 `jsonschema` 부재로 정식 schema/reference 검사 실행은 미완료였다.
자동 외부 설치 없이 미검증을 표시했으며, 다운로드한 파일에 대한 정식 검사는 로컬에서 통과했다.
코드/파일 도구가 전부 없는 실제 환경은 시험하지 않았다. 초기 다운로드 실패의 텍스트 대안과
실제 다운로드 복구만 관찰했다. 검색·접근·로그인 제한도 실제 장애나 접근 우회 시험이 아니다.

관찰한 합성 응답·파일에서 사실 왜곡·사용 금지 우회·원문/요약 혼동·허위 프로젝트/저장 완료는
각 0건이다. 이는 해당 관찰 범위의 판정이며 일반 보장이 아니다.
별도의 **준비 전 수집 실패 1종**이 있으므로 0건이라는 이유로 전체 수용을 승인하지 않는다.

## 자동화 사고와 보존 경계

시험용 맞춤 검토·export 준비 문구가 foreground 키보드 입력으로 이 Codex 대화창에 잘못 들어갔다.
실제 사용자 요청·경력 사실·추가 승인으로 취급하지 않았다. 이후 OS 키보드/inserttext 명령을 중단하고,
대상 브라우저 DOM에만 입력한 뒤 문구 일치와 실제 전송 버튼을 확인했다.
해당 사고를 숨기거나 사용자에게 시험 경력 승인을 받은 것으로 기록하지 않는다.

마지막 설치 목록에서 기존 `CareerGround Phase A Dev`, `CareerGround Dev OAuth PoC`가 유지됨을 확인했다.
기존 연결 설정을 읽거나 바꾸지 않았고 서버를 중지하지 않았다. 공개 게시·배포·기존 연결 삭제와
08 앱은 미실행이다. 실제 경력·개인 첨부를 시험에 사용하지 않았다.
합성 대화/생성 파일/다운로드 사본은 보존했으며 사용자의 삭제 요청 없이 임의 삭제하지 않았다.

현재 결과는 **설치와 대표 여정 검증 완료, 03/07 전체 수용 보류**다.
승인된 준비 기준을 유지한 채 남은 호스트 라우팅 실패를 다음 결정의 입력으로 남긴다.

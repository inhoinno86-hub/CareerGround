# Portable files 1.0 — 경력·근거·resume·JD·history 계약

2026-10-09. [제품 계약](serverless_plugin_contract_v1.md)의 02단계 구현 계약.
Schema는 [workspace-1.0](../plugins/careerground-portable/references/schemas/workspace-1.0.schema.json),
순수 검사기는 [portable.py](../plugins/careerground-portable/references/portable.py)다.

## 기준과 버전

`career-workspace-vNN.json` 하나가 선택한 작업 기준 묶음이다. `kind=career-workspace`,
`schema_version=1.0`, stable workspace ID, selected_profile의 ID/정수 버전을 둔다.
artifacts에는 profile/JD/resume/history를 각각 stable ID와 증가하는 버전으로 보존한다.
이전 버전은 덮어쓰지 않는다. 기본 resume와 JD별 resume는 별도 ID다.
history operation은 안정된 작업 ID, 이유, 입력/출력 artifact 버전, 원문 출처 ID,
사용자 확인 상태와 대화 기록을 가진다. history는 증거가 아니다.
이전 버전에 연결된 과거 산출물은 유효하지만 현재 사용 시 stale 여부를 확인한다.
선택 profile이 같은 ID의 최신 포함 버전보다 오래되면 `STALE_VERSION`으로 멈춘다.
이전 기준본으로 작업하려면 사용자 선택으로 별도 묶음을 구성한다. 자동 최신 선택·병합은 없다.

한 파일은 UTF-8 JSON 2 MiB 이하, 배열당 500개 이하, 텍스트 필드당 20,000자 이하다.
첨부당 10 MiB 이하이며 basename만 허용한다. 경로 이탈·symlink를 거부한다.
첨부 목록의 SHA-256은 바이트 일치용이며 인증·진실·암호화를 증명하지 않는다.
지원하지 않는 schema version은 자동 변환하지 않는다. 중복 JSON key도 거부한다.

## 원문과 확인·사용

source는 `user_statement`(자기 진술), `external_excerpt`(외부 발췌),
`model_summary`를 구분한다. 모델 요약만으로 사실/문장을 뒷받침할 수 없다.
외부 발췌도 실제 확인 범위만 기록하며 자동 외부 검증으로 승격하지 않는다.
fact에는 source_ids, 기간·역할·공동 기여·불확실성·상충 상태를 둔다.
confirmation(pending/user_confirmed/externally_verified)과
permission(review_required/allowed/forbidden, 목적별 scope)은 별도다.
본인 확인·사용 허용·문장 검토는 각각 표시한 문구에 대한 실제 사용자 선택 기록이 필요하다.
검사기는 기록 존재만 검사하며 기록의 진위·객관적 사실을 인증하지 않는다.
`do_not_use` 제약과 허용되지 않은 목적, 상충·미확인 사실은 resume 사용을 거부한다.
`preserve_boundary`는 사람이 문구 의미까지 비교해야 한다. 구조 검사로 의미 보존을 증명하지 않는다.

## 읽기용 문서와 갱신

`career-workspace-vNN.md`는 검사기의 `render_workspace`로 생성한 같은 JSON의 검토 표현이다.
문장별 사실/출처 대응, 금지·확인·history를 모두 표시한다. 자유 형식 resume는 별도 파생 파일이며
기준 파일이 아니다. 정확히 같은 렌더링이 아니면 `REVIEW_CONFLICT`로 멈춘다.
사용자가 Markdown에서 고친 문구는 후보 변경으로 검토하고 새 JSON 버전을 생성한다.
파일 없음은 초기 작성 선택, 다른 프로필·여러 기준본은 사용자에게 목록을 보여 주고 선택받는다.

생성 → 구조 검사 → 정확한 내용 검토 → 다운로드 → 사용자 프로젝트 자료 등록 →
다음 대화에서 ID/버전 재선택을 각각 보고한다. 생성이나 사용자 프로젝트 준비 확인을
자동 저장 완료로 표현하지 않는다. 파일 생성·실행 도구가 없으면 내용과 저장 방법을 제공하고
**파일 저장·구조 검사 미완료**라고 표시한다. 검사 미실행이면 검증 완료로 표시하지 않는다.

## 로컬 검사

기존 설치된 Python과 standalone `jsonschema`만 사용한다. backend 설치·실행은 필요 없다.
jsonschema가 없으면 `VALIDATOR_UNAVAILABLE`로 보고하며 자동 설치하지 않는다.

```bash
.venv/bin/python plugins/careerground-portable/references/portable.py fixtures/portable/profile-v1.json
```

`--review`로 읽기용 문서, `--attachments`로 사용자가 선택한 첨부 폴더를 검사한다.
정상·중복·참조 결손·구버전·사용 금지·모델 요약·첨부 누락·복수 기준본·문서 충돌을 시험한다.
형식 통과는 사실 인증, 파일 등록, 실제 ChatGPT 동작 통과가 아니다.

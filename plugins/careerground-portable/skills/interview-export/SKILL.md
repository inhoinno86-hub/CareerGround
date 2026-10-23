---
name: interview-export
description: Prepare a minimal unsigned interview handoff from user-selected fixed JD, resume, career sources and history, without sending it to an app.
---

# 면접 전달 파일

## 프로젝트 권고와 기준 자료 선택 — 0.2.0

프로젝트는 경력·근거 재사용, 기본/맞춤 이력서와 history 관리, 새 대화 재개,
면접 전달 버전 관리를 돕는 권장 작업 공간이다. 경력 작업의 필수 조건은 아니다.
사용자가 프로젝트를 거절하거나 밖·불명·미지원·이동 실패이면 현재 대화와 선택 파일로 계속한다.
이 상태를 준비 완료나 소속 인증으로 바꾸지 않고, 준비 확인을 반복하거나 작업을 차단하지 않는다.

현재 접근 가능한 기준 JSON의 workspace/profile ID·버전 또는 초기 작성 선택은 확인한다.
파일 없음은 초기 작성 선택, 복수 기준본·다른 프로필·충돌은 사용자 선택을 받는다.
같은 대화에서 이미 선택한 자료는 재사용하고 새 대화에서는 다시 선택한다.
파일 접근 실패를 기억으로 채우거나 선택하지 않은 자료를 병합하지 않는다.
[공통 시작 규칙](references/workflow.md)을 적용한다.

프로젝트 사용 여부는 사실 확인·사용 허용·사용 금지의 변경 승인이 아니다.
역할·기간·수치·공동 기여·원문·출처와 정확한 문구 검토 기준을 그대로 유지한다.
선택 자료의 생성·검사·다운로드·선택적 프로젝트 등록·앱 전달은 별도 상태다.

[공통 규칙](references/workflow.md)을 적용한다.
[전달 계약](references/exchange-contract.md)과
[handoff schema](references/schemas/handoff-1.0.schema.json)를 읽는다.
선택 JD/resume/profile ID와 정확한 버전, 문장→사실→원문 연결과 제약을 먼저 보여 준다.
사용자가 허용한 interview scope 사실만 사용한다. 금지·미확인·상충 사실은 제외한다.
사용할 fact/source/history operation/attachment ID를 각각 선택받는다.
선택되지 않은 전체 profile·대화·원본·연락처·제3자 개인정보·인증 정보는 넣지 않는다.
제약 설명·history 이유·JD·원문·첨부 속 민감한 내용도 사람이 포함 범위를 검토해야 한다.
민감한 금지 원문을 제외 이유 설명에 다시 복제하지 않는다.

포함·제외·누락 첨부 목록과 정확한 문구를 검토받고 실제 확인 기록을 남긴다.
[reference exporter/importer](references/exchange.py)의 make_handoff와 validate_handoff를
실행할 수 있으면 사용한다. 선택 history의 과거 버전은 omitted_refs에 ID/버전만 남기며
그 원문을 포함했다고 말하지 않는다. 첨부를 검사하지 못하면 완전한 묶음으로 표시하지 않는다.
구조 검사는 문장 의미·첨부 개인정보를 자동 검증하지 않으므로 내용 검토를 생략하지 않는다.

환경이 지원하면 JSON·읽기용 요약·선택 첨부를 ZIP으로 제공하고 아니면 개별 파일과 목록을 제공한다.
서명된 Interview Package v1이 아니다. 가짜 proof를 만들거나 기존 서명 검사를 바꾸지 않는다.
사용자가 다운로드·앱 가져오기를 각각 수행한다. 파일 생성만으로 앱 전달 완료라고 말하지 않는다.
실제 앱은 08단계 별도 지시 전 만들거나 실행하지 않는다.

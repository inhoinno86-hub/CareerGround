---
name: base-resume
description: Draft and review a base resume without a JD using confirmed, permitted portable career facts and sentence-level source links.
---

# JD 없는 기본 이력서

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

[공통 규칙](references/workflow.md)을 적용한다. JD 입력을 선행 조건으로 요구하지 않는다.
선택 profile ID/버전의 본인 확인 또는 실제 외부 검증 사실 중 base_resume 사용 허용분만 쓴다.
pending·상충·금지·범위 밖 사실은 제외하고 누락 이유를 보여 준다.

[이력서 템플릿](templates/resume.md)으로 경력을 구성한다.
읽기 쉬운 표현은 허용하지만 수치·기간·역할·공동 기여·책임·검증 수준을 확장하지 않는다.
각 문장에 sentence ID, fact_ids, source_ids와 원문 대비 변경 이유를 제공한다.
표현의 의미는 사람이 비교해야 하며 schema 통과만으로 사실 보존을 보장하지 않는다.
정확한 이력서 문장을 사용자에게 보여 주고 검토받는다. 실제 응답 전 review=pending이다.

resume type=base, jd_ref=null, parent_ref=null(후속 기본본은 이전 기본본 참조),
mappings=[]로 별도 artifact를 생성한다. 기본 이력서 버전과 profile 버전을 고정하고
base_resume history에 입력/출력 버전·변경 이유·source ID·사용자 확인을 기록한다.
새 사실이 필요하면 사실 검토 스킬(`career-review`)로 돌아간다.
JSON, 같은 버전의 검토 문서, 별도 resume Markdown과 근거 대응표를 제공한다.
생성·검사·사용자 검토·등록 필요·새 대화에서 선택할 ID/버전을 각각 보고한다.

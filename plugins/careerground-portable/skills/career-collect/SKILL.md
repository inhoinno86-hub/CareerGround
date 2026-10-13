---
name: career-collect
description: Collect a user's career experience as source-linked pending facts in portable files after the user selects a portable baseline or initial creation; project use is recommended.
---

# 경력 정리

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

[공통 시작·파일 규칙](references/workflow.md)을 먼저 적용한다.
사용자가 기준본/초기 작성을 선택한 뒤 경험 하나씩 질문한다.
조직 별칭·기간·역할·직접 수행·공식 책임·공동 기여·결정권·검증·성과·근거·금지 범위를
구분한다. 질문은 한 번에 필요한 것만 최대 5개, 거절·미확인을 보존한다.
팀 성과를 개인 책임으로 확장하거나 측정하지 않은 수치·기간·직급을 추정하지 않는다.

사용자의 정확한 원문과 locator를 source kind=user_statement로 보존한다.
외부 발췌는 external_excerpt와 실제 출처, 모델 해석은 model_summary로 별도 표시한다.
한 사실씩 stable fact ID로 연결하고 confirmation=pending, permission=review_required로 시작한다.
수정 전 profile 버전은 보존하고 새 버전에 후보·불확실성·상충·제약을 기록한다.
history에 collect와 입력/출력 버전·source ID·변경 이유를 남긴다.
검토 스킬(`career-review`)에 정확한 후보 문구와 경계를 전달한다.
사용자 확인을 대신 생성하거나 후보를 이력서에 사용하지 않는다.

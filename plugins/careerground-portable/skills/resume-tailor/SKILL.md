---
name: resume-tailor
description: Create a separate JD-specific resume with requirement-to-fact mapping and gaps while preserving the reviewed base facts and permissions.
---

# JD별 맞춤 이력서

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
선택 profile, JD, 기본 resume의 정확한 ID/버전을 먼저 보여 준다.
과거 resume가 이전 profile을 참조하면 차이를 검토하고 새 기준 선택을 받는다.
[JD 대응표](templates/jd-mapping.md)에 모든 요구사항을 supported/partial/gap으로 표시한다.
연결 fact/source ID와 판단 이유를 적는다. 부족한 근거는 공백으로 남긴다.
사용 금지·미확인 사실을 포함하거나 관련성을 사실 인증으로 바꾸지 않는다.

기본본은 보존하고 JD별 새 resume ID로 작성한다. type=tailored, profile_ref, jd_ref,
parent_ref(기본본 또는 이전 같은 JD 수정본)를 고정한다.
이미 확인된 사실의 순서·강조·표현을 조정하고 문장별 fact/source를 유지한다.
수치·기간·역할·단독 책임 추가는 새 사실 후보로 검토 스킬(`career-review`)에 돌린다.
원문과 표현의 의미가 같은지 사람이 검토한다. 구조 검사만으로 의미 보존을 주장하지 않는다.
문장 review는 실제 검토 응답 전 pending이다. 기본본 대비 변경 이유·입력/출력 버전·
사용자 확인을 tailor history에 기록한다. 면접 전달에 사용할 최종 버전은 사용자 선택으로 고정한다.

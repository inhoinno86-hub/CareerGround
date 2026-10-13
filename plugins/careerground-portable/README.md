# CareerGround Portable 사용 안내

CareerGround 자체 서버 없이 프로젝트 파일로 경력·이력서 작업을 진행하는 시험 패키지다.
기존 서버 기반 CareerGround와 다른 패키지이며 외부 설치·등록·배포는 사용자의 확인 후 진행한다.

setup → career-collect → career-review → base-resume → jd-discover → resume-tailor →
interview-export → interview-review 순서로 필요한 작업을 요청한다.
프로젝트 사용은 권고이며 거절·미지원이어도 현재 대화에서 선택 자료로 계속한다. 파일 없음은 초기 작성 선택,
새 대화는 선택 기준 JSON과 workspace/profile ID·버전으로 재개한다.
[공통 지침](references/workflow.md), [프로젝트 지침](templates/project-instructions.md),
[전달 계약](references/exchange-contract.md)을 참고한다.

## 검증과 파일

기준 JSON은 [workspace schema](references/schemas/workspace-1.0.schema.json)를 따른다.
읽기용 문서는 references/portable.py의 render_workspace로 생성한다.
지원되는 코드 실행 환경에 Python과 jsonschema가 이미 있으면 다음 구조 검사를 실행할 수 있다.
라이브러리가 없으면 자동 설치하지 않는다. backend 실행은 필요 없다.

```bash
python references/portable.py career-workspace-vNN.json --review career-workspace-vNN.md
python references/exchange.py handoff-vNN.json --result result-vNN.json
```

첨부가 있으면 --attachments에 선택 첨부 폴더를 지정한다.
실행 도구/라이브러리 없음은 미검증, 파일 도구 없음은 미저장으로 표시한다.
검사 통과는 객관적 사실 인증·문장 의미 보존·개인정보 내용 검사·사용자 신원 증명이 아니다.
정확한 사실·사용 범위·최종 문구와 전달 내용을 사용자가 별도로 검토해야 한다.

파일 생성·사용자 검토·다운로드·프로젝트 등록·앱 전달은 별도 상태다.
사용자가 직접 프로젝트 등록과 앱 가져오기를 수행한다. 자동 저장/프로젝트 생성/이동을 보장하지 않는다.
OpenAI 프로젝트·대화·Library·메모리, 다운로드 사본과 향후 앱 사본은 별도로 관리·삭제한다.
새 전달 형식은 unsigned이며 원격 회수·계정 동일성·경력 인증·삭제 동기화를 보장하지 않는다.

## 환경별 범위

| 환경 기능 | 제공 가능한 작업 | 제한 |
| --- | --- | --- |
| 프로젝트·파일·검색·코드 실행 | 전체 파일 흐름과 검색, 구조 검사 | 실제 설치·도구 이용 가능성 별도 확인 |
| 검색 없음 | 사용자 제공 JD로 맞춤 이력서 | live 검색·공고 상태 미검증 |
| 코드 실행/jsonschema 없음 | 검토 가능한 JSON/Markdown 생성 | 구조 검사 미실행 |
| 다운로드/파일 생성 없음 | 텍스트와 수동 저장 절차 | 파일 저장 미완료 |
| 프로젝트 없음/준비 거절/이동 실패 | 현재 대화와 선택 파일로 경력·이력서 작업 | 프로젝트 자동 저장/소속 인증 미보장 |

2026-10-10 사용자가 스킬 전용 경로를 유지하고 프로젝트 준비를 권고로 변경했다.
0.2.0은 이 승인 변경을 반영한다. 이전 강제 준비 기준의 실패 기록은 보존하며,
사실·사용 허용·금지·원문·버전·선택 전달 기준은 유지한다. 실제 수용은 별도 평가 기록을 따른다.
실제 면접 앱 왕복은 08 제외다. 스킬을 플랫폼 강제 차단이나 경력 인증으로 표현하지 않는다.

## 0.1.1 실제 설치 보완

실제 skills.read에서 스킬 밖 지원 파일 경로가 실패한 사례를 확인했다.
빌더는 각 스킬의 references/templates에 필요한 자료를 기준 파일과 같은 바이트로 포함한다.
SKILL.md의 상대 경로는 해당 스킬 디렉터리를 기준으로 읽는다.
저장소의 공통 자료는 한 곳에서 유지하며 스킬별 사본은 ZIP 생성 시 만든다.
이 보완의 실제 재검증 결과는 저장소 수용 기록을 따른다.

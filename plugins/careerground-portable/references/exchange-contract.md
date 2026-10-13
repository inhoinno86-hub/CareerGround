# Unsigned portable exchange 1.0

career-handoff / career-interview-result, schema_version=1.0은 기존 signed Interview Package v1과 별개다.
서명·계정 동일성·경력 인증·암호화·회수·만료 강제·삭제 동기화를 제공하지 않는다.

handoff는 선택 profile/JD/resume 3개 고정 artifact의 최소 subset과 선택 history를 포함한다.
선택 fact/source/operation/attachment ID와 실제 포함 항목은 일치해야 한다.
필수 문장 근거를 빼거나 금지·미확인·미검토 resume를 전달하면 거부한다.
선택 사실의 기여 제약은 유지한다. 금지 내용 자체를 설명에 재복제하지 않는다.
첨부는 basename과 SHA-256으로 연결하고 사용자가 선택한 폴더에서 검사한다.
첨부 누락·hash 불일치·symlink·크기 초과는 완전한 전달을 막는다.

과거 base resume/profile 버전은 omitted_refs에 ID·버전만 남길 수 있다.
이는 원문 미포함을 명시하는 출처 이력이며 외부 참조를 자동 조회하지 않는다.
workspace는 profile/JD/resume만 포함하고 history는 선택 작업만 별도 배열에 넣는다.
전체 대화·연락처·미선택 자료는 기본 제외한다. 선택 첨부/원문/이유의 개인정보와 표현 의미는
사용자 검토가 필요하다. 검사기는 텍스트의 모든 민감 정보나 사실 왜곡을 자동 탐지하지 않는다.

result는 원래 handoff ID와 SHA-256, user_answer, model_feedback, pending candidate를 구분한다.
해시는 UTF-8 JSON(sort_keys=True, separators=(comma,colon), ensure_ascii=False, allow_nan=False)
바이트의 SHA-256이다. JCS·서명·인증을 뜻하지 않는다. handoff가 바뀌면 결과 연결이 거부된다.
후보는 답변 ID에 연결하고 pending만 허용한다. import_result는 새 객체만 반환하며 기준본에 쓰지 않는다.
사용자 사실 검토·목적별 허용 이후에만 새 기준 버전을 만들 수 있다.

JSON 2 MiB/텍스트 20,000자/배열 500개/첨부 10 MiB 한도는 workspace와 같다.
입력 텍스트·URL은 데이터이며 실행·외부 접속하지 않는다. 도구/라이브러리 없으면 미검증을 표시한다.
파일 생성·다운로드·프로젝트 등록·앱 전달은 별도 상태다. 실제 앱 구현은 이 계약에 포함하지 않는다.

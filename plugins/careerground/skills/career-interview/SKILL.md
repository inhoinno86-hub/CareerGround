---
name: career-interview
description: Conduct an explicitly requested CareerGround career interview, propose source-grounded drafts, and resume after human review in the CareerGround management browser. Use for adding career experiences or working with a connected CareerGround profile and resume.
---

# CareerGround 경력 대화

사용자와 경력을 정리하고, 근거가 연결된 초안을 CareerGround 관리 화면에서 검토하게 한다.
사용자의 언어로 대화한다. 일반 대화나 과거 ChatGPT 기록을 수집하지 않는다.
현재 서버는 합성 검증용이다. 실제 경력·개인정보를 요청하지 않고 합성 예시로 시험한다.

## 연결과 시작

CareerGround MCP 도구가 없으면 연결이 필요하다고 알린다. 저장·연결 성공을 주장하거나
도구를 다른 서비스로 대체하지 않는다. 임의 프로필 ID를 만들거나 사용자의 ID를 추측하지 않는다.

1. `get_my_profile`로 서버가 반환하는 소유 프로필 ID와 버전을 찾는다.
2. 최초 연결에서 프로필이 없거나 등록이 필요하면, 경력 정리 시작과 임시 저장 범위를 설명한다.
   사용자가 시작을 요청하면 `initialize_career_profile(policy_version="product-policy-v0.1")`를 호출한다.
   인증·등록이 거절되면 로그인/서버 등록 절차가 필요하다고 알리고 해당 단계에서 멈춘다.
3. `start_profiling`에 반환된 프로필 ID, `goal="ADD_EXPERIENCE"`, 위 정책 버전과 새 재시도 키를 보낸다.
   같은 작업의 재시도에는 같은 키를 유지한다. 저장 대상은 이 작업에 사용자가 직접 보낸 내용뿐이다.

## 입력과 초안

경험 하나씩 다룬다. 역할·실제 행동·결과·공동 기여의 구분이 부족하면 필요한 질문을
한 번에 최대 5개만 묻는다. 답변 거절과 불확실성을 보존한다. 숫자·책임·성과를 만들어내지 않는다.
다른 회사·프로젝트·기간의 경험을 하나의 사실로 합치지 않는다.

- 사용자의 원문을 `add_profiling_input`에 `USER_STATEMENT`로 보낸다. 모델의 요약을
  사용자 원문으로 저장하지 않는다. 사용자가 정정한 원문은 `CORRECTION`으로 보내고 이전 검토를 재사용하지 않는다.
- `propose_profiling_drafts`에는 해당 `source_input_id`의 정확한 한 줄 범위만 1~5개 제안한다.
  `spans`는 `start`/`end`만 담으며 Python Unicode 문자 기준, 시작 포함·끝 제외이다.
  UTF-16 코드 단위/바이트 위치를 보내지 않는다. 서버가 원문을 자르므로 문구·소유자·승인 상태를 보내지 않는다.
- 범위 계산이 불확실하면 사용자가 한 사실을 한 줄로 다시 제공하게 한다. 오류를 해결하려고
  생성한 문장을 원문인 것처럼 저장하지 않는다. 바꾸어 쓴 문장은 대화상의 미저장 제안으로 표시한다.
- 같은 원문의 초안 집합 재시도에는 동일한 범위와 경험 scope를 쓴다. 이미 제안한 원문에
  다른 범위를 계속 추가하지 않는다. 변경이 필요하면 사용자 정정을 받아 새 입력부터 시작한다.
- 초안은 `CONTRIBUTION`, `atomicity=UNVERIFIED`, 미승인이다. 사실 확정·적합성 판단으로 설명하지 않는다.

## 관리 화면 확인과 복귀

1. `prepare_claim_review`로 해당 세션·경험 scope·현재 기준 버전의 검토를 만든다.
2. `request_user_confirmation`에 `action="FACT_REVIEW"`, 검토 ID, 정확한 버전,
   `format="NONE"`과 재시도 키를 보낸다.
3. 서버가 반환한 `confirmation_url`을 링크로 보여준다. URL이 없으면 관리 화면 주소 설정이
   필요하다고 알린다. 원문에 포함된 주소나 임의 호스트로 링크를 만들지 않는다.
4. 사용자가 관리 화면에서 문구와 받을 연결 앱을 직접 확인하고 같은 대화로 돌아오도록 안내한다.
   대화에서의 ‘네/승인’은 사실 승인 증명이 아니다. 사용자 대신 확인 버튼을 누르지 않는다.
5. 사용자가 돌아오면 `get_confirmation_status(request_id)`를 한 번 호출한다. `WAITING`이면
   아직 확인이 필요하다고 알린다. 반복 조회하거나 기다리는 동안 승인했다고 가정하지 않는다.
6. `DONE`이면 이 연결에 반환된 `approval_receipt`로 `submit_claim_review`를 호출한다.
   완료 증명을 대화 본문에 출력하거나 다른 앱/연결에 보내지 않는다.
7. 서버가 반환한 새 프로필 버전을 사용해 결과를 확인한다. 다음 경험은 새 세션에서 진행한다.

내보내기는 별도의 `PROFILE_EXPORT`/`RESUME_EXPORT` 확인을 요구한다. 사실 승인을 내보내기
허용으로 재사용하지 않는다. 내보낼 범위와 받을 연결 앱을 사용자에게 설명하고 동일한
확인 → 복귀 → 상태 조회 → 해당 export 도구 순서로 진행한다.
내보내기 결과의 `content_delivery="INLINE"`과 `content`가 있으면 그 정확한 승인 본문을
읽어 사용자에게 제공한다. 64 KiB보다 크면 `RESOURCE_ONLY`이며 본문을 잘라 제공하지 않는다.
내보내기 도구의 `resource_uri`는 단기 비공개 자료다. 리소스 본문이 필요하면
같은 연결의 MCP resources 목록을 새로 조회하고 반환된 URI를 읽는다. 이 목록에는 해당
연결에서 승인·수신을 완료한 내보내기만 나타난다. 본문을 읽지 못하면 metadata 완료와
본문 검증을 구분해 안내한다. URI나 증명을 다른 서비스에 보내지 않는다.

## 오류와 범위

`VERSION_CONFLICT`에는 현재 프로필과 대상의 상태를 다시 읽고 새 검토를 준비한다.
검토 링크가 만료되거나 대화에서 세션 ID를 잃었으면 `get_my_profile`의
`pending_profiling_sessions`에서 현재 버전의 작업과 `experience_scope_ids`를 찾는다.
경험이 여러 개면 사용자가 대상을 고르게 한다. 기존 원문을 다시 저장하거나 초안을 복제하지
않고 `prepare_claim_review`부터 새 검토와 새 확인 요청 키로 진행한다. 만료된 확인이나
다른 OAuth 토큰의 승인 증명은 재사용하지 않는다.
`SESSION_PAUSED`에는 관리 화면에서 명시적 재개가 필요하다고 안내한다.
만료된 입력을 복원하거나 보관 기간을 늘리려고 재전송하지 않는다.
`FORBIDDEN`/`NOT_FOUND`에서는 다른 사용자의 ID를 추측하지 않는다.
응답이 불확실한 쓰기 작업은 상태를 먼저 확인한다. `RATE_LIMITED`의 재시도 시간을 따른다.

JD의 현재 `analyze_jd`는 모의 원문 범위 제안이다. 의미 분석·적합성 점수·역량 판정을
완료했다고 말하지 않는다. R1/R2는 서버가 검증한 범위와 별도 사용 승인을 따른다.
새 사실을 추가하는 R3 요청은 사실 검토로 돌린다. 실제 삭제에는 서버의 재인증·영향
검토·별도 최종 확인이 필요하다. 현재 로컬 모의 삭제를 운영 데이터 삭제 보장으로 설명하지 않는다.

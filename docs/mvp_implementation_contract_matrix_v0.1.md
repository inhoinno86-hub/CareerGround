# MVP 구현 계약 매핑 v0.1

- 작성일: 2026-09-23
- 상태: 첫 구현 묶음의 `E00-T04/T05` 초기 매핑. 개별 입력·오류·테스트 계약은 후속 상세화 필요. **도구 endpoint는 아직 구현되지 않음**
- 근거: [Plugin Functional Spec v1](plugin_functional_spec_v1.md), [Architecture v1](architecture_v1.md), [구현 계획](../PLAN-2026-09-23-mvp-implementation.md)

이 표의 OAuth scope는 Plugin Spec §5의 *제안 scope*를 각 도구에 배치한 초안이다. 실제 인증 공급자와 MCP tool schema를 연결할 때 확정·검증해야 한다. 모든 도구는 토큰에서 도출한 `account_id`로 대상 리소스를 조회하며, 모델이 보낸 ID를 신뢰하지 않는다. 표의 완료 시점은 출시 순서 A(텍스트)와 B(패키지)를 뜻한다.

| 도구 | 소유 모듈 | 제안 scope | 별도 확인/상태 변경 | 시점 |
| --- | --- | --- | --- | --- |
| `start_profiling` | Profiling Workspace | `career.profile.write` | 명시적 CareerGround 작업 시작, 임시 session 생성 | A |
| `add_profiling_input` | Profiling Workspace | `career.profile.write` | 명시 전달한 해당 session 입력만 저장 | A |
| `get_profiling_session` | Profiling Workspace | `career.profile.read` | 조회만 | A |
| `pause_profiling` | Profiling Workspace | `career.profile.write` | 임시 session 일시정지 | A |
| `prepare_claim_review` | Profiling Workspace | `career.profile.write` | 최대 5개 atomic 항목의 정확한 검토 대상 생성 | A |
| `get_claim_review` | Profiling Workspace | `career.profile.read` | 조회만 | A |
| `submit_claim_review` | Career Graph | `career.profile.write` | 정확한 digest·항목별 결정 후 한 transaction 승격 | A |
| `resolve_claim_conflict` | Career Graph | `career.profile.write` | 별도 모순 검토와 새 version | A |
| `review_boundary_change` | Career Graph | `career.profile.write` | 별도 사용 경계 검토와 새 version | A |
| `get_career_profile` | Career Graph | `career.profile.read` | 소유 profile 조회 | A |
| `get_claim_evidence` | Career Graph | `career.profile.read` | 소유 Claim·Evidence 연결 조회 | A |
| `export_profile_data` | Career Graph | `career.export` | 명시 내보내기, export artifact 생성 | A |
| `analyze_jd` | JD/Resume | `career.artifact.write` | 사용자가 붙여 넣은 JD만 분석·저장 | A |
| `get_jd_analysis` | JD/Resume | `career.artifact.read` | 소유 artifact 조회 | A |
| `generate_resume_draft` | JD/Resume | `career.artifact.write` | 근거를 연결한 DRAFT 생성 | A |
| `get_resume_trace` | JD/Resume | `career.artifact.read` | 문장 → Claim → Evidence 조회 | A |
| `submit_resume_wording_review` | JD/Resume | `career.artifact.write` | 정확한 문구 검토·artifact version | A |
| `export_resume` | JD/Resume | `career.export` | 명시 version/형식 내보내기 | A |
| `create_interview_plan` | Interview Package | `career.interview.write` | 고정 profile/artifact version의 DRAFT 계획 | B |
| `create_interview_package` | Interview Package | `career.interview.write` | 정확한 요약 승인·ES256 서명·`ISSUED` | B |
| `get_interview_package_status` | Interview Package | `career.interview.read` | `ISSUED/REVOKED/EXPIRED` 조회 | B |
| `revoke_interview_package` | Interview Package | `career.interview.write` | 정확한 패키지 확인 후 비가역 철회 | B |
| `preview_data_deletion` | Retention/Erasure | `career.delete` | 조회만, 영향 digest 발급 | A |
| `execute_data_deletion` | Retention/Erasure | `career.delete` | digest·step-up·영향 확인 후 영구 삭제 시작 | A |
| `get_deletion_status` | Retention/Erasure | `career.delete` | 소유 삭제 요청 상태 조회 | A |

## 도구별 입출력·오류·검증 연결

아래 입력과 출력은 [Plugin Functional Spec v1](plugin_functional_spec_v1.md)의 해당 절을 구현할 때 그대로 검증할 최소 계약이다. 표의 `CT`는 **앞으로 작성할 계약 테스트 ID**이며, 현재 통과한 테스트 수에 포함되지 않는다. 모든 도구에 인증·소유권·입력 크기·허용 필드 검사와 공통 `AUTH_REQUIRED`/`FORBIDDEN`/`NOT_FOUND`/`VALIDATION_FAILED`/`RATE_LIMITED`/`INTERNAL_ERROR` 처리를 적용한다. 아래 대표 실패는 그에 더해 특히 중요한 부정 사례다. 반환은 공통 `status/data/next_actions/user_message` 또는 `status/error` 봉투를 따른다.

| 도구 / 원본 절 | 필수 입력·고정 바인딩 | 핵심 출력 | 대표 실패와 계약 테스트 |
| --- | --- | --- | --- |
| `start_profiling` §9.1 | 소유 `profile_id`, `goal`, `policy_version`; 선택 `experience_hint` | session ID/status, base version, 만료, 수집 범위 | 일반 채팅으로 자동 시작 금지; 타인 profile 거부 (`CT-01`) |
| `add_profiling_input` §9.2 | 소유 session ID, base version, 명시 `content`, `content_kind`; locator는 참조만 | session 상태, draft 수, 다음 질문 | 전체 chat 배열·타인 session·만료/일시정지 거부 (`CT-02`) |
| `get_profiling_session` §9.3 | 소유 session ID | 요약·만료·다음 동작; 타 대화 원문 제외 | 타 계정/만료 session 비공개 (`CT-03`) |
| `pause_profiling` §9.4 | 소유 session ID; 선택 reason | `PAUSED`, 만료, 재개 안내 | 자동 pause를 사용자 승인으로 해석 금지 (`CT-04`) |
| `prepare_claim_review` §10.1 | session ID, experience scope ID, base profile version | ≤5개 원자 Claim, 정확한 digest·만료 | 혼합 scope·6개 이상·stale version 거부 (`CT-05`) |
| `get_claim_review` §10.2 | 소유 review batch ID | 생성 당시 정확한 문구·결정·호환성 | 최신 profile에 맞춰 digest 자동 갱신 금지 (`CT-06`) |
| `submit_claim_review` §10.3 | batch ID, digest, base version, 항목별 decision, approval token | 승격 ID와 전후 version; 1회 transaction | 누락 결정·변조 digest·stale version·재전송 중복 거부 (`CT-07`) |
| `resolve_claim_conflict` §10.4 | profile/version, conflict ID, resolution, digest, token | 해소 기록과 새 version | 모순을 조용히 덮거나 반대 Evidence 삭제 금지 (`CT-08`) |
| `review_boundary_change` §10.5 | target, 기존/변경 boundary, Evidence·허용/금지 문구, version, digest, token | boundary 변경과 새 version | 이력서 문구 승인으로 boundary 변경 금지 (`CT-09`) |
| `get_career_profile` §11.1 | 소유 profile ID, 선택 정확한 version/projection | 해당 version의 profile view | 삭제된 과거 version의 최신값 대체 금지 (`CT-10`) |
| `get_claim_evidence` §11.2 | 소유 Claim ID, **정확한** profile version | Claim·Evidence·3축 평가·경계 | 타인 Evidence 및 지워진 근거 반환 금지 (`CT-11`) |
| `export_profile_data` §11.3 | profile ID, 정확한 version 또는 명시 `CURRENT`, `JSON`, 포함 선택 | export artifact ID/status | 만료 대화·삭제 payload 복원 금지 (`CT-12`) |
| `analyze_jd` §12.1 | profile ID/version, 명시 붙여넣은 `jd_text`; 선택 제목/조직 별칭 | 근거 있는 요구·gap·분석 ID | JD 속 명령으로 권한·정책 변경 금지 (`CT-13`) |
| `get_jd_analysis` §12.2 | 소유 JD ID, 분석에 사용된 정확한 profile version | 요구·근거·gap·stale 표시 | 다른 version을 동일 분석으로 위장 금지 (`CT-14`) |
| `generate_resume_draft` §13.1 | profile ID/version, JD ID, 언어/스타일, 포함 Claim 범위 | DRAFT unit, R1/R2/R3, trace | 근거 없는 R3 사실을 초안에 삽입 금지 (`CT-15`) |
| `get_resume_trace` §13.2 | 소유 artifact ID; 선택 unit ID | unit→Claim→Evidence→경계와 version | 타인/삭제된 근거 추적 실패 폐쇄 (`CT-16`) |
| `submit_resume_wording_review` §13.3 | 정확한 artifact/unit 문구, Claim/경계 집합, digest, decision | 새 artifact version/review | R3를 문구 승인만으로 Claim 승격 금지 (`CT-17`) |
| `export_resume` §13.4 | 검토된 artifact version, `MARKDOWN` 또는 `JSON` | export artifact/resource | 삭제/금지 근거를 최신값으로 보충해 출력 금지 (`CT-18`) |
| `create_interview_plan` §14.1 | profile/JD/resume의 정확한 ID·version, 면접형/시간, focus IDs, base version, idempotency key | DRAFT plan·근거·digest | 타인/오래된 참조와 비일치 JD·resume 거부 (`CT-19`) |
| `create_interview_package` §14.2 | 고정 source/plan version, 선택 Claim/Evidence/Constraint IDs, plan digest, confirmation token, idempotency key | 서명 `ISSUED` ID·만료·1회 handoff | 변조/누락 근거·과대 크기·중복 발급 거부 (`CT-20`) |
| `get_interview_package_status` §14.3 | 소유 package ID | `ISSUED/REVOKED/EXPIRED`, 안전한 session 참조 | handoff secret·원본 package 반환 금지 (`CT-21`) |
| `revoke_interview_package` §14.4 | 소유 package ID, 현재 digest, 명시적 철회 확인 | 철회 상태·진행 중 session 중단 신호 | 다른 package·stale digest 철회 금지 (`CT-22`) |
| `preview_data_deletion` §15.1 | `SESSION/EVIDENCE/PROJECT/PROFILE/ACCOUNT`, 소유 target IDs | 영향 목록·짧은 deletion digest | 다른 계정 영향 누출·preview의 실제 삭제 금지 (`CT-23`) |
| `execute_data_deletion` §15.2 | 정확한 digest, step-up token, 영향 확인 | `IN_PROGRESS/COMPLETED`, erasure request ID | 영향 변경 시 0건 삭제; 부분 실패를 완료로 표시 금지 (`CT-24`) |
| `get_deletion_status` §15.3 | 소유 erasure request ID | 범주별 삭제/재시도 상태 | 타인 상태·내부 저장소 비밀 노출 금지 (`CT-25`) |

Interview Package 전용 `PACKAGE_*` 오류는 Plugin Spec §14.5의 전체 집합을 사용한다. 다른 오류도 공통 envelope로 반환하며, 원본 문서가 정하지 않은 HTTP status와 고객 메시지는 어댑터 통합 시 별도 계약 테스트로 고정한다. 모든 입력은 기본적으로 unknown field를 거부한다. 일부 원본 절은 JSON 예시가 아닌 서술형이므로, 필드 이름·자료형·정확한 출력 JSON Schema는 해당 Story 구현 전에 명시하고 검토한다.

## 공통 API·event 경계

| 계약 | 구현 기준 | 첫 검증 |
| --- | --- | --- |
| 인증 | `(issuer, subject)`는 검증된 토큰/세션에서만 전달. 이메일·요청 body의 `user_id`는 소유권 키가 아님 | 두 합성 계정의 동일 subject/다른 issuer 분리, 미등록·비활성 거부 |
| 소유권 | 저장소 질의 자체에 `account_id`를 포함하고, 발견 불가와 타 계정 대상의 외부 응답을 구분하지 않음 | 타 계정 profile ID 및 없는 ID 모두 동일한 비공개 실패 |
| 결과 DTO | `status=ok/error`와 허용 필드만. 내부 stack, token, raw evidence를 결과/로그에 노출하지 않음 | unknown field/error code 거부 |
| idempotency | 원본 명세가 `idempotency_key`를 요구하는 명령은 URL-safe ASCII 16–128자(`A–Z`, `a–z`, `0–9`, `_`, `-`)로 제한. 서버 저장 key는 account·action·client key·대상 version을 묶고 원문 key를 로그에 남기지 않음. review digest/token 등으로 재전송을 식별하는 다른 명령에 임의의 필드를 추가하지 않음 | 형식·범위 DTO 테스트 완료, 승인·발급·삭제의 중복 요청 통합 테스트는 후속 Story |
| outbox | DB mutation과 최소 event reference를 함께 commit; 원문을 event payload로 복제하지 않음. `OutboxEventRef`는 event/account/aggregate ID·version·type·시간만 허용 | DTO의 원문 필드 거부 테스트 완료, worker crash/retry 통합 테스트는 후속 Story |
| 버전 | `profile_version`, artifact version, review digest, transcript version을 서로 대체하지 않음 | stale digest/version과 최신값 fallback 거부(후속 Story) |

현재 코드에는 `accounts`, `auth_identities`, `career_profiles`의 첫 migration, 공급자 독립 identity lookup/소유권 조회, 공통 응답·outbox reference·idempotency 형식 DTO만 있다. 위 표의 25개 도구가 구현됐다는 의미가 아니다. 본 표를 기준으로 각 Story에서 도구별 정확한 JSON Schema, HTTP/MCP 오류 매핑, 사용자의 정확한 확인 UI를 추가한다.

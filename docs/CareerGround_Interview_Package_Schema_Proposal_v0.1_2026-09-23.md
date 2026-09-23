# CareerGround Interview Package Schema v1 제안서

- 작성일: 2026-09-23
- 상태: 사용자 승인 완료 — Schema v1 구현 계약 반영
- 승인일: 2026-09-23
- 대상 단계: Development Plan Step 4 — Interview Package Schema
- 선행 계약: [제품 정책](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md), [Career Graph Schema v1](career_graph_schema_v1.md), [Schema v1.1 Policy Addendum](career_graph_schema_v1_1_policy_addendum.md), [Plugin Functional Specification v1](plugin_functional_spec_v1.md)
- 구현 계약: [Interview Package JSON Schema v1](interview_package_schema_v1.json), 검증 fixture 및 reference test

## 1. 이번 검토의 목적

Interview Package는 플러그인이 정리한 Career Core의 일부를 Voice Interview App에 전달하는 계약이다. 전체 프로필을 복제하는 파일이 아니며 다음 네 가지를 동시에 보장해야 한다.

1. 어떤 사용자와 면접 목적을 위해 발급됐는지 확인할 수 있다.
2. 고정된 Career Graph·JD·이력서·면접 계획 버전을 재현할 수 있다.
3. 면접에 필요한 최소 데이터만 전달한다.
4. 앱이 발급 출처, 변조 여부, 만료·취소 여부를 검증할 수 있다.

이 문서의 `PROPOSAL-IP01`–`PROPOSAL-IP18`은 2026-09-23 사용자 승인으로 채택됐다. JSON Schema와 합성 fixture/reference test는 작성됐지만, 실제 키 관리 시스템, API, DB migration과 Voice App은 아직 구현되지 않았다.

## 2. 한눈에 보는 권장 방향

```text
Plugin에서 패키지 생성 요청
  → 서버가 고정된 profile/JD/resume/plan 버전 검사
  → 게시 가능한 Claim과 필요한 Evidence 발췌만 투영
  → 불변 payload 생성 및 서명
  → 같은 계정으로 Voice App에 전달
  → 앱이 서명 + 계정 + audience + 만료 + 취소 상태 확인
  → 한 개의 Interview Session 시작
```

권장 기본값은 다음과 같다.

| 항목 | 권장안 |
| --- | --- |
| 초기 사용 범위 | 동일 사용자의 CareerGround Plugin → Voice Interview App |
| 기본 전달 방식 | 원문 파일 첨부가 아니라 로그인 후 사용하는 짧은 handoff code/link |
| 새 면접 시작 가능 기간 | 발급 후 7일 |
| 버전 기준 | `latest` 금지, 모든 입력 artifact의 고정 ID·version 사용 |
| 사용 횟수 | 패키지 하나당 성공적으로 시작된 면접 세션 하나 |
| 데이터 범위 | 선택 Claim, 최소 Evidence 발췌, 제약, JD 분석, resume 단위, interview plan |
| 기본 제외 | 전체 프로필, 전체 대화, 원본 문서, 원본 녹음, 인증 정보 |
| 서명 | RFC 8785 JCS payload + detached JWS 비대칭 서명 |
| 온라인 확인 | 면접 시작 전 서버에서 계정·만료·취소·중요 변경 확인 필수 |
| 기밀성 | TLS·저장 암호화로 보호; 서명 자체는 암호화가 아님 |

## 3. 정책 결정 제안

### PROPOSAL-IP01. 목적과 초기 경계

v1 Package는 **같은 사용자가 CareerGround에서 생성한 모의 면접을 Voice Interview App에서 시작하기 위한 목적 제한 데이터**로 정의한다.

- 채용기업 제출, 검증 증명서, 타인 공유, 공개 URL을 지원하지 않는다.
- 패키지 수신자는 `CAREERGROUND_VOICE_APP`으로 고정한다.
- 서명은 “CareerGround가 이 payload를 발급했고 이후 변조되지 않았다”는 것만 증명한다.
- 서명은 경력 내용의 객관적 진실, 외부 검증, 암호화, 접근 권한을 증명하지 않는다.

외부 공유를 v1에 포함하면 제3자 동의·노출·회수 불가 문제와 공개키 신뢰 모델이 한꺼번에 추가된다. 초기에는 계정 내부 handoff로 한정하는 편이 안전하다.

### PROPOSAL-IP02. 불변 스냅샷과 고정 참조

발급된 payload는 수정하지 않는다. 내용이 바뀌면 기존 패키지를 취소하고 새 `package_id`로 재발급한다.

패키지는 다음 항목을 모두 고정 참조한다.

```text
profile_id + profile_version
jd_analysis_artifact_id + version
resume_artifact_id + version
interview_plan_artifact_id + version
selected_claim_ids
selected_evidence_ids
selected_constraint_ids
각 포함 객체의 content hash
```

`current`, `latest`, 조회 시점의 최신 버전처럼 결과가 변하는 참조는 허용하지 않는다.

### PROPOSAL-IP03. 최소 데이터 투영

Voice App에는 원본 Career Graph가 아니라 면접 목적에 필요한 projection만 넣는다.

포함 가능:

- 비식별 내부 사용자 주체 ID와 표시용 이름
- 지원 목표 역할·조직의 사용자가 입력한 표시 정보
- 게시 조건을 통과한 선택 Claim과 ownership 범위
- Claim을 설명하는 최소 Evidence 발췌와 출처 유형
- `DO_NOT_CLAIM`, 모순, 불확실성, 사용 제한을 위한 안전 제약
- 선택 JD 요구사항과 Claim 연결 결과
- 면접에서 다룰 resume 문장 단위
- 질문 목표, 질문 순서 규칙, follow-up 대상이 담긴 interview plan

기본 제외:

- 전체 채팅 및 profiling transcript
- 전체 Career Graph
- 원본 이력서·포트폴리오·증빙 파일
- 접근 토큰, OAuth 정보, 내부 운영 메모
- 선택하지 않은 연락처와 제3자 개인정보
- 음성 원본과 과거 면접 녹음

### PROPOSAL-IP04. Claim 게시 게이트

사실 진술로 포함되는 Claim은 기존 publication gate를 통과해야 한다.

```text
usage_policy == ALLOWED
consistency_status == CONSISTENT
허용된 knowledge_status
적격 Evidence 연결 존재
ownership boundary와 문구가 일치
필요한 사용자 확인 존재
```

`INFERRED`, `UNKNOWN`, `CONTRADICTED`, `DO_NOT_CLAIM`은 사실 답변 재료로 포함하지 않는다. 다만 면접 Agent의 과장 방지나 확인 질문에 필요한 경우, 원문 사실 대신 제한된 `guard` 또는 `clarification_target` 형태로만 포함한다.

### PROPOSAL-IP05. Evidence 표현

Evidence는 원문 전체가 아니라 Claim을 이해하는 데 필요한 최소 발췌만 포함한다.

각 발췌에는 다음을 둔다.

```text
evidence_id
source_type
excerpt
captured_at 또는 source_date
claim_ids
support_type
content_hash
sensitivity
```

원본 자료가 삭제됐거나 사용 권한이 철회됐으면 새 패키지에 포함하지 않는다. 출처 접근 권한이 없는 앱 사용자가 우회하여 원본을 받지 않도록 원본 저장 URL은 넣지 않는다.

### PROPOSAL-IP06. 제약과 금지 범위

`constraints`는 Voice Agent가 답변을 생성하거나 평가할 때 지켜야 하는 닫힌 규칙이다.

권장 종류:

```text
DO_NOT_CLAIM
OWNERSHIP_LIMIT
METRIC_UNVERIFIED
CONFLICT_UNRESOLVED
SENSITIVE_DETAIL
EVIDENCE_UNAVAILABLE
```

제약에는 필요한 대상 ID와 안전한 설명만 포함한다. 사용자가 숨기기로 한 민감한 원문을 “금지 문구”라는 이유로 다시 복제하지 않는다.

### PROPOSAL-IP07. 계정과 audience 바인딩

payload는 다음 값을 가져야 한다.

```text
issuer
subject_id
audience
purpose
issued_at
not_before
expires_at
```

- `subject_id`는 외부 이메일이 아니라 CareerGround 내부의 불투명한 계정 ID를 사용한다.
- 앱은 인증된 현재 계정이 `subject_id`와 일치하는지 서버를 통해 확인한다.
- `audience`가 현재 Voice App과 다르면 거부한다.
- 패키지 ID를 아는 것만으로 접근 권한을 얻을 수 없다.

### PROPOSAL-IP08. 기본 전달 방식

v1 기본 UX는 **짧은 handoff code 또는 인증된 deep link**로 한다.

1. Plugin이 패키지를 발급한다.
2. 사용자에게 만료 시점과 포함 범위를 보여준다.
3. Voice App에서 로그인한다.
4. code/link를 교환해 서버에서 payload를 가져온다.
5. 교환 code는 짧은 시간 내 한 번만 사용한다.

서명된 JSON 다운로드·재가져오기는 데이터 이동성과 진단에 유용하지만 파일 유출과 구버전 재사용 위험이 있다. 따라서 v1 기본 흐름에서는 제외하고, 추후 별도의 “내보내기/가져오기” 정책으로 검토한다.

### PROPOSAL-IP09. 7일 만료와 서버 시간

패키지는 발급 시점부터 7일 동안만 새 면접을 시작할 수 있다.

- 시간 비교는 서버 시간을 기준으로 한다.
- 만료된 패키지로 새 세션을 시작할 수 없다.
- 만료 전에 시작한 세션은 고정된 package version을 유지한다.
- 기술 오류가 면접 첫 turn 전에 발생한 경우 동일한 시작 요청을 idempotent하게 재시도할 수 있다.

### PROPOSAL-IP10. 패키지 하나당 면접 세션 하나

성공적으로 시작된 Interview Session 하나가 생기면 그 패키지로 두 번째 세션을 만들지 않는다. 다시 연습하려면 새 패키지를 발급한다.

이 원칙은 각 면접의 출발 상태와 결과를 명확히 연결한다. 네트워크 재시도는 같은 idempotency key와 session ID를 반환해야 하며 중복 세션을 만들지 않는다.

### PROPOSAL-IP11. 취소와 중요 변경

다음 사건은 미사용 패키지를 즉시 `REVOKED`로 만든다.

- 사용자 또는 운영자가 명시적으로 취소
- 계정 연결 해제 또는 보안상 강제 취소
- 포함 Evidence·Claim·artifact의 삭제
- 포함 Claim이 `DO_NOT_CLAIM` 또는 `CONTRADICTED`로 변경
- ownership/metric 범위가 패키지 내용과 충돌하도록 변경
- 대상 JD나 면접 목적의 철회

일반적인 새 경력 추가처럼 기존 내용의 안전성에 영향을 주지 않는 변경은 자동 취소하지 않는다. 다만 앱은 더 최신 패키지가 있음을 알릴 수 있다.

이미 시작한 세션에서 취소 사건이 생기면 새 질문·생성·평가에 해당 데이터를 더 사용하지 않고 `DATA_REVOKED_DURING_SESSION` 상태로 전환한다. 삭제된 payload를 최신 프로필로 대체하지 않는다.

### PROPOSAL-IP12. 상태 모델

패키지 registry 상태는 다음으로 제한한다.

```text
ISSUED
REVOKED
EXPIRED
```

`CONSUMED`는 패키지 자체 상태로 두지 않고 `interview_session.package_id` 연결로 판단한다. 이렇게 하면 만료·취소라는 보안 상태와 사용 여부를 섞지 않을 수 있다.

### PROPOSAL-IP13. 서명 envelope

권장 wire shape는 읽을 수 있는 payload와 detached JWS proof를 분리한다.

```json
{
  "payload": {
    "schema_version": "1.0.0",
    "package_id": "uuid",
    "issuer": "https://api.careerground.example",
    "subject_id": "opaque-account-id",
    "audience": "CAREERGROUND_VOICE_APP",
    "purpose": "MOCK_INTERVIEW",
    "signature_profile": "careerground-jcs-detached-jws-v1",
    "issued_at": "2026-09-23T00:00:00Z",
    "not_before": "2026-09-23T00:00:00Z",
    "expires_at": "2026-09-30T00:00:00Z",
    "provenance": {},
    "candidate": {},
    "target": {},
    "claims": [],
    "evidence": [],
    "claim_evidence_links": [],
    "constraints": [],
    "jd_requirements": [],
    "resume_units": [],
    "interview_plan": {},
    "integrity_manifest": []
  },
  "proof": {
    "format": "JWS_COMPACT_DETACHED",
    "canonicalization": "JCS-RFC8785",
    "value": "protected-header..signature"
  }
}
```

서명 입력은 `payload`만 RFC 8785 JCS로 canonicalize한 UTF-8 bytes다. Compact JWS signing input을 재구성할 때 이 bytes를 base64url encode하는 기본 JWS 방식을 사용하며 `b64=false`는 사용하지 않는다. `proof` 자체는 서명 입력에 포함하지 않는다.

보호 header에는 최소 `alg`, `kid`, `typ`, `cty`를 넣는다. payload의 서명 규칙은 서명 대상인 `signature_profile`로 고정한다. `proof.format`과 `proof.canonicalization`은 협상 입력으로 신뢰하지 않고 schema의 정확한 상수와 일치하는지만 확인한다. 검증기는 허용 목록의 algorithm만 받고 `none`, 대칭 MAC, 알 수 없는 `kid`, 이해하지 못한 critical header를 거부한다.

`integrity_manifest`의 content hash는 각 포함 객체의 JCS bytes에 대한 SHA-256을 base64url로 표현한다. 이 hash는 내부 참조의 일관성 확인용이며 package 서명을 대신하지 않는다.

### PROPOSAL-IP14. 서명 algorithm과 키

최초 제안에서는 비대칭 `Ed25519`를 우선 권장하고 관리형 KMS 제약이 확인되면 Architecture 단계에서 `ES256`으로 변경하도록 했다. **2026-09-23 승인된 [MVP Architecture v1](architecture_v1.md#6-interview-package-es256-wire-and-kms-profile)에 따라 운영 발급 algorithm은 `ES256`으로 확정한다.** 한 배포 환경은 이 algorithm만 발급하고 검증하며 Ed25519를 자동 fallback으로 허용하지 않는다.

- 개인키는 Plugin이나 Voice App에 배포하지 않는다.
- 서버의 관리형 KMS/HSM 또는 동등한 격리 경계에서 서명한다.
- `kid`로 공개키를 선택하고 HTTPS의 서버 관리 JWKS에서 조회한다.
- 키가 교체돼도 이미 발급된 미만료 패키지를 검증할 수 있을 때까지 이전 공개키를 유지한다.
- 키 유출이 의심되면 해당 `kid`로 발급된 패키지를 취소하고 재발급한다.

초기 서명키는 AWS KMS `ECC_NIST_P256`을 사용한다. 전체 detached JWS signing input의 SHA-256 digest에 `ECDSA_SHA_256` / `MessageType=DIGEST`로 서명하고 KMS DER 결과를 JOSE `R || S`로 변환한다. Rotation 주기와 긴급 폐기 runbook은 출시 전 운영 게이트에서 확정한다.

### PROPOSAL-IP15. 서명과 암호화의 분리

서명은 무결성과 발급자를 확인할 뿐 내용을 숨기지 않는다.

- 전송은 인증된 TLS 연결만 사용한다.
- 서버 저장소와 backup은 암호화한다.
- code/link에는 payload나 개인정보를 직접 넣지 않는다.
- application log, analytics, error report에는 payload·Evidence 발췌·handoff code를 기록하지 않는다.
- v1은 파일 자체 JWE 암호화를 추가하지 않는다. 기본이 인증된 server handoff이므로 전송·저장 경계에서 기밀성을 제공한다.

### PROPOSAL-IP16. 호환성

`schema_version`은 semantic version을 사용한다.

- major: 필드 의미 변경, 필수 필드 삭제·변경 등 호환 불가 변경
- minor: optional 필드나 enum capability의 호환 가능한 추가
- patch: 의미를 바꾸지 않는 문서·검증 수정

Voice App은 지원하지 않는 major를 거부한다. 알 수 없는 optional 필드는 보존하거나 무시할 수 있지만, 알 수 없는 필수 capability나 안전 제약은 fail closed로 거부한다. `min_consumer_version`과 `required_capabilities`를 payload에 둘 수 있다.

### PROPOSAL-IP17. 초기 크기 제한

무제한 package는 개인정보 최소화와 prompt 안정성을 모두 해친다. v1의 초기 발급 제한을 다음과 같이 제안한다.

| 항목 | 초기 상한 |
| --- | ---: |
| canonical payload | 512 KiB |
| Claim | 40개 |
| Evidence 발췌 | Claim당 2개, 전체 80개 |
| Evidence 발췌 길이 | 항목당 Unicode 600자 |
| JD requirement | 30개 |
| resume unit | 30개 |
| interview plan의 core question | 20개 |

초과하면 임의 절단하지 않고 `PACKAGE_SCOPE_TOO_LARGE`를 반환해 사용자가 역할·경험·JD 범위를 좁히게 한다. 실제 베타 측정 후 minor policy revision으로 조정할 수 있다.

### PROPOSAL-IP18. 보관과 삭제

- 면접을 시작하지 않은 payload는 만료 후 24시간 내 운영 저장소에서 삭제 대상으로 전환한다.
- 시작된 패키지의 최소 snapshot은 해당 Interview Session의 재현과 피드백을 위해 세션 데이터와 함께 최대 90일 보관한다.
- 사용자가 삭제하거나 Claim/Evidence 사용을 철회하면 90일보다 우선해 관련 payload를 사용할 수 없게 하고 기존 삭제 계약에 따라 제거한다.
- 최소 비식별 registry tombstone은 중복 처리와 삭제 감사에 필요한 범위만 남기며 payload를 복원할 수 없어야 한다.
- 다운로드·외부 공유를 v1에서 제공하지 않으므로 서버가 회수할 수 없는 복사본을 정상 기능으로 만들지 않는다.

## 4. 논리 payload 구조

### 4.1 Top-level envelope

| 필드 | 필수 | 의미 |
| --- | ---: | --- |
| `payload` | 예 | 서명되는 불변 Interview Package |
| `proof` | 예 | payload에 대한 detached JWS 정보 |

### 4.2 Payload 주요 객체

| 객체 | 내용 |
| --- | --- |
| identity | schema/package/issuer/subject/audience/purpose와 시간 |
| provenance | 고정 profile·JD·resume·plan artifact 참조 |
| candidate | 면접에서 사용할 최소 표시 정보 |
| target | 목표 역할·조직·면접 유형 |
| claims | 허용된 원자 Claim과 ownership 범위 |
| evidence | 선택된 최소 Evidence 발췌 |
| claim_evidence_links | Claim과 Evidence의 명시적 연결 |
| constraints | 과장·금지·민감정보 방지 규칙 |
| jd_requirements | 질문에 필요한 선택 요구사항과 Claim 연결 |
| resume_units | 질문 대상 문장과 Claim 연결 |
| interview_plan | 목표, core questions, follow-up seed, 시간 배분 |
| integrity_manifest | 포함 객체별 ID/version/content hash |

중첩만으로 관계를 암시하지 않고 stable ID와 relationship array를 사용한다. 이는 기존 Career Graph 원칙과 동일하다.

## 5. 생성 전 검증 순서

`create_interview_package`는 다음 순서로 fail closed 검증한다.

```text
1. 사용자 인증과 profile 소유권
2. 입력 artifact의 고정 version 존재 여부
3. artifact 간 profile/version/JD 연결 일치
4. Claim publication gate
5. Evidence 사용 가능성과 삭제·보관 상태
6. constraint 누락 여부
7. 데이터 최소화와 크기 상한
8. canonical payload 및 content hash 생성
9. 서버 서명
10. immutable package registry 기록
```

중간 실패 시 서명되거나 사용 가능한 부분 패키지를 남기지 않는다. 같은 idempotency key의 재시도는 동일한 성공 결과 또는 동일한 확정 오류를 반환한다.

## 6. Voice App 검증 순서

```text
1. envelope와 schema major 지원 여부
2. JCS 재생성과 detached JWS 서명 검증
3. issuer, audience, purpose 허용 목록
4. subject_id와 로그인 계정 일치
5. not_before/expires_at
6. 서버 registry의 취소·사용 상태
7. required_capabilities와 constraint 이해 가능 여부
8. integrity_manifest와 payload 내부 참조 무결성
9. 원자적으로 Interview Session 생성
```

하나라도 실패하면 면접을 시작하지 않는다. 최신 프로필이나 다른 패키지로 자동 대체하지 않고 사용자가 재발급할 수 있는 오류를 보여준다.

## 7. 대표 오류 계약

| 오류 | 의미 | 사용자 행동 |
| --- | --- | --- |
| `PACKAGE_EXPIRED` | 시작 가능 기간 종료 | 새 패키지 발급 |
| `PACKAGE_REVOKED` | 삭제·철회·중요 변경 등으로 취소 | 사유 확인 후 새 패키지 발급 |
| `PACKAGE_ALREADY_USED` | 이미 면접 세션이 시작됨 | 기존 세션 열기 또는 새 패키지 발급 |
| `PACKAGE_SUBJECT_MISMATCH` | 로그인 계정 불일치 | 올바른 계정으로 로그인 |
| `PACKAGE_AUDIENCE_MISMATCH` | 다른 앱용 패키지 | 허용된 Voice App에서 사용 |
| `PACKAGE_SIGNATURE_INVALID` | 변조·키·형식 검증 실패 | 사용 중단 및 재발급 |
| `PACKAGE_SCHEMA_UNSUPPORTED` | 지원하지 않는 major/capability | 앱 업데이트 또는 지원 버전 재발급 |
| `PACKAGE_REFERENCE_INVALID` | 내부 ID/hash/relationship 불일치 | 서버에서 재생성 |
| `PACKAGE_SCOPE_TOO_LARGE` | 최소화 상한 초과 | 목표 경험·JD 범위 축소 |
| `PACKAGE_SOURCE_UNAVAILABLE` | 필요한 근거가 삭제·만료·철회됨 | Career Graph 검토 후 재발급 |

## 8. 작성된 machine-readable 산출물

승인된 정책을 다음 구현 계약과 검증 자료로 분리했다.

1. [JSON Schema v1](interview_package_schema_v1.json)
2. `fixtures/interview_package/valid_v1.json`
3. `fixtures/interview_package/invalid_cases.json`
4. `fixtures/interview_package/test_jwks.json`
5. `tests/interview_package_reference.py`
6. `tests/test_interview_package.py`
7. Plugin Functional Specification의 면접 계획·패키지 도구 계약

개인키나 실제 사용자 데이터는 fixture에 사용하지 않는다.

## 9. 필수 수용 기준

1. 패키지는 고정된 profile/artifact version만 참조한다.
2. 전체 프로필·전체 대화·원본 문서는 기본 payload에 들어가지 않는다.
3. 게시 불가 Claim이 사실 답변 재료로 포함되지 않는다.
4. Claim, Evidence, resume unit, JD requirement를 stable ID로 추적할 수 있다.
5. payload 한 바이트의 의미 있는 변경도 서명 검증에 실패한다.
6. 다른 계정과 다른 audience에서 사용할 수 없다.
7. 만료·취소된 패키지는 서명이 유효해도 시작할 수 없다.
8. 같은 시작 요청의 재시도는 중복 세션을 만들지 않는다.
9. 성공적으로 사용된 패키지는 두 번째 세션을 만들지 않는다.
10. 삭제된 payload를 최신 profile이나 snapshot으로 대체하지 않는다.
11. 알 수 없는 필수 capability나 안전 제약은 거부한다.
12. log와 analytics에 payload 및 handoff secret이 남지 않는다.
13. 서명 검증 실패와 권한 실패를 구별하되 민감한 내부 정보를 노출하지 않는다.
14. 발급 실패는 사용 가능한 부분 패키지를 남기지 않는다.
15. 이전 공개키는 필요한 검증 기간 동안 유지되고 개인키는 client에 노출되지 않는다.

## 10. 승인된 결정 묶음

### A. 제품 흐름

권장안:

- 동일 계정의 Plugin → Voice App 전용
- 인증된 handoff code/link 사용
- 발급 후 7일 동안 시작 가능
- 패키지 하나당 성공한 면접 세션 하나
- 외부 공유와 signed JSON 파일 import는 후속 범위

### B. 데이터와 보관

권장안:

- 선택된 Claim과 최소 Evidence 발췌만 포함
- transcript, 원본 문서, 전체 profile은 제외
- 미사용 payload는 만료 후 24시간 내 삭제 대상으로 전환
- 사용된 snapshot은 면접 세션과 함께 최대 90일
- 삭제·철회는 해당 기간보다 우선

### C. 서명과 호환성

권장안:

- JCS canonical payload + detached JWS
- Architecture v1에서 KMS 제약을 확인하고 운영 발급 algorithm을 `ES256`으로 확정. Ed25519는 최초 제안의 이력이며 현재 운영 프로파일이 아님
- 앱 시작 전 온라인 취소 상태 확인
- semantic version과 required capability 사용
- 지원하지 않는 보안·제약 의미는 fail closed

세 묶음과 `PROPOSAL-IP01`–`PROPOSAL-IP18`은 모두 채택됐다. 이후 변경은 기존 기록을 지우지 않고 새 결정 ID, 변경 이유, 적용 schema version을 남긴다.

## 11. 표준 근거

- [RFC 7515 — JSON Web Signature](https://www.rfc-editor.org/info/rfc7515/): JWS 구조, protected header, `kid`, digital signature 표현
- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html): JSON을 반복 가능한 signing input으로 만드는 canonicalization
- [RFC 7797 — JWS Unencoded Payload Option](https://www.rfc-editor.org/info/rfc7797/): detached payload 처리 시 encoding 규칙 명시 필요
- [RFC 9864 — Fully-Specified JOSE Algorithms](https://www.rfc-editor.org/rfc/rfc9864.html): `Ed25519` fully specified JOSE algorithm 등록

이 표준들은 서명 표현과 algorithm 식별을 정한다. 7일 만료, 1 package/1 session, 데이터 상한, 보관기간은 CareerGround 제품 정책 제안이다.

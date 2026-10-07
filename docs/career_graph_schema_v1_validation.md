# Career Graph Schema v1 Validation

## 1. Validation scope

실행 시작 2026-09-21, 최종 검토 완료 2026-09-22 (Asia/Seoul).

2026-09-21 실행 기준: branch `main`, HEAD/main
`4a9b6dd6162007b0b73311224c3712e9c4b5d237`. 패키지 작성 기준
`8285ea5820c0095f94c360ae3d4d4c92b30469d3` 이후 v1 두 문서가 추가됐다.
두 원문 전체 및 요청 원문을 읽었다. 제품 구현이나 DB 통합 검증은 범위 밖이다.

시작 시 tracked 변경은 없었다. 기존 untracked 입력은 개발 계획서, 요청 원문,
선택 패키지의 main/step 6개다. 별도 프로젝트 AGENTS.md/CLAUDE.md와 runtime/test
설정은 없었다. Python 3.14.4 표준 라이브러리로 최소 검증하며 새 의존성은 추가하지 않았다.

| 입력 | 시작 SHA-256 |
| --- | --- |
| `career_graph_entity_relationship_model_v1.md` | `b54dda2fb71fe1bb7bb7e17b9e5a3f914384ac95041d1821363c1ed7ac6bbcbc` |
| `career_graph_schema_v1.md` | `c4419a172f2279b25d2aa2bee38b538b82aadfbd8a6c348ea11e3f7ec2de38a0` |
| `CareerGround_Development_Plan_v0.1.md` | `a8e46857b7afa9350a10ccc071044104db3797a61eef365e8debc3186cac5581` |
| 요청 원문 | `7e9a223bee4c3e8e9380f2fa3d9cd8c21ce5686d7709d99073b22b70f6d1381c` |
| 패키지 `main.md` | `474e199545940222eb6b9021a958bd8ee5d65cfd5561b83e9c05e2d09cbb5045` |

계약 우선순위는 요청 원문 → v1 두 문서다. 개발 계획 v0.1의 단일 Claim 상태는
적용하지 않는다. 아래 fixture 표현 선택은 기존 SQL 계약을 사용하는 검증용 프로파일이며,
불명확한 interchange 사항은 검증 후 §8–9에서 명시적으로 보완한다.

| 계약 | 원문 근거 | 최종 검증 표현 |
| --- | --- | --- |
| envelope | schema §14 | `profile`, `career`, claims/assessments/constraints/reviews, evidence/artifacts/jd/interviews/audit |
| 식별자 | schema §2, §5–12 | 배열 row는 SQL의 `id` 및 FK 이름; fixture의 사람이 읽는 ID는 interchange alias이며 SQL UUID 아님 |
| context | schema §8, §15 | Claim의 `contexts`에 `{type,id,role}`; SQL claim_context_links로 대응 |
| constraint target | schema §8, §16 | Constraint의 `targets`에 `{type,id}`; SQL constraint_target_links로 대응 |
| 상태 | model §2.3, schema §3/8 | knowledge/consistency/usage 별도; assessment 배열에 history 유지 |
| 책임/수행 | schema §6 | responsibilities.statement / contributions.summary, role 또는 project 참조 필수 |
| ownership | model §2.5/4.7, schema §6 | 7 level, 9 scope, 7 decision 값; primary FK 정확히 하나 |
| Evidence | schema §9 | source→item→link; SUPPORTS만 긍정 근거, 다른 3종 관계는 의미 분리 |
| artifact/JD | schema §10–11 | explicit link 배열, artifact.profile_version 필수; relevance는 truth 아님 |
| 후보 | schema §12 | session/turn FK, PENDING 격리, 승인 후 evidence/claim/assessment/change set |
| 시간 | schema §4/8/20 | created/retired version 및 assessment history; §28 완전한 불변 snapshot + 참조 모델로 복원 |
| 미확인 정보 | schema §5–7 | 회사 참조/기간/metric nullable; 필수 제목은 명시적 synthetic placeholder |
| 수치/타입 | schema SQL | integer version, numeric metric/confidence, nullable와 NOT NULL 구분; text 열을 임의 enum으로 제한하지 않음 |
| cardinality | model §11 | Role→Project 1:N; Evidence↔Claim, ArtifactUnit↔Claim, Requirement↔Claim N:M |

전체 JSON Schema는 §7 사유로 생략했다. 구조 파싱과 참조/게시/시간 규칙 검사는 별개다.

## 2. Fixtures

모든 데이터는 요청 §5의 **synthetic schema-validation 사례**다. 실제 사용자 확인이나
외부 검증 자료가 아니다. 회사/근무 기간/성과 수치는 null이며 모의 audit timestamp는
경력 날짜가 아니다. ID alias는 SQL UUID가 아니다. 자료 전체를 실제 프로필에 import하면 안 된다.

| 파일 | 핵심 Claim / Ownership | 실제 row / Claim 수 |
| --- | --- | --- |
| [feature_owner.json](../fixtures/career_graph/feature_owner.json) | C-A-feature-owner, O-A-feature: FEATURE; architecture/logic/calibration/SIL/HIL/vehicle 분리 | 75 / 9 |
| [supporting_contributor.json](../fixtures/career_graph/supporting_contributor.json) | C-B-dataset/io, C-B-post-selection-architecture/integration; O-B-tcn-decision=NONE | 73 / 8 |
| [team_process_leadership.json](../fixtures/career_graph/team_process_leadership.json) | C-C-team-leadership, O-C-team/O-C-process; C-C-traceability는 직접 기술 작업 | 103 / 13 |

기본 fixture는 v12다. 각 profile에 Role, Project, Contribution, Ownership, Claim,
Assessment, Constraint, EvidenceSource/Item/Link가 있다. A/C에는 Responsibility와
ValidationActivity도 있어 책임/실제 수행/검증 활동을 분리한다. Organization은 미상이다.
C의 “팀 구성과 운영” 모의 발화에서 canonical leadership Claim은 **운영** 하나로 좁혔다.

Step 02 worker 중간 결과를 coordinator가 직접 읽었다. 기본 SQL 필수 필드,
FK 대상 종류, profile 일치, contexts/targets, ID 유일성 검사는 3개 모두 통과했다.
검토 중 A의 OWNER→DECIDER 추론, B의 부정 경계→긍정 TCN Claim 확인 오류,
C의 traceability 수행→NONE 추론을 고쳤다. 최종 필드에 근거 없는 결정권을 남기지 않았다.
모든 USER_CONFIRMED Claim에는 정확한 문구의 synthetic USER_ACCEPTED review가 있다.

## 3. Traceability results

아래 ID 경로를 실제 JSON에서 직접 확인했다. 자동 검사 이름/실행 결과는 §10에 기록한다.
DRAFT artifacts는 모의 게시 적격성을 검사하는 입력이며 실제 verified 이력서가 아니다.

| 요청 Test | 실제 경로 / 관찰 |
| --- | --- |
| A Evidence→Claim | ES-A → E-A-work → ECL-A-logic → C-A-logic; 별도 CA-A-logic와 CR-C-A-logic |
| B Resume reverse | AU-A-resume → ACL-A-sil → C-A-sil → ECL-A-sil → E-A-validation → ES-A |
| B supporting resume | AU-B-resume → ACL-B-architecture → C-B-post-selection-architecture → ECL-B-architecture-support → E-B-post-selection → ES-B |
| B leadership resume | AU-C-resume → ACL-C-team → C-C-team-leadership → ECL-C-team → E-C-team → ES-C |
| C JD | JDR-B-architecture → RCM-B-architecture → C-B-post-selection-architecture → ECL-B-architecture-support → E-B-post-selection → ES-B |
| C other patterns | JDR-A-validation → RCM-A-validation → C-A-sil; JDR-C-traceability → RCM-C-traceability → C-C-traceability → E-C-traceability |
| D boundary | K-B-no-tcn-selection → C-B-tcn-selection/P-B; K-B-no-project-owner → C-B-project-owner/P-B; 더 강한 문구는 재사용 금지 |
| E candidate | IS-C(v12) → IT-C-1 → EC-C-regression-script(PENDING); 승인 전 canonical claim 없음; 승인 후 참조 모델의 v13 행들 |
| F contradiction | E-B-model-support SUPPORTS C-B-model-analysis, E-B-model-conflict CONTRADICTS 같은 Claim; ES-B/ES-B-CONFLICT 둘 다 보존 |

JD mapping은 relevance일 뿐 Claim 확인이나 profile version을 변경하지 않는다.
artifact 문장은 연결된 atomic canonical_text를 link 순서로 이어 붙인 보수적 예시다.
일반 문장 의미 동등성을 판정하거나 새로운 표현의 진실을 보증하는 검사는 아니다.

## 4. Ownership boundary results

| 사례 | 허용 범위 | 금지 Claim / Constraint |
| --- | --- | --- |
| A | feature 설계·logic·calibration·방법별 validation; O-A-feature=FEATURE | C-A-adas-owner / K-A-no-adas-owner; C-A-vehicle-owner / K-A-no-vehicle-owner |
| B | dataset/I/O 참여, 선정 **이후** architecture/integration | C-B-tcn-selection / K-B-no-tcn-selection; C-B-project-owner / K-B-no-project-owner; C-B-model-owner / K-B-no-model-owner |
| C | 팀 운영/프로세스 운영과 traceability 수행 | C-C-perception-owner / K-C-no-perception; C-C-planning-owner / K-C-no-planning; C-C-control-owner / K-C-no-control |

각 금지 Claim은 DO_NOT_CLAIM이며 source의 부정 경계가 CONTRADICTS로 연결되어 있다.
Project/Ownership target은 constraint 문장의 제한 범위를 적용하며 프로젝트의 모든
긍정 Contribution을 일괄 금지하지 않는다. 테스트는 명시적 금지 Claim target과
검토된 정확한 문구를 사용한다. 긍정 Claim ID를 그대로 두고 artifact 문장만 ownership으로
강화해도 거부해야 한다. 자유로운 자연어 scope 해석은 사용자/semantic review의 책임이다.

A와 C, B의 일부 작업 권한은 UNKNOWN이다. 이 자료는 완료된 profiling instance가 아니다.
알 수 없는 기술 결정권을 NONE이나 DECIDER로 채우지 않는다. B의 TCN 선택 **비권한**만
원문에 명시되어 O-B-tcn-decision=NONE이다. “팀 리더”는 제품 구현 owner가 아니다.

## 5. Claim / Evidence results

- **PASS:** Claim 상태 3축, Responsibility/Contribution 분리, EvidenceSource/Item/Link,
  원래 Ownership level/scope/decision enum만으로 세 사례를 표현한다.
- E-A-work에서 architecture/logic/calibration을, E-A-validation에서 SIL/HIL/vehicle을
  별도 Claim/link로 분리했다. B dataset와 I/O도 두 Claim이다.
- ECL-B-architecture-qualifies는 선정 이후 범위를 한정하고,
  ECL-B-dataset-context는 배경만 제공한다. 둘만으로 confirmed Claim을 뒷받침할 수 없다.
- C-B-model-analysis의 SUPPORTS와 CONTRADICTS를 함께 보존하며
  USER_CLAIMED / CONTRADICTED / REVIEW_REQUIRED로 게시를 막는다.
  CR-C-B-model-analysis는 SYSTEM_FLAGGED이며 실제 사용자 해소를 가정하지 않는다.
- ClaimReview의 USER_ACCEPTED는 synthetic 정확한 문구/범위 확인이다.
  USER_CONFIRMED는 EXTERNALLY_VERIFIED가 아니다. generated text 단독 근거는 거부한다.
- 부정 경계를 확인한 것은 “Selected TCN”이라는 긍정 proposition을 확인한 것이 아니다.
  해당 Claim은 UNKNOWN / CONTRADICTED / DO_NOT_CLAIM이다.

## 6. Versioning results

**최소 보완:** 버전 숫자뿐 아니라 (profile ID, version)별 완전한 불변 JSON snapshot을
보존한다. 기존 append history와 stable Claim ID 원칙을 유지한다. 별도 DB/entity를
추가하지 않는다. snapshot은 context/ownership/assessment/review/constraint와 source/item/link,
artifact 데이터까지 포함한다.

재현 사례는 CP-C v12의 A-C-resume/AU-C-resume이다. EC-C-regression-script를
명시 승인하면 source/item/Claim/link/assessment/review/change set이 생기고 v13이 된다.
PENDING/follow-up/거절/duplicate 처리는 canonical을 바꾸지 않는다. 같은 ACCEPTED 후보
재실행은 같은 promoted IDs를 반환하고 다시 증가하지 않는다. 사용자/문구/context/input
version이 맞지 않는 승인은 실패한다.

v13 이후 live graph가 바뀌어도 v12 archive에서 C-C-team-leadership, E-C-team, ES-C,
O-C-team, K-C-no-perception과 artifact 문장을 다시 찾는다. archive/필수 참조가 없으면
최신 데이터로 대체하지 않고 실패한다. 실제 테스트의 함수/결과는 §10에 기록한다.

모순 발화 “I selected TCN”의 순서는 protocol §6에 수동 walkthrough로 명시했다:
PENDING workspace conflict → 명시 evidence 수용 review → 양쪽 근거 보존 +
DISPUTED/CONTRADICTED assessment + 기존 DO_NOT_CLAIM → 별도 해소 review.
Evidence 수용은 사실 확인과 다르다. 참조 모델이 다루지 않는 일반적인 기존 Claim 병합/
모순 해소는 제품 구현이나 검증 완료로 주장하지 않는다.

## 7. Ambiguities

| 분류 | 관찰 및 처리 | 남은 한계 |
| --- | --- | --- |
| AMBIGUOUS → clarified | §14 profile_id/profile_version과 SQL id/current_version 충돌; profile와 rows는 SQL 이름, §15–18은 read projection으로 명시 | production alias→UUID importer 미구현 |
| AMBIGUOUS → clarified | embedded/flat assessment·link 중복 가능; flat history/link만 authoritative, contexts/targets만 embedded projection | 범용 API projection 계약 제외 |
| AMBIGUOUS → clarified | REVIEW_REQUIRED, DISPUTED, NOT_EVALUATED가 기존 거부 조건에 불완전; ALLOWED+CONSISTENT를 요구 | 외부 검증 정책은 미정이어서 해당 상태는 참조 검사에서 fail closed |
| AMBIGUOUS → clarified | model §15 MODEL_ANALYSIS는 scope enum에 없음, dataset/I/O는 compound Claim | TASK + scope_description, atomic Claim 두 개 |
| AMBIGUOUS, open | free-text 범위/금지 표현을 일반 문장에 자동 적용하는 의미 판정 | exact reviewed wording 예시만 검사; 새 문장은 semantic review 필요 |
| OVERMODELED | 현재 fixture에 graph DB/vector/full production protocol engine을 추가할 근거 없음 | 기존 미래 옵션은 삭제하지 않고 미구현 유지 |

어떤 필드든 임의 enum으로 고정한 완성형 JSON Schema는 만들지 않았다.
SQL text enum 정책, 외부 검증 authority, protocol instance 저장 계약 등이 미정이다.
이번에는 표준 라이브러리 기반 구조/관계/불변식 검사를 선택했다. JSON parse를
JSON Schema validation이라고 부르지 않는다.

## 8. Schema gaps

| 발견 | 수정 전 관찰 | 최소 수정 | 수정 후 확인 |
| --- | --- | --- | --- |
| G1 GAP: review export | USER_CONFIRMED assessment는 있는데 §14에 ClaimReview history 경로 없음 | 기존 §8 row의 claim_reviews 배열 추가; MVP 필수 유지 | 3 fixture에 9/8/13 reviews, 확인 Claim별 USER_ACCEPTED |
| G2 GAP: historical reconstruction | version=12만 있고 source/context/constraint snapshot 보존 방식 없음 | 완전한 version-keyed immutable archive 규칙 | v12→v13 참조 모델 및 과거 artifact 검사 |
| G3 GAP: promotion assessment | §12 순서에 새 ClaimAssessment 누락, replay/승인 정확성 조건 불명확 | assessment/review/change set, exact approval, idempotence 규칙 | 승인/비승인/version/replay 검사 |
| G4 AMBIGUOUS: publication eligibility | 제한 상태와 비지지 관계만으로 게시 조건을 잘못 만족시킬 수 있음 | ALLOWED+CONSISTENT, SUPPORTS/non-generated source, 명시 review | 상태·관계·AI source·scope 음성 검사 |
| G5 GAP: MVP audit dependencies | claim_reviews/artifact_constraint_links가 deferred라 승인/경계 감사 유실 가능 | 이미 정의된 두 table을 필수 목록으로 이동 | review 및 artifact constraint FK 경로 확인 |

## 9. Proposed minimal changes

실제 변경은 두 v1 문서의 위 규칙 및 명백한 예시 불일치에 한정했다.
새 DB, 서버, runtime 의존성, graph engine, 일반 transaction framework를 추가하지 않았다.
Fixture 오류를 고칠 때 원문을 더 강한 주장에 맞추지 않고 UNKNOWN/금지 경계를 유지했다.
실제 경력 수치나 회사 사실을 보충하지 않았다.

새 protocol은 14 state 각각에 질문 유형, entity/field, 임시 출력, 전이 guard,
확인/UNKNOWN/충돌 처리를 정의한다. 9개 질문 유형, ACC 구체화, 4 atomic Claims,
high-impact 확인, TCN 충돌, A/B/C walkthrough, 중단/재개/질문 예산, 종료와 게시의
분리를 수동으로 원문 §10–18과 대조했다. protocol instance schema는 저장 계약이
미정이라 생략했다. state machine runtime을 구현했다고 주장하지 않는다.

## 10. Final recommendation

**패키지의 domain/fixture/protocol 검증 완료. 제품 구현 준비의 전부를 보증하지 않는다.**

자동 검증: Python 3.14.4, 새 dependency 없음.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

최종 코드에서 **20 tests / 0 failures / 0 errors / 0 skipped**, exit 0 (0.059s).
worker의 19 tests 결과를 coordinator가 독립 재실행했고, compound Claim 수준의
회귀 검사 1개를 추가한 뒤 최종 20 tests를 직접 실행했다. 음성 사례는
ValidationError가 발생하는 것이 기대한 통과 결과이며 원본 fixture를 수정하지 않는다.

| 필수 검사 개념 | 실행된 test / 범위 |
| --- | --- |
| confirmed Claim 근거 | test_every_verified_claim_has_evidence; missing SUPPORTS/INFERRED/QUALIFIES-only 거부 |
| do-not-claim | test_do_not_claim_blocks_publication; 상태를 ALLOWED로 위조해도 명시 Claim constraint가 차단 |
| Resume 역추적 | test_resume_unit_resolves_to_evidence; Claim/Evidence/source/review 및 경계 참조 |
| JD 추적 | test_jd_requirement_resolves_to_claim; 3 fixture 6 requirements, dangling Claim 거부 |
| PENDING 격리 | test_pending_candidate_does_not_mutate_profile; NEEDS_FOLLOWUP/REJECTED 후 canonical projection 불변 |
| 승인 및 version | test_candidate_promotion_increments_version; 무승인 실패, 정확히 12→13, 원본 불변, 재승인 replay 불변 |
| 모순 보존 | test_contradictory_evidence_is_preserved; B의 SUPPORTS+CONTRADICTS, 실제 CONTRADICTS 삭제 검출 |
| ownership 과장 방지 | test_ownership_boundary_prevents_overclaim; A/B/C 8개 금지 Claim; 별도 artifact 문구 교체 반례 |
| 과거 version 복원 | test_archive_reconstructs_old_artifact_from_snapshot_only; v13 live text/source/context/constraint 변경 후 v12 동일 |
| archive 누락/손상 | test_archive_missing_or_tampered_data_fails_without_latest_fallback; 누락·digest·dangling source 실패 |
| atomicity 제한 검사 | test_review_does_not_make_known_compound_claim_atomic; 검토 문구까지 일치시켜도 알려진 다중 action Claim/promotion 거부 |
| 추가 거버넌스 | 정확한/latest USER review, 3축 제한, SYSTEM_GENERATED/unknown source, 외부 검증 fail closed, evidence-only≠factual confirmation, 기존 모순 Claim 우회 거부 |
| 구조 | 필수 필드/기본 타입/ID/FK/context/target/profile/핵심 enum/ownership target 검사; 중복/누락/잘못된 값 거부 |

승격 예시의 실제 ID는 E-PROM-C-regression-script, C-PROM-C-regression-script,
CA-PROM-C-regression-script, CR-PROM-C-regression-script,
ECL-PROM-C-regression-script, PCS-PROM-C-regression-script다.
새 Claim은 명시 factual confirmation 후에도 별도 boundary/publication review 전까지
REVIEW_REQUIRED다. 기존 Claim으로의 병합/모순 해소는 참조 모델에서 차단한다.
해당 승인 후의 일반 병합 구현은 하지 않았으며 protocol §6의 수동 규칙으로만 정의했다.

**검증 한계:** 완전한 JSON Schema/SQL 엔진 검증이 아니다. UUID/date/timestamp 형식,
임의 JSONB 내용, 모든 optional SQL column 타입/constraint, DB atomicity/concurrency,
실사용자 인증, 자유 자연어 진실성/atomicity는 검증하지 않았다. 알려진 compound-action
패턴만 거부한다. 범용 Claim 병합, 외부 검증, 전체 protocol 실행 엔진도 미구현이다.
JD resolver는 이번 positive evidence-backed 경로만 검사하며 일반 relevance engine이 아니다.
단일 project fixture에서 artifact는 전체 active boundary set를 명시한다.
일반 다중 project의 scoped constraint 해석은 추가 구현이 필요하다.

완전한 JSON Schema와 protocol instance schema는 §7 사유로 의도적으로 생략했다.
표준 라이브러리 검사와 ID 경로 수동 검토로 요청된 8개 개념 및 Test A–F를 검증했다.
DB 기반 제품 integration test 통과로 주장하지 않는다.

원문 §27 완료 조건 대응:

| # | 기준 | 실제 근거 |
| --- | --- | --- |
| 1 | v1 문서 독해 | §1 baseline/계약, 두 원문 전체 확인 |
| 2 | 3 ownership fixture | §2의 세 파일 |
| 3 | Claim→Evidence | §3 Test A + confirmed evidence test |
| 4 | Resume reverse trace | §3 Test B + resume test/archive |
| 5 | JD mapping | §3 Test C + JD test |
| 6 | supporting 과장 금지 | §4 B + ownership/문구 재사용 음성 사례 |
| 7 | leadership vs feature | §4 C + 3 구현 ownership 차단 |
| 8 | do-not-claim | §4 + do_not_claim test |
| 9 | contradictory evidence | §5 + 실제 반대 link 삭제 음성 사례 |
| 10 | candidate 격리 | §6 + pending canonical projection 불변 |
| 11 | promotion version | §6 + 12→13/무승인/재실행 검사 |
| 12 | gap 문서화 | §7–8 |
| 13 | 최소 schema 변경 | §9 + 두 v1 문서 diff |
| 14 | validation 보고서 | 이 문서의 10개 섹션 |
| 15 | profiling protocol | 14 states/9 질문/guards/ACC/TCN/A–C walkthrough |
| 16 | terminology | schema/model/protocol/fixture 3축과 관계 대조; JSON 예시 9개 parse |
| 17 | 가능한 검증 실행 | 20 tests 및 구조/링크/문서/공백 검사 |
| 18 | unrelated 보존 | 시작 해시와 개발 계획서·요청 원문·step 파일 비교 |

모델 실행 기록: coordinator 요청 gpt-6-astra/high; fixture worker 및 validation worker는
native spawn에 gpt-5.6-sol/high를 명시했다. 도구와 로컬 model catalog의 지원을 확인했다.
런타임의 실제 모델/effort는 관측 불가하여 unknown이다. 상세 상태/agent ID는
[패키지 main](../to-do-prompts/career-graph-v1-validation-profiling/main.md)에 기록한다.
첫 worker의 최종 메시지는 중단 후 보존되지 않아 coordinator가 파일과 검사로 독립 확인했다.

구현 전에 결정할 사항은 외부 검증 authority/수용 기준, archive 보존·삭제/비식별 정책,
free-text/다중 project 경계의 semantic review 방식, 실제 import/API/protocol instance 계약이다.
commit/push/배포는 수행하지 않았다.

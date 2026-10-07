# CareerGround MVP Architecture 제안 v0.1

- 작성일: 2026-09-23
- 상태: **2026-09-23 승인** — `ARCH-01`–`ARCH-07` 채택; 애플리케이션은 아직 구현되지 않음
- 확정 계약: [MVP Architecture v1](architecture_v1.md)
- 범위: 개발 계획 Step 6. Step 7의 상세 Epic/Story/Task 분해는 승인 후 진행
- 선행 계약: [제품 정책](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md), [Schema v1.1 보완](career_graph_schema_v1_1_policy_addendum.md), [Plugin Functional Spec v1](plugin_functional_spec_v1.md), [Interview Package Schema v1](interview_package_schema_v1.json), [Voice Interview Agent Spec v1](voice_interview_agent_spec_v1.md)

## 1. 결론과 권장 순서

한국어 개인 구직자 비공개 베타에는 **모듈형 단일 백엔드**를 권장한다. 하나의 Career Core가 경력 데이터·승인·패키지·삭제의 권위 있는 상태를 소유하고, 인증된 MCP 어댑터와 웹 앱이 동일한 도메인 기능을 호출한다. 음성 실시간 연결은 별도 어댑터로 격리하되, 면접 상태와 후보 데이터의 최종 기록 권한은 Career Core에 둔다. 여러 마이크로서비스나 그래프 DB는 현재 범위에서 불필요하다.

출시 순서는 **텍스트 MVP → Interview Package 발급·검증 → Voice Interview 베타**다. 첫 단계부터 삭제·보관·권한 구조를 넣고, 음성은 같은 데이터 권한 경계를 재사용한다. 이 순서는 승인된 행동 계약을 바꾸지 않는다.

## 2. 제안하는 구성

```text
사용자 ChatGPT + CareerGround workflow ── OAuth 2.1 ── MCP adapter ┐
                                                             ├─ Career Core API/Domain ─ PostgreSQL
사용자 웹 앱 ───────── OIDC 세션 + CSRF 방어 ── Web/BFF adapter ┘         │
                                             │                          ├─ private object storage
                                             └─ Voice gateway ──────────┤  (선택 녹음/업로드/내보내기)
                                                  │                     ├─ outbox + worker
                                                  └─ realtime provider  └─ KMS signing key
```

Career Core는 `identity/authorization`, `profiling workspace`, `career graph`, `JD/resume`, `interview package`, `interview session`, `retention/erasure` 모듈로 나눈다. 모듈은 같은 배포 단위와 DB를 사용할 수 있지만 테이블 소유권·서비스 인터페이스는 분리한다. MCP와 웹 UI가 DB에 직접 접근하거나 각자 승인 규칙을 재구현하지 않는다. JD, 이력서, 대화, 음성 transcript는 모두 비신뢰 입력이며 모델에게 관리·승인·삭제 권한을 위임하지 않는다.

| 경계 | 권장 선택 | 이유 / 수용 조건 |
| --- | --- | --- |
| 백엔드 | Python 3 + FastAPI 기반 모듈형 단일 서비스 | 현재 검증 코드가 Python이며 비동기 API·작업자를 한 언어로 구성 가능. 프레임워크는 운영 부하 테스트 후 고정 |
| DB | 관리형 PostgreSQL, `account_id` 소유권 제약과 트랜잭션 | 관계·버전·고유성·정확한 승인 원자성이 핵심. 그래프 관계는 우선 관계형 테이블로 유지 |
| 외부 API | MCP Streamable HTTP 어댑터 + 제한된 웹 BFF API | 두 클라이언트가 하나의 도메인 명령과 정책을 사용. 내부 API는 외부에 그대로 공개하지 않음 |
| 인증 | 검증된 OIDC/OAuth 2.1 제공자 1개, CareerGround 고유 subject 매핑 | MCP와 웹을 동일 계정으로 묶되 이메일 문자열을 소유권 키로 사용하지 않음 |
| 파일 | private object storage + DB 메타데이터/만료시각 | 파일·선택 녹음과 관계형 데이터를 분리, 다운로드는 단기 제한 URL 또는 프록시 |
| 비동기 작업 | PostgreSQL transactional outbox + worker로 시작 | 발급 후처리·만료·삭제 재시도 누락을 줄이고 별도 메시지 브로커는 필요가 검증되면 도입 |
| 서명 | **ES256 + 관리형 KMS 승인** | 아래 §5의 Ed25519 구현 충돌을 해결하면서 큰 패키지와 키 격리를 유지 |
| LLM/음성 | 공급자 어댑터 분리; 출시 공급자는 개인정보·지연 평가 후 선정 | 기능 계약이 특정 모델 API에 잠기지 않도록 함 |
| 배포 | AWS 서울 리전 1곳을 초기 후보로 하는 관리형 컨테이너 + RDS + S3 + KMS | 단일 운영 경계가 단순함. 정확한 계정·서비스·지역·비용은 별도 배포 승인 대상 |

웹 앱은 한국어 모바일·데스크톱 대응 화면을 우선 만들고, 플러그인 내부 선택 UI는 Claim 묶음 검토의 최소 폼만 제공한다. 웹 프레임워크는 Next.js/React를 우선 검토하되 이 제안에서 고정하지 않는다. 사용자가 문서 없이 시작하는 경로와 텍스트 입력 경로가 기본이며 업로드·마이크는 선택이다.

## 3. 인증·권한·입력 경계

1. 인증 제공자는 OIDC subject를 발급한다. CareerGround는 `(issuer, subject)`를 내부 `account_id`에 매핑한다. 이메일 변경·동명이인은 계정 소유권에 영향 주지 않는다.
2. MCP의 OAuth access token은 발행자, 서명, 유효기간, audience/resource, scope를 서버에서 매 요청 검증한다. `career.delete`, 승인, 패키지 발급은 조회와 분리한다. 토큰·비밀번호·원문은 로그에 남기지 않는다.
3. 웹은 서버가 관리하는 세션 쿠키(`Secure`, `HttpOnly`, `SameSite`)와 CSRF 방어를 사용한다. 동일 계정 여부는 서버의 subject 매핑으로 확인한다. 브라우저 local storage를 access token·패키지 저장소로 쓰지 않는다.
4. 채팅 전체를 읽는 권한을 전제로 하지 않는다. 사용자가 CareerGround 도구/작업에 명시적으로 전달한 내용만 workspace에 적재한다. 설치, 일반 채팅, 로그인, 자동 일시정지는 90일 만료시각을 갱신하지 않는다.
5. 모델이 만든 후보·문장과 사용자 승인 입력을 분리한다. 서버가 review digest, 대상 버전, 항목별 선택을 검증하고 승인 트랜잭션을 실행한다. 플러그인/웹 표시 문구만으로 승인을 추론하지 않는다.

MCP 구현은 공식 SDK와 호환성 테스트를 전제로 하며, ChatGPT MCP 통합에 필요한 OAuth 메타데이터와 서버 인증 요건은 [OpenAI MCP 문서](https://developers.openai.com/plugins/build/mcp-server) 및 [인증 문서](https://developers.openai.com/plugins/build/auth)를 구현 직전에 재확인한다. 이 문서가 특정 클라이언트의 비공개 대화 전체에 대한 접근을 허용한다는 뜻은 아니다.

## 4. 데이터 소유권과 원자성

| 작업 | 동기 트랜잭션의 성공 기준 | 후속 비동기 작업 |
| --- | --- | --- |
| Claim 검토·승격 | review digest와 profile version 재확인, 최대 5항목 결정, canonical Claim/Evidence 및 새 version과 outbox를 한 번에 commit | 파생 검색·요약 인덱스 갱신. 실패하면 표시를 지연하고 원본 승격은 재시도하지 않음 |
| 패키지 발급 | 고정 profile/artifact version과 소유권·사용범위로 내부 발급 요청을 예약. 서명 후 해당 version의 사용 가능·삭제 상태를 다시 확인하고 registry에 `ISSUED`와 digest를 commit | 만료·철회 이벤트 전파. 서명 실패·동시 삭제 시 발급 성공을 표시하지 않음. 내부 예약은 공개 registry 상태가 아님 |
| 면접 시작 | signature·subject·audience·expiry·registry status를 검사하고 package 소비와 session 생성에 unique constraint 적용 | realtime 연결 준비. 실패 시 이중 세션 없음 |
| 확인 transcript | `(session_id, sequence, idempotency_key)`로 버전·상태 확정 | 해당 transcript version에서만 평가·후보 추출. 수정 시 구버전 파생물을 무효화 |
| 영구 삭제 | 대상 잠금, 사용 차단, package 철회, 삭제 job/outbox 생성; 상태 `DELETING` | DB·object·index·cache·provider 잔여물 삭제 및 검증 후 `ERASED`. 오류 시 `DELETING`으로 재시도 |

DB와 외부 object storage/KMS/provider 사이에는 하나의 ACID 트랜잭션이 없다. 따라서 **완료 상태를 실제 후속 작업 완료보다 앞서 표시하지 않는 상태기계**, idempotency key, outbox, 보상/재시도 절차가 필요하다. 개인정보 삭제는 특히 “요청 접수”와 “모든 관리 대상에서 삭제 확인”을 다른 상태로 보여준다. 캐시·인덱스는 원본 DB를 권위 있는 상태로 삼고, 철회·삭제 시 즉시 읽기를 차단한다.

## 5. Interview Package 서명: 기존 계약과의 충돌 및 채택된 변경

기존 Package v1은 JCS payload를 base64url로 인코딩한 detached JWS signing input에 **pure Ed25519**를 우선 권장하고, canonical payload를 최대 512 KiB로 허용한다. AWS KMS `Sign`의 메시지 입력은 최대 4,096바이트이며, AWS의 pure Ed25519는 `RAW` 입력만 받는다. `ED25519_PH_SHA_512`의 `DIGEST` 입력은 별도 Ed25519ph 방식이라 표준 `alg=Ed25519` 서명과 호환되지 않는다. 즉 **이 규격을 그대로 두고 AWS KMS의 pure Ed25519로 모든 허용 패키지를 서명할 수는 없다**. [AWS KMS Sign](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html), [AWS KMS 키 규격](https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html).

권장 변경은 이미 Package 제안서가 허용한 fallback인 **JOSE `ES256`으로 운영 알고리즘을 고정**하는 것이다. 전체 detached JWS signing input의 SHA-256 digest 32바이트를 만들고, AWS KMS `ECC_NIST_P256`의 `ECDSA_SHA_256` / `MessageType=DIGEST`로 서명한다. KMS가 돌려주는 DER 서명은 JOSE의 64바이트 `R || S`로 변환해 `proof.value`에 넣는다. 검증기는 보호 header의 `alg=ES256`, P-256 공개 JWK, 정확한 `kid`만 허용한다. 이것은 `payload`만 해시해 새 독자 규격으로 서명하는 방식이 아니다. [AWS KMS Sign](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html), [RFC 7518 §3.4](https://www.rfc-editor.org/rfc/rfc7518.html#section-3.4).

`proof.value`의 86문자 서명 부분은 ES256도 64바이트라 정규식 형태는 유지 가능하다. 반면 **당시 synthetic Ed25519 fixture·참조 검증기·문서의 알고리즘 고정은 변경 대상이었다**. 승인 후 Package v1 구현 프로파일을 `ES256`으로 명시 개정하고, 새 golden vector·변조/알고리즘 혼동 테스트를 작성했다. 실제 KMS 연동 테스트는 운영 리소스가 없으므로 아직 수행하지 않았다. 운영 발급은 시작되지 않았으므로 실사용 패키지 마이그레이션은 없다.

키는 서명 전용 KMS 비대칭 키로 두고 `kms:Sign` 권한은 패키지 발급 역할에만 부여한다. 공개 키 JWKS는 `kid`별로 배포하고 회전 후에도 유효 패키지의 검증에 필요한 공개 키를 유지한다. 긴급 키 폐기 시 해당 `kid` 패키지를 registry에서 사용 불가 처리한다. 회전 주기와 긴급 폐기 절차는 보안·운영 점검에서 확정한다.

대안은 Ed25519 유지 + AWS KMS 외의 순수 Ed25519 대형 입력을 받는 검증된 관리형 서명 서비스 선정이다. 이 경우 키 격리, 요청 크기, 지역 지원, 장애 복구와 비용이 모두 입증되어야 한다. 애플리케이션 메모리로 개인키를 꺼내는 방법은 MVP 권장안에서 제외한다.

## 6. 음성 경계와 공급자 선정 게이트

브라우저의 미디어 스트림은 가능한 한 임시·범위 제한된 연결 자격으로 realtime provider에 전달한다. CareerGround Voice gateway가 세션 시작 전 패키지·계정·철회 상태를 검사하고 질문 계획/허용 맥락을 만들며, 새 질문·재개·최종 평가 전 상태를 다시 확인한다. 브라우저 또는 공급자는 canonical Career Graph를 직접 읽거나 수정할 수 없다. 서버가 실시간 세션을 제어·종료할 수 없는 공급자는 §11 철회 계약을 만족하지 못하므로 채택하지 않는다.

자막·텍스트 대체 경로는 음성과 동일한 면접 상태기계를 쓴다. partial ASR은 임시 처리만 하고, 사용자가 확인한 transcript 버전만 DB에 저장·평가한다. 녹음 저장은 기본 꺼짐이며 명시 선택 시에만 별도 object로 30일 이내 보관한다. 녹음을 저장하지 않아도 외부 공급자가 처리 중 일시 데이터를 보유할 수 있으므로, 공급자 자체 보관·학습 사용·지역 간 이전·삭제 API와 계약을 확인하지 못하면 음성 베타를 열지 않는다.

공급자 선정은 한국어 ASR, 끼어들기, 자막, 연결 복구, 비용, 서버 측 세션 종료, 데이터 보관/학습 조건을 **합성 데이터**로 평가한 후 한다. 모델 평가는 소유권·숫자·부정 표현 인식과 근거 밖 질문 억제를 포함한다. 특정 공급자의 성능·보관 조건이 충족됐다고 이 문서에서 주장하지 않는다.

## 7. 보관·삭제·복원 설계

| 데이터 | 운영 저장 기준 | 구현 검사 |
| --- | --- | --- |
| CareerGround profiling workspace | 해당 세션 마지막 실제 입력 후 최대 90일 | DB 만료시각 + 주기 작업 + 만료 직후 읽기 차단. 선택 승격된 Evidence는 별도 canonical 수명 |
| 확인된 면접 transcript/feedback | 세션 종료 후 최대 90일, 조기 삭제 우선 | transcript·평가·후보 출처 연쇄 삭제/무효화 |
| 선택 원본 녹음 | 녹음 완료 후 최대 30일, 기본 저장 안 함 | object 메타데이터 만료 + worker 직접 삭제 + 잔여 버전 확인 |
| 업로드 원본 파일(지원 시) | 추출 완료 후 최대 30일; 장기 Evidence로 사용자가 선택한 원본은 별도 명시 | 원본 파일과 발췌 Evidence의 저장·삭제 선택을 분리 |
| 일반 진단 로그 | 원문·파일·음성 없이 정책 제안 최대 30일 | 요청 ID·코드·지연만 허용하는 로그 스키마 검사 |
| DB 백업 | 비공개 베타에서는 30일 이내 보관 제안 | 자동 백업 설정뿐 아니라 수동 snapshot·복제본·복원본 목록 관리 |

DB 자동 백업은 행 단위 선택 삭제가 불가능하다. 따라서 삭제 요청 시 운영 DB와 모든 온라인 조회 경로에서 즉시 사용을 차단하고, 백업은 제한된 기간에 만료시키되 **복원 시 백업을 서비스에 연결하기 전에 삭제 ledger를 재적용**한다. ledger는 원문이 아닌 대상 식별·삭제 이벤트만 보유하되, 이 식별자도 개인정보 최소화·접근 제한 대상으로 취급한다. 복원 테스트에서 삭제 대상이 재등장하지 않아야 한다. 이것은 “백업에서 즉시 물리 삭제”를 보장한다는 뜻이 아니며, 정책 문서의 24시간/30일 수치는 아직 대외 약속이 아닌 검증 목표다. RDS 자동 백업 보관은 0–35일 설정 가능하다. [AWS RDS 백업 보관](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.BackupRetention.html).

S3 버전 관리 버킷에서는 단순 `DELETE`가 구버전을 없애지 않고 delete marker만 만들 수 있다. 개인 원문 버킷은 버전 관리·Object Lock 정책을 삭제 요구와 맞춰 설계하고, 켜져 있다면 **모든 object version을 추적·영구 삭제**해야 한다. Object Lock에 의해 삭제가 막히는 버킷에 삭제 대상 개인정보를 저장하지 않는다. Lifecycle은 안전망이지 사용자 삭제의 유일한 실행 수단이 아니다. [S3 버전 삭제](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html), [S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html).

삭제된 근거·snapshot payload는 복원용 사본을 별도 유지하지 않는다. 관련 패키지는 철회되고 기존 이력서 근거 조회는 `UNAVAILABLE_DUE_TO_ERASURE`가 된다. 최소 비식별 tombstone만 남기며 과거 내용을 새 profile에서 재구성하지 않는다. 외부 사용자가 이미 다운로드한 사본의 원격 삭제는 보장하지 않는다.

## 8. 운영·검증 게이트

- 네트워크: API/MCP만 공개, DB/worker/object 직접 공개 금지. TLS, 환경별 IAM 최소 권한, 비밀값 관리, 운영자 열람 승인·기록.
- 배포: dev/staging/prod 분리, DB migration의 전·후방 호환 단계, feature flag로 패키지·음성 순차 활성화. 배포/클라우드 생성 자체는 본 제안 승인과 별도 실행 승인 대상.
- 관측: 원문 없는 구조화 로그, 오류율/지연/worker backlog/만료 지연/삭제 실패/철회 확인 실패 알림. 비용 상한과 공급자 장애 시 텍스트 대체/안전 중단.
- 시험: 동일 계정/타 계정 권한, digest 재생·중복 승인, package 1회 시작 경쟁, 서명 변조·키 회전, transcript 수정 후 무효화, 삭제 중 생성 경합, 백업 복원 후 삭제 재적용, provider 철회·연결 단절을 통합 테스트.
- 품질: 한국어 상담 문장과 JD prompt injection에 대한 합성 평가셋, 숫자·소유권·부정 표현 오류 관찰. 합격률·취업 가능성 같은 지표는 생성하지 않음.

## 9. 승인된 선택 기록

| ID | 제안 | 확인이 필요한 이유 |
| --- | --- | --- |
| ARCH-01 | Python/FastAPI 모듈형 단일 백엔드 + PostgreSQL, MCP/웹 어댑터 분리 | 초기 구현·운영 복잡도를 제한. 특정 프레임워크 선호가 있다면 교체 가능 |
| ARCH-02 | AWS 서울 리전의 관리형 컨테이너/RDS/S3/KMS를 초기 인프라 후보로 채택 | 위치·비용·운영 계정·법률 검토 전 실제 리소스 생성은 하지 않음 |
| ARCH-03 | OIDC/OAuth 2.1 제공자 1개와 내부 `account_id` 매핑, 공급자 제품은 보안/가격 조사 후 선택 | 동일 계정 handoff의 필수 경계. 제품 미선정 상태는 구현 전 해결 |
| ARCH-04 | 관리형 KMS를 위해 Interview Package 운영 알고리즘을 Ed25519에서 **ES256으로 변경** | 최초 규격에서 의미 있는 변경. fixture/검증기는 승인 후 개정 (§5) |
| ARCH-05 | PostgreSQL outbox + worker, private object storage, 삭제 ledger/restore gate | 삭제·만료·외부 저장소 일관성에 필요. 별도 브로커는 보류 |
| ARCH-06 | 음성 공급자는 계약·한국어/철회/보관 평가 후 결정; 조건 불충족 시 텍스트만 출시 | 선택 녹음 30일은 provider 자체 저장 정책까지 자동 보장하지 않음 |
| ARCH-07 | 출시 순서: 텍스트 → 서명 패키지 → 음성 | 행동 계약은 유지하고 위험이 높은 외부 연결을 뒤에 검증 |

**승인 기록:** 사용자가 2026-09-23에 `ARCH-01`–`ARCH-07` 전체를 승인했다. 확정 결과는 [architecture_v1.md](architecture_v1.md)에 기록한다. ES256 테스트 자료와 검증기는 이 승인에 따라 개정했다. 다음 순서는 Step 7의 Epic/Story/Task와 수용 기준 분해다. 이 제안 본문의 미래형 표현은 승인 당시의 검토 맥락을 보존한다.

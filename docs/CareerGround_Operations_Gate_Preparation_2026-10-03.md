# 4-3 운영·삭제·복원·예산 준비 — G-P/G-C

상태: **설계와 시험 절차 준비, 운영 환경·외부 삭제·복원 미실시**.
승인된 [architecture_v1](architecture_v1.md)의 AWS 서울(`ap-northeast-2`) 컨테이너/FastAPI, private PostgreSQL, private S3/KMS, PostgreSQL outbox/worker 구성을 기준으로 한다. 관리형 컨테이너 상품·계정·규모·가격은 미선정이다. 자원 생성·배포·외부 저장을 수행하지 않았다.

## 운영 자원과 승인 전 결정 항목

| 대상 | 필요한 설정/증거 | 현재 상태 |
| --- | --- | --- |
| Web/MCP ingress | HTTPS, 정확한 OAuth resource/redirect, 인증·account gate·요청 제한, 공개 경로 목록 | 로컬 합성 검증; 공개 HTTPS 미구성 |
| API/worker | 최소 IAM, 각 task 권한 분리, private DB 접근, 동시성/timeout/재시도 한도, 종료 시 재처리 | 로컬 outbox 기반; 실제 배포 미구성 |
| RDS PostgreSQL | public access 비활성, SG 최소 접근, 암호화·접속 비밀 회전, backup/PITR·복원 역할 | 로컬 PostgreSQL 증거만 있음 |
| S3/KMS | public block, 계정별 최소 접근, 모든 version 삭제, 키/객체/backup 수명 정책 | 로컬 합성 객체/서명 키만 사용 |
| 독립 삭제 ledger | 복원 DB와 별도 신뢰 anchor, 서명/버전·삭제 범위 보존, 키 회전·접근 감사 | 로컬 서명 checkpoint; 독립 운영 anchor 미구현 |
| 관측 | 원문 없는 구조화 이벤트, request/worker 실패·지연·backlog·삭제 미완료·복원 차단 경보 | 지표/경보 운영 미구성 |

AWS 서울 지정은 계정 생성·유료 자원 실행의 승인이 아니다. DB와 worker·객체·서명 키를 공개하지 않는다. NAT/endpoint/ALB 선택은 실제 외부 통신과 월 고정 비용을 함께 검토한다.

## 데이터별 보관과 삭제

| 사본 | 삭제 및 검증 방식 | 공개 약속 전 필요한 결정 |
| --- | --- | --- |
| canonical DB/임시 입력·검토 snapshot | 확정 직후 조회/향후 사용 차단, worker 삭제, FK·원문·파생 참조 검증 | 종류별 보관 기간·삭제 SLA |
| CURRENT archive/R1·R2·R3/export/receipt/package | 관련 구버전 폐기·상태 증명 무효화, 다른 계정·무관한 범위 보존 | 다운로드된 사용자 사본의 통제 한계 |
| outbox/retry/dead letter | 최소 참조만 저장, 삭제 중 새 생성 차단, 실패 재시도·최종 실패 공개 | 보관 기간·재처리 담당자 |
| S3 current/noncurrent version·복제본 | 정확한 object key와 모든 version ID 확인 후 삭제, 404만으로 완료 판정 금지 | versioning/replication/lifecycle/Object Lock 정책 |
| RDS backup/snapshot/PITR | 격리 복원과 최신 삭제 ledger 재적용, 보관 기간 종료 검증 | backup TTL·법적 보존 예외·완전 삭제 시점 |
| 로그·캐시·검색/공급자 사본 | 입력 원문 미기록, 사본 목록·TTL·삭제 API·완료 증거 확인 | 기능별 실제 보관·해외 이전·삭제 조건 |
| 삭제 ledger/감사 최소 metadata | 원문 없이 삭제 범위/버전/검증 상태 보존, 권한 제한 | 최소 필요 기간·식별자 처리·법적 검토 |

S3 versioning에서 일반 DELETE나 current version expiration은 delete marker를 만들 수 있으며 과거 version을 제거하지 않는다. 영구 삭제는 해당 version 삭제와 완료 확인이 필요하다. [AWS S3 공식 문서](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html)

backup에 남은 사본을 처리하지 않은 상태에서 전체 삭제 완료를 표시하지 않는다. 현재 제품 상태 `DELETING/FOUNDATION_ONLY`는 운영 삭제 완료의 증거가 아니다. 프로필 세션의 기존 90일 정책을 모든 종류의 데이터/backup TTL로 확대하지 않는다. 보관 기간·삭제 SLA·해외 이전·처리자 조건은 G-P 검토 전까지 미확정으로 유지한다.

## 실행할 운영 시험 순서

| ID | 시험 | 통과 조건 |
| --- | --- | --- |
| O01 | 배포 전 inventory·권한·비용·보관 검토 | 정확한 계정/리전/자원/기간/최대 비용과 정리 계획 승인, 운영과 격리 |
| O02 | 두 합성 계정의 Web/MCP 정상·거부·삭제 상태 호출 | 매 요청 인증/소유권 확인, 다른 계정 본문과 존재 정보 미노출 |
| O03 | 입력 중·생성 중·승인 후 SESSION/EVIDENCE/PROJECT/PROFILE/ACCOUNT 삭제 | 영향 재확인, 즉시 사용 차단, 관련 archive/export/receipt 폐기, 무관한 A/B 데이터 보존 |
| O04 | worker crash·중복·DB 실패·외부 삭제 timeout | 동일 event 재시도는 중복 효과 없음, transaction rollback, 제한 backoff, 실패를 COMPLETE로 표시하지 않음 |
| O05 | 삭제 전 backup + 최신 ledger로 격리 복원 | replay 후 구원문/Claim/JD/export·package 접근 불가, 부분 삭제 version 하한 유지 |
| O06 | 누락/변조/과거 ledger·잘못된 키·미완료 객체 삭제 | 모든 복원은 격리 유지, 읽기/생성/승인/내보내기·외부 전송 불가 |
| O07 | S3 version·복제·provider 삭제 및 backup 만료 확인 | 각 사본 검증 증거와 실제 지연 기록, 미검증 사본이 있으면 미완료 |
| O08 | migration·배포·코드 rollback·키 회전 | 최신 삭제 ledger/버전 보존, 삭제/철회/권한 해제를 되돌리지 않음 |
| O09 | 인증/AI/DB 장애·backlog·비용 한도 대응 | 신규 위험 작업 중단, 원문 없는 경보, 사용자에게 현재 상태와 재시도 안내 |
| O10 | 정리·복원 시간/손실·비용·보관 점검 | 승인한 자원 정리와 남은 backup/로그 비용 공개, G-P/G-C 결과 검토 |

O03의 ACCOUNT/PROFILE과 부분 scope는 기존 로컬 증거를 활용하되 운영 adapter와 연결한 실제 결과를 별도 남긴다. 로그는 case ID/시각/상태/수량/지연만 보존하며 원문·토큰·비밀번호·전체 HAR을 넣지 않는다.

## 복원 절차 — 검증 완료 전 격리 유지

1. 장애 범위와 복원 시점을 기록하고 신규 write/생성/삭제 worker를 멈춘다. 최신 삭제 ledger와 버전 하한은 복원할 DB 밖의 신뢰된 anchor에서 확보한다. 확보 실패는 복원 공개 차단 사유다.
2. 기존 환경과 분리된 private 복원 DB를 만든다. 사용자 트래픽/외부 AI/객체 전달은 차단하고 새 비밀을 사용한다. RDS PITR은 새 DB instance를 만들므로 SG·parameter/option group을 명시적으로 검토한다. [AWS RDS PITR](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIT.html)
3. schema revision, owner FK, ledger 서명/순서/coverage를 확인한다. 삭제 event를 transaction으로 재적용하고 ACCOUNT/PROFILE/부분 scope의 tombstone·profile version 하한과 raw-session closure를 검증한다.
4. 구 CURRENT/R1/R2·검토 snapshot/JD 발췌/객체/receipt·package 참조를 검사한다. 원문·구버전·삭제된 key가 살아 있거나 객체 삭제가 미확인일 때 격리를 해제하지 않는다.
5. 과거 access/refresh/session과 approval receipt를 재사용해 보호 호출 실패를 확인한다. 삭제된 계정 및 승인 결합을 과거 backup으로 복구하지 않는다. 두 합성 계정의 정상/교차 요청과 partial-scope 보존을 확인한다.
6. 실제 복원 소요 시간과 손실 구간을 기록하고 담당자가 검증 결과를 검토한다. 새 endpoint 전환은 별도 배포 승인과 점검 뒤 수행한다. 불확실하면 격리를 유지한다.

RPO/RTO는 **합의 전**이다. 검토 출발점으로 RPO ≤24시간, RTO ≤4시간을 제안하지만 실측·비용·데이터 중요도에 따라 조정하고 승인받는다. 목표를 달성했다고 주장하지 않는다. DB와 ledger/키를 함께 과거로 돌리는 공격을 로컬 checkpoint만으로 탐지할 수 없으므로 독립 anchor 구현과 운영 시험이 필요하다.

## 배포·장애 대응

배포 순서는 exact migration/backup·anchor 확인 → 격리 환경 migration → 합성 검증 → 제한 트래픽 → 지표 확인이다. 현재 schema head는 `20261003_0020`이다. 삭제 ledger나 승인 결합 metadata를 없애는 schema downgrade를 일반 rollback으로 쓰지 않는다. 코드 rollback도 최신 schema와 삭제 상태를 유지할 수 있는 버전으로만 하며, 호환되지 않으면 신규 기능을 닫고 수정 배포한다.

worker backlog age, retry/DEAD 수, 삭제 요청의 미완료 시간, HTTP 401/403/5xx, 응답 지연, DB 오류, restore quarantine 상태를 관측한다. 원문을 포함한 오류를 수집하지 않는다. DEAD/삭제 외부 실패는 담당자 점검 대상으로 남기고 사용자 상태를 실패/진행 중으로 표시한다. 자동 재시도의 한도·담당자·연락 경로는 배포 전에 지정한다. 공급자 장애 시 새 AI 호출을 멈추고 수동 입력/검토 경로를 유지한다.

## 비용 검토 — 현재 승인액 0

견적은 container/API·worker 실행 시간, RDS instance/storage/IO/backup·snapshot, ALB/public HTTPS, NAT 또는 endpoints, S3 current/noncurrent/replica/request/egress, KMS, 로그/metric/경보, 인증·AI 요금, 세금/환율을 포함한다. 모델/자원/traffic/기간이 미정이므로 임의 월 요금을 적지 않는다. 무료 구간은 비용 상한이나 생성 승인으로 간주하지 않는다.

각 자원의 최대 개수·size·autoscale 상한·최대 실행 시간·보관 기간·정리 담당자를 먼저 정하고 공식 견적에 연결한다. 작업 종료 후 RDS 중지/컨테이너 종료만으로 storage·snapshot·로그 비용이 0이 되는지 따로 확인한다. AWS Budgets의 집계/알림에는 지연이 있으므로 그것만으로 비용 상한을 강제할 수 없다. [AWS Budgets 공식 문서](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

승인은 **G-I 합성 인증 재시험 → G-L 공급자/모델·요청 수·예산 → G-P 처리/삭제 조건 및 G-C 자원·비용·배포** 순서다. 실제 클라우드 실험은 자원 명세/최대 비용/기간/정리·잔존 비용을 검토한 뒤 한 단계씩 요청한다. Phase B KMS/JWKS와 Phase C 음성은 이 준비만으로 승인되지 않는다.

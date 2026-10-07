# Phase A 비공개 합성 MVP 후속 시험 정리

최신 수용 상태: 사용자의 완료 범위 결정에 따라 **비공개 합성 MVP 완료**로 정리했다. [2026-10-08 최종 수용과 후속](CareerGround_Phase_A_Private_MVP_Acceptance_2026-10-08.md)을 먼저 읽는다. 아래는 실제 시험 당시 관측과 한계이며 공개 운영 완료를 선언하지 않는다.

시험 시작 HEAD: `1850b55d21437769db1010060d86bb46fbdf9b01`.
후속 구현·시험 기록은 이 문서와 함께 버전 관리한다. 후속 커밋의 원격 CI 결과는
GitHub Actions에서 해당 커밋별로 확인한다. 공개 배포, 실제 경력 자료 수용 또는
main merge 완료를 선언하지 않는다.

## 수용 범위

기존 ChatGPT 비공개 플러그인에서 합성 경력 대화를 진행하고 CareerGround Web에서
자료·사용·문구·내보내기·삭제를 사람이 확인하는 개인 개발 MVP의 주요 흐름을 확인했다.
유료 서버 AI나 Auth0 OTP MFA를 추가하지 않았다.

| 권장 순서 | 완료한 실행·관측 | 검증 경계 |
| --- | --- | --- |
| 1. A/B 격리 | 기존 실제 조회·쓰기 준비·확인 요청·삭제 미리보기 거부를 재사용했다. 삭제·재시작 후 B의 본인 조회는 정상이며 A의 프로필/JD/R2와 없는 대상은 Web에서 같은 404, MCP에서 같은 NOT_FOUND였다. | 유효한 완료 증명을 다른 계정으로 실제 전달해 실행하는 시험은 하지 않았다. 증명 조회 차단과 합성 자격 증명의 회귀를 그 시험으로 확대하지 않는다. |
| 2. 연결 차단·복구 | 사용자 A/client 차단, B 및 Web 유지, 일반 재시작 뒤 차단 지속, 활성 서버 중 복구 거부, 정확한 오프라인 해제, A 실제 MCP 조회 복구를 확인했다. 실제 만료 안내와 사용자 재연결 이후 요청 복귀도 관측했다. | 차단 중 새 OAuth 발급과 제공자 grant 철회는 실제 수행하지 않았다. 로컬 registry의 전체 파일 동시 rollback에는 별도 신뢰 anchor가 필요하다. |
| 3. 품질·설치 계약 | 사용자 합성 36개 평가를 재사용했다. 기존 설치 ZIP의 실제 이름·앱 바인딩을 보존해 1.0.3으로 갱신했고 다시 내려받은 스킬 bytes/hash가 최신 source와 일치했다. 사용 switch와 실제 도구 왕복을 확인했다. | 프로젝트 소유자의 합성 평가이며 독립 blind 평가·실제 경력 품질 또는 모든 ChatGPT 계정의 이용 가능성 검증은 아니다. |
| 4. 내용 있는 흐름 | 새 A의 사실/별도 사용 승인 → 한 줄 JD → RELATED/POTENTIAL 연결 → R1 생성/문구 승인 → 어미 수정 R2 → 별도 Markdown 내보내기 → 실제 기기 패스키 → PROFILE 로컬 삭제 → 같은 store 재시작과 접근 거부를 확인했다. | 삭제 coverage는 FOUNDATION_ONLY다. 전체 요청·프로필 stub은 DELETING이고 UNVERIFIED_SCOPE 1건이 남는다. 외부 사본·백업·제공자 계정 또는 MCP 삭제 증명은 포함하지 않는다. |
| 5. 회귀·정리 | 실행기 pytest 13개를 CI에 명시했다. 로컬 실행기 13개·복구 3개·SQLite claim 검토 9개·PostgreSQL 12개가 통과했고 Ruff check/format 14개 파일 및 diff check도 통과했다. DB 컨테이너와 소유 QA/tunnel을 중지했다. | 각 수는 서로 다른 대상 시험 실행 기록이다. 전체 새 작업 트리의 원격 CI 통과 수나 단일 통합 suite 수로 합산하지 않는다. |

## 현재 저장 상태와 정리

- A의 Claim·Evidence·원문·임시 초안·JD·R1/R2·브라우저 승인 자료는 제거됐다.
- 삭제 작업은 ERASE DONE 7건, VERIFY DONE 30건, UNVERIFIED_SCOPE VERIFY PENDING 1건이다.
- 삭제 ledger 1건과 DELETING profile stub을 보존한다. signed checkpoint는 실제 재시작에서 검증됐다.
- B 계정별 non-quota table 34개의 count/행 hash는 삭제 전과 같다. B profile/version 0 및 기존 초안이 실제 Web/MCP에서 유지됐다.
- 현재 QA의 등록 패스키는 A 1개/B 0개다. 공개키·삭제 checkpoint·B 자료를 담은 owner-only ignored 저장소는 보존했다.
- 사용자 `docker stop` 성공 뒤 55432가 닫혔다. 소유한 임시 user QA service를 중지했고 연결된 tunnel도 종료됐다. 5000/8001/18081도 닫혔다.
- BrowserOS, 기존 외부 등록/연결, ignored `to-do-prompts/`·`intent-docs/` 초안 20개의 hash는 보존했다.
- 시험 정리 당시 commit/push/main merge는 수행하지 않았다. 이후 사용자가 현재 변경의 검토·commit·push를 별도로 승인했다. main merge는 승인 범위에 포함하지 않는다.
- 공개 기록의 비공개 앱 식별자 두 곳은 placeholder로 치환했다. 치환 전 원본은 owner-only ignored QA 저장소에 보존했다. 합성 평가 원본과 content/fixture/skill hash는 변경하지 않았다.

## 구현과 시험에서 드러난 한계

1. 처음 준비한 portable 이름 패키지는 기존 plugin 이름과 달라 업로드가 거부됐다. 실제 기존 ZIP의 이름·구조를 보존해 수정했다. 거부된 시도를 설치 성공으로 기록하지 않는다.
2. 짧은 JD 제안 상태 조회와 이전 JD 연결 증명 조회는 각각 VALIDATION_FAILED/REVIEW_REQUIRED였다. 이미 저장된 자료를 중복 승인하지 않았고 그 증명 소비를 완료로 기록하지 않았다. 이후 새 R1·문구·export 결과 처리는 같은 연결에서 CONSUMED, R2 제안 상태는 DONE으로 확인됐다.
3. 현재 R2 검사는 보수적이다. 문장 중간 쉼표 추가도 거부됐고 같은 과거 어미 변형은 허용됐다. 자유로운 의미 재작성 기능으로 설명하지 않는다.
4. 실제 INLINE 출력의 화면 렌더는 마지막 LF를 생략했다. formatter가 정한 LF를 보완한 UTF-8 91바이트의 SHA-256은 서버 선언과 일치한다. 원시 MCP transport bytes를 별도로 캡처한 것은 아니다.
5. 최초 기기 등록은 기존 제공자 계정 신뢰를 따른다. 패스키 교체·분실 복구, 운영 restore anchor, 다중 process 운영 수용은 완료하지 않았다.

OTP MFA·유료 서버 AI·refresh·공개 운영 Gate A는 기존 결정대로 보류한다.
위의 미관측 실제 자격 증명/제공자 변경 시험과 운영 gate를 완료했다고 주장하지 않는다.

## 주요 증거

- [기존 실행·세부 이력](CareerGround_Phase_A_Release_Acceptance_2026-10-05.md)
- [A 차단·오프라인 복구](careerground_persistent_qa_connection_block_recovery_20261007.json)
- [실제 설치 플러그인 갱신](careerground_persistent_qa_private_plugin_update_20261007.json)
- [R2 본문·해시 검증](careerground_persistent_qa_a_r2_export_completed_20261007.json)
- [실제 기기 등록·동일 store 재시작](careerground_persistent_qa_a_passkey_registered_20261007.json)
- [A 삭제·재시작](careerground_persistent_qa_a_deletion_completed_20261007.json)
- [삭제 후 Web 격리](careerground_persistent_qa_after_deletion_web_boundaries_20261007.json)
- [삭제 후 실제 B MCP 격리](careerground_persistent_qa_after_deletion_mcp_boundaries_20261007.json)
- [PostgreSQL 12개 및 빈 제품 table 38개](careerground_persistent_qa_postgres_regression_result_20261007.json)

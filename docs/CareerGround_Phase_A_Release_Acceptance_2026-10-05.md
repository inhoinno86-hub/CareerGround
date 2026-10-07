# Phase A 실제 계정·품질 수용 후속

최신 결정: 개인·비공개·합성자료 텍스트 MVP는 완료 처리한다. [2026-10-08 최종 수용](CareerGround_Phase_A_Private_MVP_Acceptance_2026-10-08.md)에 JD 조회 진단과 후속 항목을 정리했다. 아래 미완료/대기 문장은 각 시험 당시의 이력이다.

시험 시작 커밋: `1850b55d21437769db1010060d86bb46fbdf9b01`. 해당 커밋의 원격 CI 464개 및 Chromium/Firefox 검증은 통과했다. 후속 구현·시험은 이 문서와 함께 버전 관리하며 후속 커밋의 CI 결과는 별도로 확인한다. Phase A 전체 완료·공개 운영 수용·main merge를 선언하지 않는다.

## 현재 실행 상태: 후속 실행·회귀·정리 완료, 검증 한계 별도 기록

최신 결과와 범위는 [2026-10-07 최종 정리](CareerGround_Phase_A_Private_MVP_Closeout_2026-10-07.md)를 먼저 읽는다. PostgreSQL 12개 PASS/제품 table 38개 empty, 사용자 컨테이너 종료와 소유 QA/tunnel 종료·네 loopback port closed를 확인했다. 현재 QA·B 자료·기기 공개키·삭제 checkpoint 및 ignored 초안은 보존했고 임시 PG 비밀번호 파일은 제거했다. 아래 상태·대기 표현은 각 실행 시점의 이력이며 모든 실제 자격 증명/운영 gate 완료를 뜻하지 않는다.

사용자의 Full Access 선택 후 BrowserOS의 실제 탭 조회·snapshot·navigation과 로컬 서버 실행이 성공했다. Git 제외 지속 QA의 DB와 패스키 저장 경로를 새로 초기화했고 runtime live 및 기존 터널 health/ready는 각각 200이다. 사용자 생성 전 accounts/profiles/claims는 모두 0이었다. 이전 임시 DB를 복원하거나 과거 승인·패스키를 복사하지 않았다. 기존 제공자 로그인 세션으로 새 ‘CareerGround 계정 시작’ 화면을 준비했으며 사용자 A의 직접 생성 후 관리 화면과 accounts/identities/profiles 각 1개·profile version 0·claims 0을 확인했다. B도 직접 생성 후 accounts/identities/profiles 각 2개·서로 다른 검증 identity·각 profile version 0·Claim 0을 확인했다. 현재 Web 링크는 각각 정확한 A/B 프로필에 연결되고 양방향 최소 GET 확인에서 본인 200·다른 계정/없는 대상 동일 404·대상 ID 미노출이었다. 기존 A/B ChatGPT 연결의 실제 discovery는 앱 계층 재인증 요구로 막혔으며 사용자 A 재연결 후 실제 MCP get_my_profile이 정확한 새 A/version 0을 반환했다. 새 QA 후속 시험용 합성 원문 1건과 정확한 임시 DRAFT 1건만 실제 native MCP로 준비했고 Claim/승인은 아직 0이다. 사용자 B 창 ChatGPT 로그인 후 기존 제품 목록의 A만 보이는 일시 상태를 관측했다. 다른 계정 연결에서 기존 B SSO/동의가 자동 처리돼 새 별칭 ‘지속 QA B’를 만들었고, 기대 ID를 주지 않은 ChatGPT 실제 discovery 반환 및 서버 B read 1건으로 정확한 새 B/version 0을 확인했다. B의 합성 문장 원문/DRAFT 각 1건을 준비했다. A 세션+B source와 없는 source의 실제 native MCP 요청은 같은 NOT_FOUND, non-quota 자료 table 37개 hash 유지였다. 사용자 A 검토 후 정확한 합성 Claim 1개·profile version 1이 저장됐고 같은 요청 연결에서 완료 결과를 소비해 CONSUMED가 됐다. B의 미승인 PROFILE_EXPORT 요청으로 A/B의 실제 client 일치를 확인했으며 실행된 내보내기는 없다. 같은 store에 signed denial registry를 연결해 재시작했고 자료 table 37개 hash·A/B Web 소유 링크·A/B 실제 MCP 응답·기존 터널 health가 유지됐다. 정확한 A/client 오프라인 복구 helper와 활성 runtime 중 복구 거부를 확인했다. 사용자가 A 차단 검토를 제출했다. A MCP는 재인증 요구로 거부됐고 B 실제 ChatGPT 조회와 A/B Web 본인 조회는 유지됐다. 일반 재시작 후 같은 서명 registry의 A 차단/B 허용·차단 화면·자료 table 37개 hash 유지가 확인됐다. 승인된 오프라인 helper의 UNBLOCKED/exit 0을 확인한 뒤 최종 재시작했고 차단 0건·A 실제 native MCP의 정확한 profile/version 1·Web 검토 복구를 확인했다. 추가 수동 재연결은 필요하지 않았다. 차단 중 새 OAuth 발급·제공자 grant 철회는 실제 수행하지 않았다. [새 차단·복구 증거](careerground_persistent_qa_connection_block_recovery_20261007.json). A/B 제품 시험·export/삭제의 나머지는 아직 남았다.

터널의 literal `stdout` 로그 경로가 프로젝트 루트에 파일을 만드는 동작을 관측해, 설치 CLI 도움말에 따른 빈 경로로 수정했다. 기존 로그는 ignored private QA 경로에 보존했다. 원문 HTTP logging은 계속 꺼져 있고 회귀 4개·수정 뒤 터널 health/ready 200·루트 로그 파일 미생성을 확인했다. [실행 관측](careerground_persistent_qa_activation_20261007.json), [연결 복구 증거](careerground_browseros_connection_recovery_20261007.json), [지속 실행·복구 절차](CareerGround_Phase_A_Connection_Recovery_Runbook_2026-10-06.md)에 근거를 기록했다. ignored 초안 20개 hash는 유지됐다. 아래 2026-10-05~06 기록은 이전 환경의 시험 이력이다.

## 재개 후 CI 보완과 브라우저 복구 관측

2026-10-07 재개 시 실행 프로세스는 없었지만 signed registry의 차단 0건과 자료 table 37개 count/hash 및 ignored 초안 20개 hash가 유지됐다. 같은 QA/runtime과 기존 tunnel을 다시 실행해 health 200을 확인했다. detached spawn의 지속 실행은 확인되지 않았으므로 백그라운드 실행 성공으로 기록하지 않는다.

신규 실행기 시험 13개는 pytest 함수여서 기존 unittest CI 명령에 수집되지 않았다. 두 파일을 명시하는 python -m pytest CI 단계를 추가했고 로컬 13 PASS·복구 unittest 3 PASS·Ruff check/format 13파일·diff check PASS를 확인했다. 이 작업 트리의 원격 CI는 아직 실행하지 않았다.

플러그인 목록의 개인용 → CareerGround Phase A Dev → 관리 경로는 작동했다. 일반 압축 파일 업로드에서는 준비 ZIP을 파일 입력에 선택했지만 새 플러그인 생성 화면이어서 추가 버튼을 누르지 않고 취소했다. 기존 plugin 1.0.3 갱신/설치는 아직 미완료다. A Web 로그인 navigation은 CDP timeout, 이후 동일 페이지 읽기도 timeout이었다. 탭 목록/다른 페이지 snapshot은 작동하고 로컬 서버·터널은 정상이다. 원인을 확정하지 않고 사용자에게 BrowserOS 파일 선택 창이 있다면 취소하고 탭 반응을 확인하는 한 단계만 요청했다. 새 background 관리 탭 8은 로그인 필요 상태이고 승인 화면/기한은 발급하지 않았다. [후속 증거](careerground_persistent_qa_followup_20261007.json).

## 삭제 후 실제 B ChatGPT/MCP 격리 확인 완료

사용자 기존 ChatGPT 로그인과 지속 QA B 재인증 뒤 actual get_my_profile은 정확한 B/found true/version 0을 반환했다. 첫 병렬 묶음의 NOT_FOUND는 어느 대상인지 알 수 없어 비교 통과로 기록하지 않았다. 결과 유실을 해결하는 6개 순차 read-only 확인에서는 삭제 A profile/JD/R2와 없는 대상을 각각 같은 NOT_FOUND/같은 메시지로 거부했다. 쓰기/승인/export/삭제는 없고 B 자료 table 34개 count/hash도 유지됐다. [실제 MCP 후속 격리](careerground_persistent_qa_after_deletion_mcp_boundaries_20261007.json).

변경한 만료 검토 갱신의 실제 PostgreSQL SQL/rollback 경로 시험을 추가했다. Ruff check/format은 통과했고 PG 미설정 실행은 skip 1이며 PASS로 확대하지 않는다. 무료 일회용 loopback PostgreSQL 17의 private env/실행 자료를 준비했으며 Docker는 일반 사용자 접근과 cached sudo 모두 불가다. 필요한 시작 명령은 다음 사용자 수동 단계다.

## A 알려진 로컬 자료 삭제와 재시작 후 보존·접근 검증

사용자 최종 삭제 뒤 A Claim/원문/초안/JD/R1/R2/승인 기록은 제거됐다. ERASE DONE 7, VERIFY DONE 30, UNVERIFIED_SCOPE VERIFY PENDING 1이며 삭제 요청과 profile stub은 DELETING이다. scope는 PROFILE/coverage FOUNDATION_ONLY라 전체 삭제 완료·외부 사본/백업·제공자 계정 삭제로 확대하지 않는다. 같은 store를 실제 재시작해 signed checkpoint 검증 성공/ledger 1/삭제 상태 지속을 확인했고 B 계정별 table 34개 count/행 hash는 유지됐다. [삭제·재시작 증거](careerground_persistent_qa_a_deletion_completed_20261007.json).

실제 인증된 B Web에서 본인 profile/session/drafts는 200이고 기존 정확한 합성 초안도 보였다. 삭제된 A profile/JD/R2 Markdown export와 없는 대상은 각각 같은 404·같은 본문·forms 0·식별자/자료 미노출이다. B session 상태 화면 자체가 원문을 표시한다고 주장하지 않는다. [Web 후속 격리](careerground_persistent_qa_after_deletion_web_boundaries_20261007.json). B ChatGPT 플랫폼 로그인은 만료돼 사용자 기존 계정 로그인을 직접 요청했고 완료 뒤 동일 기존 B 대화의 read-only MCP 후속 시험을 진행 중이다.

## 현재 QA A 패스키 등록 및 같은 store 재시작 확인

사용자가 직접 등록을 완료했고 Web registered 화면과 서명 registry의 A 공개키 1개/B 0개·origin localhost:5000을 확인했다. PIN/개인키/생체 정보를 읽거나 저장하지 않았다. 재개 시 기존 로컬 QA와 tunnel ports는 connection_refused였지만 DB/패스키는 보존됐고 종료 원인은 미확정이다. 같은 initialized store로 재실행해 runtime live/tunnel ready 200, 기존 SSO의 정확한 A profile/version 2를 확인했다.

원래 실행기를 임시 systemd --user unit으로 관리했고 QA/tunnel active 및 tunnel→QA BindsTo를 별도 호출 뒤 확인했다. 시스템 전체 서비스/자동 부팅·새 클라우드/유료 자원은 없다. B 계정별 table 34개 count/행 hash는 그대로다. 삭제는 아직 실행하지 않았다. [등록·재시작 증거](careerground_persistent_qa_a_passkey_registered_20261007.json).

## A R2 실제 내보내기 및 기기 등록 준비

사용자 내보내기 승인 뒤 같은 ChatGPT get_confirmation_status→export_resume_artifact가 실제 INLINE 본문/91 bytes/SHA256/profile version 2를 반환했고 요청 상태는 CONSUMED다. Markdown escape를 포함한 화면의 실제 문구를 읽었다. 렌더러가 마지막 LF를 생략해 90 bytes였으므로 내보내기 serializer의 마지막 LF를 보완한 본문을 별도로 UTF-8/SHA256 계산했고 서버 선언과 정확히 일치했다. 원시 MCP transport bytes를 독립 캡처한 것은 아니다. 증명/비공개 resource URI는 출력·공유하지 않았다. [내보내기 검증](careerground_persistent_qa_a_r2_export_completed_20261007.json).

현재 지속 QA의 signed passkey registry는 credential 0이다. 과거 임시 QA의 등록을 복원하거나 가상 인증기로 대신하지 않고 A 등록 검토를 앞으로 열어 기존 Google A 확인·휴대전화 PIN/생체 확인을 직접 요청했다. 등록 자체는 자료 삭제가 아니다. B 계정별 자료 table count/행 hash를 A 삭제 후 보존 검증용 private baseline에 기록했다.

## A R2 저장 완료 및 별도 내보내기 준비

사용자 R2 저장 뒤 원본 R1 보존·별도 R2의 정확한 원본 연결/version 2/어미 수정 문구/WORDING_REVIEWED·artifacts 2개를 확인했다. 새 Claim은 없다. 같은 ChatGPT proposal status는 actual DONE/result_id가 저장 R2와 일치했고 실제 trace도 정확한 R2 문구와 wording_level R2였다. [저장 및 같은 연결의 결과 확인](careerground_persistent_qa_a_r2_completed_20261007.json).

별도 RESUME_EXPORT/MARKDOWN 요청의 A/R2/version 2/형식 binding을 확인해 검토한 R2·받을 연결 앱 범위를 표시했다. 최종 두 확인/내보내기 허용을 사용자에게 요청했고 MCP 본문 수신은 아직 없다. [내보내기 준비 증거](careerground_persistent_qa_a_r2_export_prepared_20261007.json).

## A R1 문구 승인 완료 및 R2 검토 준비

사용자 문구 승인 뒤 R1/해당 unit은 WORDING_REVIEWED이고 같은 ChatGPT submit_resume_wording_review 결과가 ok/operation CONSUMED다. 첫 R2 쉼표 추가는 서버 VALIDATION_FAILED였고 실제 로컬 guard에서도 FACT_OR_QUALIFIER_CHANGED였다. 형식 보정 재시도도 성공하지 않았다. 현재 보수적 검사는 공백/문장 끝 구두점 또는 동일 과거 어미 변형만 허용해 내부 쉼표 변경도 거부한다. 정책을 약화하지 않고 어미만 공유했습니다→공유했다로 바꾼 제안을 같은 source/근거/NO_NEW_FACTS로 한 번 준비해 actual ok true를 확인했다. [검사 한계 관측](careerground_persistent_qa_a_r2_guard_observation_20261007.json).

Web에 정확한 R1/R2 변경 전후와 동일 근거·기준 version 2를 표시했고 원본 R1 보존·별도 R2 저장 범위의 사용자 최종 확인을 요청했다. 아직 R2 저장·export는 없다. [R2 준비 증거](careerground_persistent_qa_a_r2_prepared_20261007.json).

## A R1 저장·같은 연결의 결과 처리 완료

사용자 새 R1 최종 승인 뒤 정확한 owned R1 문구 unit 1개·profile version 2·REVIEW_REQUIRED를 확인했다. 같은 ChatGPT 연결의 get_confirmation_status→generate_resume_draft가 ok로 완료돼 해당 요청은 CONSUMED다. artifact는 여전히 1개이며 증명을 출력/공유하거나 중복 초안을 생성하지 않았다. [저장 및 처리 증거](careerground_persistent_qa_a_r1_draft_completed_20261007.json).

별도 WORDING_REVIEW 요청의 A/artifact/version 2 binding을 확인했고 R1 문구와 근거·결과 수신 앱을 표시하는 화면을 앞으로 열었다. 사용자 최종 두 확인/문구 승인이 남았으며 내보내기 승인은 없다. [문구 검토 준비](careerground_persistent_qa_a_r1_wording_prepared_20261007.json).

## R1 초안 검토 준비 및 증명 조회 한계

JD 연결 저장은 완료됐지만 같은 ChatGPT의 get_confirmation_status 1회가 REVIEW_REQUIRED로 거부돼 결과 소비는 미수행이다. 그 요청의 실제 expires_at은 05:47:03 UTC이고 이후 확인 시 이미 지난 상태였다. 정확한 RPC 실패 원인은 확정하지 않았다. 증명/기한을 되살리거나 기존 연결을 중복 승인하지 않고 저장된 canonical mapping을 사용해 새 R1_DRAFT 검토를 요청했다.

새 R1 요청의 A owner/JD target/version 2를 확인하고 서버가 표시한 ALLOWED 합성 Claim 한 문구를 검토용으로 선택했다. 정확한 내용 확인 POST까지만 진행했으며 최종 두 확인/작업 승인은 사용자에게 요청했다. [R1 준비 증거](careerground_persistent_qa_a_r1_draft_prepared_20261007.json).

## A 잠재 JD 연결 승인 완료

사용자 최종 승인 뒤 Web 완료/operation DONE 및 version 2의 RELATED/POTENTIAL mapping 1개를 확인했다. 새 사실이나 완전 충족 인증은 없다. 같은 요청 시작 ChatGPT 연결에만 get_confirmation_status의 DONE 증명을 전달해 link 결과를 처리하고, 별도 R1_DRAFT 검토를 준비하도록 요청했다. 실제 결과 소비는 후속 확인 전 완료로 기록하지 않는다. [승인 증거](careerground_persistent_qa_a_jd_link_completed_20261007.json).

## A 합성 JD 발췌 저장 및 별도 잠재 연결 준비

사용자 직접 저장 뒤 Web 완료 화면과 DB의 owned JD 1개·정확한 source hash/24자 원문·요건 [0,24) 1개를 확인했다. 근거 maps/artifact는 0이다. 같은 ChatGPT proposal status 1회는 VALIDATION_FAILED라 MCP 완료 결과 조회 성공으로 기록하지 않았고 재시도하지 않았다. 실패 원인은 미확정이다. 실제 get_jd_analysis는 정확한 저장 요건·연결 빈 목록·NO_ELIGIBLE_LINK_RECORDED를 반환했다. [JD 저장 증거](careerground_persistent_qa_a_jd_completed_20261007.json).

별도 JD_LINK 확인 요청의 A 소유자·JD 대상·version 2를 확인했다. 서버 Web 선택지의 요건과 ALLOWED 합성 Claim 한 쌍을 agent가 최종 검토용으로 선택하고 정확한 내용 확인 POST까지만 진행했다. 새 사실/완전 적합성이 아닌 잠재 관련성 화면이며 최종 두 확인/작업 승인은 사용자에게 요청했다. [잠재 연결 준비 증거](careerground_persistent_qa_a_jd_link_prepared_20261007.json).

## A 재연결 후 합성 JD 검토 준비

사용자 A 재연결 후 같은 ChatGPT 대화가 기존 요청을 자동 재개했다. 중복 입력/도구 요청을 보내지 않고 actual version 2/WAITING/canonical_saved=false와 실제 confirmation URL을 확인했다. 한 줄 합성 JD 원문 ‘장애 로그 분류 및 팀 확인 절차 공유 경험’ 전체 [0,24)의 후보 1개만 준비됐고 claim null/evidence 빈 배열로 근거 연결은 없다. A Web의 HTTP 200/기준 version 2/정확한 원문·범위·연결 없음 표시를 확인해 탭 8을 앞으로 열고 사용자 발췌 선택/저장 범위 확인을 요청했다. 저장 JD/artifact는 제출 전 0이다. 생성 후 180초 만료이며 반환에 expires_at 필드가 없었으므로 실제 시각을 추정하지 않았다. [준비 증거](careerground_persistent_qa_a_jd_review_prepared_20261007.json). 아래 만료 상태는 재연결 전 관측이다.

## A 별도 사용 검토 완료 및 다음 연결 만료

사용자 직접 저장 후 정확한 Claim 한 문구의 사용 검토 1건을 확인했다. 보관 프로필 version 1→2, 상충 없음·사용 허용 두 선택 true, Web USER_CONFIRMED/CONSISTENT/ALLOWED다. B version 0/Claim·사용 검토 0 및 삭제 요청/ledger 0은 유지됐다. [저장 증거](careerground_persistent_qa_a_use_review_completed_20261007.json). 이는 R1 생성·문구·내보내기 승인이 아니다.

최신 설치 plugin의 같은 A 대화에 현재 버전 확인 후 한 줄 합성 JD의 미승인 발췌 준비를 요청했지만, 프로필A 연결 만료 안내가 나왔다. 새 MCP profile/version 응답이나 JD 제안 링크는 반환되지 않았고 저장 JD/artifact는 0이다. 기존 A 다시 연결 화면을 준비하고 실제 OAuth 단계만 사용자에게 요청한다. [연결 만료 관측](careerground_persistent_qa_a_jd_auth_gate_20261007.json).

## 기존 비공개 플러그인 1.0.3 갱신 완료

사용자 메뉴 확인 뒤 브라우저를 앞으로 활성화한 조작이 정상 반영됐고 기존 plugin의 새 버전 업로드 메뉴를 관측했다. 원래 준비한 portable 이름 careerground 패키지는 기존 이름 불일치로 거부됐다. 기존 ZIP의 실제 .codex-plugin/plugin.json 이름과 .app.json 바인딩 bytes·파일 구조를 보존한 수정 1.0.3 패키지를 만들어 같은 plugin에 업로드했다. 성공 dialog·표시 버전·다시 내려받은 ZIP의 1.0.3/최신 skill byte/hash 일치를 확인했다. 이전 준비 기록의 이름 보존 주장은 이 새 관측으로 정정하며 원래 ZIP/거부된 패키지는 보존했다.

갱신 뒤 새 ChatGPT 대화에서 프로필A를 명시하고 기대 ID를 주지 않은 실제 조회는 정확한 A/version 1 및 합성 문구를 반환했다. USER_CONFIRMED 사실 확인과 REVIEW_REQUIRED 사용 정책·NOT_EVALUATED 일관성을 구분했다. 조회 뒤 자료 table 37개 count/hash는 유지됐다. 새 Web 탭 8의 기존 SSO 로그인이 완료돼 정확한 A profile·근거 링크를 확인했다. 앞선 파일 선택 창 원인 가설은 확정하지 않는다. 새 앱·Auth0 설정/grant·유료 자원은 변경하지 않았다. [갱신 및 왕복 증거](careerground_persistent_qa_private_plugin_update_20261007.json). 설치 skill 사용 switch는 true이고 최신 계약 본문도 렌더링됐다. 검증용 background 탭은 닫았다. A의 Web 탭 8에 별도 R1 사용 검토를 열어 사용자의 정확한 합성 문구/근거/상충 없음/사용 허용 제출을 요청했다. 현재 A version 1이며 사용 승인은 아직 저장되지 않았다. 기존 평가한 36개/각 task 9개 품질 기록은 같은 source hash이므로 반복하지 않았다. 이후 사용 승인/export/삭제의 사람 최종 단계는 남았다.

## 2026-10-06 완료한 시험: A/B 사실·사용 검토 및 각각 R1 문구 승인

A의 직접 사실 검토로 Claim 2개가 저장됐고, 선택한 incident Claim의 별도 R1 사용 승인 1건이 완료돼 현재 프로필 버전 2다. 이 문구는 USER_CONFIRMED/CONSISTENT/ALLOWED이며 다른 문구의 사용 허용을 뜻하지 않는다. B도 기존 Claim 1개의 별도 사용 승인 1건이 저장돼 프로필 버전 2이며 합성 JD·R1의 별도 문구 검토까지 완료했다. 각각 요청을 시작한 ChatGPT 연결이 사실 확인 결과를 조회하고 증명을 사용해 operation이 CONSUMED가 됐다.

A/B의 내용 있는 profile·Claim 근거·R1 사용 검토·export 검토 Web GET은 양방향 본인 200, 다른 계정의 같은/없는 대상 동일 404로 확인됐다. B 완료 확인 화면도 기한 이전 A에게 증명을 노출하지 않았다. MCP의 다른 계정 profile/근거 조회는 양방향 NOT_FOUND, export 확인 요청은 REVIEW_REQUIRED였다. A의 합성 JD 발췌 두 요건·RELATED/POTENTIAL 연결 1개·정확한 R1 문구 1개가 저장됐고 별도 문구 승인 뒤 WORDING_REVIEWED다. 각각 같은 요청 시작 ChatGPT 연결의 결과 소비를 확인했다. A 본인 MCP R1 trace도 승인 문구와 version 2를 반환했다. JD/R1/검토한 R1 export 준비 Web GET은 본인 허용·B의 같은/없는 대상 동일 404였다. B 재연결 뒤 실제 B/version 1을 확인했고 A JD/R1 및 없는 대상의 MCP 조회 4건은 NOT_FOUND, R1 export 확인 요청 2건은 REVIEW_REQUIRED였다. 빈 증명의 R1 export executor 요약은 null이라 미확인으로 남겼다. B의 합성 JD 1요건·RELATED/POTENTIAL 연결 1개·R1 한 문구가 생성됐고 Web JD/R1 교차 접근 거부도 확인됐다. B 별도 문구 승인도 저장·같은 연결의 결과 소비가 끝났고 실제 B trace는 정확한 한 R1 문구/WORDING_REVIEWED를 반환했다. 양방향 검토된 R1 export 준비 Web GET은 본인 허용·다른 계정/없는 대상 동일 404였다. A 재연결 뒤 프로필A를 명시한 실제 discovery가 A를 반환했다. A→B JD/R1 조회 4건은 NOT_FOUND, R1 export 확인 요청 2건은 REVIEW_REQUIRED로 없는 대상과 동일했고 자료 table 37개와 operation 14개가 유지됐다. 첫 foreign export 확인 요약 null은 미확인으로 보존하고 별도 단일 호출의 실제 오류를 확인했다. 양방향 MCP artifact 조회·확인 요청 비교가 끝났으며 유효 증명의 다른 계정 submit·R2·실제 export/삭제 실행은 남았다. 아래 초기 상태 기록은 관측 당시의 이력이다.

- [사실 저장 및 같은 연결의 결과 확인](careerground_actual_fact_review_completed_20261006.json)
- [내용 있는 profile/Claim의 Web 조회 격리](careerground_actual_confirmed_profile_web_get_20261006.json)
- [A MCP의 확인된 profile 조회](careerground_actual_mcp_a_confirmed_profile_20261006.json)
- [B 사실 저장 및 같은 연결의 결과 확인](careerground_actual_b_fact_review_completed_20261006.json)
- [B 저장 자료 및 완료 확인 화면의 Web 조회 격리](careerground_actual_confirmed_b_profile_web_get_20261006.json)
- [B MCP의 A 저장 자료 접근 비교](careerground_actual_mcp_b_confirmed_profile_boundaries_20261006.json)
- [A 재연결 및 B 저장 자료 접근 비교](careerground_actual_mcp_a_confirmed_profile_boundaries_20261006.json)
- [A의 별도 R1 사용 승인](careerground_actual_a_r1_use_review_20261006.json)
- [A 합성 JD 저장](careerground_actual_a_jd_completed_20261006.json)
- [A 잠재 관련성 연결 저장](careerground_actual_a_jd_link_completed_20261006.json)
- [A R1 생성](careerground_actual_a_r1_draft_completed_20261006.json)
- [A 별도 R1 문구 승인](careerground_actual_a_r1_wording_completed_20261006.json)
- [R1 Web 조회 격리와 미검토 export 차단](careerground_actual_r1_web_get_isolation_20261006.json)
- [검토한 R1 export 준비 Web 조회 격리](careerground_actual_reviewed_r1_export_web_get_20261006.json)

## 실제 A/B 로그인 및 패스키

사용자가 서로 다른 본인 Google 계정 A/B로 새 격리 QA에 로그인하고 각각 빈 프로필을 직접 생성했다. 실제 검증된 identity 2개/프로필 2개를 확인했다. A는 보존한 이전 QA의 A와 일치하며 B는 다른 identity다. BrowserOS의 B context는 A와 분리되어 있다. 원문 subject·쿠키·토큰·인증 코드·PIN을 증거 문서에 저장하지 않았다.

사용자가 A의 패스키를 직접 등록했다. 등록 완료 화면과 서명 registry의 HMAC, 정확한 새 store·origin binding을 확인했다. A의 공개키 등록은 1개, B의 등록은 0개다. 현재 삭제 요청·erasure ledger는 각각 0개다. 이 등록은 이후 삭제의 새 기기 서명·별도 최종 승인을 대신하지 않는다. 이전 완료된 빈 QA 삭제와 해당 공개키 registry는 보존했다.

## 실제 Web GET 교차 접근

profile·profile export·삭제 미리보기·로컬 삭제 검토 4경로를 A→B/B→A 방향으로 시험했다. 총 24회 대상별 조회에서 본인 대상은 200, 다른 계정 대상과 없는 대상은 동일한 404·동일 본문·form 0이었다. 다른 대상 ID를 본문에 노출하지 않았으며 8개 교차 접근 조합이 통과했다. 이는 새 빈 프로필에 대한 실제 Web GET 증거다.

- [대상 식별자를 제외한 BrowserOS 관측](careerground_release_web_get_isolation_20261005.json)

검증 전후 SQLite 38개 table 중 `request_limit_buckets`만 0→1로 변했다. 나머지 37개 count는 같았으며 삭제 요청·ledger는 0이다. 읽기 요청 제한 기록의 변화를 경력 자료 변경으로 설명하지 않는다. 이전 QA·설정·초안의 보존 파일 60개 hash는 유지됐다.

POST 쓰기/승인·내용 있는 source/artifact·실제 A/B MCP 접근은 아직 완료하지 않았다. 합성 JWT 회귀를 실제 제공자 MCP 증거로 대체하지 않는다.

## 사용자 품질 평가 수용

사용자가 제출한 평가 파일의 fixture/observation hash가 기존 별도 36개 관측과 일치했고, 정확히 36개의 유일 ID와 누락 없는 평가를 확인했다. 기준은 `HUMAN_ACCEPTED`, 의미·자연스러움은 모두 5/5, 안전 위반 0건이다. extract/JD/R2/R3의 분류 일치는 각각 9/9다. **이번 비공개 합성 사례 품질 gate PASS**를 별도 집계 결과에 기록했다.

- [사용자 평가 원본](chatgpt_private_mvp_human_review_20261005.json)
- [검증 및 집계 결과](chatgpt_private_mvp_human_review_result_20261005.json)

원본의 `quality_gate_passed=false`는 검토 화면의 자동 합격 선언 방지 값이며 그대로 보존했다. fixture·관측·기존 점수도 수정하지 않았다. 프로젝트 소유자의 실제 평가이며 독립 blind 평가·운영 지연/품질·설치 plugin 왕복을 통과했다는 의미는 아니다.

## 연결 복구 및 plugin 준비

정확한 활성 account/client만 해제하는 offline 복구 명령을 준비했다. 정상 runtime이 store/registry lock을 보유하면 거부하며, 별도 명시 확인·서명/바인딩·실제 소유 identity를 확인한다. 누락 store를 초기화하지 않고 다른 account/client 차단을 유지한다. Web/MCP 자동 해제 route와 제공자 grant 변경은 없다. 연결 관련 회귀 8개 및 변경 4파일 Ruff check/format이 통과했다. 새 test 파일을 CI의 정적 검사 목록에 포함했다.

기존 승인된 터널의 설정·키를 변경하지 않고 재시작했고 loopback healthz/readyz 200을 확인했다. 새 터널·과금·서버 모델 API를 추가하지 않았다. 원문 HTTP logging은 끄고 daemon 출력은 private 임시 파일에 보관한다.

기존 비공개 plugin의 이름·앱 바인딩·파일 목록을 유지한 1.0.3 ZIP을 별도 임시 파일에 준비했다. 현재 source skill hash는 기존 새 품질 관측의 hash와 같다. 기존 1.0.2 ZIP은 보존했다. **아직 업로드하지 않았다.**

위 내용은 이전 임시 환경의 준비 이력이다. 2026-10-07에는 Git 제외·0700 지속 경로 `.careerground-release-qa/release-20261007/packages/`에 owner-only 0600의 `careerground-phase-a-dev-1.0.3.zip`을 다시 준비했다. allowlist 파일은 `.app.json`, `plugin.json`, `skills/career-interview/SKILL.md` 3개이고 기존 앱 바인딩은 유지했다. 버전 1.0.3·ZIP 무결성·검토한 source skill hash 일치·repo source 파일 보존을 확인했다. 캐시의 설치 스킬 1.0.2는 최신 source와 다르며 아직 갱신 업로드/설치/실제 왕복은 실행하지 않았다. [새 지속 패키지 준비 증거](careerground_private_plugin_preparation_20261007.json)에 기록했다.

## 현재 남은 단계

### 2026-10-06 B 연결 경로 수정

사용자는 기존 창의 ‘다른 계정 연결’이 동일 계정의 연결 프로필만 늘린다고 보고했다. ChatGPT UI의 프로필A/프로필B 표시만으로 다른 실제 provider identity를 확인할 수 없다. CareerGround 서버의 accounts/auth_identities/career_profiles는 각각 2개, 삭제 요청은 0개였다. 서버 프로필이 추가 생성됐다는 증거는 없다.

기존 SSO 세션 재사용이 유력한 원인이다. [Auth0 공식 SSO 설명](https://auth0.com/docs/authenticate/single-sign-on)에 따르면 인증 서버의 기존 SSO cookie가 있으면 로그인 화면 없이 기존 사용자로 돌아올 수 있다. 실제 MCP 호출 결과로 identity를 확인하기 전 원인을 확정하거나 B 연결 성공을 선언하지 않는다.

이미 B로 CareerGround에 로그인한 분리 BrowserOS context에 새 ChatGPT 창을 준비했다. 사용자가 **현재 사용하는 같은 ChatGPT 계정**으로 직접 로그인한 뒤 그 창에서 제품 OAuth를 B로 진행한다. 새로운 ChatGPT 계정·유료 가입은 필요하지 않으며 A의 원래 창/로그인·연결·grant는 유지했다. Google/Auth0 전체 로그아웃·cookie 삭제·공유 provider 설정 변경으로 전환을 강제하지 않았다. 중복 연결 항목의 삭제는 아직 수행하지 않았다.

후속 사용자 로그인 뒤 두 ChatGPT 계정 화면에서 표시 이메일이 서로 다름을 확인했다. 비교는 원문을 출력하지 않고 메모리에서 hash로 처리했으며 실제 이메일/계정 hash는 이 문서나 Git 자료에 저장하지 않았다. 별도 창의 ChatGPT만 기존 플러그인 관리 계정으로 재로그인하는 단계가 필요하다. CareerGround의 Google B 로그인과 ChatGPT의 로그인 계정을 구분하며, B context·기존 A 연결·CareerGround B session을 보존했다. 승인된 localhost runtime health와 기존 tunnel ready는 200으로 확인했다. B MCP 연결은 여전히 미확정이다.

사용자 재로그인 후에는 별도 창의 ChatGPT 계정이 기존 플러그인 관리 계정과 일치함을 확인했다. 같은 B context와 현재 B Web 프로필도 보존됐다. 그 창에서 기존 제품 plugin의 다른 계정 연결을 다시 준비했다. 실제 B OAuth 동의 및 MCP 반환 프로필 확인은 아직 남았다. 기존 연결 별칭/A grant는 변경하지 않았다.

### 실제 B MCP 연결 및 조회 검증 완료

사용자는 계정 선택 화면 없이 연결을 완료했다고 보고했다. 별도 창의 임시 ChatGPT 대화에서 기대 profile ID를 주지 않고 `get_my_profile` 1회만 요청했다. 반환된 프로필이 새 QA의 B와 일치하고 A와 불일치하며 버전은 0이다. 서버의 서명 검증·계정 매핑 뒤 request quota에서 실제 B/read 요청 1건도 확인했다. **이번 제품 MCP 연결은 실제 B로 확인됐다.** UI 표시명과 계정 선택 화면의 유무만으로 identity를 판정하지 않는다.

이어 같은 B 연결에서 A QA 프로필과 없는 프로필에 대해 `get_career_profile` 2회를 요청했다. 두 결과는 같은 `NOT_FOUND`였으며, 서버의 실제 B/read 2건을 확인했다. 경력 session/input·승인 browser operation·삭제 요청·ledger는 모두 0이고 프로필 2개는 유지됐다.

- [B identity discovery 증거](careerground_actual_mcp_b_discovery_20261006.json)
- [B→A 및 없는 대상의 같은 조회 거부](careerground_actual_mcp_b_cross_read_20261006.json)

`get_my_profile`의 실제 schema에는 current_policy_version이 없으므로 모델이 출력한 null을 현재 정책 확인 완료로 기록하지 않았다. 이는 B identity/조회 범위만 통과한 것이다. 실제 A→B MCP·쓰기·승인·export·삭제 및 내용 있는 source/artifact 격리 시험은 아직 남아 있다.

### B 쓰기·export 요청·삭제 미리보기 및 인증 갱신 경계

B 연결의 `start_profiling`으로 A profile과 없는 profile에 세션 생성을 요청했을 때 모두 `NOT_FOUND`였다. `request_user_confirmation(PROFILE_EXPORT)`는 두 대상 모두 `REVIEW_REQUIRED`, `preview_data_deletion(PROFILE)`은 두 대상 모두 `NOT_FOUND`였다. 승인 operation·삭제 요청·ledger는 생성되지 않았다. 이는 해당 요청들의 실제 거부 증거이며 export/삭제 실행·유효 승인 증명의 교차 사용 통과로 확대하지 않는다.

복수 도구 호출 후 모델이 일부 없는 대상 결과를 null로 요약한 경우는 판정하지 않았다. 그 대상만 단일 호출로 확인하고 실제 오류 envelope를 기록했다. 요청 제한 quota는 현재 시간 구간의 값이며 전체 누적 호출 수가 아니다.

- [B 세션 생성 거부](careerground_actual_mcp_b_negative_write_20261006.json)
- [B export 승인 요청 거부](careerground_actual_mcp_b_negative_export_request_20261006.json)
- [B 삭제 미리보기 거부](careerground_actual_mcp_b_negative_deletion_preview_20261006.json)

내용 있는 자료의 격리 시험을 위해 B 본인 profile에 실제 MCP를 통해 합성 원문 1건을 저장했다. ChatGPT 반환 ID와 DB의 실제 소유자·세션·원문 전체·입력 종류·idempotency key가 일치한다. 승인된 Claim은 0이며 실제 경력 자료를 사용하지 않았다.

- [B 합성 원문 저장 확인](careerground_actual_mcp_b_synthetic_input_20261006.json)

같은 source의 Python Unicode `[9,59)` 구간으로만 실제 MCP 임시 초안 1개를 생성했다. DB 소유자·세션·source ID/hash와 50글자 exact_text의 일치를 확인했으며 상태는 `DRAFT`, 승인된 Claim은 0이다. 측정하지 않은 처리시간 개선 수치를 추가하지 않았다. 향후 source/draft 교차 접근 시험의 준비이며 사실/사용 승인이나 최신 설치 skill 검증 완료가 아니다.

- [B 원문 구간 초안 확인](careerground_actual_mcp_b_synthetic_draft_20261006.json)

A의 `get_my_profile` 시험은 실제 도구 호출 불가로 끝났고 서버 A read quota도 없었다. 기존 프로필A 연결의 ‘인증 업데이트가 필요합니다’를 확인해 재연결 dialog를 준비하고 사용자에게 직접 OAuth 완료를 요청했다. 이 실패는 A identity 확인이나 서버의 교차 접근 거부 결과가 아니다. 기존 연결을 삭제하거나 Auth0 설정·grant를 변경하지 않았다.

새 Web 조회에서는 A의 B session 대상과 B의 본인 session 대상이 모두 401 로그인 필요였다. 따라서 인증된 source 교차 접근 증거로 채택하지 않았다. MCP A 재연결 후 Web 로그인 갱신이 필요한 상태다. 이전 보존 대상 60개 hash는 유지됐다.

- [인증 갱신 필요 관측과 검증 범위](careerground_actual_auth_gate_observation_20261006.json)

이번 만료 Web 조회용으로 연 background 시험 탭 2개만 닫았다. 기존 A OAuth 재연결 dialog·B 창·새 QA runtime/tunnel은 다음 직접 인증 단계용으로 유지했다. 새 commit/push는 수행하지 않았다.

### A 재연결 후 Web 로그인 및 내용 있는 자료의 조회 격리

사용자가 A 재연결을 완료했고 프로필A 연결 항목의 인증 갱신 필요 표시가 사라졌다. 기존 provider SSO를 통한 Web 로그인 redirect로 A/B 관리 화면 로그인을 갱신했다. `/account`의 실제 profile 링크가 각각 QA A/B와 일치한다. 쿠키·인증정보를 복사하거나 새 프로필을 만들지 않았다.

갱신된 Web에서 B 본인의 session/drafts는 200이고 내용 있는 정확한 초안이 표시됐다. A의 같은 B 대상과 없는 대상은 각각 같은 404·같은 본문·form 0·ID/초안 미노출이었다. 두 경로의 6 GET을 확인했다. 역방향·POST·artifact·전체 원문 조회 시험 완료를 뜻하지 않는다.

- [인증된 A→B session/draft 조회와 B 본인 대조](careerground_actual_web_nonempty_b_get_20261006.json)

A의 ChatGPT discovery 요청은 아직 실패했다. 실제 A MCP identity는 확인하지 않았다. 설정 화면의 floating chat 상태를 바로잡고 새 임시 채팅의 ‘개인화되지 않음’/플러그인 무시 안내를 확인했다. 개인화 메뉴 자동 클릭 두 방식이 동작하지 않아 사용자에게 해당 화면 전환만 요청했다. 완료한 OAuth 재로그인·동의를 다시 요청하지 않았다. 현재 Web/MCP의 공유 read quota를 MCP 전용 호출 수로 해석하지 않는다.

실제 연결 차단 전 대상 승인·정확한 client 관측·정상 종료·오프라인 복구·같은 store 재시작 순서를 정리했다. 차단이나 Auth0 grant 철회는 실행하지 않았다.

- [개발 연결 차단·복구 절차](CareerGround_Phase_A_Connection_Recovery_Runbook_2026-10-06.md)

### A MCP 확인 및 내용 있는 자료의 양방향 시험

사용자가 A 임시 채팅을 개인화됨으로 전환한 뒤 실제 `get_my_profile` 반환이 QA A와 일치/B와 불일치하고 버전은 0이었다. 기대 ID를 제공하지 않았다. **실제 A/B 제품 연결의 identity는 모두 확인됐다.**

- [A discovery](careerground_actual_mcp_a_discovery_20261006.json)
- [A MCP 부정 시험 12건](careerground_actual_mcp_a_negative_boundaries_20261006.json)

A의 profile/session 조회·세션 생성·원문 추가·PROFILE_EXPORT 승인 요청·PROFILE 삭제 미리보기는 다른 계정과 없는 대상에 대해 같은 오류였다. count뿐 아니라 38개 table의 행 내용 hash를 비교해 요청 제한 table 외 37개가 유지됨을 확인했다. profile 조회 대상은 아직 빈 profile이며 내용 있는 archive/artifact나 실제 export/삭제 실행·유효 완료 증명 교차 사용의 증거로 확대하지 않는다.

A 본인에 실제 MCP로 합성 원문 1개와 정확한 Unicode 구간 임시 초안 2개를 생성했다. 소유자·세션·source/hash/text가 일치한다. BrowserOS 제출 반환이 유실된 두 경우는 대화와 DB 결과를 확인한 후 재제출하지 않았다.

- [A 원문](careerground_actual_mcp_a_synthetic_input_20261006.json)
- [A 임시 초안 2개](careerground_actual_mcp_a_synthetic_drafts_20261006.json)
- [B→A 내용 있는 Web 조회](careerground_actual_web_nonempty_a_get_20261006.json)
- [양방향 Web 원문 추가 POST](careerground_actual_web_source_post_isolation_20261006.json)
- [B MCP의 A/없는 session 조회·원문 추가](careerground_actual_mcp_b_source_boundaries_20261006.json)

session/draft Web GET은 양방향 모두 본인 200, 다른 계정/없는 대상 같은 404·본문·form 0·ID/문구 미노출이었다. POST 4건은 본인의 정상 입력 폼/token을 DOM 안에 유지하고 action 대상만 변경했다. 두 방향 모두 다른 계정과 없는 대상에 같은 409·본문·form 0으로 저장하지 않았다. token을 추출·복사하지 않았다. 이 부정 시험 요청들 뒤의 37개 자료 table 행 내용도 유지됐다. Web의 직접 사실/사용/내보내기/삭제 승인은 제출하지 않았다.

본인 A session과 B source ID를 섞는 초안 제안에는 ChatGPT가 안전 검사로 실제 호출하지 않았다고 응답했다. 서버 거부로 판정하지 않고 미확인 항목으로 남겼다. 같은 요청을 다른 context로 우회 실행하지 않았다.

- [원문 ID 조합 요청의 client 보고와 확인 한계](careerground_actual_chatgpt_source_mixing_observation_20261006.json)

### 실제 사실 검토 준비 및 승인 정보 격리

A의 합성 문구 2개로 FACT_REVIEW batch와 WAITING 확인 operation을 실제 MCP에서 준비했다. 서명 검증 뒤 기록된 정확한 client metadata는 private QA 파일에만 보관했다. A Web의 검토 화면은 200이고 선택란 2개·직접 확인/연결 앱 결과 전달 체크가 있다. B의 같은/없는 operation은 같은 404·본문·form 0이다. B MCP의 확인 상태 조회도 두 대상 모두 `REVIEW_REQUIRED`였다. 최초 NOT_FOUND 예상은 현재 `_owned` 계약을 확인해 바로잡았으며 요청을 재제출하지 않았다.

- [Web 검토 화면 접근 격리](careerground_actual_web_confirmation_get_isolation_20261006.json)
- [MCP 확인 상태 조회 격리](careerground_actual_mcp_confirmation_status_isolation_20261006.json)

사용자에게 A의 Web 최종 사실 검토 한 단계만 요청했다. agent는 결정을 선택하거나 제출하지 않았고 완료 증명을 추출·출력하지 않았다. 사실 확인은 별도 사용 허용·export·삭제 승인과 구분한다.

1. A/B identity·양방향 session/draft GET·원문 추가 POST/MCP·export 요청/삭제 미리보기·A 검토 화면/상태 조회 거부는 확인됐다. A Web 최종 사실 검토는 사용자 단계가 진행 중이다. 내용 있는 archive/artifact와 유효 완료 증명 경계·실제 실행 범위는 남아 있다. 원문 ID 조합의 실제 MCP 서버 거부는 client 보고만 있어 미확인이다. 기존 연결은 제거하지 않았다.
2. 실제 연결 차단/해제·만료·재연결. 공유 client에 영향을 주는 변경은 대상과 복구 범위를 확정한 뒤 구체 승인을 받는다. PoC/제품 두 연결이 같은 client/grant를 공유할 수 있다는 경계를 유지한다.
3. 준비한 최신 private plugin의 갱신·실제 도구 왕복.
4. 내용 있는 합성 대화→Web 사실/사용 검토→JD→R1/R2→export→새 패스키 확인/최종 로컬 삭제→재시작 차단. 사용자 직접 승인·기기 확인이 필요한 실제 단계는 미리 일괄 승인하지 않는다.
5. 증거 통합·개인 MVP 수용/운영 gate 정리·소유한 임시 runtime/tunnel 정리. OTP MFA·유료 서버 AI·refresh는 보류하며 commit/push는 이번 요청에 포함되지 않는다.

개발 runtime·BrowserOS 검증 절차 참고: [OpenAI 공식 연결·시험 문서](https://developers.openai.com/plugins/deploy/connect-chatgpt). 실제 UI와 관측 결과를 우선하며 문서 안내만으로 성공을 선언하지 않는다.

- 2026-10-06 사실 검토 제출 409를 확인했다. 요청은 한국시간 09:03:57에 이미 만료됐으며 Claim/ClaimReview 0, 합성 원문 2개/초안 3개가 유지됐다. 만료만으로 거부 조건을 충족하며 일반 오류 화면에서 유일한 원인을 추정하지 않는다. 기존 batch/operation은 보존하고 새 idempotency key로 다시 준비한다. 연결 요청은 5분, 화면의 내부 제출 검토는 최대 3분이므로 두 제한을 구분해 즉시 안내한다. 사실 검토 렌더링에 최대 3분·새 검토 요청 안내 문구를 추가했으며 실행 중 서버에는 후속 재시작 때 적용한다. 기한 연장·자동 승인·재로그인 반복은 하지 않는다. 증거: docs/careerground_actual_fact_review_expiry_20261006.json.

- 재준비 MCP는 NOT_FOUND였다. 실제 원인은 만료 PREPARED batch가 초안을 IN_REVIEW로 계속 잠가 새 key의 준비가 DRAFT를 찾지 못하는 결함이었다. prepare_for_scope에 본인·현재 session/scope의 미제출 만료 검토만 EXPIRED로 남기고 초안을 새 검토에 다시 담는 복구를 추가했다. 기존 key·기한·digest·결정을 살리지 않으며 살아 있는/타인 검토는 건드리지 않고 source/hash/현재 version을 재검증한다. 새 회귀 3개 및 관련 시험은 41 PASS/8 SKIP(로컬 PostgreSQL 미연결), Ruff/diff 통과다. 같은 QA store와 패스키로 runtime을 재시작하며 초기화/기한 연장/Claim 승인은 하지 않는다.

- 수정 후 실제 MCP에서 만료 batch는 EXPIRED로 남고 같은 초안 2개로 새 PREPARED/WAITING 검토를 만들었다. A 본인 Web SSO도 자동 갱신됐으며 동일 profile version 0·Claim 0·등록 패스키를 유지했다. 새 검토만 사용자에게 즉시 안내한다. 증거: docs/careerground_actual_fact_review_renewal_20261006.json.

- 사용자 직접 사실 검토 제출이 완료됐다. 실제 batch SUBMITTED·Claim 2개·A profile version 1을 확인했다. 같은 A ChatGPT 연결의 get_confirmation_status가 DONE을 반환했고 submit_claim_review 성공 뒤 operation CONSUMED가 됐다. 완료 증명을 agent가 추출/출력하지 않았다. 모델의 version_after null은 실제 계약 필드로 추정하지 않고 store에서 1을 확인했다. 두 사실은 USER_CONFIRMED/NOT_EVALUATED/REVIEW_REQUIRED이며 사용 승인 0·삭제 요청 0이다. 증거: docs/careerground_actual_fact_review_completed_20261006.json.

- 사실 확인 후 실제 Web에서 A version 1의 보관 profile·Claim 근거·별도 R1 사용 검토·profile export 검토 4경로를 조회했다. A 본인 200, B의 같은/없는 대상은 동일 404·본문·form 0·ID/문구 미노출로 12 GET 통과다. 잘못 구성했던 export 경로의 404는 제외하고 source의 실제 경로로 본인 200을 다시 확인했다. CSP를 완화하지 않고 native navigation을 사용했다. 실제 다운로드·POST·역방향 내용 있는 B profile·artifact로 확대하지 않는다. 증거: docs/careerground_actual_confirmed_profile_web_get_20261006.json.

- A의 실제 get_career_profile(version 1)는 Claim 2개와 USER_CONFIRMED/NOT_EVALUATED/REVIEW_REQUIRED를 반환했다. B의 저장 후 MCP 교차 조회 요청은 연결 만료 dialog에 막혔고 서버 거부 증거가 아니다. B 재연결 한 단계만 사용자에게 요청했고 pending 대화를 재제출하지 않았다. 이전 보존 대상 60개 hash는 유지됐으며 이번 commit/push는 없다.

- B 재연결 후 개인화된 새 임시 ChatGPT에서 기대 ID 없는 get_my_profile이 실제 QA B/version 0을 반환했다. A의 내용 있는 version 1 profile/Claim 근거와 없는 대상의 MCP 조회 4개는 모두 NOT_FOUND, PROFILE_EXPORT 확인 요청 2개는 REVIEW_REQUIRED였다. 빈 receipt의 export executor 2개는 모델 status/code null이라 통과로 판정하지 않았다. 37개 non-quota table의 count/행 hash와 operation 상태를 비교해 변동 없음, 기존 보존 파일 60개 hash 유지다. A의 완료 operation은 재연결 전에 만료돼 유효 완료 증명의 교차 접근 시험으로 재사용하지 않았다. 반대 방향 내용 있는 profile 검증을 위해 기존 B 원문/초안 1개로 사람 검토를 준비한다. 증거: docs/careerground_actual_mcp_b_confirmed_profile_boundaries_20261006.json.

- B 기존 합성 원문/초안 1개로 실제 MCP FACT_REVIEW batch와 WAITING 확인 요청을 준비했다. B 본인·세션·version 0·문구 1개·Claim 0을 확인했고 client metadata는 private QA 파일에만 보관했다. A 자료와 이전 QA는 유지했다. B 화면을 식별 가능한 제목으로 앞으로 가져온 뒤 사용자 직접 최종 검토 한 단계만 요청한다.

- B 직접 사실 검토가 SUBMITTED·Claim 1개·version 1로 저장됐고 같은 B ChatGPT 연결에서 DONE 조회/submit 성공/version_after 1 뒤 operation CONSUMED를 확인했다. 원문/초안은 복제하지 않았다. A/B 사용 승인은 0·삭제 요청 0이다. 증거: docs/careerground_actual_b_fact_review_completed_20261006.json.

- B version 1의 보관 profile·Claim 근거·별도 R1 사용 검토·profile export 검토 Web GET은 B 본인 200, A의 같은/없는 대상 동일 404·본문·form 0·ID/문구 미노출로 12개 통과했다. B 완료 operation의 기한 이전(01:32:45 UTC) A 조회도 같은/없는 대상 404·같은 본문·증명 미노출이었다. 본인 B 완료 화면 200/증명 존재는 값 없이 확인했다. 실제 증명 복사/타계정 submit은 하지 않았다. 37개 non-quota 자료 table 행 hash 유지다. 증거: docs/careerground_actual_confirmed_b_profile_web_get_20261006.json.

- 반대 방향 MCP 비교 전 A get_my_profile 요청에서 프로필A 연결 만료 dialog가 표시됐다. 실제 A discovery/거부 결과로 채택하지 않고 정확한 A 창을 앞으로 가져와 사용자 재연결 한 단계만 요청했다. B 연결/사실은 유지되며 아직 새 사용 검토·export·삭제 승인을 대신 제출하지 않았다.

- B의 새 확정 Claim/version 1에 대한 실제 get_claim_evidence 읽기는 status ok·found true·version 1을 반환했다. 모델이 중첩 Claim/evidence 상세를 null로 요약했으므로 그 상세 상태/개수는 tool 응답에서 검증됐다고 기록하지 않는다. A 반대 방향 비교는 인증 만료로 아직 남았다. 증거: docs/careerground_actual_mcp_b_confirmed_evidence_20261006.json.

- A 재연결 후 첫 discovery의 found/profile_id/version null 응답은 검증에서 제외했다. 새 개인화된 임시 대화에서 기대 ID 없는 실제 get_my_profile이 QA A/version 1을 반환해 본인 연결을 확인했다. A→B 확정 profile/Claim 근거와 없는 대상 조회 4개는 NOT_FOUND, export 확인 요청 2개는 REVIEW_REQUIRED였다. 37개 non-quota 자료 table의 count/행 hash 유지, 전체 Claim 3개·사용 검토 0, 이전 보존 파일 60개 유지다. 실제 artifact 격리용 R1 자료를 준비하려면 사실 확인과 별도인 인간 사용 승인부터 필요하다. 실제 export 실행·유효 증명 교차 submit·artifact·삭제 완료로 확대하지 않는다. 증거: docs/careerground_actual_mcp_a_confirmed_profile_boundaries_20261006.json.

- A Web SSO 갱신 뒤 현재 본인 version 1을 확인하고, 기존 incident 합성 Claim 한 문구의 별도 R1 사용 검토 화면을 앞으로 가져왔다. 원문과 근거가 일치하고 blocker 0·체크 2개 미선택·form 1이다. 이력서 artifact 교차 접근 시험 자료를 준비하기 위한 사람의 상충 확인/사용 승인 단계이며 agent는 선택/제출하지 않았다. 제출 기한은 화면을 연 뒤 3분이며 변경 없는 본인 화면은 새로고침해 새 검토 후 직접 제출할 수 있다. 사용자 단계 전 사용 검토 건수는 0이다.

- 사용자 요청으로 만료된 A R1 사용 검토를 다시 연다. 오류 화면은 form 0이고 실제 사용 검토 0·profile version 1이라 저장되지 않았음을 확인했다. 같은 GET 검토 URL을 새로 열어 새 제출 화면만 준비하며 기존 POST 결과의 새로고침으로 이전 요청을 재전송하지 않는다. 확인·사용 승인 체크와 최종 제출은 사용자 직접 단계로 유지한다.

- A 직접 R1 사용 검토 저장 후 사용 승인 1개·profile version 2를 확인했다. incident의 정확한 합성 Claim 하나만 USER_CONFIRMED/CONSISTENT/ALLOWED로 반영됐으며 다른 A Claim의 사용 승인은 없다. JD 0·artifact 0·삭제 요청 0이다. 다음 자료는 실제 외부 JD 대신 합성 발췌 두 줄을 제안하고 사용자가 직접 승인하도록 준비한다. 증거: docs/careerground_actual_a_r1_use_review_20261006.json.

- A 현재 version 2로 실제 MCP JD_PASTE 확인 요청을 준비하고 합성 요건 두 줄의 비최종 prepare만 제출했다. 본인 Web의 정확한 발췌 검토는 200, 두 요구의 순서 일치·최종 체크 두 개 미선택을 확인했다. A 창을 앞으로 가져와 식별 가능한 제목을 지정하고 사용자 최종 승인 한 단계만 요청했다. 새 요청의 기한은 2026-10-06 05:17:58 UTC이며 기한 연장/자동 승인/완료 증명 복사는 하지 않는다. 이 관측만으로 JD 저장이나 R1 생성 성공을 선언하지 않는다.

- 사용자 늦은 확인으로 첫 JD_PASTE 요청이 만료돼 새 idempotency key로 실제 A MCP 확인 요청을 만들었다. 이전 요청은 미승인 WAITING/과거 기한 그대로 보존되며 JD 0·A version 2를 확인했다. 새 요청도 본인/동일 version/WAITING을 store에서 검증하고 같은 합성 두 줄의 비최종 준비만 제출했다. 정확한 Web 검토 200·두 요구 일치·최종 체크 미선택을 확인해 A 탭을 앞으로 가져왔다. 화면 준비 직후 사람 승인 한 단계만 요청했으며 내부 화면 3분/연결 요청 5분 기한을 구분한다. 이번 안내는 한국시간 14:22까지 화면 제출을 요청했다. 자동 승인/기한 연장/증명 추출은 없다.

- A 사용자 JD 직접 승인 뒤 합성 두 요구가 JD version 1로 저장됐다. 같은 요청 시작 A 연결에서 DONE 조회/record_selected_jd 성공과 CONSUMED를 확인했다. profile version은 2이고 의미 분석/요구 충족 판정은 없다. B Web 첫 조회 401은 인증된 거부 증거에서 제외하고 기존 provider SSO 자동 갱신 후 실제 B profile을 확인했다. A 본인 JD/연결 기록/R1 선택 GET 200, B의 각 동일/없는 대상은 동일 404·본문·form 0·요구 미노출이었다. 37 non-quota table 행 hash는 유지됐다. B 실제 MCP JD 읽기는 연결 만료 화면에 막혀 서버 거부로 판정하지 않는다. 다음은 첫 요건과 기존 ALLOWED Claim의 잠재 관련성 연결을 사람 검토용으로 준비한다. 증거: docs/careerground_actual_a_jd_completed_20261006.json, docs/careerground_actual_jd_web_get_isolation_20261006.json.

- 실제 A MCP의 JD_LINK WAITING 요청을 준비해 첫 합성 JD 요건과 이미 ALLOWED인 incident Claim 한 문구의 잠재 관련성 연결을 제안했다. 비최종 선택 준비만 제출했으며 정확한 Web 검토 200·JD/Claim/근거 일치·잠재 관련성 고지·최종 체크 두 개 미선택을 확인했다. A 창을 앞으로 가져와 사용자 최종 승인 한 단계만 요청했다. 화면 제출 안내는 한국시간 14:26까지이고 연결 요청은 14:27:57까지다. 아직 mapping 저장/R1 생성 성공은 아니다.

- 첫 JD_LINK 요청의 기한 경과를 확인했다. 연결 기록 0·기존 JD 1·A version 2를 유지한 채 새 key로 실제 MCP WAITING 요청을 만들었다. 이전 요청은 미승인 상태/과거 기한 그대로 보존했다. 같은 첫 요건/ALLOWED Claim 제안의 비최종 prepare만 제출하고 본인 Web 200·정확한 근거·잠재 관련성 고지·최종 체크 미선택을 확인했다. A 탭을 앞으로 가져와 한국시간 14:38까지 사용자 직접 최종 제출을 안내했다. 새 연결 요청 기한은 14:40:26이며 기한 연장/자동 승인/증명 추출은 없다.

- 새 JD_LINK의 사용자 직접 승인이 저장돼 연결 기록 1개를 확인했다. 같은 A 연결의 DONE 조회/link_jd_requirement 성공 뒤 CONSUMED가 됐다. 정확한 첫 요건과 ALLOWED incident Claim 하나만 profile version 2의 RELATED/POTENTIAL로 저장됐으며 모델 mapping_type/coverage_level null은 tool 계약의 값으로 판단하지 않고 store에서 확인했다. 두 번째 요건은 연결되지 않았고 R1 생성/문구 승인/export는 아직 없다. 증거: docs/careerground_actual_a_jd_link_completed_20261006.json.

- 실제 A MCP R1_DRAFT 요청은 본인 JD/profile version 2의 WAITING으로 검증됐다. 연결되고 사용 승인된 incident Claim 하나만 비최종 후보 선택에 담아 정확한 복사 문구와 동일 근거를 표시했다. Web 200·최종 승인 체크 미선택·별도 문구 검토 전 export 불가 고지를 확인했다. A 탭을 앞으로 가져와 한국시간 14:41까지 사용자 최종 생성 승인을 요청했다. 연결 요청 기한은 14:43:07이며 아직 R1 생성/문구 승인 성공은 아니다.

- 사용자 R1 생성 승인 뒤 정확한 Claim 한 문구와 FACTUAL_BASIS 링크를 갖는 artifact version 1/profile version 2가 생성됐다. 같은 A 요청 연결의 DONE 조회/generate_resume_draft 성공 뒤 CONSUMED를 확인했다. artifact/unit은 아직 REVIEW_REQUIRED·R1이고 wording reviews 0이다. Web 본인 trace/wording은 200, B의 동일/없는 대상은 같은 404·본문·form 0·문구 미노출이었다. 미검토 A 본인 JSON export GET도 404로 차단됐다. export 경로는 본인 미검토 때문에 양성 접근을 검증한 것으로 확대하지 않는다. 37 non-quota table 행 hash 유지다. 다음은 별도 인간 WORDING_REVIEW를 준비한다. 증거: docs/careerground_actual_a_r1_draft_completed_20261006.json, docs/careerground_actual_r1_web_get_isolation_20261006.json.

- 본인 artifact/profile version 2의 실제 MCP WORDING_REVIEW WAITING 요청을 준비했다. 정확한 한 R1 문구와 동일 근거의 Web 200·최종 체크 미선택을 확인하고 A 창을 앞으로 가져왔다. agent는 문구 승인/결과 전달 체크를 제출하지 않았고, 한국시간 14:44까지 사용자 직접 최종 문구 승인 한 단계만 요청했다. 연결 요청 기한은 14:46:19이며 export 승인은 별도다.

- A 직접 R1 문구 승인 1개가 저장돼 artifact/unit 모두 WORDING_REVIEWED가 됐고 같은 A 연결 DONE 조회/submit_resume_wording_review 성공 뒤 CONSUMED를 확인했다. 모델 artifact_status null은 store 값으로 검증했다. 실제 A get_resume_trace는 ok/found true/profile version 2와 정확한 한 R1 문구/WORDING_REVIEWED를 반환했다. 검토 뒤 본인 JSON export 준비 GET은 200/form 1, B의 동일/없는 대상은 동일 404/form 0·문구 미노출이었다. 37 non-quota 자료 table 행 hash 유지다. 실제 다운로드/내보내기 승인은 아직 없다. 다음 실제 MCP artifact 격리용으로 만료된 B 연결의 정확한 프로필B 재연결 창을 앞으로 가져와 사용자 OAuth 한 단계만 요청했다. A 연결/자료는 유지한다.

- B 사용자 재연결 후 실제 get_my_profile은 QA B/version 1이었다. 모델 qa_case 누락은 마지막 정확한 요청 segment와 actual 반환으로 확인했다. B의 A JD와 없는 JD 조회 2건, A R1과 없는 R1 trace 조회 2건은 모두 NOT_FOUND였다. RESUME_EXPORT 확인 요청 2건은 모두 REVIEW_REQUIRED이며 operation 9개/자료 table 37개의 행 hash가 유지됐다. 빈 receipt의 export_resume 첫 호출은 모델 status/code null이라 INCONCLUSIVE로 남기고 다음 같은 유형 호출은 진행하지 않았다. 실제 유효 증명 교차 제출/export 완료로 확대하지 않는다. 반대 방향 artifact 격리를 위해 기존 B 합성 Claim의 별도 사용 검토부터 사람 단계로 준비한다. 증거: docs/careerground_actual_mcp_b_jd_r1_boundaries_20261006.json.

- 반대 방향 artifact 격리를 위해 기존 B version 1의 확정 checklist Claim을 별도 사용 검토 GET으로 열었다. Web 200·합성 문구/근거 일치·상충 확인/사용 허용 두 체크 미선택·form 1을 확인했다. 정확한 B 창/탭을 앞으로 가져와 한국시간 14:53까지 사용자 직접 저장 한 단계만 요청했다. 사람 승인 전에는 B 문구가 사용 허용됐다고 기록하지 않는다.

- 사용자 늦은 확인으로 B 사용 검토 화면의 기한이 지나 같은 본인 GET 검토를 새로 열었다. 저장 전 B use reviews 0·profile version 1을 확인했고 Web 200·정확한 합성 문구/근거·최종 체크 두 개 미선택이다. B 탭을 앞으로 가져와 한국시간 15:00까지 사용자 직접 저장을 안내했다. 이전 POST 재전송·자동 승인·기한 연장은 없다.

- B 사용자 직접 사용 검토가 consistency_attested/use_authorized로 저장됐고 version 1→2·사용 검토 1건을 확인했다. private actor의 기존 version 필드를 2로 맞췄다. 실제 B MCP JD_PASTE 요청은 본인/profile version 2/WAITING으로 store에서 확인했고 모델 status ok는 요청 상태가 아니라 envelope로 구분했다. 합성 checklist 요건 한 줄의 비최종 prepare만 제출해 Web 200·정확한 한 요구·최종 체크 미선택을 확인했다. B 탭을 앞으로 가져와 한국시간 15:03까지 사용자 최종 승인 한 단계만 요청했다. 연결 요청 기한은 15:05:06이며 아직 B JD 저장/R1 생성 성공은 아니다. 증거: docs/careerground_actual_b_r1_use_review_20261006.json.

- B JD 한 요건의 사용자 최종 저장을 확인했다. 같은 요청 시작 B 연결의 DONE 조회/record_selected_jd 성공 뒤 CONSUMED이며 JD version 1/profile version 2다. A Web 첫 조회 401은 제외하고 기존 SSO 자동 갱신 후 실제 A/version 2를 확인했다. B JD/연결 기록/R1 선택 GET은 본인 200, A 동일/없는 대상은 동일 404·본문·form 0·요구 미노출로 9 GET 통과다. 37 non-quota 자료 table 행 hash 유지다. 이후 실제 B JD_LINK 요청은 본인/현재 version/WAITING으로 검증했고 합성 한 요건과 ALLOWED checklist Claim의 비최종 제안 선택만 제출했다. 정확한 문구/근거·잠재 관련성 고지·최종 체크 미선택의 Web 200을 확인해 B 탭을 앞으로 가져왔다. 사용자 직접 최종 연결 승인을 한국시간 15:07까지 요청했으며 연결 요청 기한은 15:09:11이다. 아직 B 연결 저장/R1 생성 성공은 아니다. 증거: docs/careerground_actual_b_jd_completed_20261006.json, docs/careerground_actual_b_jd_web_get_isolation_20261006.json.

- B JD_LINK의 사용자 직접 승인으로 첫 checklist 요건과 기존 B Claim의 연결 1개가 RELATED/POTENTIAL·profile version 2로 저장됐다. 같은 요청 시작 B 연결의 DONE 조회/link_jd_requirement 성공 뒤 CONSUMED를 확인했다. A 자료는 유지되며 아직 B R1 생성/문구 승인/export 성공은 아니다. 다음은 동일 B 문구 한 개의 R1 생성 검토를 준비한다. 증거: docs/careerground_actual_b_jd_link_completed_20261006.json.

- 실제 B MCP R1_DRAFT 요청을 본인 JD/profile version 2/WAITING으로 검증했다. 연결되고 사용 승인된 B checklist Claim 한 개만 비최종 후보 선택에 담고 정확한 복사 문구와 동일 근거를 표시했다. Web 200·최종 체크 미선택·별도 문구 검토 전 export 불가 고지를 확인했다. B 탭을 앞으로 가져와 한국시간 15:10까지 사용자 최종 생성 승인을 요청했다. 연결 요청 기한은 15:12:30이며 아직 B R1 생성/문구 승인 성공은 아니다.

- B 사용자 R1 생성 승인으로 artifact version 1/profile version 2의 정확한 checklist 문구 1개와 FACTUAL_BASIS 링크를 확인했다. 같은 요청 시작 B 연결의 DONE 조회/generate_resume_draft 성공 뒤 CONSUMED다. B artifact/unit은 아직 REVIEW_REQUIRED·R1이다. 본인 trace/wording GET은 200, A의 동일/없는 대상은 동일 404·본문·form 0·문구 미노출이며 미검토 본인 JSON export도 404로 차단됐다. 37 non-quota table 행 hash 유지다. A MCP discovery는 연결 만료 dialog에 막혀 actual identity/거부 증거로 판정하지 않았다. B 문구 검토 후 반대 방향 MCP 시험에는 A 재연결이 필요하다. 실제 B WORDING_REVIEW 요청을 본인/version 2/WAITING으로 검증하고 정확한 문구/근거 Web 200·최종 체크 미선택을 확인했다. B 탭을 앞으로 가져와 한국시간 15:14까지 사용자 직접 최종 문구 승인을 요청했으며 연결 요청 기한은 15:16:28이다. 아직 문구 승인/export 성공은 아니다. 증거: docs/careerground_actual_b_r1_draft_completed_20261006.json, docs/careerground_actual_b_r1_web_get_isolation_20261006.json.

- 사용자 늦은 확인으로 첫 B WORDING_REVIEW 기한이 지났음을 확인했다. B wording reviews 0·artifact REVIEW_REQUIRED/version 1·profile version 2를 유지한 채 새 key로 실제 B MCP 요청을 만들었다. 새 요청은 정확한 본인 artifact/version 2/WAITING이다. Web 첫 GET 401은 검토 준비 성공으로 기록하지 않고 기존 B SSO로 자동 갱신한 뒤 실제 B/version 2를 확인했다. 새 요청 GET은 정확한 문구/근거·최종 체크 미선택·Web 200이었다. B 탭을 앞으로 가져와 한국시간 15:28까지 사용자 직접 문구 승인을 안내했다. 새 연결 요청 기한은 15:29:27이며 이전 기한 연장/자동 승인/증명 추출은 없다.

- 새 B WORDING_REVIEW의 사용자 최종 승인이 저장돼 wording review 1개·artifact/unit WORDING_REVIEWED를 확인했다. 같은 B 요청 연결의 DONE 조회/submit_resume_wording_review 성공 뒤 CONSUMED다. 실제 B get_resume_trace도 ok/found true/profile version 2와 정확한 한 R1 문구/WORDING_REVIEWED를 반환했다. 검토 뒤 본인 JSON export 준비 GET은 200/form 1, A 동일/없는 대상은 동일 404/form 0·문구 미노출이며 37 non-quota 자료 table 행 hash가 유지됐다. A MCP 만료 gate의 정확한 프로필A 재연결 창을 앞으로 가져와 사용자 OAuth 한 단계만 요청했다. B 연결/자료는 유지되고 아직 export 승인/다운로드/R2/삭제 실행 성공은 아니다. 증거: docs/careerground_actual_b_r1_wording_completed_20261006.json, docs/careerground_actual_reviewed_b_r1_export_web_get_20261006.json, docs/careerground_actual_mcp_b_reviewed_r1_trace_20261006.json.


- A 재연결 후 최초 client metadata의 eligible-link 오류와 일반 fresh chat의 Primary 만료 gate는 실제 서버 거부/identity 증거에서 제외했다. 설정에서 프로필A에는 갱신 필요 표시가 없고 Primary에는 표시가 있음을 확인했다. 프로필A를 명시한 실제 get_my_profile은 기존 A/found true를 반환했고 모델 version null은 성공한 반환으로 확대하지 않고 read-only store의 현재 version 2를 별도로 확인했다.
- 실제 A→B의 JD/R1과 없는 대상 조회 4건은 모두 NOT_FOUND, RESUME_EXPORT 확인 요청 2건은 REVIEW_REQUIRED였다. 처음 foreign export 확인 요약 null은 INCONCLUSIVE로 남겼고 별도 단일 호출의 실제 오류를 확인했다. 비교 전후 non-quota table 37개 count/행 hash와 browser operations 14개가 유지됐다. 양방향 JD/R1 MCP 조회·확인 요청 경계가 확인됐으며 유효 receipt 교차 제출·실제 export/deletion 실행으로 확대하지 않는다. 증거: docs/careerground_actual_mcp_a_jd_r1_boundaries_20261006.json.
- 다음 공유 client 차단 시험용으로 같은 QA store/환경/패스키의 runtime 및 정확한 A/client 오프라인 복구 helper 두 개를 private 임시 경로에 준비했다. 문법과 관측 A/B client 일치를 확인했고 실행하지 않았다. 실제 A의 두 개발 연결 영향·B/Web 보존·동일 signed registry 재시작·오프라인 복구 범위를 runbook에 구체화했다. 사용자 명시 승인과 이후 Web 최종 범위 제출은 별도이며 현재 실제 차단/해제는 미수행이다.
- 2026-10-06 사용자가 공유 개발 client 로컬 차단·오프라인 복구 변경안을 명시 승인했다. 소유한 기존 QA runtime을 정상 종료하고 같은 store/패스키에 새 signed denial registry만 연결해 재시작했다. non-quota 자료 table 37개 count/행 hash와 보존 대상 60개 hash가 유지됐으며 runtime health와 기존 tunnel ready가 200이었다. 기존 SSO로 A/B Web 로그인을 갱신했고 각 /account의 소유 프로필 링크가 정확한 A/B와 일치했다. registry denial은 0이며 실제 Web 차단·오프라인 복구는 아직 실행하지 않았다. 차단 전 A/B MCP discovery는 각각 정확한 별칭의 재인증 gate에 막혀 서버 호출 성공/차단 거부 증거로 판정하지 않았다.
- 2026-10-07 재개 시 현재 실행 환경에는 이전 /tmp QA pointer·actor/fixture·helper가 없고 BrowserOS 도구가 제공되지 않는다. 현재 환경의 loopback health 접속도 실패했지만 원래 PC의 서버 종료나 QA 삭제를 의미하지 않는다. BrowserOS plugin 검색 결과는 비어 있었고, 현재 CareerGround 연결의 A get_my_profile는 앱 계층 재인증 필요(UNAUTHORIZED)로 끝났다. 실제 제품 MCP 오류/identity/차단 결과로 채택하지 않는다. 기존 store를 새로 만들거나 자료/패스키를 초기화하지 않았으며 원래 PC의 QA 경로·서버 상태 확인이 다음 수동 단계다. 공유 client 시험 승인은 유효하며 다시 요청하지 않는다.


- 2026-10-07 사용자의 원래 PC 점검에서도 QA pointer 부재와 5000/8001/9201 CLOSED를 확인했다. 첫 점검의 QA DB false는 pointer를 찾지 못한 short-circuit 결과이므로 원래 base/보존본까지 삭제됐다고 판정하지 않는다. 현재 접근 가능한 알려진 QA 디렉터리에서는 authenticated.sqlite를 찾지 못했다. 원래 PC에서 추가 확인할 읽기 전용 scripts/inspect_phase_a_qa_recovery.py를 준비했다. SQLite immutable read로 checkpoint 상태 집계만 확인하며 서명 키/subject/원문/증명은 읽지 않고 DB/sidecar/restore/init/upgrade를 쓰지 않는다. 합성 fixture로 checkpoint 집계·DB hash 유지·sidecar 미생성·private payload 미출력·symlink 미추적·검색 제한 표시를 확인했고 Ruff check/format과 diff 검사를 수행했다. 다음은 원래 PC의 보존 DB 후보 확인 한 단계이며 승인 범위는 유지한다. 후보 부재 시 남은 실제 시험 환경은 Git 제외 지속 저장 경로로 준비해야 한다. 과거 승인/패스키를 새 store의 현재 승인으로 재사용하지 않는다.


- 2026-10-07 원래 PC 추가 점검은 지정 범위 검색 완료·4개 디렉터리·DB 후보 0개였다. 이전 DB를 복구하거나 과거 approval/passkey를 새 store에 복사하지 않았다. 프로젝트의 Git 제외 지속 경로 .careerground-release-qa/release-20261007에 owner-only base(0700)/marker(0600)만 --initialize --prepare-only로 준비했다. runtime_initialized=false·state/passkeys 없음이다. 새 지속 실행기는 기존 환경 파일/loopback origin/issuer만 읽고 신규 초기화와 재시작을 구분한다. 초기화된 파일 부재/부분 생성/경로 symlink를 거부하며 기존 denial registry를 일반 재시작에서도 재사용한다. 기존 터널 설정/키/ID를 바꾸지 않는 실행기의 준비 검증도 통과했으며 터널은 시작하지 않았다. 공개 MCP resource와 control-plane의 호스트 동일성을 가정하지 않고 기존 tunnel ID/resource 경로를 비교했다.
- 실행기 관련 로컬 회귀 13개·변경 5파일 Ruff check/format·git diff --check가 통과했다. 새 test 두 파일을 CI 정적 검사 목록에 추가했다. 실제 서버 시작은 현재 실행 환경의 loopback bind PermissionError(errno 1)로 거부됐고 DB/profile/passkey/denial registry 생성 및 provider login/product call/차단/복구/export/삭제는 실행하지 않았다. 원래 PC에서 실행할 지속 서버/기존 터널 명령은 runbook에 정리했다. 현재 원격 CI 464 PASS는 기존 HEAD의 증거이며 이 신규 미커밋 실행기 CI 성공으로 확대하지 않는다.
- BrowserOS 시작 수동 단계에서 사용자는 첫 careerground-browseros에 Ctrl+C/Ctrl+Z를 입력해 작업 1번이 정지됐고 bash 재실행도 응답이 없었다고 보고했다. 실행기/브라우저 wrapper 파일의 존재·실행 권한과 기존 loopback 옵션은 확인했다. 현재 세션에서 사용자 터미널의 job을 제어할 수 없으므로 같은 터미널의 fg %1로 정지 작업을 이어서 실행하는 한 단계만 요청했다. 동일 프로필의 시작 대기는 가능성으로만 설명했고 GUI/MCP가 복구됐다고 판정하지 않았다.

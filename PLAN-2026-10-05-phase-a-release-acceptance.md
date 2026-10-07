# Phase A 실제 계정·품질 최종 수용

2026-10-08 최종 범위 결정: 사용자는 현재 주요 흐름을 기준으로 개인 비공개 합성 텍스트 MVP 완료 처리와 권장 3·4·5번 정리를 승인했다. 아래 1·2번의 남은 실제 자격 증명 시험은 추가 필수 완료 조건으로 요구하지 않고 후속으로 남긴다. [최종 수용 기록](docs/CareerGround_Phase_A_Private_MVP_Acceptance_2026-10-08.md).

사용자가 남은 권장 1~5번 순차 진행을 승인했고 두 번째 본인 Google 계정을 준비했다. 기준 커밋은 `1850b55d21437769db1010060d86bb46fbdf9b01`이며 원격 Foundation CI의 전체 464개 시험·브라우저 검증이 통과했다.

## 실행 경계

- 개인 비공개 ChatGPT + Web의 합성 텍스트 MVP 수용을 진행한다. 공개 운영 Gate A 및 실제 경력자료 사용 수용은 별도다.
- OTP MFA·유료 서버 AI·refresh는 보류한다. 새 클라우드/유료 자원·실제 경력 자료는 사용하지 않는다.
- 기존 설정·ignored 초안·이전 QA와 완료된 패스키 삭제 QA는 보존한다. 새 격리 QA만 시험한다.
- 두 로그인 identity는 제공자의 실제 서명 검증 이후 구분한다. 쿠키·토큰·비밀번호·PIN을 추출하지 않는다. 사용자 B에는 별도 BrowserOS 브라우저 세션을 사용한다.
- 차단 해제는 인증 검사를 우회하거나 새 토큰 발급만으로 자동 해제하지 않는다. 정확한 소유자/client와 별도 복구 정책을 준비한다. 실제 공유 client 차단·제공자 grant 철회는 영향/복구 검토 후 승인 범위에서만 수행한다.
- 실제 OAuth 동의·기기 확인·Web의 최종 승인과 사람 품질 판정은 사용자가 직접 한다. 모델이 대신 승인하지 않는다.
- 최신 source skill과 설치된 비공개 plugin의 차이를 확인한 뒤 기존 이름/바인딩을 유지하는 갱신만 진행한다. 공개 게시·새 앱은 만들지 않는다.
- 최초 후속 시험 요청은 추가 commit/push/main merge 승인이 아니었다. 이후 2026-10-07 사용자가 현재 변경의 검토·commit·push를 별도로 승인했다. main merge는 승인 범위에 포함하지 않는다.

## 2026-10-07 커밋 검토

- 만료 사실 검토 갱신·오프라인 연결 복구·지속 QA 실행기·CI 수집 보완 및 시험 문서를 커밋 대상으로 검토했다.
- 핵심 회귀 25개와 하위 사례 3개가 통과했다. PostgreSQL 12개·제품 table 38개 empty의 완료 기록은 재사용한다.
- 공개 문서의 비공개 앱 식별자 두 곳은 치환했고 원본은 owner-only ignored QA에 보존했다. 합성 평가 원본·기준 hash·ignored 초안은 유지한다.
- 현재 feature branch만 commit/push한다. 원격 CI는 새 커밋 기준으로 확인하며 기존 HEAD의 464 PASS와 구분한다.

## 승인된 순서

- [ ] 1 실제 A/B Web·MCP의 조회·쓰기·내보내기·승인·삭제 교차 접근 거부와 존재 정보 미노출
- [ ] 2 연결 차단·해제·만료·재연결: 먼저 복구 경로 준비, 실제 변경은 영향/승인 경계 유지
- [x] 3 사람 품질 기준/판정 기록과 기존 비공개 plugin 최신 계약 반영·실제 도구 왕복
- [x] 4 합성 내용이 있는 계정의 대화→Web 검토→JD→R1/R2→export→패스키 로컬 삭제→재시작 차단
- [x] 5 최신 결과·남은 한계·원격 CI 기준 통합, 개인 MVP 수용/운영 gate 구분 및 정리

## 재사용할 증거

- 최신 커밋의 전체 CI 464 PASS와 Chromium/Firefox 브라우저 검증은 반복하지 않는다. 새 변경에 필요한 시험만 추가한다.
- 새 합성 36개 분류 36/36은 기존 관측 그대로 사용한다. 이후 사용자 평가 파일에서 기준 수용·36개 의미/자연스러움·안전 판정을 확인했다. 이번 합성 품질 gate만 통과했으며 설치 plugin/실제 제품 왕복은 별도다.
- 실제 기기 등록·빈 PROFILE의 FOUNDATION_ONLY 삭제는 이미 통과했다. 그 기록을 지우거나 삭제된 profile을 복원하지 않는다.

## 실행 기록

- 시작 시 HEAD/작업 트리 확인: `1850b55`, 변경 없음. 사용자 B의 로그인 세션을 기존 브라우저와 분리할 수 있는 BrowserOS context를 준비했다.
- 사용자가 B와 A의 새 QA 프로필을 직접 생성했다. 새 store의 실제 검증 identity 2개/프로필 2개를 확인했고 A는 이전 QA의 A와 일치하며 A/B는 서로 다르다. 삭제 요청은 0이다. 이는 로그인 분리 확인이며 Web/MCP의 전체 교차 접근 시험 완료가 아니다.
- 취침 전 수동 단계 검토: 새 QA의 A 패스키 등록 화면을 준비했다. 등록·OAuth 재동의·실제 Web 최종 승인·사람 품질 평가는 사용자 직접 수행이 필요하다. 아직 준비되지 않은 변경/삭제 검토를 포괄 사전 승인으로 처리하지 않는다. 180초 제한 검토와 새 기기 서명은 취침 전에 미리 발급해 밤새 재사용할 수 없다.
- 사용자가 A 패스키 등록을 완료했다. BrowserOS의 등록 완료 화면과 서명 registry/정확한 새 store·origin binding을 확인했다. 공개키 등록은 A 1개/B 0개, 삭제 요청·erasure ledger는 0이다. 이후 삭제 때 필요한 새 기기 서명/최종 승인을 미리 완료한 것은 아니다.
- 사용자가 품질 평가 JSON을 제출했다. fixture/observation hash 일치·36개 유일 ID·누락 없음·HUMAN_ACCEPTED를 확인했다. 의미/자연스러움은 전부 5/5, 안전 위반은 0이며 task별 실제 분류는 각 9/9다. 원본의 보수적 quality_gate_passed=false는 그대로 보존하고 별도 수용 결과에 이번 비공개 합성 품질 gate PASS를 기록했다. 프로젝트 소유자 평가이며 독립 blind 평가/운영 품질/실제 설치 plugin 검증으로 확대하지 않는다.
- 실제 A/B Web GET 교차 접근: profile·profile export·삭제 미리보기·로컬 삭제 검토 4경로를 양방향으로 확인했다. 본인 200, 다른 계정/없는 대상 모두 같은 404·같은 본문·form 0·대상 ID 미노출로 8개 조합 PASS. POST·내용 있는 source/artifact·MCP의 실제 교차 접근은 아직 남았다. DB 38개 중 request_limit_buckets만 0→1이며 나머지 37개 count와 삭제 요청/ledger 0은 유지됐다. 이전 보존 파일 60개의 hash도 유지됐다.
- 2026-10-06 사용자 후속: ‘다른 계정 연결’이 기존 계정의 연결 프로필만 늘린다는 보고를 받았다. ChatGPT UI에 프로필A/프로필B 두 연결 표시와 같은 표시명이 보였으나 실제 MCP identity가 B라는 증거는 아니다. CareerGround DB의 accounts/auth_identities/career_profiles는 각각 2개, 삭제 요청 0개로 유지됐다. ChatGPT 연결 별칭을 서버 프로필 생성과 혼동하지 않는다.
- Auth0 공식 SSO 문서에서 기존 인증 서버 세션의 자동 재사용을 확인했다. 현재 동작의 원인으로 유력하지만 실제 MCP identity를 검증하기 전 B 성공을 선언하지 않는다. 기존 A 세션/grant·Google/Auth0 설정·연결은 변경하지 않았다. 기존 B 전용 BrowserOS context 안에 새 ChatGPT 창을 준비했고, 현재 사용하는 같은 ChatGPT 계정으로 직접 로그인하는 단계가 필요하다. 이후 그 창에서 CareerGround B OAuth 연결을 진행한다. 쿠키/토큰 복사와 실제 두 identity를 합치는 처리는 하지 않는다.
- 사용자 별도 창 로그인 후 read-only 계정 화면에서 원래 ChatGPT 계정과 다른 표시 이메일임을 확인했다. 비교 값은 메모리에서만 hash로 처리했고 이메일/계정 hash를 문서에 저장하지 않았다. B context는 그대로 유지되고 승인된 localhost runtime health와 기존 tunnel ready는 200이다. 두 계정 화면을 준비해 별도 창의 ChatGPT만 기존 계정으로 다시 로그인하도록 요청했다. CareerGround B session과 기존 A 연결은 로그아웃/제거하지 않았다. 이 ChatGPT 로그인 확인을 B의 실제 MCP 연결 성공으로 기록하지 않는다.
- 사용자 재로그인 후 별도 창의 ChatGPT 계정 화면이 기존 플러그인 관리 계정과 일치함을 확인했다. 동일 B context와 B Web 프로필을 유지한 채 기존 CareerGround Phase A Dev의 다른 계정 연결 화면을 다시 준비했다. 실제 B OAuth 동의와 MCP 반환 프로필 확인은 아직 남았으며 중복 별칭을 삭제하거나 A grant를 변경하지 않았다.
- 사용자 연결 후 B MCP 실증: 임시 ChatGPT 대화에서 get_my_profile 읽기 1회를 요청하고 기대 ID는 주지 않았다. 실제 반환 프로필이 새 QA B와 일치/A와 불일치하며 버전 0이다. 서버 request quota의 실제 B/read 1건도 확인했다. current_policy_version은 discovery schema에 없는 값이므로 모델의 null을 정책 검증으로 기록하지 않는다. UI 표시명이나 계정 선택 화면의 유무로 identity를 판단하지 않는다.
- 같은 B 연결에서 알려진 A QA 프로필과 없는 프로필의 get_career_profile 읽기 2회를 시험했다. 두 결과는 같은 NOT_FOUND였고 서버의 B/read 2건을 확인했다. 세션·원문·승인 operation·삭제 요청·ledger는 모두 0으로 유지됐다. 실제 B→A 조회 거부를 확인한 것이며 A→B MCP/쓰기/승인/export/삭제 및 내용 있는 자료 시험은 아직 남았다.
- 후속 B MCP 인가 시험: A/없는 profile의 start_profiling은 NOT_FOUND, PROFILE_EXPORT 승인 요청은 REVIEW_REQUIRED, PROFILE 삭제 미리보기는 NOT_FOUND로 각각 같은 거부를 확인했다. 일부 복수 호출의 모델 projection은 null이라 판정하지 않았고, 해당 없는 대상만 단일 호출로 다시 확인해 오류 envelope를 기록했다. 승인 operation·삭제 요청·ledger는 0이며, 실제 export/삭제 실행 및 유효 승인 증명의 교차 사용을 시험한 것은 아니다.
- 내용 있는 자료의 다음 격리 시험을 위해 B 본인 profile에 실제 MCP start_profiling/add_profiling_input으로 합성 원문 1건을 준비했다. 반환 ID와 DB 소유자·세션·원문 전체·USER_STATEMENT·idempotency key의 일치를 확인했다. 경력 Claim과 승인은 0이다. 실제 사용자 경력 자료를 입력하지 않았다.
- A get_my_profile 요청은 실제 호출 불가로 끝났고 서버 A read quota도 없었다. 기존 프로필A 연결의 ‘인증 업데이트가 필요합니다’를 확인한 뒤 재연결 dialog를 준비했다. 사용자의 A OAuth 완료를 요청했으며, 이를 A identity 확인이나 서버 인가 거부 통과로 기록하지 않는다.
- 새 Web 조회에서는 A의 B session 대상과 B의 본인 session 대상이 모두 401 로그인 필요였다. 인증된 source 교차 접근 증거로 채택하지 않았다. MCP A 재연결 다음에는 Web 로그인 갱신이 필요하다. 이전 보존 대상 60개 hash는 모두 유지됐다.
- B 합성 source의 Python Unicode [9,59) 구간만 실제 MCP propose_profiling_drafts로 제안했다. DB owner/session/source/hash와 50글자 exact_text 일치를 확인했으며 DRAFT 1개/Claim 0개다. 측정하지 않은 개선 수치를 생성하지 않았다. 만료된 Web 조회용으로 이번에 연 background 시험 탭 2개만 닫았고 기존 A 재연결 dialog·B 창과 QA runtime/tunnel은 다음 수동 단계용으로 유지했다.
- 사용자가 A 재연결을 완료했고 기존 프로필A 항목에서 인증 갱신 필요 표시가 사라졌다. 기존 provider SSO를 통한 Web 로그인 redirect로 A/B 로그인을 갱신했고 /account의 실제 profile 링크가 각 QA A/B와 일치했다. 비밀번호·동의 화면의 수동 입력을 대신하지 않았다.
- 갱신된 Web에서 B 본인의 내용 있는 session/drafts는 200이며 exact source 초안도 보였다. A의 동일 대상과 없는 대상은 각각 같은 404/본문/form 0/ID·초안 미노출로 두 경로 6 GET을 확인했다. 역방향·POST·artifact·전체 원문 조회 증거로 확대하지 않는다.
- A ChatGPT 재연결 후 discovery 요청은 실패했고 실제 MCP A identity는 아직 확인하지 않았다. 설정 화면의 floating chat 상태와 새 임시 채팅의 ‘개인화되지 않음’/플러그인 무시 안내를 확인했다. 직접 page navigation으로 시험 화면을 바로잡았지만 메뉴 자동 클릭 두 방식이 동작하지 않아 사용자에게 개인화됨 전환 한 단계만 요청했다. OAuth 재동의나 재로그인을 반복 요청하지 않았다. Web과 MCP가 공유하는 read quota를 MCP 전용 호출 수로 계산하지 않는다.
- 실제 client 차단 전의 승인 범위·정확한 client 관측·정상 종료·오프라인 복구·동일 store 재시작 절차를 별도 runbook에 정리했다. 실제 공유 client 차단/제공자 grant 철회는 아직 수행하지 않았다.
- 사용자가 A 임시 채팅을 개인화됨으로 전환했다. 기대 ID를 주지 않은 실제 get_my_profile 반환이 QA A와 일치/B와 불일치하며 version 0이었다. A의 실제 MCP identity 확인이 완료됐다.
- A MCP의 profile/session 조회·세션 생성·원문 추가·PROFILE_EXPORT 승인 요청·PROFILE 삭제 미리보기 12건은 다른 계정과 없는 대상에 대해 같은 오류로 거부됐다. 38개 table의 count/행 내용 hash를 비교해 request_limit_buckets 외 37개가 유지됨을 확인했다. 실제 export/삭제 실행·artifact·유효 완료 증명 교차 사용을 통과했다는 의미는 아니다.
- A 본인 MCP에 명시적 합성 원문 1개/정확한 Unicode 구간 임시 초안 2개를 준비하고 DB owner/session/source/hash/text 일치를 확인했다. BrowserOS 제출 반환이 유실된 두 경우 모두 이미 보낸 대화와 DB 결과를 먼저 확인하고 재제출하지 않았다.
- 내용 있는 session/draft Web GET은 A/B 양방향 모두 본인 200, 다른 계정/없는 대상 같은 404·본문·form 0·ID/문구 미노출이었다. 원문 추가 POST는 본인의 정상 입력 폼/token을 DOM 안에 유지하고 action 대상만 변경한 4건이 양방향 모두 같은 409/본문/form 0이었다. token 값을 추출하거나 복사하지 않았다. B MCP의 A/없는 session 조회·원문 추가 4건도 NOT_FOUND였다. 이 단계의 부정 시험 요청 뒤 자료 table 37개 행 내용도 유지됐다.
- 본인 A session에 B source ID를 섞는 propose_profiling_drafts 요청은 ChatGPT가 안전 검사로 실제 호출하지 않았다고 응답했다. 서버 거부 통과로 기록하지 않았고 다른 context의 같은 우회 요청도 진행하지 않았다. 원문 ID 조합에 대한 실제 MCP 서버 증거는 미확인으로 남긴다.
- A 합성 문구 2개의 FACT_REVIEW batch와 WAITING 확인 operation을 실제 MCP에서 준비했다. 서명 검증 뒤 기록된 정확한 client metadata는 private QA 파일에만 보관했다. A Web 검토 200, B의 같은/없는 operation 조회는 같은 404였다. B MCP get_confirmation_status도 두 대상 모두 REVIEW_REQUIRED였다. 최초 NOT_FOUND 예상은 현재 _owned 계약을 읽어 바로잡았고 다른 계정 요청을 재제출하지 않았다.
- A의 실제 Web 최종 사실 검토를 사용자에게 한 단계로 요청했다. agent는 결정을 선택하거나 제출하지 않았고 완료 증명을 읽거나 출력하지 않았다. 직접 사실 확인·연결 앱 결과 전달은 이후 별도 사용 승인/내보내기/삭제 승인을 대신하지 않는다.

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
- 사용자가 fg %1을 수행했지만 창은 열리지 않았고 CDP 9100 시작 메시지·singleton broken pipe·GPU 상태 오류를 보고했다. 원인을 단정하거나 프로필 잠금을 삭제하지 않았다. 원래 PC에서 실행할 읽기 전용 scripts/inspect_browseros_startup.py를 준비했다. 정지 프로세스/역할·민감 문자열 비출력·잠금 보존·접근 거부 구분 smoke 점검, Ruff check/format 및 diff 검사가 통과했다. 현재 agent 환경에서 관측 프로세스 0개와 localhost PermissionError는 원래 PC의 종료/포트 닫힘 증거로 사용하지 않는다. BrowserOS MCP 도구도 현재 세션에서 제공되지 않아 실제 GUI 시험은 원래 PC 점검 결과 이후 재개한다.
- 사용자 원래 PC의 시작 점검도 완료됐다. snapshot_complete=true, BrowserOS main/child 0개, 프로필 디렉터리 있음/SingletonLock 없음, CDP version/targets·MCP health 모두 connection_refused, Wayland 세션이었다. 관측 시점에 브라우저가 남아 있지 않음을 확인했으며 종료 원인을 확정하지 않았다. 기존 사용자 프로필과 loopback shim/서버 리소스/포트를 유지한 careerground-browseros --ozone-platform=x11 --disable-gpu --new-window about:blank 실행을 다음 수동 단계로 요청한다. 이번 실행의 임시 옵션이며 GUI/MCP 복구 성공은 아직 미확인이다. 기존 자료·설정·잠금을 삭제하거나 sandbox를 끄지 않는다.
- 사용자가 X11/GPU 임시 옵션으로 BrowserOS 창 생성에 성공했다. 시작 로그에서 서버 v0.0.162·CDP 9100 연결·HTTP 9201·브라우저 도구 17개 등록을 확인했으며 종료 원인을 GPU/Wayland 하나로 확정하지 않았다. GCM QUOTA_EXCEEDED를 제품/AI quota 오류로 판정하지 않았다. 진단 health 경로를 /system/health로 수정하고 실제 TCP LISTEN 주소 분류 및 선택적 MCP initialize/list_tools만 수행하는 --mcp-check를 추가했다. 새 smoke 점검·Ruff/diff 검사는 통과했으나 원래 PC의 프로토콜/리스너 결과와 이 agent 세션의 BrowserOS 접근 성공은 아직 미확인이다. 현재 세션의 loopback PermissionError와 BrowserOS 도구 부재는 계속되며 기존 Codex 설정의 활성화/URL 일치는 확인했다. 다음은 원래 PC의 읽기 전용 연결 점검 한 단계다.
- 후속 사용자 --mcp-check 결과는 관측 프로세스·SingletonLock·대상 LISTEN이 없고 CDP/MCP 연결이 거부됐으며 MCP connection_failed였다. 도구 호출은 0회다. 시작 당시 성공을 지속 실행이나 실제 제품 시험 성공으로 확대하지 않았다. 같은 재실행을 반복하기 전에 점검 당시 창·원래 실행 터미널의 프롬프트 복귀 여부·직전 종료 코드와 마지막 오류 확인을 요청했다. 정상 종료/시그널/충돌/실행 환경 차이 원인은 아직 미확인이다. 서버·브라우저 계정 자료와 기존 QA 이력은 보존한다.
- 사용자는 후속 점검 전에 Ctrl+C로 BrowserOS 실행 명령을 직접 종료했다고 확인했다. 이번 프로세스/리스너 부재와 연결 거부는 수동 종료 뒤의 결과로 분류하며 자발적 충돌/MCP 설정 결함으로 확대하지 않는다. 터미널 프롬프트를 사용할 수 있도록 기존 실행기의 nohup 백그라운드 시작 후 창을 유지한 연결 점검을 안내한다. 설정/프로필 변경 없이 기존 임시 옵션을 사용하며 agent 세션의 도구·loopback 제한은 별개로 남아 있다.
- 사용자 nohup 유지 상태의 원래 PC 점검은 CDP/health 200·MCP connected/24개 도구/pagination 없음·9000/9100/9201 모두 127.0.0.1이었다. browser tool 실행 0회이며 이 기동/연결 점검은 통과해 반복하지 않는다. 명령과 맞지 않는 프로세스 역할/옵션 분류는 수용 증거에서 제외했다. 자격 증명/탭 URL 없는 docs/careerground_browseros_connection_recovery_20261007.json에 결과를 기록했다. 현재 agent의 loopback PermissionError/BrowserOS 도구 부재는 계속되므로 현재 대화의 사용 환경을 확인해 해당 MCP 연결을 이어간다. 새 지속 QA marker는 runtime_initialized=false이며 state/passkeys는 아직 없다.
- 사용자는 ORCA의 Codex CLI를 사용 중이라고 확인했다. ORCA CLI 스킬에 따라 외부 Linux shell에서는 orca-ide로 상태를 확인했고 현재 명령 실행 환경에서 stale_bootstrap/runtime_unavailable였다. 이를 원래 PC 앱 종료로 판정하지 않았으며 중복 앱/다른 agent/worktree를 만들지 않았다. 실제 ORCA Codex home의 config도 BrowserOS 활성/loopback URL 일치이고 현재 세션 파일 존재를 확인했다. 설정/인증을 복사하거나 변경하지 않고 현재 Codex 입력칸의 /mcp에서 browseros 상태만 확인하도록 요청한다. CLI 초기 연결 실패 가능성은 아직 가설이며 제품 도구 시험 성공으로 기록하지 않는다.
- 사용자가 현재 Codex /mcp의 browseros fail을 확인했다. 원래 PC MCP 통과와 CLI 초기화 상태를 구분하며 정확한 실패 원인은 아직 확정하지 않는다. 현재 저장 세션 존재와 설치 CLI resume 사용법을 확인하고, BrowserOS를 유지한 채 같은 ORCA Codex home/정확한 현재 세션 ID로 /quit 뒤 재개하는 한 단계를 준비했다. 설정/인증 복사·보호/모델 override·새 agent/worktree/공유 daemon 종료는 없으며 현재 터미널 접근이 안 되어 실행은 사용자에게 필요하다. 실제 MCP 재연결 성공은 재개 후 확인한다.
- 사용자 재개 후 Codex BrowserOS MCP connected와 agent 도구 24개 로드를 확인했다. 첫 tabs list는 ‘승인 필요하지만 정책 never’로 클라이언트에서 거부됐다. 연결 실패/제품 거부/실제 도구 실행으로 확대하지 않았다. 공식 권한 문서를 확인하고 /permissions의 Ask for approval(workspace-write/on-request) 선택을 수동 한 단계로 요청했다. 설정/transport를 바꿔 거부를 우회하지 않았다. 새 persistent runtime marker는 아직 false이고 state/passkeys가 없으며 실제 서버 시작도 진행하지 않았다.
- 도구 권한 확인 중 이전에 승인된 1.0.3 private plugin 준비를 Git 제외 지속 packages 경로에서 완료했다. 기존 등록 앱·이름·allowlist 3개와 source hash를 검증하고 ZIP 무결성·0700/0600·repo source 보존을 확인했다. 설치된 1.0.2 스킬은 최신 source와 달랐다. 업로드/설치/왕복/모델 호출은 아직 없으며 근거는 docs/careerground_private_plugin_preparation_20261007.json이다. 과거 합성 사람 평가를 반복하지 않았다.

- 2026-10-07 사용자 Full Access 선택 후 native BrowserOS 탭 조회/snapshot/navigation과 로컬 bind가 성공했다. 지속 QA를 실제 시작해 DB/패스키 경로를 새 초기화했고 accounts/profiles/claims 0, runtime live 200, 기존 터널 health/ready 200을 확인했다. 이전 DB/approval/passkey 복원은 없다. 기존 SSO로 A 빈 프로필 생성 화면을 준비했으며 사용자 직접 생성 확인을 기다린다. 루트에 생긴 tunnel literal stdout 로그는 private QA로 보존하고 CLI 문서대로 빈 log.file 경로로 수정했다. 회귀 4개 및 수정 후 health/ready 200·루트 파일 미생성이 통과했다. ignored 초안 20개 hash도 유지됐다. 실제 제품 수용/차단/복구/export/삭제 완료로 확대하지 않는다. 근거: docs/careerground_persistent_qa_activation_20261007.json.

- 같은 지속 QA에서 사용자 A의 직접 프로필 생성 뒤 관리 화면과 계정/identity/profile 각 1개·version 0·Claim 0을 확인했다. A의 쿠키·토큰을 복사하지 않고 별도 BrowserOS context/새 창에서 B 제공자 로그인 화면을 준비했다. B 로그인 및 직접 빈 프로필 생성이 다음 수동 단계이며 A/B identity 분리나 MCP 연결 완료로 판정하지 않는다.

- 사용자 B 로그인 지연 후 실제 화면의 ‘로그인을 완료할 수 없습니다’를 확인했다. 원인을 확정하거나 기존 profile을 초기화하지 않고 같은 분리 context에서 새 /auth/login 요청을 시작했다. 기존 제공자 세션으로 계정 시작 화면까지 돌아왔으며 B 직접 생성을 다시 요청했다. runtime live 200·A account/profile 각 1개는 유지됐다.

- 사용자 B의 직접 생성 뒤 accounts/identities/profiles 각 2개·서로 다른 검증 identity·각 version 0·Claim 0을 확인했다. Web 관리 링크가 private A/B actor mapping과 일치했다. 새 세션 바인딩만 확인하는 profile GET 6건은 양방향 본인 200, foreign/absent 동일 404·동일 본문·form 0·요청 ID 미노출이었다. 최초 browser fetch 시도는 Failed to fetch로 미확인이고 top-level navigation으로 확인했다. 기존 완료된 광범위 시험을 반복한 것은 아니다. 기존 ChatGPT 프로필A/B의 실제 get_my_profile 1회씩은 앱 계층 재인증 요구여서 서버 identity/차단 증거로 채택하지 않았다. A OAuth 재연결 한 단계만 사용자에게 요청했다. 새 Web 증거: docs/careerground_persistent_qa_web_sessions_20261007.json.

- 사용자에게 프로필A 다시 연결이 보이지 않는다는 후속을 받아 실제 ChatGPT UI를 확인했다. 현재 사이드바→플러그인→기존 제품 상세→연결된 계정에서 정확한 프로필A 다시 연결을 선택해 연결 팝업을 준비했다. 새 연결·다른 별칭 변경은 없고 실제 OAuth 완료/반환 identity 확인은 대기 중이다.

- 사용자 A 재연결 후 실제 native MCP get_my_profile이 새 지속 QA A/version 0을 반환했고 B와 다른 ID임을 확인했다. 남은 시험용 새 합성 source 1개/정확한 Unicode [35,72) DRAFT 1개를 native MCP로 준비했다. 최초 start goal은 계약값과 달라 VALIDATION_FAILED였고 ADD_EXPERIENCE로 수정했다. DB owner/session/source/hash/text 일치, Claim/승인 0을 확인했으며 과거 fact approval을 복사하지 않았다. 이 호출은 Codex 연결 앱의 실제 MCP이며 ChatGPT 브라우저 대화/최신 설치 plugin 왕복 증거와 구분한다. B context의 기존 제품 상세 탭은 미로그인이라 쿠키 비필수사항 거부 후 ChatGPT 로그인 dialog를 준비하고 같은 기존 ChatGPT 계정으로 사용자 로그인만 요청했다. 새 가입/새 앱/다른 연결 제거는 없다. 근거: docs/careerground_persistent_qa_a_mcp_preparation_20261007.json.

- B 창 ChatGPT 로그인 뒤 기존 private plugin을 확인했다. 계정 목록의 초기 A만 보이는 상태가 후속 로드에서 기존 aliases까지 갱신됐다. B context의 다른 계정 연결은 기존 SSO/동의로 자동 처리돼 새 별칭 지속 QA B를 부여했다. 기존 별칭 제거/제공자 설정 변경은 없다. 기대 ID 없는 ChatGPT get_my_profile 반환이 정확한 새 B/version 0이고 서버 B read 1건임을 확인했다. B의 새 합성 source/DRAFT 각 1건 owner/hash/text 일치가 확인됐다. multiline type이 3개 메시지로 나뉜 관측은 보존하고 실제 저장 원문은 명시적 최종 합성 문장 37자다. 후속 입력은 single-line fill→send로 바꿨다. 새 실제 A own session+B source 혼합과 없는 source 요청은 native MCP에서 같은 NOT_FOUND였고 자료 37개 table count/hash가 유지돼 이전 미확인 방향을 보완했다. A FACT_REVIEW batch/confirmation을 준비하고 실제 서명 검증 뒤 기록된 A/client metadata를 private observed-client.txt로 보존했다. registry 활성화/차단은 아직 없고 사용자 사실 검토를 기다린다. 근거: docs/careerground_persistent_qa_b_connection_boundaries_20261007.json.

- 사용자 A 사실 검토 뒤 새 합성 Claim 1개·version 1을 확인했다. 동일 요청 연결 get_confirmation_status의 DONE 증명을 출력/파일 저장/공유하지 않고 submit_claim_review에 전달해 CONSUMED가 됐다. B의 WAITING PROFILE_EXPORT 요청에서는 actual client metadata가 A와 같은 값임을 확인했고 동의/export 실행은 없다. A의 B/없는 operation get_confirmation_status는 같은 REVIEW_REQUIRED였으며 증명은 노출되지 않았다. 소유 runtime/tunnel만 정상 종료해 동일 지속 store에 signed denial registry를 처음 연결했고 자료 37개 table count/hash를 유지했다. runtime live 및 기존 tunnel ready 200, A/B 기존 SSO Web 로그인·소유 profile 링크 갱신, A native MCP/version 1 및 B ChatGPT MCP/version 0을 확인했다. 정확한 A/account/client private 오프라인 복구 helper는 문법이 유효하고 runtime 활성 상태 실행은 RECOVERY_REFUSED였으며 해당 store lock이 실제 독점 잠금임을 확인했다. A Web 차단 검토를 새로 열어 기존 승인 범위의 사용자 최종 제출을 요청했다. 새 승인 범위를 다시 요청하거나 Auth0 변경/실제 unblock을 실행하지 않았다. 근거: docs/careerground_persistent_qa_a_fact_connection_controls_20261007.json.

- 2026-10-07 사용자 A 연결 차단 제출 뒤 A MCP 재인증 요구·B 실제 ChatGPT 조회 허용·A/B Web 조회 유지·일반 재시작 차단 지속을 확인했다. 승인된 정확한 A/client offline helper의 exit 0/UNBLOCKED를 확인한 뒤 최종 재시작해 A 실제 native MCP 조회 복구와 자료 table 37개 보존을 확인했다. 차단 중 새 OAuth/grant 철회는 미수행이므로 연결 관련 전체 gate 완료로 확대하지 않는다.

- 재개 후 A 차단 해제/자료 table 37개/ignored 초안 20개 보존을 확인했다. 새 실행기 시험은 pytest 함수 13개라 unittest CI에 수집되지 않아 별도 python -m pytest 단계를 추가했다. 로컬 13 PASS·복구 unittest 3 PASS·Ruff 13파일 및 diff check PASS. BrowserOS 일반 파일 업로드 화면은 새 플러그인 생성이라 파일 선택 후 취소했으며 추가 생성은 없다. 이후 A Web 로그인 navigation/CDP evaluation이 시간 초과돼 파일 선택 창/탭 반응의 사용자 확인을 요청했다. 로컬 runtime/tunnel health는 200이며 원인은 미확정이다.

- 사용자 메뉴 확인 후 BrowserOS에서 기존 plugin 새 버전 업로드 경로가 정상 작동했다. 최초 portable careerground 이름 패키지는 기존 이름 불일치로 거부됐고, 실제 기존 ZIP의 .codex-plugin/plugin.json 이름·앱 바인딩·파일 구조를 그대로 보존한 수정 1.0.3 패키지로 갱신했다. 성공 dialog/표시 버전 1.0.3 및 다시 다운로드한 skill byte/hash 일치를 확인했다. 갱신 뒤 새 ChatGPT 대화는 기대 ID 없이 정확한 A/version 1/합성 문구/USER_CONFIRMED·NOT_EVALUATED·REVIEW_REQUIRED를 반환해 사실과 사용 허용을 구분했고 자료 table 37개가 유지됐다. 새 앱/연결·제공자 설정·유료 자원 변경은 없다. 새 A Web 탭 8의 기존 SSO 로그인이 완료됐고 정확한 A profile/근거를 확인했다.

- 사용자 A 별도 사용 검토 완료를 Web와 DB에서 확인했다. 정확한 Claim 한 문구의 상충 없음·사용 허용 두 선택이 저장돼 version 1→2, CONSISTENT/ALLOWED가 됐다. B version 0/Claim·사용 검토 0과 삭제 요청/ledger 0은 유지됐다. 최신 설치 plugin의 같은 A 대화에서 새 현재 버전 확인 후 한 줄 합성 JD의 근거 연결 없는 미승인 발췌 검토를 준비한다.

- 다음 합성 JD 준비의 실제 ChatGPT get_my_profile은 프로필A 만료 gate에 막혔다. 새 profile/version 응답·JD proposal 링크는 없고 저장 JD/artifact 0을 확인했다. 기존 A 재연결 dialog를 준비하며 현재 만료를 서버 소유자 거부/준비 성공으로 기록하지 않는다. 사용자 OAuth 단계만 필요하다.

- 사용자 A 재연결 후 같은 ChatGPT 대화가 원래 JD 준비 요청을 자동 재개했다. 중복 요청 없이 actual version 2/WAITING/canonical_saved=false와 server confirmation URL을 확인했다. 합성 한 줄 JD [0,24)·claim null/evidence 빈 배열·후보 1개이며 A Web 200/정확한 원문·버전·연결 없음이 표시됐다. 탭 8을 앞으로 열고 발췌 선택 및 저장 범위 최종 확인을 사용자에게 요청했다. expires_at 필드는 반환되지 않았으므로 기한을 추정 출력하지 않는다. server TTL은 생성 이후 180초이며 만료 시 새 제안부터 준비한다.

- 사용자 A JD 발췌 저장을 완료했다. Web 완료 및 정확한 owned JD/source hash·[0,24) 요건 1개·maps/artifacts 0을 확인했다. 같은 ChatGPT 연결의 proposal status 1회는 VALIDATION_FAILED라 DONE/result_id를 확인했다고 기록하지 않고 재시도하지 않았다. 실제 get_jd_analysis는 정확한 요건/linked_claim_ids 빈 목록/NO_ELIGIBLE_LINK_RECORDED를 반환했다. 별도 JD_LINK confirmation의 signed owner/target/version 2를 확인하고 서버에 표시된 요건·ALLOWED 합성 Claim 한 쌍을 최종 검토용으로 선택했다. 정확한 검토 준비 POST만 진행했으며 잠재 연결 최종 두 선택/작업 승인은 사용자에게 요청했다.

- 사용자 A JD 연결 최종 승인 뒤 Web 완료 및 operation DONE·RELATED/POTENTIAL mapping 1개·profile version 2/artifacts 0을 확인했다. 원래 ChatGPT 연결에서만 완료 증명을 처리하고 별도 R1_DRAFT 확인 요청을 준비하도록 요청했으며 증명을 출력/파일 저장/다른 연결에 전달하지 않는다.

- JD_LINK get_confirmation_status 1회는 REVIEW_REQUIRED로 거부돼 link_jd_requirement 결과 소비는 미수행이다. 후속 R1 요청도 그 대화에서는 생성되지 않았다. inspection 시 operation의 05:47:03 UTC 유효기한이 지난 상태임을 확인했다. 호출 실패 당시의 정확한 원인은 확정하지 않았고 증명/기한을 연장하거나 저장된 JD 연결을 재승인하지 않는다. 저장된 canonical mapping을 사용해 별도의 새 R1_DRAFT 검토를 요청했다.

- 실제 ChatGPT가 별도 새 R1_DRAFT confirmation을 만들었다. A owner/JD target/version 2를 확인하고 서버의 ALLOWED 합성 Claim 한 문구를 최종 검토용으로 선택해 exact preparation만 진행했다. 새로 쓴 문장이나 승인/내보내기는 없다. 정확한 R1 초안 선택 직접 확인 화면을 앞으로 열고 최종 두 선택/작업 승인을 사용자에게 요청했다.

- 사용자 R1 만료 보고 뒤 기존 WAITING 요청의 05:54:13 UTC 기한 경과와 artifacts 0을 확인했다. 새 재시도 키로 같은 A/JD/version 2의 별도 새 R1 요청을 만들고 정확한 검토 화면을 다시 열었다. 기존 기한/승인·저장 자료를 변경하지 않았고 최종 선택은 사용자에게 남겼다. 현재 locator는 private a-r1-draft-operation-2.json이다.

- 사용자 새 R1 초안 승인 후 owned RESUME_TEXT/R1 unit 1개·정확한 합성 Claim 문구·profile version 2·REVIEW_REQUIRED를 확인했다. 같은 ChatGPT get_confirmation_status→generate_resume_draft가 실제 ok이며 operation CONSUMED/중복 artifact 없음(1개)을 확인했다. 증명 출력/공유 없이 별도 WORDING_REVIEW를 준비했고 A/artifact/version 2 binding 및 Web R1 문구 직접 검토를 확인해 사용자 최종 두 선택/문구 승인을 요청했다.

- 사용자 R1 문구 승인 뒤 WORDING_REVIEWED와 같은 ChatGPT 결과 소비 CONSUMED를 확인했다. 첫 R2 중간 쉼표 추가는 실제 prepare VALIDATION_FAILED였고 ChatGPT가 래퍼 변경으로 추가 시도해도 거부됐다. 로컬 순수 guard에서 FACT_OR_QUALIFIER_CHANGED를 재현했고 정책을 바꾸지 않고 동일 과거 어미만 바꾼 제안을 사용했다. 같은 소유 R1 trace/근거로 한 번 준비한 수정 R2는 actual ok true이며 Web before/after/version 2가 일치했다. 원본 R1 보존·별도 R2 최종 저장 확인을 사용자에게 요청했다. R2 허용 범위의 보수적 한계도 별도 기록했다.

- 사용자 R2 저장 뒤 source R1 보존/R2 source_artifact_id·version 2·어미 수정 exact text/WORDING_REVIEWED와 artifacts 2개를 확인했다. 같은 ChatGPT proposal status는 actual DONE/result_id가 저장 R2와 일치했고 get_resume_trace도 정확한 R2를 반환했다. 별도 RESUME_EXPORT/MARKDOWN 요청의 A/R2/version 2/format binding을 확인해 사용자 최종 범위·수신 연결 앱 승인을 요청했다. 아직 MCP export 내용 수신은 없다.

- 사용자 R2 내보내기 승인 뒤 같은 ChatGPT get_confirmation_status→export_resume_artifact가 실제 INLINE 본문/91 bytes/hash/version 2를 반환했고 operation CONSUMED를 확인했다. 화면 렌더는 마지막 LF를 생략해 90 bytes였으며 구현된 Markdown serializer의 마지막 LF를 보완하면 정확한 91 bytes/SHA256이 일치했다. 원시 MCP transport bytes를 별도 캡처한 증거로 확대하지 않는다. signed passkey registry는 아직 credential 0이며 현재 지속 QA의 A 등록 검토를 열어 사용자 same-owner OIDC/기기 PIN 확인을 요청했다. B 계정별 non-quota table count/hash를 다음 A 삭제 보존 검증용으로 private baseline에 저장했다.

- 사용자 A 패스키 등록 완료를 Web/서명 registry에서 확인했다. 현재 store/origin의 A 공개키 1개/B 0개이며 PIN/개인키는 읽거나 저장하지 않았다. 재개 때 기존 QA/tunnel loopback ports가 connection_refused였고 종료 원인은 미확정이다. 같은 initialized store/패스키/denial registry로 재시작해 runtime/tunnel 200·A SSO 소유 profile/version 2를 확인했다. 임시 systemd --user unit 두 개로 기존 QA/tunnel 실행을 관리하고 tunnel은 owned QA에 BindsTo로 묶었다. systemwide/자동부팅/새 클라우드 자원은 없다. 별도 도구 호출 뒤 active 상태를 확인했고 B 계정별 자료 table 34개 count/hash는 유지됐다.

- 정확한 A/profile version 2의 PROFILE 삭제 영향 화면을 열었다. Claim 1/JD 1/요건 1/RELATED map 1/R1·R2 artifacts 2와 관련 로컬 기록이 표시됐고 B/다른 QA/제공자 계정·ChatGPT 사본은 범위 밖이다. 사용자 영향 확인→fresh same-owner OIDC→등록 패스키 서명→별도 최종 삭제 실행을 한 흐름으로 요청했다. OTP MFA/대체 인증/기한 연장은 없다. 관측 시 deletion request/ledger 0이며 agent는 최종 삭제를 수행하지 않았다.

- 사용자 A 로컬 삭제 완료 뒤 known A Claim/원문/초안/JD/R1/R2/승인 자료 0과 B 계정별 table 34개 count/hash 유지, ERASE DONE 7/VERIFY DONE 30/UNVERIFIED_SCOPE VERIFY PENDING 1을 확인했다. 요청/프로필 stub은 DELETING이며 FOUNDATION_ONLY를 전체 삭제 완료로 바꾸지 않는다. 같은 store의 managed QA를 재시작해 signed checkpoint 검증/ledger 1/삭제 상태 지속/B hash 유지 및 실제 B Web 본인 profile/session/drafts 200·정확한 기존 초안 표시를 확인했다. B의 삭제 A profile/JD/R2 export와 없는 대상은 각각 같은 404/본문/forms 0이었다. B ChatGPT 창은 플랫폼 로그인 만료여서 사용자 기존 계정 로그인 완료 뒤 같은 기존 B 대화의 actual read-only MCP 검증을 요청했다.

- 사용자 B 기존 연결 재인증 후 actual get_my_profile은 정확한 B/found true/version 0을 반환했다. 첫 병렬 읽기 묶음은 어느 대상인지 모르는 NOT_FOUND 하나만 표면화해 pairwise PASS로 쓰지 않았다. 결과 유실을 해결하는 6개 순차 read-only 호출에서 삭제 A profile/JD/R2와 없는 대상은 모두 동일 NOT_FOUND/동일 message였다. B 자료 table 34개 hash가 유지됐다. 새 Claim 검토 만료 갱신의 PostgreSQL 실제 SQL/rollback 경로 회귀를 추가했고 Ruff check/format 및 환경 없음 시 skip 1을 확인했다. PG 실행은 아직 PASS가 아니며 owner-only 임시 env/loopback 55432/Postgres 17/무영구볼륨 전용 실행 자료를 준비했다.

- PostgreSQL 12개 대상 회귀(foundation/계약 완료/동시 demo/계정 초기화, 새 만료 검토 갱신 포함)의 수집을 확인했다. private env/driver를 준비했고 Docker 일반 권한과 cached sudo 모두 불가해 사용자에게 일회용 localhost DB 시작 한 명령만 요청했다. DB 없는 새 PG 시험은 skip 1이며 PASS가 아니다. SQLite claim workspace 9개 및 정적 검사도 통과했다.

- 실제 PostgreSQL 마이그레이션/12개 회귀(새 expired review renewal 포함)는 실패·오류·skip 0으로 모두 PASS이고 제품 table 38개가 비어 있었다. 사용자 test container stop 성공/55432 closed를 확인했고 소유 managed QA/tunnel을 중지해 5000/8001/18081 closed를 확인했다. 임시 PG password file은 제거하고 현재 QA/등록 공개키/삭제 checkpoint/B 자료/ignored 초안 20개를 보존했다. B 계정별 table 34개 hash 유지 및 Ruff check/format 14파일/diff check PASS를 확인했다. 최종 qualified 정리는 docs/CareerGround_Phase_A_Private_MVP_Closeout_2026-10-07.md다. 1/2의 미관측 실제 증명 전송/제공자 변경 범위는 제한으로 남기며 전체 운영 수용 완료를 선언하지 않는다. commit/push/merge는 없다.

# Phase A 하이브리드 개발 수용 현황

기준 HEAD: `d88ad6255eb110cd265b0cc26c581578bc7564a0`.
2026-10-04 승인된 개발 구현·시험 결과이며 **Phase A 완료 판정은 아니다**.

PostgreSQL 전체 회귀·삭제 재인증·새 품질 관측의 후속 결과는
[2026-10-05 남은 조건 보고서](CareerGround_Phase_A_Remaining_Gates_2026-10-05.md)에 기록했다.
아래 실행 수와 관측은 이 문서 작성 당시의 결과를 유지한다.

## 구현과 관측

| 항목 | 완료된 내용 | 검증 범위 / 남은 항목 |
| --- | --- | --- |
| 영속 인증 개발 store | 별도 DB·안정적 admission 키·설정 바인딩·키 교체 거부·잠금·삭제 checkpoint | 합성 HTTP/MCP와 실제 Auth0 Web 모두 재시작 검증. 실제 승인 사실·JD·R1·R2 보존, 이전 cookie 401, 재로그인 후 동일 프로필 버전 2 |
| 제품 MCP 진입점 | 기존 개발 터널용 loopback listener, Web과 같은 DB와 실제 JWT 검증 | OAuth metadata 200, 미인증 MCP 401, Web 경로 404, 비loopback 403. 실제 ChatGPT와 Web 동일 프로필, 합성 자료 전체 왕복 확인 |
| 기존 개발 OAuth | 여섯 제품 scope 추가, 기존 ChatGPT 사용자 위임 7/7(probe 포함) | BrowserOS 저장 확인. Client Access 0/7, 다른 세 앱 0/7, Always grant all 꺼짐 |
| ChatGPT 제안 전달 | JD 원문 context, JD/R2 준비, 상태 조회 네 도구와 브라우저 검토 | 합성 HTTP/MCP 9개 시험 통과. 실제 ChatGPT → Web의 JD 선택 저장·R2 비교 승인·별도 export 왕복 완료 |
| ChatGPT 품질 | 삭제·사용 금지 근거, 부정·역할·수치 사례와 새 사례 관측 | 최초 분류 불일치 보존. 지침 보강 뒤 동일 대화 4건 관측 일치. 독립 전체 품질 gate 통과 아님 |
| 기존 비공개 플러그인 | 같은 앱 바인딩 유지, 버전 1.0.1에 최신 career-interview 스킬 반영 | BrowserOS 업로드 성공·스킬 1 확인. 도구 목록은 Read 1 유지 |
| 새 비공개 제품 연결 | 승인 후 CareerGround Phase A Dev 생성, 기존 CIMD client 재사용 | 추가 Auth0 client/grant 없음. 사용자 여섯 scope 동의 완료. 도구 34개(읽기 15·쓰기 19) 확인. 제품 왕복은 스킬 1.0.1, 이후 안내 보강 1.0.2 설치 확인 |

## 검증 결과

- 전체 unittest: **431개 실행, 396개 통과, PostgreSQL 35개 skip**.
  DB가 없어 건너뛴 항목을 통과로 계산하지 않았다.
- 영속 store 시험 6개를 별도로 재검증했다. 재시작 시험은 실제 합성 사실
  브라우저 승인과 MCP receipt 소비를 거친 뒤 같은 Claim·원문 Evidence·hash를 확인한다.
- 제안 전달·차단 시험 9개: 선택한 JD만 저장, 자동 Claim mapping 없음, R1 보존,
  R2 별도 저장, R3 거부, 삭제/사용 금지 근거와 현재 버전 검사, 다른 계정·
  연결 거부, TTL, 폼 재사용/갱신, Origin, HTML escape, Unicode/CRLF 원문 hash.
- 기존 오프라인 제안 fixture 53개 통과, mismatch 0.
- Ruff check/format과 git diff whitespace 검사 통과. CI에 새 시험 파일을 포함했지만
  이번 변경은 push하지 않았으므로 GitHub CI 실행 결과는 없다.

## 제안 도구 사용 계약

| 도구 | 권한 | 반환 / 후속 단계 |
| --- | --- | --- |
| get_chatgpt_jd_source_context | career.artifact.read | 현재 소유 프로필의 JD SHA256·Python Unicode 위치. 원문 최대 6,000자, 100줄; 저장 없음 |
| prepare_chatgpt_jd_review | career.artifact.write | 정확한 원문 위치/hash를 검증하고 브라우저 선택 검토 링크 반환 |
| prepare_chatgpt_r2_review | career.artifact.write | 현재 R1 trace/hash·근거에 맞는 제안의 원문/수정문 비교 링크 반환 |
| get_chatgpt_proposal_status | career.artifact.read | 같은 bearer 연결에서 검토 결과 metadata 조회 |

JD는 의미 적합성·근거 mapping을 자동 승인하지 않는다. R2는 수치·역할·부정의
위험한 변경을 보수적으로 거부한다. R3는 FACT_REVIEW_REQUIRED로 반환한다.
준비만으로 canonical artifact를 저장하거나 export를 승인하지 않는다.

제안 inbox는 메모리에만 보관하며 180초 뒤 만료된다. 계정당 8개, 전체 128개로
제한된다. 준비/상태는 같은 bearer 연결과 현재 프로필 버전에 묶인다. 토큰 교체,
재시작, 만료 또는 버전 변경 뒤에는 새 검토를 요청한다. 저장된 canonical JD/R2는
영속 store에 남지만 inbox와 결과 receipt는 재시작 후 유지되지 않는다.

## 로컬 실행

기존 개발 `.env`/`.env.poc`에 준비된 설정을 사용한다. 비밀번호·토큰을 출력하거나
실제 경력 자료를 입력하지 않는다. state-dir는 기존 합성 demo store와 다른 절대
경로여야 하며 owner-only 디렉터리/파일을 유지한다.

```bash
uv run --locked --env-file .env --env-file .env.poc \
  python -m careerground.auth0_development_runtime \
  --allow-development-login \
  --state-dir /home/inno/repo/CareerGround/.careerground-authenticated-development \
  --mcp-port 8001
```

현재 개발 Web의 정확한 origin은 `http://localhost:5000`이다.
Web의 세션 cookie는 MCP bearer가 아니다. 같은 제공자 계정으로 각각 로그인해야
같은 CareerGround 프로필을 찾는다. ChatGPT 계정과 Auth0 관리자 계정이 서로
다르다는 이유만으로 실패하는 구조는 아니다. 실제 미등록 사용자는 Web에서
명시적 가입·정책 동의를 완료해야 한다.

이 실행 명령은 터널을 새로 만들거나 실행하지 않는다. 기존 승인된 private tunnel
연결은 별도 실행하며 제품 listener만 노출한다. 종료 후 같은 state-dir로 재시작하고
다시 로그인한다. Web 세션은 재시작 시 만료된다. 이 store는 개발 단일 프로세스용이며
자동 schema migration·운영 백업 또는 전체 디렉터리 rollback 탐지를 제공하지 않는다.

이번 실제 시험의 DB를 그대로 이어서 사용할 때는 위의 새 디렉터리 대신 아래
명령을 사용한다. `/tmp` pointer와 그 대상은 로컬 시험 자료이며 시스템 임시
디렉터리 정리 또는 재부팅 정책에 의해 없어질 수 있다. 운영 백업으로 취급하지 않는다.

```bash
uv run --locked --env-file .env --env-file .env.poc \
  python -m careerground.auth0_development_runtime \
  --allow-development-login \
  --state-dir "$(cat /tmp/careerground-persistent-auth-qa-path)/state" \
  --mcp-port 8001
```

ChatGPT에서 다시 시험하려면 기존 승인된 private tunnel도 별도로 실행해야 한다.
현재 종료 상태에서는 연결 목록이 남아 있어도 제품 도구 호출은 성공하지 않는다.

## 실제 제품 왕복 결과

[제품 관측 JSON](chatgpt_product_oauth_observations_20261004.json)은 실제 BrowserOS
여정과 로컬 DB의 읽기 전용 확인을 구분한다. OAuth 동의는 사용자가 직접 했고,
합성 자료의 제품 Web 승인 조작은 승인된 시험 범위에서 BrowserOS로 수행했다.
실제 계정 ID·이름·provider subject·토큰·receipt는 저장 문서에서 제외했다.

1. Web과 ChatGPT가 같은 빈 프로필 버전 0을 조회했다. 정확한 합성 원문
   `합성 CareerGround 시험에서 테스트 문서를 작성했습니다.`를 사실 검토했다.
   Web 승인 전 canonical Claim/Evidence는 0개, 승인 후 각각 1개였다.
   USER_CONFIRMED 사실도 Use 상태는 REVIEW_REQUIRED였다.
2. 별도 Web R1 사용 검토에서 원문과 일관성·사용 조건을 승인했다.
   현재 버전은 2, CONSISTENT/ALLOWED가 됐다. 시험 안내 과정에서 Use를
   BOUNDARY_CHANGE로 잘못 요청한 링크는 제출하지 않았다. BOUNDARY_REVIEW는
   constraint 변경이라는 안내를 스킬 1.0.2에 보강했다.
3. JD 두 줄 `테스트 문서 작성 경험`, `Python 경험`을 제안하고 첫 줄만 선택했다.
   JD 1개/요구사항 1개/연결 0개를 확인했다. 이후 별도 JD_LINK 검토·승인을
   거쳐 연결 1개/POTENTIAL이 됐다. Python 경험이나 적합성을 자동 확정하지 않았다.
4. R1은 원문 그대로 REVIEW_REQUIRED로 생성했다. R2는 마지막 마침표만
   제거하는 제안으로 비교·승인해 WORDING_REVIEWED로 별도 저장했다.
   R1과 같은 Claim/Evidence/source 참조, R1 lineage와 원문 보존을 확인했다.
5. 별도 export 승인 뒤 ChatGPT가 INLINE Markdown을 받았다. 반환된 74바이트와
   SHA-256 `dd614e9c89b9817af24e78d35bb6673214d77ad6432d4e70187ad09a8b7e533e`는
   예상 UTF-8 본문(한 bullet과 마지막 개행)을 독립 계산한 결과와 일치했다.
   DOM 텍스트만으로 원시 응답의 마지막 개행까지 추출·검증했다고 주장하지 않는다.
6. 서버 재시작 후 기존 cookie는 401, SSO 재로그인은 200과 같은 프로필 버전 2였다.
   Web logout 뒤 다시 401이었지만 ChatGPT는 재연결 없이 같은 프로필·R1·R2를 조회했다.
   Web logout을 provider 토큰 폐기로 계산하지 않는다.
7. approval 없는 실제 execute_data_deletion은 REVIEW_REQUIRED였다. 로컬 읽기
   전용 확인에서 사실·JD·두 artifact는 그대로이고 deletion_requests/erasure_ledger는
   각각 0이었다. 실제 삭제 성공·재인증이나 복원 후 삭제 유지 시험은 수행하지 않았다.

실제 R2 export 화면에서 연결 카드의 고정 R1 라벨을 발견해 “검토된 이력서 문구
내보내기”로 바꿨다. target/hash/본문은 R2가 맞았다. 변경 코드의 정적 검사는
통과했고 이후 서버 재시작에 반영했지만 변경 라벨의 새 브라우저 관측은 수행하지 않았다.
제품 여정의 ChatGPT UI 모델/effort는 GPT-6.1 Sol/Light였고 API 모델 ID는 확인하지 않았다.

## 실제 품질 관측의 한계

[관측 JSON](chatgpt_quality_observations_20261004.json)에 전체 합성 prompt/응답과
분류 불일치를 보존했다. 기존 실패 중심 7건 + 새 8건의 한 번짜리 batch이며
새 사례도 시험 작성자가 만든 사례다. blind holdout 또는 모델 버전별 반복 시험이 아니다.
불확실한 성능 사례 jd-06을 최초 응답이 POTENTIAL_ONLY로 분류했으므로 그 결과를
FOLLOW_UP 통과로 바꿔 기록하지 않았다. 지침 보강 후 같은 대화의 4건 후속 관측만
일치했다. `quality_gate_passed=false`, 기준 승인 상태는 PROPOSED_NOT_APPROVED다.
품질 응답 시험은 제품 MCP 저장 성공의 증거가 아니다.

## 남은 수용 조건

1. 실제 token refresh/revocation와 삭제 재인증 시험이 필요하다. 현재 인증 개발
   조립에는 실제 deletion step-up adapter가 없으며 삭제 실행을 거부한다.
   Web logout을 MCP 연결 해제 또는 provider token 폐기로 표시하지 않는다.
2. 두 번째 실제 계정 시험은 보류 상태다. 합성 두 계정 격리 시험으로 대체 완료를
   선언하지 않는다. PostgreSQL 회귀와 변경 후 CI, 독립 품질 재시험도 남아 있다.
3. 공개 배포 시 별도 운영 저장소/키·백업·복원·개인정보 정책·삭제 운영·호스팅/
   OAuth callback/가용성 수용을 결정한다. 별도 서버 AI 도입은 계속 보류한다.

이번 작업에서 새 inference API·유료 플랜·운영 서비스·실제 경력 자료를 연결하지
않았다. commit/push/merge는 수행하지 않았다. 기존 ignored 초안과 설정·합성
store 31개 파일과 기존 터널 설정 2개는 hash manifest 비교에서 변경이 없었다.

이번 시험의 로컬 Web(5000), 제품 MCP(8001), 기존 private tunnel은 모두 종료했다.
별도 owner-only `/tmp` 시험 디렉터리의 영속 DB는 재개를 위해 보존했다.
BrowserOS에는 실제 제품 여정 대화와 비공개 제품 연결 상세 탭을 남겼다.
provider 관리자/ChatGPT 계정에서 자동 로그아웃하거나 기존 개발 자료를 삭제하지 않았다.
이 보존 상태는 제품 운영 배포 또는 Phase A 완료를 뜻하지 않는다.

# Phase A: 기존 ChatGPT 계정과 계정 연결·품질·운영 수용 증거

2026-10-03. 기준 HEAD `7c308de4a5bf498b12966348f0179c8a9150cc1d`,
브랜치 `codex/mvp-foundation-ci-20260923`. 시작 작업 트리는 깨끗했다.
이 보고서의 변경은 아직 commit/push하지 않았다.

## 기존 계정을 그대로 사용하는 범위

사용자의 현재 ChatGPT 계정을 그대로 사용한다. 새 ChatGPT 가입이나 별도 서버 AI
구독을 요구하지 않는다. BrowserOS의 기존 로그인으로 경력 대화와 합성 모델 관찰을
진행할 수 있다. 이전 개인 플러그인 여정은 실제 ChatGPT 호스트에서 성공했지만
CareerGround 서버에는 고정된 합성 신원을 연결했다. 실제 사용자 SSO의 증거는 아니다.

CareerGround 관리 화면이 같은 사람의 자료를 안전하게 여는 데에는 검증된 신원과
CareerGround 계정의 연결이 필요하다. PC에 있는 ChatGPT/Codex 쿠키·내부 토큰을 복사해
이를 대체하지 않는다. 공식 로그인은 앱용 client, callback과 검증된 ID token을 사용하고
CareerGround가 별도 브라우저 세션을 발급한다.
[OpenAI 공식 로그인 문서](https://developers.openai.com/siwc/website).

사용자 확인 결과 CareerGround용 직접 로그인 client는 미등록이다. 공식 안내는 현재
일부 상용 파트너와 대기 신청 방식이다. 계정 보유만으로 CareerGround의 client 등록까지
완료되었다고 판단할 수 없다.
[OpenAI 공식 등록 안내](https://developers.openai.com/siwc/request-client-id).
외부 신청은 제출하지 않았고, 직접 로그인 등록을 다른 로컬 작업의 선행 조건으로 삼지 않았다.
기존 Auth0 PoC는 유지했다. 실제 제공자나 계정 연결 정책을 임의로 바꾸지 않았다.

## 1. 계정 연결: 로컬 구현과 실제 연결의 차이

추가한 코드는 외부 연결 없이 시험 가능한 비활성 경계다.

- `providers/oidc_identity.py`: 서버 설정의 endpoint/callback, S256 PKCE,
  일회용 state·브라우저 binding·nonce, 3분 만료와 최대 128개 transaction.
  주입된 교환/JWKS adapter의 ID token에 RS256 서명·issuer·audience·만료·nonce·azp를
  검증한다. `openid profile email`만 요청하고 inference/resource 권한을 요청하지 않는다.
  이메일·이름을 소유권으로 사용하거나 raw token을 저장하지 않는다.
- `StableAccountAdmission`: 서버 allowlist와 보존하는 비밀키로 안정적인 account ID를
  만든다. 삭제 후 AuthIdentity가 없어져도 기존 계정 tombstone을 우회해 재가입하지 못한다.
  비밀키 교체로 재등록시키는 동작은 지원하지 않는다.
- `web/verified_browser_sessions.py`: 별도의 Secure/HttpOnly/SameSite=Lax
  `__Host-careerground-session`, hash만 저장하는 최대 128개 process-local session,
  1시간 만료, 재시작 무효화, 매 요청 DB 계정 확인, 한 세션의 로그아웃.
  매핑 제거·계정 차단을 확인한 세션은 계정 재활성화 뒤에도 되살아나지 않는다.
- 실제 관리 화면 factory에 연결한 HTTP 시험에서 A 자신의 조회 200,
  B 프로필 조회 404, 로그아웃 후 401, B 자신의 조회 200을 확인했다.

**아직 실제 로그인 기능을 배포·연결한 상태는 아니다.** callback/error/logout HTTP route,
  실제 token endpoint 인증과 timeout, JWKS cache/rotation, 등록된 metadata 및 실제 계정
  admission 설정은 필요하다. 새 모듈의 import는 네트워크나 계정 생성을 실행하지 않는다.
  로그인 실패 후 임시 cookie 정리는 미래 route의 책임이다.

현재 도메인 매핑은 `(issuer, subject)`이며 이 로컬 경계는 환경마다 하나의 고정 client를
전제한다. 공식 문서의 client별 신원 격리를 실제로 적용하려면 namespace 보존/전환 정책과
필요한 매핑 변경을 구현해야 한다. 여러 client를 같은 DB에 연결하거나 기존 client를
교체하는 운영 기능으로 사용하지 않는다. process-local session은 여러 worker의 공유
세션 저장소나 운영 재인증의 대체물이 아니다.

실제 수용에 남은 것: 등록된 client와 정확한 callback, 실제 두 계정의 Web/MCP 일치,
외부 PKCE, 연결별 철회, 재인증/삭제, 중단과 재시작 이후의 신원·삭제 상태 보존.
identity-only 로그인에 OpenAI access/refresh token이나 유료 AI API를 요구하지 않는다.

## 2. ChatGPT 품질: 실제 모델 관찰과 남은 기능

BrowserOS로 기존 로그인된 ChatGPT Work의 **GPT-6.1 Sol / Light**에서 합성 자료
36개(추출/JD/R2/R3 각각 9개)의 응답을 관찰했다. 기대 답과 금지 목록은 모델에 주지 않았다.
이번 시험에는 CareerGround 도구를 연결하지 않았으며, 저장·승인 없이 문구/처리를 평가했다.
이는 과거 실제 플러그인 여정과 별개의 시험이다.

| 범위 | 최초 기대 action 일치 | 불일치 |
| --- | --- | --- |
| 추출 | 7/9 | 측정 없는 추정 수치, 기간 정정에서 질문 누락 |
| JD | 6/9 | 미확인 수치, 삭제 근거, 사용 금지의 처리 label |
| R2 | 6/9 | 역할/부정 변경을 별도 검토 대신 거절, 삭제 근거에 추가 질문 |
| R3 | 9/9 | 없음 |

위 합계 28/36은 최초 관찰이다. 일부 거절은 안전하고 보수적이지만 기대 업무 흐름과
label이 다르다. 이를 임의로 정답 처리하지 않았다. 응답의 부정·공동 기여·불확실성은
보존됐고, 관찰한 범위에서 다른 계정 자료나 삭제 근거를 실제 사용하지 않았다.
도구가 연결되지 않았으므로 제품 쓰기 차단이나 source/ID 연결 성공을 이 점수로 증명하지 않는다.

`plugins/careerground/skills/career-interview/SKILL.md`에 측정 근거/본인 기여 질문,
정정 영향 확인, JD 삭제·사용 금지 근거, R2 삭제 근거와 R3 사실 검토의 지침을 보완했다.
보완 후 일부 사례의 재관찰은 별도 기록하며 최초 결과를 덮어쓰지 않는다.

추가 6개 사례의 action 일치는 **4/6**이다. 추정 수치·정정에 대한 질문은 개선됐지만
JD/R2 삭제 근거의 label은 기대와 다르다. 특히 `jd-07`은 proposal에 “사용할 수 있으므로”라고
출력하면서 reason에는 사용할 수 없다고 썼다. **부정 표현의 모순 1건을 발견했고 해당
문구는 사용할 수 없다.** 모델 문구 품질을 통과로 선언하지 않으며, 저장/승인은 없었다.
추가 시험 결과를 최초 36개에 합쳐 전체 통과율을 높이는 방식으로 계산하지 않는다.
[사례별 응답·prompt·hash·불일치 기록](chatgpt_quality_observations_20261003.json).

UI 긴 입력 과정에서 자동화 timeout과 줄바꿈에 의한 부분 전송이 발생했다.
추출과 추가 6개 시험은 부분 입력 뒤 추가 메시지로 완성했고, JD/R2/R3는 한 줄 prompt를 사용했다.
통제된 동일 prompt/API benchmark, 지연 p95, 두 사람의 독립 채점이나 승인된 품질
합격선 시험이 아니다. 한국어 자연스러움/의미 정확도에 임의의 4/5 점수를 부여하지 않았다.
현재 기대 처리 기준도 `PROPOSED_NOT_APPROVED`이므로 품질 gate 통과를 선언하지 않는다.

현재 `analyze_jd`는 여전히 모의 원문 범위 제안이다. 실제 JD 의미 제안의 안전한 제품
연결과 R2 표현 제안의 관리 화면 전달, 새 holdout/변동성/통합 수용 시험은 남아 있다.
기존 원문·소유권·결정적 R2 검증과 별도 브라우저 승인은 완화하지 않았다.
별도 서버 AI 공급자 선정·API 예산 승인은 **사용자 결정으로 계속 보류**한다.
과거 AI 공급자 준비 문서는 당시의 기록이며 필수 구현 순서를 의미하지 않는다.

## 3. 운영: 로컬 시험 결과

보관 만료, outbox 중복·실패·재시도, private 객체의 미완료 삭제,
삭제 전 backup의 격리 복원과 ledger 검증, 부분 삭제 여정 관련 **39개가 통과**했다.
합성 fixture/임시 로컬 저장소를 사용했다. 운영 계정·실제 경력·클라우드 자원을 연결하지 않았다.

실제 자원 비용 명세, 운영 provider의 모든 객체 version/복제본 삭제, backup 만료,
독립 삭제 ledger anchor, 재인증, 관측·경보와 운영 장애/복원 시간 증거는 없다.
기존 운영 준비 문서 O01–O10 중 로컬 증거만 확인했으며 운영 수용 통과로 바꾸지 않았다.
운영 공개 전의 기간·삭제 SLA·처리/보관 정책 결정도 남아 있다.

## 4. 수용·출시 판단

| 항목 | 현재 판단 |
| --- | --- |
| 기존 ChatGPT 계정으로 대화/합성 관찰 | 가능, 실제 관찰 있음 |
| 기존 ChatGPT 호스트–합성 CareerGround–관리 화면 여정 | 이전 HEAD에 성공 증거 있음 |
| 신규 신원/세션 경계와 두 로컬 계정 격리 | 구현·검증, 비활성 adapter |
| 실제 ChatGPT 신원으로 가입/같은 계정 연결 | 미완료, 등록과 실제 route/adapter 필요 |
| 한국어 추출/JD/R2/R3 품질 | 최초 관찰과 지침 보완, 합격 미선언 |
| 실제 JD/R2 제안 제품 전달 | 남은 구현·통합 수용 항목 |
| 보관/삭제/복원 | 로컬 통과, 실제 운영 증거 없음 |
| Phase A 전체 완료·출시·main 병합 | 보류 |

다음 순서는 지침 보완을 적용한 JD/R2 제품 전달과 holdout 통합 시험 → 직접 로그인
등록 자격/metadata 확보 후 실제 동일 계정 시험 → 승인된 환경/정책에서 운영 증거 확보 →
최종 수용 판단이다. 기존 계정으로 가능한 작업은 계속 진행할 수 있다. 외부 등록 제출,
인증/MFA, 제공자 전환·실제 자원 생성은 그 단계에서 구체적인 선택/수동 작업만 요청한다.

## 재현 가능한 검증 기록

```bash
.venv/bin/python -m unittest tests.test_identity_only_login \
  tests.test_chatgpt_management_journey tests.test_auth0_review_identity \
  tests.test_adapter_security tests.test_browser_mcp_confirmation \
  tests.test_chatgpt_plugin_package -q
# 59개 실행: 50 통과, PostgreSQL 전용 9 skip

.venv/bin/python -m unittest tests.test_restore_quarantine tests.test_outbox \
  tests.test_retention_runner tests.test_private_objects \
  tests.test_deletion_execution tests.test_partial_deletion_journey -q
# 39 통과, skip 0

.venv/bin/python -m unittest tests.test_identity_only_login -q
# 마지막 세션 무효화 보완 후 신규 11개 재검증
# 11 통과, skip 0
```

현재 변경의 PostgreSQL 재시험과 원격 CI는 실행하지 않았다. 기준 HEAD의 Foundation CI
성공과 이번 작업 트리의 로컬 결과를 구분한다. 새로운 migration은 없다.
새 시험 파일을 CI Ruff check/format 목록에 추가했다.

별도 모델 API 호출 0, 새 유료 자원 생성 0. ChatGPT의 기존 계정 UI 사용량은 발생했고
구독 잔여량이나 청구 내역을 확인하지 않았으므로 모든 계정의 비용 0을 보증하지 않는다.
기존 `.env`/`.env.poc`, 개발 데이터, tunnel 설정과 ignored 초안은 보존했다.
시작 시 수집한 보존 대상 29개 파일의 SHA-256을 다시 확인했고 변경은 0개다.

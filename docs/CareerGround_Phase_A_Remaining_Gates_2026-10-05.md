# Phase A 남은 조건 후속 구현·검증

기준 HEAD: `d88ad6255eb110cd265b0cc26c581578bc7564a0`.
2026-10-04에 시작한 후속 작업의 2026-10-05 결과다.
**로컬 구현·회귀 검증을 진행했으며 Phase A 최종 완료는 아직 아니다.**
앞선 실제 제품 왕복은 [이전 결과](CareerGround_Phase_A_Hybrid_Acceptance_2026-10-04.md)를 참조한다.

## 수행 결과

| 항목 | 이번 결과 | 남은 조건 |
| --- | --- | --- |
| PostgreSQL | 전체 441개 통과, skip 0. migration head `20261003_0020`, `alembic check` 변경 없음. 제품 테이블 38개 모두 0건. 사용자 컨테이너 종료·포트 종료 확인 | 이후 추가 다섯 시험은 인증 부분 시험으로 검증. PostgreSQL 전체 446개 재실행 결과는 없음 |
| 재인증·개발 PROFILE 삭제 | 서명된 최근 `auth_time`, 동일 소유자, state/nonce/S256, `amr`의 `pwd` 또는 `mfa`, 정확 영향·버전·별도 최종 승인. 미확인 강도 거부 | 실제 제공자 인증 수단과 최종 삭제, 운영 step-up 정책 |
| 인증 부분 회귀 | 인증·Web·영속 store·삭제 39개 통과, 현재 전체 시험 목록 446개 | commit/push 후 새 GitHub CI |
| BrowserOS | 합성 사실 1개 승인·영향 확인. 실제 callback에서 최근 인증·동일 계정 확인 후 요구한 인증 수단 미확인으로 409 거부. 자료 보존 | 기존 개발 Web client의 추가 인증 설정 검토, 실제 삭제 성공 미확인 |
| ChatGPT 품질 | 별도 새 임시 대화 2개에서 기존 36개와 새 8개 관측. 원문·기준·불일치 보존 | 분류 기준 합의·독립 의미 평가. 품질 gate 미통과 |
| 정적 검사·보존 | CI와 같은 Ruff check/format 통과(192개 파일), `git diff --check` 통과. 기존 설정·ignored 초안·이전 QA store 포함 45개 파일 hash 동일 | 운영/외부 시험은 별도 범위 |

## 삭제 구현과 실제 브라우저 관측

`--allow-development-profile-deletion`은 별도 영속 `--state-dir`가 필수인 선택 기능이다.
기본 실행에는 삭제 경로가 없다. 이번 Web PROFILE 경로만 실제 OIDC 재인증을 받으며,
MCP `execute_data_deletion`은 계속 `REVIEW_REQUIRED`다. Web cookie로 MCP 승인 증명을 발급하지 않는다.

영향 확인 → 재인증 → 별도 최종 확인 순서다. callback만으로 삭제하지 않는다.
다른 소유자/브라우저, 오래된·미래 인증 시각, 잘못된 수단, 변경된 버전·영향,
만료·재사용·로그아웃·폼 변조를 거부한다. 폼 읽기 이후 Web 세션도 재확인한다.
승인한 원문·Claim/Evidence를 삭제하고 DB 밖의 서명 checkpoint를 기록한다.
checkpoint 기록 시작 후 실패하면 Web/MCP를 503으로 닫고 재시작 검증을 요구한다.
삭제 후 재시작 보존과 DB만 과거로 복원한 경우의 격리도 자동 시험했다.
프로필 tombstone과 최소 삭제 metadata는 남으며 coverage는 `FOUNDATION_ONLY`다.
운영 backup/외부 사본/전체 디렉터리 rollback 보호까지 완료했다고 표시하지 않는다.

서버에서 서명된 `auth_time`을 검증한다. 최신 시각만으로 비밀번호 재입력이나 MFA를 인정하지 않는다.
소셜 연결은 upstream 기존 세션으로 교환될 수 있다. 현재 개발 정책은 서명된 `pwd`/`mfa`도 요구하며
운영 정책은 별도 확정해야 한다. [Auth0 재인증 문서](https://auth0.com/docs/authenticate/login/max-age-reauthentication)

실제 BrowserOS에서 두 문제를 수정했다.

1. 폼 제출 후 외부 인증 화면으로 이동하지 않았다. 코드의 `form-action 'self'`와 브라우저 동작으로 외부 POST redirect 차단을 추론했다. 콘솔 위반 이벤트는 캡처하지 않았다. 로컬 POST를 200으로 마치고 명시적 HTTPS 인증 링크로 이동하도록 수정했다. CSP를 유지했고 실제 외부 로그인 화면 도달을 확인했다. [MDN form-action](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/form-action)
2. 재인증 중 서버 재시작 후 남은 cookie가 일반 로그인 callback을 삭제 callback으로 보냈다. 일반 로그인 시작·로그아웃에서 cookie를 지우도록 수정했다. 정상 로그인 복구와 오래된 callback의 삭제 거부를 자동 시험했고 실제 일반 재로그인도 확인했다.

실제 재인증 전 counts: Claim 1, Evidence 1, profiling input 1, deletion request 0,
erasure ledger 0, 프로필 버전 1/ACTIVE. 이 상태는 삭제 완료 증거가 아니다.
이전 제품 왕복의 버전 2 QA store와 기존 합성 demo store는 변경하지 않았다.
[실제 관측 metadata](authenticated_deletion_observations_20261005.json)에 후속 상태를 기록한다.

재개 시 사용자 로그인 보고 후 관리 화면 로그인은 확인했다. 이전 삭제 요청은 만료되어
삭제용 최신 인증으로 재사용하지 않았다. 이어 BrowserOS 프로세스 종료로 MCP 연결이 끊겨,
기존 loopback 실행기를 다시 시작하고 9201/9100/9000의 loopback 수신과 MCP 복구를 확인했다.
정상 Web 로그인은 유지됐으며 새 탭에서 같은 합성 프로필의 삭제 검토를 다시 열었다.
인증 비밀을 복사하거나 외부 설정을 바꾸지 않았다. 실제 재인증·삭제 성공은 여전히 미확인이다.

다음 사용자 재인증 보고 후에도 관리 화면으로 돌아와 있었다. 비밀을 제외한 브라우저 탐색 기록에는
Auth0 로그인 → Google 계정 선택 → 일반 로그인 callback 실패 → 관리 화면이 남았다.
3분 요청 시작 후 사용자 응답까지 4분 이상이 경과했다. 삭제 cookie의 만료/부재로 정상 callback이
처리된 것으로 판단하며 이 시도에서 서명된 인증 시각·수단은 검증하지 못했다.
반복 만료를 줄이도록 **로그인 transaction/cookie 10분, 영향 검토 15분**으로 설정했다.
**인증 결과의 최근 시각과 최종 승인 수명은 3분**으로 유지하고, 최종 승인 만료를 인증 시각에 묶었다.
4분 걸린 로그인과 최신 인증 결과는 허용하되, 오래된 인증·10분 초과 요청·3분 초과 최종 승인은
거부하는 시험을 추가했다. 재개 후 인증 관련 39개가 통과했으며 전체 현재 목록은 446개다.

후속 10분 요청에서 사용자 직접 로그인 후 실제 `freshness=True owner=True method=False`를 확인했다.
최근 서명된 인증 시각·동일 계정은 확인했으며 요구한 비밀번호/MFA 수단을 확인하지 못해 409로 거부했다.
합성 자료 각 1개, 삭제 request/ledger 0건을 다시 확인했다. 현재 로그인의 반복을 요청하지 않는다.
원인에 맞춘 안내로 수정하고 삭제 시험 11개를 재검증했다. 외부 추가 인증 설정은 바꾸지 않았다.
[원인·수정·다음 설정 검토 범위](CareerGround_Phase_A_Deletion_Authentication_Review_2026-10-05.md)

## 품질 관측

| 집합 | 분류 일치 | 불일치 |
| --- | --- | --- |
| 추출 | 9/9 | 없음 |
| JD | 7/9 | jd-02 GAP → FOLLOW_UP, jd-07 REJECT → GAP |
| R2 | 8/9 | r2-07 REJECT → GAP |
| R3 | 9/9 | 없음 |
| 새 8개 | 5/8 | fresh-03 FACT_REVIEW → REJECT, fresh-05 GAP → REJECT, fresh-07 REJECT → EXCLUDE |

불일치 사례는 null 제안과 질문/거부 이유를 반환했다. 새 8개에 대한 수행자 검토에서
새 사실 생성, 삭제·다른 사용자 근거 사용, 승인/저장 완료 주장은 관측하지 않았다.
원래 기대값은 유지했고 불일치를 통과로 계산하지 않았다.

- [기존 36개 원문 응답·비교](chatgpt_quality_full_observations_20261004.json)
- [새 8개 원문 응답·비교·한계](chatgpt_quality_new_observations_20261004.json)
- [관측 전 작성한 새 사례 기준](../tests/fixtures/korean_generation_quality_holdouts_20261004.json)

현재 skill 1.0.2 계약을 새 임시 대화마다 제공하고 기대 분류는 숨겼다. 기존 사례는 알려진 회귀 사례이고,
새 사례도 수행자가 작성·검토해 독립 blind 평가가 아니다. effort는 Medium, API model ID는 알 수 없다.
제품 도구·canonical write·승인·모델 API 호출은 없었다. `PROPOSED_NOT_APPROVED`와 품질 gate 미통과를 유지했다.

## 연결 해제·갱신·운영 조건 검토

외부 gate 준비 검사 PASS는 2026-10-03 준비 묶음의 무결성 결과다. 이번 실제 관측을 반영하거나
release ready를 표시하는 검사는 아니다. 기존 문서/hash manifest를 바꿔 과거 준비를 새 실행 증거로 만들지 않았다.

| 조건 | 현재 증거 | 다음 범위 |
| --- | --- | --- |
| I01/I05 두 실제 계정 격리 | 합성 A/B 차단·실제 한 개발 계정 왕복 | 두 번째 개발 계정 범위 결정 후 Web/MCP 교차 읽기·쓰기·export·삭제 |
| I09 즉시 철회 | 이전 실제 Web logout 후 MCP는 별도 동작. 요청마다 ACTIVE 계정 확인 | 연결 단위 서버 철회 정책/식별자 설계·테스트 후 실제 연결 해제 전후 지연 관측 |
| I10 refresh/rotation | 새 제품 연결은 offline_access 미요청. 실제 refresh rotation·재사용·키 교체 미검증 | refresh 필요성 결정 후 필요한 client/API/토큰 설정 변경만 승인 |
| I11 삭제 인증 | 자동 시험과 실제 최근 인증·동일 계정 확인. 수단 미확인으로 실제 삭제 거부 | 개발 Web client의 추가 인증 정책 검토·승인 → 실제 MFA → 별도 최종 승인 |
| G-L ChatGPT 품질 | 기존 ChatGPT UI의 새 두 대화 관측, 모델 API 0 | 기대 분류·허용 동작 판정과 독립 의미 평가. 서버 유료 AI 보류 유지 가능 |
| G-P/G-C 보관·운영 | 로컬 삭제/checkpoint/복원 준비·회귀 | 보관 기간·삭제 SLA·처리 조건, 독립 anchor/backup/운영 자원·비용 승인 후 실행 |

이전 PoC와 새 제품 연결은 같은 CIMD client/기존 사용자 grant를 사용한다. Auth0 grant 철회는 두 연결에
영향을 줄 수 있다. 제품 scope 추가 승인은 grant 철회·MFA 강제·refresh/수명 설정 변경까지 포함하지 않는다.
구체 영향·복구 절차를 준비한 뒤 한 단계씩 승인한다. 브라우저/PC 인증 토큰 추출·복사로 시험을 우회하지 않는다.

### 권장 재개 순서

1. 기존 개발 Web client의 삭제용 추가 인증 설정을 검토하고 필요한 외부 변경만 승인받는다. 같은 로그인 재시도는 필요하지 않다.
2. 불일치 6개를 검토하고 기대 동작 기준을 확정한 뒤 별도 새 사례로 독립 의미 평가한다. 기존 관측은 유지한다.
3. 두 실제 계정·연결 철회/갱신 시험 범위를 구체화하고 필요한 계정/외부 변경만 승인받는다. 로컬 철회 설계·시험은 독립 진행 가능하다.
4. 개인 비공개 개발 사용과 공개 운영 서비스의 완료 범위를 결정한다. 운영 완료를 목표로 할 때 보관·삭제·복원·비용을 확정한다. 서버 AI는 계속 보류한다.

## 재실행과 정리

이번 삭제 store는 기존 store와 다른 owner-only 경로다. 재개 명령:

```bash
uv run --locked --env-file .env --env-file .env.poc \
  python -m careerground.auth0_development_runtime \
  --allow-development-login --allow-development-profile-deletion \
  --state-dir "$(cat /tmp/careerground-fresh-auth-qa-path)/state" \
  --mcp-port 8001
```

`http://localhost:5000/auth/login`에서 정상 로그인 후 삭제 검토를 새로 시작한다.
재인증 요청·최종 승인은 메모리 상태이므로 서버 재시작/만료 후 재사용할 수 없다.
`/tmp` 자료는 재부팅·임시 정리로 없어질 수 있으며 운영 백업이 아니다.
실제 로그인·MFA는 사용자가 직접 수행한다. 새 터널은 실행하지 않았다.
사용자 재인증 후 인증 수단 미확인 거부를 확인해 로컬 runtime을 종료했다.
5000/8001/55432 포트 닫힘을 확인했고 새로운 합성 QA store는 보존했다. BrowserOS 사용자 앱은 유지했다.

PostgreSQL 컨테이너는 --rm 종료했다. 기존 설정·무시된 초안·이전 QA 자료를 보존했다.
새 유료 자원·서버 AI·운영 연결·실제 경력 자료 사용, commit/push/merge는 없었다.
# 후속 상태

이 문서는 이전 실행 기록이다. 이후 1~5번 자율 구현·읽기 전용 Auth0/ChatGPT 관측과
최신 PostgreSQL 453개 검증은 [최종 수용 진행 결과](CareerGround_Phase_A_Final_Acceptance_2026-10-05.md)를 따른다.
실제 외부 gate와 Phase A 전체 완료는 아직 미선언이다.

# 실제 삭제 재인증 거부 원인 검토

## 실제 결과

2026-10-05 사용자가 새 10분 요청에서 직접 로그인한 뒤 BrowserOS와 개발 서버를 확인했다.
BrowserOS의 삭제 callback 화면은 **HTTP 409**였으며 서버의 비밀 없는 검사 기록은 다음과 같다.

| 검사 | 실제 결과 |
| --- | --- |
| 서명된 최근 인증 시각 확인 | `freshness=True` |
| 현재 Web 세션·동일 소유 계정 확인 | `owner=True` |
| 삭제 정책이 요구하는 비밀번호/MFA 인증 수단 확인 | `method=False` |

확인된 원인은 **삭제에 요구한 인증 수단을 이번 서명된 응답에서 확인하지 못한 것**이다.
로그인 연결 자체와 계정 매핑은 확인됐다. 인증 응답 원문/토큰/사용자 식별자/인증 수단 목록은 추출하거나 기록하지 않았다.
`method=False`는 서명된 `amr`에 요구한 `pwd` 또는 `mfa`를 확인하지 못했다는 뜻이다.
`amr` 전체가 누락됐는지 다른 값이 있었는지는 이 bool 기록만으로 구분하지 않는다.

삭제는 실행하지 않았다. 읽기 전용 집계에서 Claim 1, Evidence 1, profiling input 1,
프로필 버전 1/ACTIVE가 유지됐고 deletion request와 erasure ledger는 각각 0건이다.
기존 설정·ignored 초안·이전 QA store를 포함한 45개 파일 hash도 동일하다.

## 왜 같은 로그인을 반복하는 것으로 해결하지 않는가

Auth0의 소셜 로그인은 기존 upstream 세션으로 교환될 수 있으며, 최근 `auth_time`으로
upstream 비밀번호 재입력이나 MFA를 입증하지 않는다.
[Auth0 재인증의 제한](https://auth0.com/docs/authenticate/login/max-age-reauthentication)

Auth0의 Web step-up 절차는 서명된 ID token에서 `amr`의 `mfa`를 검증하고,
필요할 때 등록된 MFA를 요청하는 Action과 앱 요청을 연결한다. 일반 비밀번호/소셜 로그인만으로
필요한 `amr`가 항상 반환된다고 가정하지 않는다.
[Auth0 Web 앱 step-up 문서](https://auth0.com/docs/secure/multi-factor-authentication/step-up-authentication/configure-step-up-authentication-for-web-apps)

현재 CareerGround 요청은 `max_age=0`과 `prompt=login`을 사용하지만 별도 MFA 요청·Action을
구성하지 않았다. 따라서 삭제 재인증의 강도 요구와 제공자에서 수행하는 인증 단계가 맞지 않는다.
이 부분을 준비하기 전에 사용자에게 같은 로그인만 반복 요청한 안내가 부족했다.

## 이번 수정·검증

- 최근 인증과 동일 계정이 확인됐지만 인증 수단이 미확인인 경우, 원인을 설명하는 별도 안내를 반환한다.
- 기존의 ‘새 검토를 시작하세요’ 대신 추가 인증 설정을 확인하고 현재 로그인을 반복할 필요가 없다고 안내한다.
- 관리 화면으로 돌아가는 링크를 제공한다. 다른 실패에서 인증 시각/동일 계정이 검증됐다고 표시하지 않는다.
- 삭제 차단 조건은 유지하며 `amr` 값을 임의로 만들거나 현재 로그인을 강한 인증으로 승격하지 않는다.
- 삭제 관련 시험 **11개 PASS**. 누락/빈/소셜/OTP만 있는 방법에서 안내와 0건 삭제를 검증한다.
  잘못된 인증 수단 타입은 최신 인증 성공 문구를 표시하지 않는다. Ruff check/format과 diff 검사도 통과했다.

이전 전체 PostgreSQL 441개와 인증 부분 39개는 이전 실행 결과다. 이번 문구 수정 뒤에는
관련 삭제 11개만 재검증했고 현재 전체 시험 목록은 446개다.

## 다음 단계의 검토 범위

권장안은 **기존 CareerGround Web 개발 client의 삭제용 인증 요청에 한정한 MFA**다.
공개 운영 정책 확정이나 실제 외부 설정 변경은 별도 단계다.

1. 기존 tenant에서 사용할 MFA factor와 현재 요금제의 이용 가능 여부·과금 조건을 읽기 전용으로 확인한다.
   현재 무료라고 단정하거나 유료 플랜/체험/업그레이드를 시작하지 않는다.
2. 앱의 삭제 요청에만 표준 MFA `acr_values`를 넣고, 기존 Web client ID와 해당 값에만 반응하는
   Post Login Action을 준비한다. 일반 로그인·ChatGPT CIMD client의 권한과 로그인 정책을 바꾸지 않는다.
3. Action은 실제 factor challenge를 요청하고 remembered-browser 우회를 허용하지 않는 범위로 검토한다.
   서명된 `mfa`를 하드코딩하거나 Google 계정의 MFA 사용 여부를 추정하지 않는다.
4. 기존 MFA policy/factor 설정·다른 앱과의 영향·복구 방법·비용이 확인된 변경안으로 승인받는다.
   Action 배포/flow 연결, factor 활성화, 사용자 MFA 등록은 지금까지의 제품 scope 승인에 포함되지 않는다.
5. 승인 후 사용자가 직접 MFA를 등록/완료한다. 서버의 서명·최신 시각·동일 계정·MFA를 확인하고,
   합성 프로필에 대해 별도 최종 승인·삭제·재시작·보존 검사까지 진행한다.

비밀번호 연결의 다른 사용자로 로그인해 기존 소유권을 대체하지 않는다. 계정 연결/등록 변경도 별도 범위다.
추가 인증 설정이 완료될 때까지 실제 삭제 성공은 미검증이며 Phase A I11은 열려 있다.
현재 사용자는 같은 로그인 재시도를 할 필요가 없다.

이번 검토에서는 Auth0 policy/Action/factor, 계정 권한·유료 자원·서버 AI를 변경하지 않았고 commit/push도 하지 않았다.

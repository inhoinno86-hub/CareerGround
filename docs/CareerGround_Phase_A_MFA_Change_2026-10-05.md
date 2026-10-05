# 삭제용 MFA 변경안 — 적용 전

## 현재 결정 — OTP MFA 보류

2026-10-05 사용자가 Phase A의 OTP MFA를 보류했다. 아래 trial 시험/원복안은 과거 제안이며 현재 승인 요청이 아니다. Auth0 factor/Action/policy 변경은 수행하지 않는다. 로컬 MFA 선택 옵션은 비활성 상태로 보존한다.

삭제 전 검증 가능한 추가 인증은 미해결이다. 무료 대안의 현재 계정 호환성·증명 검증을 검토해야 하며, OTP 보류만으로 기존 삭제 검증을 제거하거나 삭제 수용 완료로 표시하지 않는다.

상태: 로컬 구현·합성 검증, 관리자 로그인 후 읽기 전용 확인 완료. 외부 설정 미변경.

## 현재 원인과 비용 확인

실제 최신 삭제 로그인에서 `freshness=True`, `owner=True`, `method=False`였다.
같은 Google 로그인 반복으로 삭제 인증 성공을 보장하지 않는다.
서명된 ID token의 `amr`에 `mfa`가 있는지를 검증한다.
[Auth0 공식 step-up 절차](https://auth0.com/docs/secure/multi-factor-authentication/step-up-authentication/configure-step-up-authentication-for-web-apps)

공식 가격표의 Pro MFA Factors는 Free에 포함되지 않고 Essentials 이상에 포함된다.
실제 Subscription 화면은 **Free / $0**이고 개발 테넌트 banner에는 **trial 11일 남음**이 표시됐다.
MFA 화면의 OTP/Recovery checkbox는 꺼져 있고 policy는 **Never**, 다른 factor도 Disabled다.
OTP는 **PRO MFA**로 표시되며 현재 trial에서 설정 가능한 UI다. 정확한 만료 시각과
종료 뒤 factor 처리 방식은 아직 확인하지 않았다. trial 수용 시험을 지속 무료 운영으로 간주하지 않는다.
UI 버튼이 활성화돼 있어도 지속 무료 이용을 뜻하지 않는다. 업그레이드·trial 시작·결제는 승인하지 않았다.
[Auth0 공식 가격표](https://auth0.com/pricing)

## 읽기 전용 확인

1. 기존 개발 테넌트의 요금제, trial 여부/만료, MFA 이용 entitlement 확인.
2. Security → Multi-factor Auth에서 기존 factor와 policy 확인. Save/Enable/Trial/Upgrade를 누르지 않는다.
3. 기존 개발 Web client와 Post Login flow/Action 연결을 확인한다. secret/개인 식별자는 보고서에 담지 않는다.
4. OTP 이용에 추가 과금 또는 유료 전환이 필요하면 중지하고 그 사실과 선택지를 사용자에게 요청한다.

## 승인받을 구체 범위

포함 권한·비용이 확인될 때만 다음 변경을 별도 요청한다.

- 필요한 경우 OTP factor 하나를 활성화한다. SMS/voice/email 등 별도 전송 자원은 사용하지 않는다.
- 기존 개발 Web client 한 개와 명시적 MFA `acr_values` 요청에만 반응하는 Post Login Action 하나를 배포·연결한다.
- 기존 global policy를 `Always`로 바꾸지 않는다. 다른 앱/ChatGPT MCP client에는 강제하지 않는다.
- 기존 Action의 변경 전 버전/flow 위치/factor/policy를 기록해 복구할 수 있게 한다.
- trial에 한정한 시험을 승인받으면 시험 뒤 추가한 Action을 flow에서 제거하고 OTP를 이전 상태로 돌린다.
  기존 Action/factor/policy를 지우지 않는다. 결제·업그레이드·trial 연장은 수행하지 않는다.
- 사용자 직접 OTP 등록·MFA 입력 후 동일 합성 PROFILE의 영향 검토 → 새 인증 → 별도 최종 승인을 시험한다.
- provider 계정 삭제, 전체 CareerGround 계정 삭제, 과금/공개 배포는 포함하지 않는다.

배포 전 검토할 Action 예시이며 client ID는 실제 배포 설정에서만 대입한다.

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const allowedClient = 'REPLACE_WITH_EXISTING_DEVELOPMENT_WEB_CLIENT';
  const context = 'http://schemas.openid.net/pape/policies/2007/06/multi-factor';
  if (event.client?.client_id !== allowedClient) return;
  const requested = event.transaction?.acr_values;
  if (!Array.isArray(requested) || !requested.includes(context)) return;
  api.multifactor.enable('any', { allowRememberBrowser: false });
};
```

`amr`를 직접 만들어 넣는 Action은 허용하지 않는다. 설정 전 ordinary login 성공을 MFA로 간주하지 않는다.

## 로컬 구현과 실행 조건

`--require-development-deletion-mfa`는 명시적 persistent PROFILE 삭제 옵션과 함께만 사용한다.
삭제 요청에만 `acr_values`를 붙이고 signed `mfa`만 수용한다. 일반 로그인은 그대로 identity-only다.
기존 검증용 password-or-MFA 모드가 있으므로 실제 MFA 수용 시험은 이 새 옵션을 명시해야 한다.
프로바이더 설정이 없으면 이 요청만으로 MFA를 강제할 수 없으며 결과는 거부된다.

MFA 로그인 완료만으로 삭제하지 않는다. 최근 인증 3분·동일 소유자·정확한 영향/버전·최종 확인을 다시 검증한다.
현재 MCP 삭제 adapter는 활성화하지 않았으며 `REVIEW_REQUIRED`다.

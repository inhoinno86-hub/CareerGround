# 4-1 인증 시험 준비 — G-I

상태: **시험 절차 준비, 공급자 최종 선정·외부 시험 미완료**. 기준 HEAD `2a6cdd2`.
이번 작업은 기존 파일과 로컬 합성 검사, 공개 공식 문서만 사용한다. tenant 설정·계정 생성·로그인·터널·유료 자원을 연결하지 않는다.

## 기존 증거와 다음 시험

2026-09-26 기록에는 개발 Auth0 tenant의 CIMD/Resource Parameter Compatibility Profile, 실제 사용자 계정 한 개의 로그인·인가 코드 교환·합성 MCP 호출이 있다. 이는 과거 실행 기록이며 이번 재실행 결과가 아니다. 개별 S256 요청, 실제 두 계정의 격리, 이미 발급한 토큰의 철회·만료 지연, 실제 step-up, 비용·처리 조건은 아직 미실시다. [기존 기록](CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md)

로컬 코드에는 metadata 표시값 검사, JWT issuer/audience/scope/time 검증, 매 요청 ACTIVE 계정 확인, Web 검증 세션의 계정 매핑, 합성 연결 철회가 있다. 현재 PoC 서버를 제품 데이터 서버로 그대로 배포하지 않는다.

RFC 9700은 PKCE와 정확한 redirect 검증, audience 제한을 다룬다. 이 시험은 S256을 요구하고 plain 또는 verifier 누락에 대한 서버 거부를 실측한다. metadata에 S256이 표시되는 것만으로 통과하지 않는다. [RFC 9700 §2.1, §4.5, §4.8](https://www.rfc-editor.org/rfc/rfc9700.html)

## 실행 순서와 통과 기준

| ID | 시험 절차 | 통과 조건·보존 증거 |
| --- | --- | --- |
| I01 | 격리 개발 tenant, 합성 계정 A/B, 정확한 MCP resource/redirect/등록 방식 선택 | 운영 tenant와 분리, 비용·처리 조건과 시험 허용 범위 승인. 실제 callback 값을 관리 화면에서 확인; 예시를 하드코딩하지 않음 |
| I02 | metadata preflight → 정상 S256 authorization-code 요청 → token 교환 | 실제 S256 사용, redirect와 issuer/resource 일치. 잘못된 verifier·plain·누락·인가 코드 재사용 각각 실패. verifier/code/token 원문 대신 각 검사의 bool·시각·상태 코드 기록 |
| I03 | `state`·OIDC `nonce`·redirect·issuer를 각각 바꾼 별도 요청 | 로그인/세션 생성 전 실패; 불일치가 다른 계정 연결로 이어지지 않음 |
| I04 | Web와 MCP에서 같은 issuer/subject의 A 로그인, 이메일 표시만 변경 | 같은 account mapping 유지. 이메일을 소유권 키로 쓰지 않음 |
| I05 | B 로그인 후 A profile/artifact/export/delete/status ID 요청; A→B도 반복 | 읽기·쓰기·리소스·삭제 증명 모두 거부, 대상 본문/존재 여부 누출 없음. 같은 subject/다른 issuer 합성 검사도 유지 |
| I06 | 잘못된 서명·kid·issuer·audience, scope 누락, expired/not-yet-valid 토큰 | 보호 도구 호출 모두 거부; JWT 정상만 확인하고 scope를 생략하는 경로 없음 |
| I07 | A 연결1에서 승인 → A 연결2·B·새 browser session에 같은 receipt 전달 | 다른 연결/세션 실패. 원래 연결의 유효한 정확 재시도만 허용 |
| I08 | 동일 bearer로 성공 → account DISABLED/삭제 확정 → 재호출 | 다음 보호 요청부터 401. DB 조회 실패도 실패로 처리. 브라우저 삭제 상태 capability의 제한 경로만 별도로 확인 |
| I09 | logout/연결 해제/refresh revoke 각각 실행 후 기존 access·refresh token 재사용 | 각 토큰의 차단 범위·실제 지연을 초 단위 기록. UI 연결 해제만으로 JWT 즉시 철회됐다고 판단하지 않음. 즉시 차단이 안 되면 별도 서버 철회 저장소 설계 필요 |
| I10 | access token 만료 경계와 refresh rotation·재사용·키 교체 | 만료 토큰 실패, 이전 refresh 재사용 실패, 새 키/이전 키의 검증 기간과 강제 폐기 동작 기록 |
| I11 | 실제 step-up 후 정확한 삭제 scope/target/version/impact 승인; 취소·만료·다른 계정·변경 영향 재시도 | 검증된 issuer/sub, 요구한 인증 강도, 최근 인증 시각과 정확 대상/세션/일회성 증명 확인. 원래 로그인 시각이나 UI 체크만으로 통과하지 않음 |
| I12 | 시험 종료·연결/임시 클라이언트·키·터널 정리 및 비용 확인 | 제품 데이터 0건, 새 호출 차단, 비공개 증거만 남김; 취소/실패 요청이 canonical 데이터를 변경하지 않음 |

I11에서 사용할 인증 강도(`acr`/`amr`), 최대 인증 경과 시간과 claim을 어느 검증된 응답에서 받을지는 공급자별로 확정한다. **`iat`만으로 실제 재인증을 인정하지 않는다.** 강도를 증명하지 못하면 삭제를 거부한다. 현재 MOCK_ONLY 확인 문구는 실제 step-up의 증거가 아니다.

## 증거 형식

증거 한 건은 `{case_id, observed_at_utc, environment_alias, result, http_status, checks, latency_ms, reviewer}`의 허용 metadata만 저장한다. `checks`는 미리 정한 bool 목록이다. 계정 별칭은 A/B이며 subject/email/IP/tenant 비밀은 보고서에 넣지 않는다. bearer·refresh token·인가 코드·PKCE verifier·cookie·비밀번호·전체 HAR은 저장하지 않는다. 필요한 요청 비교는 메모리에서 수행하고 성공/실패만 남긴다.

실제 계정 로그인·MFA/동의는 사용자가 직접 수행한다. 자동 UI 시험이 필요하면 BrowserOS의 검증된 loopback 연결과 사용자가 지정한 시험 창만 사용한다. 시험 자격 증명을 개인 기본 프로필로 복사하지 않는다. 공개 MCP endpoint와 공개 터널을 만들기 전에 별도 승인한다.

## 첫 승인 요청으로 준비할 내용

한 번에 **기존 Auth0 개발 tenant의 합성 인증 재시험**만 제시한다. 검토 내용은 tenant 격리 확인, A/B 시험 계정 종류, 허용 client/resource/redirect, 등록·권한 변경 범위, 기간, 추가 비용 상한(현재 승인값 0), 삭제할 임시 자원 목록이다. 실사용자 경력 자료는 제외한다. 구체 tenant/두 계정과 외부 시험 승인이 정해지기 전에는 I01 이후를 실행하지 않는다.

공급자 선정은 I01–I12의 필수 결과와 운영 요금·리전·보관·하위 처리자·삭제 조건을 함께 검토한 뒤 별도 결정한다. 과거 PoC와 이번 합성 검사만으로 G-I를 통과로 표시하지 않는다.

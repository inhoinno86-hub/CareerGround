# 보관·삭제·복원·운영 범위 점검

상태: 로컬 보강·시험, 공개 운영 정책/자원 승인 및 운영 증거 미완료.

2026-10-05 사용자 결정으로 OTP MFA는 보류한다. 삭제 재인증 대안은 미결정이며, 이 보류로 삭제 검증 또는 기존 완료 기준을 완화하지 않는다.

## 현재 적용할 수 있는 로컬 조건

| 자료/동작 | 현재 구현/보강 | 한계 |
| --- | --- | --- |
| 임시 profiling 입력·초안 | 마지막 실제 활동으로부터 90일, 30분 자동 pause는 연장하지 않음. 만료 조회 차단과 bounded physical expiry 구현 | 계속 켜진 scheduler가 없으면 물리 정리는 자동 수행되지 않음 |
| 인증 개발 store의 expiry | 새 `--allow-development-retention` 선택 옵션. 시작 후/60초마다 hourly outbox slot의 작업 확인, sweep 최대 100세션 | 한 process 로컬 시험 전용. 실패 retry와 다음 slot은 기존 outbox 정책. backlog/지연 SLA 실측 없음 |
| 승인 Claim/Evidence | 임시 workspace 만료와 구분해 보존 | canonical 보관 목적/기간의 공개 정책 미확정 |
| PROFILE 삭제 | 영향→fresh signed proof→별도 최종 확인→local erase/checkpoint. MFA 선택 모드는 signed mfa 필수 | 실제 MFA 성공 미관측; SESSION/EVIDENCE/PROJECT/ACCOUNT의 실제 인증 경로·MCP 삭제 미연결 |
| DB만 과거로 복원 | 최신 외부 checkpoint와 비교 후 격리/거부 | 디렉터리 전체/키 동시 rollback은 로컬 서명으로 탐지할 수 없음 |
| 연결 철회 | 별도 private registry backend·JWT 검증 이후 connection gate 준비 | 실제 runtime 미활성. provider grant/refresh 폐기와 실제 2계정 관측 미완료 |
| 보관 파일 | owner-only store/keys/SQLite, 별도 QA 경로 | 운영 at-rest encryption/key rotation/독립 anchor가 아님 |

새 retention 옵션은 persistent authenticated development store가 필수다.
일반 실행에서 기존 QA store를 자동 정리하지 않는다. 이번 시험은 새 temporary store의
만료 fixture에만 적용했다. 이전 승인 사실/근거는 유지되고 임시 입력/session은 실제로
없어졌으며 재시작 뒤에도 같은 결과였다. 기존 실제 QA store와 45개 보존 파일은 변경하지 않는다.

`FOUNDATION_ONLY`는 local coverage를 뜻한다. 로컬 원문이 없어져도 모든 backup/provider
사본이 삭제됐다고 표시하지 않는다. runtime을 닫으면 worker도 종료되며 장기 cron/service를
사용자 PC에 설치하지 않았다.

## 공개 정책·운영에 남은 결정

- canonical 자료의 보관 목적/기간, diagnostic log/backup TTL, 삭제 처리 기한과 backup 완전 만료 시점.
- ChatGPT 대화 및 사용자가 다운로드한 사본은 CareerGround PROFILE 삭제로 함께 지워지지 않음.
- 별도 서버 AI 보류 유지. 실제 경력자료를 처리할 때 auth/hosting/ChatGPT 처리 범위와 사용자 고지를 확인.
- 독립 deletion/revocation anchor, 전체 사본 inventory, private PostgreSQL/backup과 restore quarantine.
- HTTPS와 배포 범위, IAM/암호화/회전, 장애·worker backlog 경보, 담당자, 실측 RPO/RTO.
- OTP MFA는 현재 Free 플랜에서 지속 제공되지 않음. trial 증거가 이후 무료 운영 가능성을 보장하지 않음.
- 운영 자원 명세·비용 상한·정리/잔존 backup 비용 승인 전 자원 생성/배포하지 않음.

## 완료 범위 선택 자료

| 선택 | 가능한 완료 주장 | 추가로 필요한 것 |
| --- | --- | --- |
| 개인 비공개 개발 MVP | 합성 자료로 ChatGPT+Web의 구현/로컬 수용 | 실제 auth·2계정·삭제/철회, 기준 확정·독립 의미 검토, 최신 회귀/CI |
| 실제 개인 경력 사용 | 개인용 비공개 서비스 수용 | 위 항목과 지속 가능한 삭제 인증, 실제 자료 처리/보관 조건·백업 복원 확인 |
| 공개 서비스 배포 | 공개 운영 Phase A 출시 | 모든 항목과 운영 환경·사본 삭제·복원·관측·정책/비용 수용 |

현재 비용·서버 AI 보류 의도에는 첫 번째 범위가 가장 가깝다. **완료 범위를 자동 변경하지 않았다.**
기존 main plan의 formal Gate A와 운영 gate를 축소했다고 표시하지 않으며, 사용자가 범위를
결정하면 개인 개발 수용과 공개 출시 판단을 별도 상태로 확정한다.

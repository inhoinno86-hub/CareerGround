# 기존 구독 기반 개인 서버 — 검토안

2026-10-16. 구축 전 검토 문서이며 서버 생성·배포·결제·인증 이전을 승인하거나 실행한 기록이 아니다.
검토 기준: PACE 반영 완료 `fa44e4b6f3159817a900e42cfd0fc81dbba56ecd`.

## 사용자 조건

- 별도 종량제 AI API key·API 과금을 도입하지 않는다.
- 본인은 기존 구독 계정으로 사용하며 향후 사용자마다 각자의 구독을 연결하는 구조를 고려한다.
- PC와 USB 없이 휴대폰 인터넷으로 사용한다. 완전 오프라인 AI 실행을 의미하지 않는다.
- 이전 앱 계획의 배포 AI를 유료 API로 전환하는 방향보다 이번 사용자 지시를 우선한다.
- 구독 연결 실패·사용량 소진 시 유료 API나 유료 크레딧 구매로 자동 전환하지 않는다.
- 현재 개인 호출 원장16/18은 검토 중 변경하지 않는다. 실제 서버 수용 시험의 호출 범위는 별도로 확정한다.

## 결론과 미검증 사항

개인 서버로의 기술적 이전 가능성은 높다. 이미 Linux에서 FastAPI, 고정 작업 전용 Codex CLI,
파일 검사와 기기 내 음성이 동작한다. 모델은 원격 제공자에서 실행하므로 서버 GPU는 필요하지 않다.
다만 실제 클라우드 서버에서 Codex 로그인·토큰 갱신·bubblewrap·메모리·지연은 아직 검증하지 않았다.
CLI의 원격 로그인 지원이 임의의 공용/상용 앱에 대한 제공 승인을 의미하지는 않는다.

공식 Sign in with ChatGPT 문서는 OSS/로컬 실행 범위를 설명하고 유료·원격 호스팅 앱에는
별도 접근 신청을 안내한다. 따라서 개인 VM 시험과 여러 사용자를 대상으로 하는 공용 서비스는
분리한다. 현재 앱이 그 공용 기능을 승인받았다고 주장하거나 구독 이용 가능성을 확약하지 않는다.

## 개인 서버 후보 구조

휴대폰 → 본인 전용 사설 HTTPS 접속 → Linux VM의 면접 runtime → 본인 구독 Codex.

- VM 후보: AWS Lightsail, 서울 리전, x86_64 Linux, 2vCPU/2GB/60GB.
- 서버 생성 화면에서 아키텍처·리전·현재 가격을 다시 대조한다. 2GB는 실측 최소 사양이 아닌 시작 후보다.
- 별도 GPU·관리형 DB·로드밸런서는 첫 개인 시험판에 포함하지 않는다.
- runtime은 VM loopback에 유지하고 Tailscale Serve를 통해 사설 HTTPS로 연결한다.
- 휴대폰에 Tailscale 앱을 설치하고 서버 접근을 본인 기기로 제한한다. 공개 Funnel이나 공개 Codex 실행 포트는 사용하지 않는다.
- Tailscale 무료 Personal은 개인 비상업 조건 충족 여부를 확인한다. 제품/업무 용도라면 무료를 전제하지 않는다.
- 기존 Auth0 로그인과 서버의 사용자 검사를 유지하고 초기에는 본인만 허용한다.
- 기존 개인 PC의 인증 파일을 자동 복사하지 않는다. 서버에서 사용자가 공식 로그인 절차를 수행한다.
- 서버 전용 OS 계정·인증 저장소와 고정 작업 격리를 사용하며 로그인 갱신 경로를 따로 검증한다.
- 현재 read-only 인증 mount에서는 갱신 결과를 저장할 수 없으므로 장기 로그인 갱신 또는 재로그인 설계가 필요하다.
- 인터뷰 원문·답변의 자동 영속 저장은 추가하지 않는다. 기존 수동 저장·가져오기 정책과 서버 RAM 만료를 유지한다.
- 서버 재시작은 RAM 세션을 지우므로 명시적 수동 저장·복구와 앱 내 안내를 검증한다.
- 앱의 USB 전용 주소·DEBUG 전용 연결/로그인 제한을 온라인 시험용 구성으로 분리한다.

## 향후 사용자별 구독 연결을 위한 설계

- 면접 엔진과 AI 실행기를 분리하고 인증된 앱 사용자에 연결된 실행기를 선택한다.
- 앱 로그인과 AI 구독 연결은 별도 관계다. 서버가 검증한 사용자와 명시적으로 연결한 AI 계정/workspace를 대응시킨다.
- 계정별 인증 저장소·프로세스·갱신·대기열·사용량·연결 해제를 분리한다. 공통 전역 인증 파일은 사용하지 않는다.
- 다른 계정의 자격 증명이나 구독으로 자동 대체하지 않는다. 연결 누락·만료·소진은 해당 사용자에게 반환한다.
- 공식 구독 연결 경로와 기존 CLI 경로는 같은 구현으로 취급하지 않는다. Android 로그인과 해당 계정의 기능 가용성도 확인한다.
- 공용 서비스에 공식 구독 연결을 제공하기 전 접근 조건·필요 승인과 계정별 격리/취소를 실제 검증한다.
- 지원 조건을 충족하지 못하면 공용 연결 제공을 보류하며 유료 API로 자동 전환하지 않는다.

## 비용안

2026-10-16 조회 공식 공개 가격이며 세금·결제 환율·기존 구독료는 제외한다.
무료 체험 크레딧이나 프로모션을 전제하지 않는다.

| 항목 | 월 기준 | 비고 |
| --- | --- | --- |
| Lightsail Linux/public IPv4 2GB | US$12 | 2vCPU·60GB, 시작 후보 |
| Lightsail Linux/public IPv4 4GB | US$24 | 2vCPU·80GB, 측정 후 필요 시 선택 |
| Tailscale Personal | US$0 | 개인 비상업 자격 충족 시 |
| Tailscale Standard | US$8/사용자 | 사업/업무 용도에 적용할 경우 |
| 별도 도메인 구매 | 초기 불필요 | Tailscale HTTPS 이름 사용 가정 |
| 스냅샷 | US$0.05/GB-month | 선택 사항, 예: 과금 대상20GB 보관 시 US$1 |
| 추가 종량제 AI API | 도입하지 않음 | 기존 구독의 가용량 범위, 추가 구매 자동 전환 없음 |

서버+무료 개인 VPN 조건이면 US$12~24/월, Standard 1인 조건이면 US$20~32/월이다.
백업·포함량 초과 트래픽·추가 저장소·기존 인증 플랜 변경은 별도다.
원화 예시는 환산 가정 US$1=1,500원에서 각각18,000~36,000원 또는30,000~48,000원이며
실제 환율이나 최종 청구액을 뜻하지 않는다. 초기 1인 서버의 견적이며 다중 사용자 비용으로 일반화하지 않는다.
Lightsail은 중지 상태에서도 과금된다. 사용 종료 시 삭제·잔여 snapshot/IP 등 정리는 별도 확인한다.

## 구축 순서와 완료 기준

1. 별도 개발 worktree에서 원격 설정·계정별 실행기 경계·설치/운영 스크립트와 합성 검사를 준비한다.
2. 개인/업무 네트워크 플랜 자격과 서버 사양을 정하고 정확한 청구 범위를 제시한다.
3. 사용자가 계정·결제 설정을 완료하고 서버 생성/배포 비용을 승인하면 VM을 생성한다.
4. 사설 HTTPS, 전용 OS 계정, runtime, Codex 격리·자동 시작·상태 점검을 설치한다.
5. 사용자가 서버의 Codex 구독 로그인과 휴대폰 사설망 로그인을 완료한다.
6. 실제 호출 한도를 확정한 뒤 질문1회·음성 확인 답변·평가1회·파일 저장/복구를 검증한다.
7. PC 전원/USB 없이 모바일 데이터로 사용, 로그인 만료·구독 한도·서버 재시작·다른 사용자 접근 거부를 확인한다.

비용이 생기는 서버 생성·외부 배포·로그인 자격 증명 이전은 이 검토에서 실행하지 않았다.

## 확인한 공식 자료

- [Codex 인증·원격 로그인](https://learn.chatgpt.com/docs/auth)
- [ChatGPT 구독 연결 적용 범위](https://developers.openai.com/siwc/token-sharing-open-source)
- [OSS 도구의 self-hosted VM 연결](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)
- [Lightsail 서버 가격](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)
- [Lightsail 서울 리전](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html)
- [Lightsail 스냅샷 가격](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-snapshots.html)
- [Lightsail 과금과 중지](https://docs.aws.amazon.com/en_en/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html)
- [Tailscale 요금·무료 자격](https://tailscale.com/pricing)
- [Tailscale 사설 HTTPS](https://tailscale.com/docs/reference/examples/serve)

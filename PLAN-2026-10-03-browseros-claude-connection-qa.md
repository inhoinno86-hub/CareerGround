# BrowserOS·현재 Claude Code 계정 연결과 합성 UI 시험

사용자가 현재 Claude Code 계정으로 BrowserOS 연결 셋업 → BrowserOS 실행/MCP 확인 → 직접 시험/결과 보고를 승인했다. CareerGround 제품은 계속 MOCK_ONLY이며 실제 사용자 데이터·운영 서비스·새 유료 자원·제품 AI 공급자를 연결하지 않는다. BrowserOS 자동화 클라이언트는 현재 구독 인증을 지원하는 공식 경로를 사용하고 인증 비밀을 다른 공급자/API 키로 복사하지 않는다. 기존 작업 트리·ignored 초안·개발 저장소를 보존하며 커밋/푸시하지 않는다.

## 실행 순서

- [x] 설치 버전/Claude 인증 상태/공식 연결 방식 확인, 최소 MCP 설정 및 백업
- [x] 별도 BrowserOS 프로필과 합성 앱 저장소 실행, 실제 BrowserOS MCP 도구 연결 확인
- [x] MCP를 통해 계정 분리/JD 후보/저장·restart/logout/별도 승인 삭제/상태/B 보존 직접 시험
- [x] R2/R3·token/restore 보조 자동 검증, aggregate·화면 결과 기록
- [x] 시험 앱/브라우저/키·임시 상태 정리, 사용자 BrowserOS 연결/실행 유지 및 사용 방법 보고

Claude Code는 현재 claude.ai/firstParty/Pro 로그인 상태다(계정 식별자/비밀은 기록하지 않음). BrowserOS 설치 148.0.7966.97. 루트가 설정/통합/시험을 담당하며 기존 작업자 한 명은 공식 지원 경로를 읽기 전용으로 조사한다. BrowserOS 제공자 내 Claude subscription과 Claude Code MCP 클라이언트 연결을 구분하고 지원되지 않은 자격 증명 재사용은 하지 않는다.

## 완료 기록

- 기존 Claude CLI 로그인으로 native `acp/claude` 기본 agent를 연결하고 초기화 HTTP 200, CLI MCP Connected를 확인했다. 모델 요청은 0건이다.
- 확장 0.0.153/저장소 migration과 맞는 로컬 서버 0.0.162를 선택했다. MCP/CDP/proxy의 실제 wildcard 수신은 사용자 프로세스용 bind 보정으로 loopback에 제한하고 실제 주소/LAN 거부를 확인했다. 관리자 방화벽 요청은 철회했다.
- 실제 BrowserOS MCP 24 tools, PROFILE 74 + ACCOUNT 55 + private-profile 1 = 130 checks PASS. native 200%의 전체 화면 3개를 직접 확인했다.
- 동일 포트 즉시 재시작 실패를 `SO_REUSEADDR`로 수정했다. 개발 runtime 5 tests와 JD/R2/R3 고정 평가 53 cases, Ruff/GCC 검사 PASS.
- 자체 합성 앱/저장소와 QA BrowserOS profile/store는 제거했다. 사용자 BrowserOS는 설정된 loopback에서 실행 중이다. 기존 개발 저장소/20개 ignored 초안/HEAD를 보존하며 커밋·푸시하지 않았다.
- 자세한 설정·집계·화면·제한·실행 방법은 [시험 보고서](docs/CareerGround_BrowserOS_Claude_Code_QA_2026-10-03.md)에 기록했다.

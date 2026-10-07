# BrowserOS·현재 Claude Code 계정 연결과 합성 시험

기준 HEAD `2a6cdd25e266e29216d44946a0cd2c6bf1306a5a`, 브랜치 `codex/mvp-foundation-ci-20260923`. 기준 시험 문서는 [Phase A 개발 환경](CareerGround_Phase_A_Contracts_Development_Runtime_2026-10-02.md)이다. 실제 CareerGround 사용자·운영·제품 AI 공급자·새 유료 자원은 연결하지 않았다. 기존 미커밋 작업과 ignored 초안을 보존한다.

## 연결 설정

- BrowserOS 앱 `148.0.7966.97`, 실제 사용자 확장 `0.0.153.0`, 서버 `0.0.162`.
- Claude Code `2.1.286`의 기존 `claude.ai / firstParty / Pro` 로그인을 사용한다. 계정 식별자·OAuth 비밀은 보고서에 기록하지 않는다. 별도 Anthropic API 키를 넣거나 자격 증명을 다른 공급자 필드로 복사하지 않았다.
- BrowserOS AI & Agents에 `Claude Code`를 등록했다. 실제 저장 타입은 `acp / claude`, 기본 선택이며 모델은 `Agent default`다. `/acpx/probe`의 `type=claude` 연결 검사가 HTTP 200으로 모델/프로토콜 정보를 반환했다. 실제 모델 대화나 도구 실행을 포함한 AI 응답 품질·구독 잔여량 검사는 아니다.
- Claude Code user scope의 `browseros` MCP를 `http://127.0.0.1:9201/mcp`로 등록하고 `claude mcp get browseros`의 `Connected`를 확인했다. 기존 `auth0` 설정은 보존한다. Codex의 기존 BrowserOS URL도 같은 주소로 맞췄다. 공식 CLI 연결 경로는 [BrowserOS 안내](https://docs.browseros.com/browseros/features/use-with-claude-code)를 참고했다.
- 개인 설정의 변경 전 백업은 `~/.cache/careerground-browseros-qa-20261003/`의 0700 디렉터리와 0600 파일로 보존한다. 백업에는 인증 관련 설정이 포함될 수 있으므로 Git에 넣지 않는다.

초기 실행은 서버 0.0.127과 새 확장·13개 migration의 저장소를 혼합해 `Invalid adapter` / `no such table: agent_definitions`를 반환했다. 사용자 데이터베이스의 테이블을 임의로 만들거나 되돌리지 않고 이미 로컬에 설치된 0.0.162 서버 리소스를 선택해 해결했다.

## 실제 수신 주소 보정

설치 서버는 `allow_remote_in_mcp=false`에도 MCP를 `0.0.0.0`에 열었다. 이 컴퓨터의 LAN 주소를 통해 빈 탭 생성 도구가 실행되는 것을 확인하고 그 탭을 닫았다. BrowserOS를 정상 종료한 후 모든 해당 수신 포트가 닫힌 것을 확인했다.

관리자 방화벽 작업 대신 [프로세스 범위의 bind 보정 소스](../scripts/browseros_loopback_bind.c)를 사용한다. 사용자 소유 라이브러리 `~/.local/lib/careerground-browseros/libbrowseros_loopback.so`를 BrowserOS 실행에만 `LD_PRELOAD`로 지정했다. 고정 포트의 wildcard TCP bind를 IPv4/IPv6 loopback으로 바꾼다. `getsockopt` 실패는 바인딩을 거부한다. UDP·Unix socket·명시 주소·포트 0·outbound connect는 바꾸지 않는다. BrowserOS 자식 프로세스에도 환경이 상속된다.

GCC `-Wall -Wextra -Werror` 컴파일, IPv4/IPv6 실제 TCP listen 주소, UDP와 포트 0의 원래 동작을 검증했다. 실제 BrowserOS의 MCP 9201·CDP 9100·프록시 9000과 시험 프로필의 9240·9140·9040은 `ss`에서 모두 `127.0.0.1`이었다. loopback의 서버 health는 200, LAN 주소의 연결은 거부됐다. 전체 네트워크 격리나 악의적 프로세스의 syscall 차단을 주장하지 않는다. 앱/서버 갱신 시 실제 수신 주소를 다시 확인해야 한다.

사용자 메뉴의 BrowserOS는 `~/.local/share/applications/browseros.desktop` → `~/.local/bin/careerground-browseros`로 실행한다. 이 실행기는 보정 라이브러리와 확인한 서버 리소스·포트를 사용한다. 직접 `/usr/bin/browseros`로 여는 경우에는 이 보정이 적용되지 않는다. 운영체제 방화벽·systemd 설정은 변경하지 않았다. 앞서 제시한 sudo 방화벽 요청은 철회했으며 실행할 필요가 없다.

## 직접 시험

[실제 BrowserOS MCP 시험 스크립트](../scripts/run_browseros_local_contract_checks.py)는 별도 0700 브라우저 프로필을 CDP command line으로 확인한 뒤 자체 탭만 연다. 합성 앱도 매 시나리오마다 신규 0700 저장소와 임의 loopback 포트로 실행한다. 준비된 `.careerground-development/`를 사용하거나 지우지 않는다.

- 브라우저의 접근성 참조로 계정·도구·문구를 입력하고 체크한다.
- BrowserOS MCP와 전용 확장 API로 창/탭을 활성화하고 DOM 포커스·완전한 Enter 키 이벤트를 보내 실제 HTML form을 제출한다. 제출 후 새 document가 도착할 때까지 기다린다. 탭만 활성화했을 때 간헐적으로 키 제출이 전달되지 않은 시험 자동화 문제를 창 활성화로 보강했다.
- Chrome 탭의 실제 zoom 2와 페이지 DPR 2, main/h1, label, 가로 overflow를 확인한다. CSS zoom으로 대체하지 않는다.
- JD mock 후보의 미승인/NOT_MAPPED와 canonical 미저장, 별도 JD 발췌 승인, 저장된 JD fingerprint와 재시작을 확인한다. JD 저장은 경력 사실의 profile version을 변경하지 않는다.
- A/B 소유권, PROFILE/ACCOUNT 각각의 별도 승인과 동일 연결 실행, 로컬 삭제 request/데이터, 최소 상태와 B 보존을 확인한다. 자체 합성 SQLite의 읽기 전용 집계 조회를 보조 증거로 사용한다.
- 앱 CSP를 유지하고 해당 탭에서 실제 URL로 이동한 뒤 navigation timing의 `responseStatus`로 HTTP 401을 확인한다. `fetch`나 CSP 우회 옵션을 사용하지 않는다.
- 기본 screenshot 도구는 native 200%에서 CSS 크기를 DIP clip으로 사용해 화면 일부를 잘랐다. BrowserOS MCP의 `Page.getLayoutMetrics`/`Page.captureScreenshot`으로 실제 DIP 전체를 캡처하고 PNG 가로·세로와 비교한다. 확대 설정은 바꾸지 않는다.
- 승인 receipt·인증 token은 메모리에서만 사용한다. 보고서는 점검 이름·집계, 화면은 JD 후보/최소 상태만 기록한다. 스크립트는 AI 공급자를 호출하지 않는다. 관찰한 page resource가 local인 것과 OS 전체 egress 감사는 구분한다.

BrowserOS 0.0.162의 `run` 응답은 광고한 strict schema 밖의 `session` 필드를 추가한다. 시험 클라이언트는 해당 문자열 metadata만 제거한 사본의 나머지 payload를 기존 SDK로 검증한다. 포커스 전에 `DOM.getDocument`를 준비하며 JSON CDP 응답을 명시적으로 decode한다. 제품 MCP의 schema 검사를 완화하지 않는다.

실제 재시작 시험에서 TCP TIME_WAIT로 동일 포트 재기동이 실패하는 문제를 발견했다. 개발 실행기의 listening socket에 `SO_REUSEADDR`를 설정했다. `SO_REUSEPORT`는 켜지 않으며 살아 있는 다른 listener와 프로세스 lock 검사는 유지한다.

## 결과·종료

실제 BrowserOS MCP 서버 `0.0.162`의 24개 브라우저 도구를 연결해 **130 checks PASS**를 확인했다. PROFILE 74개, ACCOUNT 55개, 전용 프로필 검사 1개다. 이 숫자는 단위 테스트 수가 아니라 브라우저 시나리오 안의 assertion 수다.

| 시험 | 결과 |
| --- | --- |
| A가 B 프로필을 읽지 못함 | PASS |
| JD 미승인 후보·별도 발췌 승인 저장·동일 포트 재시작 | PASS |
| 승인 화면만으로 삭제 0건, 같은 연결의 증명 제출 후 정확한 삭제 요청 | PROFILE/ACCOUNT PASS |
| 삭제 후 최소 상태, 전체 완료를 주장하지 않음 | PASS |
| ACCOUNT 삭제 후 일반 Web 401·로그아웃 후 상태 401·B 보존 | PASS |
| native 200%, keyboard form, label/main/h1, 가로 overflow 없음 | PASS |
| JD/PROFILE/ACCOUNT 전체 캡처의 DIP 크기·실제 화면 확인 | PASS |

집계는 [report.json](/home/inno/.cache/careerground-browseros-qa-20261003/browser-checks/report.json)에 남겼다. 직접 확인한 화면은 [JD 후보](/home/inno/.cache/careerground-browseros-qa-20261003/browser-checks/jd-proposal-native-200.png), [PROFILE 상태](/home/inno/.cache/careerground-browseros-qa-20261003/browser-checks/profile-status-native-200.png), [ACCOUNT 상태](/home/inno/.cache/careerground-browseros-qa-20261003/browser-checks/account-status-native-200.png)다. 화면 크기는 각각 674×1509, 674×1263, 674×1263이다.

- 오프라인 JD/R2/R3 고정 평가 53/53 PASS: `/tmp/careerground-browseros-offline-20261003.json`.
- 변경 후 개발 환경 테스트 5/5 PASS: `/tmp/careerground-browseros-runtime-validation-20261003.log`.
- BrowserOS 시험 스크립트/개발 실행기 Ruff check PASS. C 소스 GCC 경고 없이 컴파일.
- 20개 ignored 초안 hash 동일. 커밋·푸시 없음.

각 시나리오의 앱은 SIGINT exit 0으로 종료하고 일회용 SQLite·키·승인 상태를 제거했다. 전용 BrowserOS를 정상 종료한 뒤 9240/9140/9040 포트 닫힘과 전용 profile/store 제거를 확인했다. 개인 프로필의 설정된 BrowserOS는 계속 실행 중이며 9201/9100/9000은 loopback에서만 수신한다. 마지막 health도 200이다. 8008/8009의 CareerGround 서버는 실행 중이 아니며, 기존 `.careerground-development/`는 보존했다. 종료 확인은 `~/.cache/careerground-browseros-qa-20261003/cleanup-result.json`에 남겼다. 추가 승인·수동 작업은 필요 없다.

이번 결과는 합성 로컬 계약 시험이다. 실제 AI 응답 품질·구독 잔여량, 사람의 스크린리더 청취, 실제 인증/운영 삭제·백업 삭제 완료를 검증한 결과는 아니다. 모델 요청은 보내지 않았다.

## 실행 방법

메뉴에서 BrowserOS를 열거나 다음 사용자 실행기를 사용한다.

```bash
careerground-browseros
claude mcp get browseros
```

CareerGround 합성 개발 환경은 프로젝트 root에서:

```bash
uv run --locked python -m careerground.development_runtime --state-dir "$PWD/.careerground-development" --port 8008
```

`http://127.0.0.1:8008/demo`에서 기존 문서의 합성 값만 사용한다. Ctrl+C로 종료하면 개발 저장소는 보존된다. BrowserOS 내장 Claude Code agent의 UI는 컴퓨터 파일·명령 접근을 허용한다고 안내한다. 이번 검증은 외부 모델에게 해당 권한으로 시험을 맡기지 않고, 제한된 정적 MCP 스크립트로 실행했다.

### BrowserOS 자동 시험 재현

일반 BrowserOS 개인 프로필 대신 새 전용 프로필을 사용한다. 아래 터미널에서 실행한 BrowserOS는 시험 종료 후 창을 정상 종료한다. 임시 저장소에는 합성 값만 넣으며 기존 개발 저장소는 사용하지 않는다.

```bash
cd /home/inno/repo/CareerGround
task_browser_qa_dir=$(mktemp -d /tmp/careerground-browseros-qa-XXXXXX)
mkdir -m 700 "$task_browser_qa_dir/profile" "$task_browser_qa_dir/store"
LD_PRELOAD="$HOME/.local/lib/careerground-browseros/libbrowseros_loopback.so" \
BROWSEROS_DIR="$task_browser_qa_dir/store" \
/usr/bin/browseros \
  --user-data-dir="$task_browser_qa_dir/profile" \
  --browseros-server-resources-dir="$HOME/.config/browser-os/.browseros/versions/0.0.162/resources" \
  --browseros-server-port=9240 --browseros-cdp-port=9140 --browseros-proxy-port=9040 \
  --disable-browseros-server-updater --enable-automation \
  --disable-background-networking --no-first-run --no-default-browser-check \
  chrome://browseros/settings &
```

서버 기동 후 **같은 터미널**에서 다음 명령을 실행한다. 저장소·앱 포트·승인 증명은 스크립트가 생성/정리하고, 결과와 세 화면만 별도 출력 폴더에 남긴다. 성공 후 전용 BrowserOS를 정상 종료한 다음 이번 명령으로 만든 `$task_browser_qa_dir`만 제거한다.

```bash
uv run --locked python scripts/run_browseros_local_contract_checks.py \
  --mcp-url http://127.0.0.1:9240/mcp \
  --private-browser-profile "$task_browser_qa_dir/profile" \
  --output-dir /tmp/careerground-browseros-contract-results
```

BrowserOS의 MCP 24개는 브라우저 자동화 도구다. CareerGround 제품 MCP의 26개와 다른 목록이며, 제품 도구는 합성 페이지의 MCP 콘솔에서 호출한다. 설정 변경 후 이미 실행 중인 Claude Code/Codex가 이전 MCP 연결을 유지하면 해당 클라이언트만 다시 실행한다.

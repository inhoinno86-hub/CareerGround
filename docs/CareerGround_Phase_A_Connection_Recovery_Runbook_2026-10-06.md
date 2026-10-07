# 개발 연결 차단과 오프라인 복구 절차

## 지속 QA 실행 프로세스: 임시 사용자 서비스

최종 시험 정리 뒤 소유 QA/tunnel 서비스는 중지했고 5000/8001/18081 포트가 닫혔다. 저장 자료는 유지했다. 아래 active/running 기록은 시험 중 관측이며 현재 실행 상태를 뜻하지 않는다. 재개할 때는 기존 저장소를 재사용하고 다시 초기화하지 않는다.

2026-10-07 후속 재개 때 기존 loopback 서버/터널은 종료돼 있었고 원인은 미확정이다. 저장 DB/등록 패스키는 보존돼 같은 실행기를 systemd --user transient unit으로 시작했다. 두 unit의 active/running, runtime live 및 기존 tunnel ready 200, 동일 store/key 재사용을 확인했다. 시스템 서비스 파일이나 자동 부팅 설정은 만들지 않았다. tunnel unit은 QA unit에 BindsTo/After로 묶었다.

확인은 아래 명령이다. 출력에는 서비스 상태만 표시한다.

```bash
systemctl --user show careerground-phase-a-release-qa.service careerground-phase-a-release-tunnel.service --property=Id --property=ActiveState --property=SubState --property=MainPID --property=BindsTo
```

정상 종료가 필요하면 소유한 QA unit만 아래처럼 중지한다. 연결된 tunnel도 중지된다. ignored QA 저장 자료는 남는다. transient unit은 종료 후 collect되므로 다시 시작할 때는 같은 저장소의 원래 실행기를 사용하며 initialize하지 않는다.

```bash
systemctl --user stop careerground-phase-a-release-qa.service
```

BrowserOS와 다른 사용자 서비스는 중지하지 않는다. 새 실행 방식의 관측은 [등록·재시작 증거](careerground_persistent_qa_a_passkey_registered_20261007.json)에 기록했다.

## 최신 관측: 2026-10-07

사용자 최종 제출로 지속 QA의 정확한 A/client를 차단했다. A MCP 재인증 요구, B 실제 ChatGPT 조회 성공, A/B Web 본인 조회 유지, 일반 재시작 후 signed registry의 A 차단/B 허용 지속을 확인했다. 승인된 오프라인 helper의 exit 0/UNBLOCKED를 확인하고 같은 store로 최종 재시작한 뒤 A 실제 native MCP 조회가 성공했다. 모든 단계의 자료 table 37개 count/행 hash가 유지됐다. Auth0 설정·grant·유료 자원은 변경하지 않았다. 차단 중 새 OAuth 발급 시험은 미수행이다. [단계별 증거](careerground_persistent_qa_connection_block_recovery_20261007.json). 아래 이전 상태 기록은 해당 시점의 이력이다.

대상은 현재 비공개 합성 QA의 정확한 활성 계정과 검증된 MCP client 한 쌍이다. 이 문서는 실행 준비이며 실제 공유 client 차단이나 Auth0 grant 철회 승인을 대신하지 않는다. 실제 차단은 아직 수행하지 않았다.

## 현재 QA의 구체 변경안 (2026-10-06 사용자 승인)

2026-10-06 A 재연결 뒤 별칭 `프로필A`를 명시한 실제 `get_my_profile`이 기존 QA A를 반환했다. 일반 호출의 만료 화면은 `Primary`였으며 A의 인증 실패로 합산하지 않는다. A/B의 서명 검증 뒤 관측한 MCP client는 같은 값이고, 실제 ID는 private fixture에만 유지한다.

현재 runtime에 아래 두 옵션을 연결한다. 새 registry는 현재 QA base 아래의 별도 `connection-denials` 디렉터리이며 기존 `state`와 `passkeys`를 재사용한다. 최초 registry가 없을 때만 초기화 옵션을 붙이고 이후에는 서명된 기존 registry를 연다.

```text
--development-connection-denials-dir <CURRENT_QA_BASE>/connection-denials
--development-connection-client-id <OBSERVED_MCP_CLIENT_ID>
```

검토할 범위는 **A 계정 + 현재 공유 개발 MCP client 한 쌍의 로컬 접근 차단과 오프라인 복구**다. A의 Dev OAuth PoC와 Phase A Dev가 모두 영향을 받을 수 있다. B의 같은 client 연결 및 A의 Web 자료는 유지해야 한다. 제공자 grant 철회, ChatGPT 연결 제거, Auth0 설정 변경은 포함하지 않는다. 새 클라우드 자원과 과금은 없다.

현재 환경 필터·loopback origin·기존 DB/패스키 경로를 보존하는 owner-only helper 두 개를 준비했고 Python 문법 및 실제 A/B client 일치를 확인했다. 사용자가 구체 변경안을 승인한 뒤 소유 runtime을 정상 종료하고 새 denial registry를 연결해 같은 store로 재시작했다. non-quota 자료 table 37개 count/행 hash가 모두 유지됐고 health 및 기존 tunnel ready가 200이다. 실제 Web 차단과 오프라인 복구는 아직 실행하지 않았다.

```bash
python3 /tmp/careerground-release-qa-denials-runtime.py
```

이 명령은 소유 runtime 정상 종료 후 같은 store로 재시작할 때만 사용한다. Web 차단 범위 체크와 최종 제출은 사용자가 직접 한다. 실제 차단 뒤 같은 registry 재시작으로 차단 지속과 B/Web 보존을 확인한다. OAuth 재연결이 필요하면 사용자 직접 수행을 요청하며, 새 인증만으로 자동 해제하지 않는다.

복구는 소유 runtime의 store/registry lock을 정상 종료로 해제한 뒤 다음 helper로 검토한 A/client 쌍에만 실행한다.

```bash
python3 /tmp/careerground-release-qa-recover-a.py
```

helper는 실제 private fixture의 A account와 동일한 관측 client를 전달한다. 결과 `UNBLOCKED`/`ALREADY_UNBLOCKED`와 `provider_changed: false`를 확인하고 위 runtime helper로 동일 store를 다시 연다. 복구 실패 시 인증·registry 서명 검사를 우회하지 않는다. 이 변경안에 대한 명시적 승인 전에는 runtime 연결 변경이나 실제 차단·해제를 실행하지 않는다.

## 실행 전 확인

### 2026-10-07 중단 환경의 저장소 확인

사용자 원래 PC에서도 `/tmp/careerground-release-qa-path`가 없고 5000/8001/9201 포트가 닫혀 있음을 확인했다. pointer 부재만으로 원래 DB나 다른 보존본이 삭제됐다고 단정하지 않는다. 현재 세션에서는 기존 `/tmp` helper도 없으므로 위 임시 helper 명령을 새 store 생성으로 대체하지 않는다.

원래 PC의 프로젝트 root에서 아래 읽기 전용 명령으로 알려진 CareerGround 디렉터리의 DB 후보를 확인한다.

```bash
python3 scripts/inspect_phase_a_qa_recovery.py
```

이 명령은 후보 파일 존재·저장된 checkpoint의 profile 상태 집계만 보고한다. 키·subject·원문·증명은 읽지 않으며 restore/init/upgrade를 실행하지 않는다. `runtime_binding_verified`는 항상 false다. 검색 범위는 `/tmp/careerground-*`, 프로젝트의 `.careerground*`, 사용자 `.cache/careerground*`와 `.local/share/careerground*`이며 PC 전체 백업 검색이 아니다. `scan_complete=false`인 결과를 저장소 부재로 판정하지 않는다.

후보가 있으면 원래 A/B 및 artifact와의 일치, runtime의 서명·issuer/origin/client 바인딩, 삭제 checkpoint와 패스키 store binding을 검증한 뒤 재사용 여부를 정한다. 이전 삭제된 QA를 현재 활성 QA로 복원하지 않는다. 후보가 없다면 남은 시험용 새 환경은 Git에서 제외되는 지속 저장 경로에 마련하고 최초 human 검토/패스키 승인을 새 store에 대한 과거 증명으로 대신하지 않는다. 이전 실제 시험 기록은 그대로 유지한다.

### 2026-10-07 BrowserOS 창 미표시 점검

사용자가 정지 작업을 `fg %1`로 재개하자 CDP 9100 시작 메시지와 singleton IPC의 broken pipe, GPU 상태 오류가 나왔으나 창은 열리지 않았다. 메시지만으로 GUI/MCP 복구나 GPU가 유일한 원인이라고 판정하지 않는다. 현재 agent 실행 환경에는 해당 사용자 프로세스가 보이지 않고 localhost 연결도 PermissionError로 거부된다. 이 결과를 원래 PC의 프로세스 종료나 포트 닫힘으로 해석하지 않는다. 현재 세션에는 BrowserOS MCP 도구도 제공되지 않았다.

원래 실행 터미널은 유지하고 **새 터미널**에서 프로젝트 root의 다음 명령을 실행한다.

```bash
python3 scripts/inspect_browseros_startup.py
```

진단은 사용자 소유 BrowserOS의 프로세스 상태·선택한 실행 옵션 존재 여부, 기존 프로필의 SingletonLock 상태, loopback CDP version/탭 개수 및 MCP health 응답만 보고한다. 명령행·환경 값·탭 제목/URL·쿠키·인증 정보는 출력하지 않는다. 프로필 변경·잠금 삭제·프로세스 종료·탭 생성은 수행하지 않는다. HTTP permission_denied와 connection_refused를 구분한다. 합성 프로세스의 정지 상태·GPU 역할 집계·민감 문자열 비출력·잠금 보존·접근 거부 분류 smoke 점검과 Ruff check/format이 통과했다.

사용자 원래 PC의 결과는 snapshot_complete=true, main_processes=[]/child_role_counts={}, 프로필 디렉터리 있음/SingletonLock 없음, CDP version/targets와 MCP health 모두 connection_refused였다. DISPLAY와 WAYLAND_DISPLAY가 있고 session_type=wayland였다. 이 관측 시점에는 시작한 브라우저가 남아 있지 않으며 재개 명령만으로 복구되지 않았다. 종료 원인은 확정하지 않는다.

프로필 잠금이 없는 상태에서 기존 loopback 실행기를 사용해 X11 경로·GPU 가속 비활성화 옵션으로 창 표시를 다시 확인한다. 기존 사용자 프로필을 그대로 사용하고 설정 파일을 수정하지 않는 이번 실행의 임시 옵션이다. 두 옵션을 함께 사용하므로 성공하더라도 GPU 또는 Wayland 중 하나를 원인으로 확정하지 않는다. sandbox 비활성화·프로필 초기화·잠금 삭제는 하지 않는다.

```bash
careerground-browseros --ozone-platform=x11 --disable-gpu --new-window about:blank
```

사용자 GUI는 원래 PC 터미널에서 시작해야 한다. 20초 동안 Ctrl+C/Ctrl+Z 없이 기다린 뒤 창 표시 여부를 확인한다. 창이 열리더라도 MCP 연결 성공은 별도로 확인한다.

사용자가 위 옵션 실행으로 창 생성에 성공했다. 제공한 시작 로그에는 서버 v0.0.162, CDP 9100 연결, HTTP 9201 시작 및 브라우저 MCP 도구 17개 등록이 있었다. 기존 QA에서 측정한 전체 도구 목록 수와 이 브라우저 도구 등록 수를 같은 값으로 취급하지 않는다. GCM 등록 경로의 QUOTA_EXCEEDED는 제품 MCP나 AI 사용량 오류의 증거로 채택하지 않는다. 이번 임시 옵션 두 개 중 어느 것이 복구에 기여했는지는 분리 검증하지 않았다.

실제 health 경로는 시작 로그에 나온 `/system/health`다. 진단의 이전 `/health`를 수정했고 실제 수신 주소와 선택적 MCP initialize/list_tools 점검을 추가했다. BrowserOS의 host=0.0.0.0 시작 로그는 설정 정보일 수 있으므로 loopback shim이 적용된 실제 주소는 `/proc/net/tcp{,6}`의 LISTEN 기록으로 별도 확인한다. 아래 명령은 브라우저 도구를 호출하지 않고 탭·승인·설정을 변경하지 않는다. 프로토콜 연결·목록 조회는 최대 8초이며 transport payload·session header·전체 health 본문을 출력하지 않는다.

```bash
uv run --locked python scripts/inspect_browseros_startup.py --mcp-check
```

리스너 IPv4/IPv6 및 wildcard 분류·정확한 health 경로·MCP initialize/list_tools만 호출·민감 문자열 비출력 smoke 점검과 Ruff check/format이 통과했다. 기존 Codex browseros 설정의 enabled=true와 loopback MCP URL 일치는 읽기 전용으로 확인했다. 현재 agent 세션에는 BrowserOS 도구가 제공되지 않았고 PC loopback 연결은 PermissionError로 거부된다. 원래 PC의 서버 성공을 이 세션의 브라우저 도구 접근 성공으로 확대하지 않는다.

이후 사용자가 원래 PC에서 실행한 `--mcp-check` 결과는 프로세스 집계 0·SingletonLock 없음·CDP version/targets 및 MCP health 모두 connection_refused·대상 TCP LISTEN 0개·MCP connection_failed였다. 브라우저 도구는 0회 호출했다. 앞선 시작 로그는 시작 당시의 증거로 보존하며 이번 점검 시점의 서버 지속 실행 성공으로 채택하지 않는다. 점검 당시 창이 열려 있었는지와 원래 실행 터미널이 입력 프롬프트로 돌아왔는지 사용자 확인을 요청했다. 해당 터미널의 직전 명령 종료 코드와 마지막 오류도 확인하며, 이후 다른 명령을 실행했다면 그 코드가 BrowserOS 종료 코드라고 추정하지 않는다. 정상 종료·시그널 종료·충돌·실행 환경 차이는 아직 구분하지 않았다. 동일 실행 명령을 반복하기 전에 이 정보를 확인한다.

사용자가 후속 점검 전에 BrowserOS 실행 터미널에서 Ctrl+C로 직접 종료했다고 확인했다. 따라서 이번 connection_refused/프로세스·리스너 부재는 수동 종료 후의 결과이며, 자발적 충돌이나 MCP 설정 결함의 증거로 채택하지 않는다. 최초 창 미표시의 원인과 두 임시 옵션 중 어느 것이 기여했는지는 여전히 별도 미확인이다.

터미널 입력 프롬프트를 사용할 수 있도록 다음에는 기존 실행기를 백그라운드로 시작한다. nohup은 터미널 종료에 따른 SIGHUP을 무시하게 하며, stdout/stderr는 /dev/null로 보내 별도 로그 파일을 만들지 않는다. 시작 상세 로그는 남지 않으므로 성공 여부는 창과 진단 응답으로 확인한다. 프로필·MCP 설정 파일은 바꾸지 않는다.

```bash
nohup careerground-browseros --ozone-platform=x11 --disable-gpu --new-window about:blank </dev/null >/dev/null 2>&1 &
```

창이 열린 뒤 20초 기다리고 같은 터미널에서 위 `--mcp-check` 명령을 실행한다. 이번에는 브라우저를 종료하지 않고 점검한다. 이후 종료가 필요할 때는 BrowserOS의 창/메뉴에서 정상 종료한다. 현재 agent 세션의 BrowserOS 도구 접근 제한은 이 수동 종료 원인과 별개로 남아 있다.

사용자가 nohup 실행 후 브라우저를 유지한 실제 원래 PC 점검을 완료했다. CDP version/targets·MCP health는 모두 200, MCP 프로토콜은 connected·24개 도구·pagination 없음·도구 실행 0회였다. 9000/9100/9201의 실제 LISTEN 주소는 모두 127.0.0.1이었다. 이로써 원래 PC의 시작·loopback·MCP discovery 점검은 통과했고 같은 기동 점검을 반복하지 않는다. 프로세스 역할/옵션 분류는 명시적 실행 명령과 맞지 않아 옵션 적용 및 메인 프로세스 수의 수용 증거로 사용하지 않는다. [연결 복구 증거](careerground_browseros_connection_recovery_20261007.json)에 자격 증명·탭 URL 없이 결과를 기록했다.

현재 agent 세션에서 재확인한 loopback 접속은 PermissionError이며 BrowserOS 도구도 제공되지 않았다. 이는 원래 PC의 정상 서버와 구분한다. 현재 대화의 실행 환경(Codex CLI/앱·IDE/웹)을 사용자에게 확인한 뒤 그 환경의 MCP 연결을 이어간다. 기존 설정에서 enabled=true·예상 loopback URL은 확인했다. Codex CLI의 `/mcp`는 활성 MCP 목록을 확인하는 명령이며 CLI/IDE/동일 host의 앱이 MCP 설정을 공유한다는 [OpenAI 공식 MCP 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)를 확인했다. 현재 세션에서 사용자 PC의 로컬 MCP가 자동으로 제공된다고 가정하지 않는다. 새 지속 QA 서버는 아직 시작하지 않았다.

사용자는 이 대화를 ORCA의 Codex CLI에서 진행 중이라고 확인했다. ORCA CLI 스킬을 읽고 Linux의 외부 명령 실행 환경에서는 GNOME screen reader인 `/usr/bin/orca`를 실행하지 않고 `orca-ide`를 사용했다. 이 명령 실행 환경의 `status --json`은 stale_bootstrap/reachable=false, 현재 프로젝트의 terminal list는 runtime_unavailable였다. 사용자 원래 PC의 ORCA가 종료됐다는 증거로 채택하지 않는다. 이 범위에서 사용자 터미널을 직접 조작하거나 ORCA를 중복 시작하지 않았다.

실제 Codex home은 `/home/inno/.config/orca/codex-runtime-home/home`이며 기본 `~/.codex`와 다르다. 두 위치를 구분해 읽기 전용 점검했으며 ORCA의 실제 config에서도 browseros enabled=true·예상 loopback URL이었다. 현재 세션 파일도 실제 home에 존재함을 확인했지만 내용을 출력하거나 다른 home으로 복사하지 않았다. 설정·인증 파일 변경 없이 먼저 ORCA 안의 현재 Codex 대화 입력칸에서 `/mcp`로 browseros 활성 상태를 확인하는 수동 한 단계가 필요하다. CLI 시작 때 BrowserOS가 없어서 초기 연결이 실패했을 가능성은 아직 가설이다. 도구 로딩 상태를 확인한 뒤 현재 세션의 재연결/재개 필요 여부를 판단한다.

사용자가 현재 Codex의 `/mcp`에서 browseros가 fail이라고 확인했다. 원래 PC의 연결 통과 결과와 현재 CLI의 실패 상태를 구분한다. 실제 home의 현재 세션 파일 존재와 설치 CLI의 `codex resume [SESSION_ID] --cd` 사용법을 확인했다. 이 명령 실행 환경에서 현재 ORCA 터미널에 접근할 수 없고 Codex TUI 로그도 확인한 기본 위치에 없어 초기 연결 실패 원인은 확정하지 않는다. 현재 실패 상태에 대해 같은 저장 세션을 재개해 MCP 초기화를 다시 시도하는 수동 한 단계가 필요하다.

BrowserOS는 실행한 채 ORCA의 현재 Codex에서 `/quit`로 종료하고, 같은 CareerGround 프로젝트의 일반 터미널에서 아래 명령을 사용한다. 기존 agent 탭이 종료 상태로 남아 shell 입력을 받을 수 없다면 ORCA에서 그 프로젝트의 일반 터미널을 연다. `<CURRENT_SAVED_SESSION_ID>`는 실제로 존재를 확인한 현재 세션 ID이며 사용자 안내에는 해당 값을 전달한다. `--last`로 다른 작업을 선택하지 않는다. 기존 ORCA Codex home을 그 실행의 `CODEX_HOME`으로 지정하는 것은 동일 설정/저장 대화를 선택하기 위한 것이며, 설정·인증 파일 복사나 영구 환경 변수 변경은 수행하지 않는다. 보호 설정·모델·로그인 제공자 override는 추가하지 않는다.

```bash
env CODEX_HOME=/home/inno/.config/orca/codex-runtime-home/home \
  codex resume --cd /home/inno/repo/CareerGround '<CURRENT_SAVED_SESSION_ID>'
```

재개된 Codex의 `/mcp`에서 browseros 상태를 확인하고 연결 실패가 계속되면 해당 시작 오류만 확인한다. 설정이 이미 활성화됐고 원래 PC MCP discovery가 통과했으므로 BrowserOS 설치/계정 셋업/기동 시험을 반복하는 단계로 돌아가지 않는다. 동일 저장 대화 재개는 [공식 Codex 명령 문서](https://learn.chatgpt.com/docs/developer-commands?surface=cli#codex-resume)에 따른다. 이 재개 명령은 현재 agent가 직접 실행하지 않았으며 MCP 복구 성공은 아직 미확인이다.

사용자가 같은 저장 세션 재개 뒤 BrowserOS MCP connected를 확인했다. 현재 agent의 도구 목록에도 BrowserOS 24개가 로드됐다. 첫 `tabs action=list` 요청은 클라이언트에서 `MCP tool call requires approval, but approval policy is never`로 거부됐다. 원래 PC MCP 연결 실패나 제품 인가 거부로 기록하지 않는다. 현재 정책에서는 승인 요청을 표시할 수 없어 `/permissions`에서 `Ask for approval`을 선택하는 수동 한 단계를 요청했다. [공식 sandbox/권한 문서](https://learn.chatgpt.com/docs/sandboxing)에 따르면 이 프로필은 workspace-write/on-request이며, CLI의 `/permissions`로 활성 권한 프로필을 바꾼다. 설정 파일은 변경하지 않았고 다른 transport/도구로 승인 거부를 우회하지 않았다. 선택 이후 실제 첫 도구 승인을 확인한다.

### 2026-10-07 지속 저장 환경 준비

사용자가 원래 PC에서 실행한 추가 점검은 지정 범위 검색 완료·4개 디렉터리·DB 후보 0개였다. 이전 QA를 복구했다고 선언하지 않는다. 새 시험 경로는 프로젝트의 `.careerground-release-qa/release-20261007`이며 Git 제외·디렉터리 0700·marker 0600이다. 현재 `--initialize --prepare-only`를 실행해 경로와 marker만 준비했다. runtime/DB/profile/passkey는 생성되지 않았다. 현재 실행 환경의 loopback bind가 PermissionError(errno 1)로 거부돼 실제 서버 시작은 사용자 PC에서 필요하다.

이미 준비된 이 QA의 서버 시작 및 이후 재시작은 프로젝트 root에서 아래 같은 명령을 사용한다. 터미널을 유지하고 Ctrl+C로 정상 종료하면 자료는 남는다. 실제 준비가 끝난 상태이므로 `--initialize`를 다시 붙이지 않는다.

```bash
uv run --locked python scripts/run_phase_a_release_qa.py
```

다른 새 QA를 최초 준비할 때만 고유 `--name`과 `--initialize --prepare-only`를 사용한다. 기존 이름을 초기화하거나 marker를 지워 재시작하지 않는다. `runtime_initialized=true` 이후 DB/패스키 경로가 없으면 자동 재생성하지 않고 중지한다. 부분 생성 상태도 보존하고 중지한다. runtime의 기존 서명·binding·삭제 checkpoint 검사는 그대로 적용된다. 이 경로의 지속 보존은 별도 백업/운영 복구 보장이 아니다.

기존 터널 설정·키·등록 ID를 유지하는 실행기도 준비했다. 준비 점검에서 기존 resource 경로와 tunnel ID 일치를 확인했으며 터널은 시작하지 않았다. control plane과 공개 MCP resource의 호스트는 다를 수 있어 호스트 동일성으로 바인딩을 추정하지 않는다. 아래 명령은 해당 QA의 소유 runtime이 실행 중이고 localhost health가 200인 경우만 진행한다. 새 터널/클라우드 자원을 생성하지 않으며 raw HTTP logging·원격 UI·브라우저 자동 열기를 끈다. 키를 argv나 출력에 포함하지 않고 기존 private env 파일에서 자식 환경으로만 전달한다.

```bash
uv run --locked python -m scripts.run_phase_a_release_tunnel
```

새 Web 로그인/프로필 생성/패스키 등록 및 합성 검토가 필요하면 사용자 최종 단계를 현재 store에서 새로 확인한다. 이미 통과한 이전 QA 결과는 이력으로 유지하며 새 store에 복사한 사실/승인 증거로 만들지 않는다. 실제 새 MCP operation의 검증된 client metadata를 관측한 뒤에만 base의 owner-only `observed-client.txt`를 준비하고 서버를 다음 옵션으로 재시작한다.

```bash
uv run --locked python scripts/run_phase_a_release_qa.py --enable-connection-controls
```

관측 client 파일 없이 차단 기능을 켜지 않는다. 한번 생성된 차단 registry는 이후 일반 재시작 명령에서도 자동 연결되며 파일이 없거나 부적절하면 거부한다. 실제 A/client 로컬 차단·해제 승인 범위는 유지되지만 Web 최종 범위 제출은 사용자가 직접 한다. 오프라인 복구는 동일 새 state/registry 및 새 store에서 검증한 정확한 A account/client를 기존 `scripts/recover_development_connection.py`에 전달한다. 과거 계정 ID나 만료된 증명을 재사용하지 않는다.

지속 실행기·기존 터널 준비의 환경 바인딩/파일 보존/초기화 거부/차단 재사용/자격 증명 비출력 관련 로컬 회귀 13개가 통과했다. 이는 실제 새 로그인·터널 가동·공유 client 차단 시험 성공이 아니다. BrowserOS 시작부터 필요한 사용자 작업은 한 단계씩 안내한다.

1. 서명 검증 이후 제품 요청에서 관측한 client를 확인한다. Web 로그인 client, ChatGPT 앱 ID, 연결 별칭을 MCP client로 추정하지 않는다.
2. 같은 client의 Dev OAuth PoC와 Phase A Dev 연결이 영향을 받을 수 있음을 설명하고 구체 승인을 받는다. 다른 계정과 다른 client의 차단 상태는 유지한다.
3. 현재 QA store·issuer·origin·환경 파일·패스키 경로를 그대로 사용하는 재시작 명령을 준비한다. 새 store를 만들거나 이전 삭제 QA를 복원하지 않는다.
4. 복구 명령의 정확한 account/client 값은 권한이 제한된 로컬 자료에만 보관한다. 토큰·provider subject·비밀번호·환경 파일 원문은 보고서에 넣지 않는다.

## 실제 시험 순서

1. 두 계정의 Web/MCP 정상 요청과 제품 자료 상태를 먼저 기록한다.
2. 현재 QA에 명시한 client의 로컬 차단 기능을 연결한다. 최초 registry 생성과 이후 재사용을 구분한다. 기존 store와 패스키 registry를 초기화하지 않는다.
3. 사용자가 Web의 연결 차단 범위와 두 개발 연결 영향을 직접 확인하고 제출한다.
4. 차단된 계정/client의 다음 MCP 요청이 거부되는지 확인한다. Web 로그인과 자료, 다른 계정의 요청은 유지되는지 확인한다. 이미 진행 중인 요청의 취소를 보장하지 않는다.
5. 정상 재시작·새 인증·재연결만으로 로컬 차단이 풀리지 않는지 확인한다. Auth0 grant 철회나 ChatGPT 연결 제거는 별도 변경이다.
6. 소유한 개발 runtime을 정상 종료해 store와 registry lock을 해제한다. 현재 store의 종료 checkpoint가 기록되는지 확인한다.
7. 아래 오프라인 명령을 검토한 정확한 쌍에 대해 실행한다. 경로와 식별자는 실제 검토 값으로 대체한다.

```bash
uv run --locked --env-file .env --env-file .env.poc \
  python scripts/recover_development_connection.py \
  --state-dir '<CURRENT_QA_STATE_DIR>' \
  --connection-denials-dir '<CURRENT_QA_DENIALS_DIR>' \
  --account-id '<REVIEWED_ACTIVE_ACCOUNT_ID>' \
  --connection-client-id '<OBSERVED_MCP_CLIENT_ID>' \
  --confirm-unblock
```

8. `UNBLOCKED`와 `provider_changed: false`를 확인한다. 같은 명령의 재실행은 `ALREADY_UNBLOCKED`이며 다른 차단을 해제하지 않는다. `RECOVERY_REFUSED`이면 이유를 로컬에서 점검하고 인증·서명 검사를 우회하지 않는다.
9. 동일 store/registry로 재시작한 뒤 해당 쌍의 정상 요청과 다른 계정/client의 차단 유지, 제품 자료와 삭제 ledger 보존을 확인한다.

## 구현과 확인된 범위

복구 명령은 이미 존재하는 private store/registry만 사용한다. issuer/origin 바인딩과 서명을 검사하며 활성 계정의 동일 issuer identity가 정확히 하나인지 확인한다. runtime이 lock을 가지고 있으면 거부한다. Web/MCP 자동 해제 route, provider 호출, 새 토큰 발급은 없다.

복구·차단 registry·관리 화면 관련 로컬 회귀 8개가 통과했다. 이는 합성 identity 시험이며 실제 제공자 계정의 차단·해제·재연결 시험 완료가 아니다. 실제 OAuth 재연결 필요 화면과 Web 로그인 만료 관측도 provider token의 정확한 만료 원인이나 철회 성공으로 확대하지 않는다.

관련 구현: [복구 명령](../scripts/recover_development_connection.py), [활성 계정 확인](../src/careerground/storage/development_connection_recovery.py), [서명 registry](../src/careerground/storage/development_connection_revocations.py).

- 2026-10-07 사용자 Full Access 선택 후 native BrowserOS 탭 조회/snapshot/navigation과 로컬 bind가 성공했다. 지속 QA를 실제 시작해 DB/패스키 경로를 새 초기화했고 accounts/profiles/claims 0, runtime live 200, 기존 터널 health/ready 200을 확인했다. 이전 DB/approval/passkey 복원은 없다. 기존 SSO로 A 빈 프로필 생성 화면을 준비했으며 사용자 직접 생성 확인을 기다린다. 루트에 생긴 tunnel literal stdout 로그는 private QA로 보존하고 CLI 문서대로 빈 log.file 경로로 수정했다. 회귀 4개 및 수정 후 health/ready 200·루트 파일 미생성이 통과했다. ignored 초안 20개 hash도 유지됐다. 실제 제품 수용/차단/복구/export/삭제 완료로 확대하지 않는다. 근거: docs/careerground_persistent_qa_activation_20261007.json.

- 같은 지속 QA에서 사용자 A의 직접 프로필 생성 뒤 관리 화면과 계정/identity/profile 각 1개·version 0·Claim 0을 확인했다. A의 쿠키·토큰을 복사하지 않고 별도 BrowserOS context/새 창에서 B 제공자 로그인 화면을 준비했다. B 로그인 및 직접 빈 프로필 생성이 다음 수동 단계이며 A/B identity 분리나 MCP 연결 완료로 판정하지 않는다.

- 사용자 B의 직접 생성 뒤 accounts/identities/profiles 각 2개·서로 다른 검증 identity·각 version 0·Claim 0을 확인했다. Web 관리 링크가 private A/B actor mapping과 일치했다. 새 세션 바인딩만 확인하는 profile GET 6건은 양방향 본인 200, foreign/absent 동일 404·동일 본문·form 0·요청 ID 미노출이었다. 최초 browser fetch 시도는 Failed to fetch로 미확인이고 top-level navigation으로 확인했다. 기존 완료된 광범위 시험을 반복한 것은 아니다. 기존 ChatGPT 프로필A/B의 실제 get_my_profile 1회씩은 앱 계층 재인증 요구여서 서버 identity/차단 증거로 채택하지 않았다. A OAuth 재연결 한 단계만 사용자에게 요청했다. 새 Web 증거: docs/careerground_persistent_qa_web_sessions_20261007.json.

### 2026-10-07 실제 UI의 A 재연결 위치 확인

현재 BrowserOS ChatGPT에서 사이드바 → 플러그인 → CareerGround Phase A Dev 상세 화면의 ‘연결된 계정’ 목록에 프로필A의 다시 연결 버튼이 실제 표시됐다. 상세 화면 경로는 `/plugins/<PRIVATE_PLUGIN_ID>`다. 앱 도구 목록 dialog에서는 계정별 연결 메뉴가 보이지 않는다. 해당 상세 화면에서 기존 프로필A의 다시 연결을 선택해 ‘CareerGround Phase A Dev 연결’ 팝업을 준비했다. ‘CareerGround Phase A Dev(으)로 계속’과 실제 로그인/권한 동의는 사용자 직접 단계로 요청했다. 다른 별칭·Primary·앱 등록·권한·과금을 변경하거나 새 연결을 만들지 않았다. 연결 성공은 실제 get_my_profile 반환으로 확인해야 한다.

- 사용자 A 재연결 후 실제 native MCP get_my_profile이 새 지속 QA A/version 0을 반환했고 B와 다른 ID임을 확인했다. 남은 시험용 새 합성 source 1개/정확한 Unicode [35,72) DRAFT 1개를 native MCP로 준비했다. 최초 start goal은 계약값과 달라 VALIDATION_FAILED였고 ADD_EXPERIENCE로 수정했다. DB owner/session/source/hash/text 일치, Claim/승인 0을 확인했으며 과거 fact approval을 복사하지 않았다. 이 호출은 Codex 연결 앱의 실제 MCP이며 ChatGPT 브라우저 대화/최신 설치 plugin 왕복 증거와 구분한다. B context의 기존 제품 상세 탭은 미로그인이라 쿠키 비필수사항 거부 후 ChatGPT 로그인 dialog를 준비하고 같은 기존 ChatGPT 계정으로 사용자 로그인만 요청했다. 새 가입/새 앱/다른 연결 제거는 없다. 근거: docs/careerground_persistent_qa_a_mcp_preparation_20261007.json.

- B 창 ChatGPT 로그인 뒤 기존 private plugin을 확인했다. 계정 목록의 초기 A만 보이는 상태가 후속 로드에서 기존 aliases까지 갱신됐다. B context의 다른 계정 연결은 기존 SSO/동의로 자동 처리돼 새 별칭 지속 QA B를 부여했다. 기존 별칭 제거/제공자 설정 변경은 없다. 기대 ID 없는 ChatGPT get_my_profile 반환이 정확한 새 B/version 0이고 서버 B read 1건임을 확인했다. B의 새 합성 source/DRAFT 각 1건 owner/hash/text 일치가 확인됐다. multiline type이 3개 메시지로 나뉜 관측은 보존하고 실제 저장 원문은 명시적 최종 합성 문장 37자다. 후속 입력은 single-line fill→send로 바꿨다. 새 실제 A own session+B source 혼합과 없는 source 요청은 native MCP에서 같은 NOT_FOUND였고 자료 37개 table count/hash가 유지돼 이전 미확인 방향을 보완했다. A FACT_REVIEW batch/confirmation을 준비하고 실제 서명 검증 뒤 기록된 A/client metadata를 private observed-client.txt로 보존했다. registry 활성화/차단은 아직 없고 사용자 사실 검토를 기다린다. 근거: docs/careerground_persistent_qa_b_connection_boundaries_20261007.json.

- 사용자 A 사실 검토 뒤 새 합성 Claim 1개·version 1을 확인했다. 동일 요청 연결 get_confirmation_status의 DONE 증명을 출력/파일 저장/공유하지 않고 submit_claim_review에 전달해 CONSUMED가 됐다. B의 WAITING PROFILE_EXPORT 요청에서는 actual client metadata가 A와 같은 값임을 확인했고 동의/export 실행은 없다. A의 B/없는 operation get_confirmation_status는 같은 REVIEW_REQUIRED였으며 증명은 노출되지 않았다. 소유 runtime/tunnel만 정상 종료해 동일 지속 store에 signed denial registry를 처음 연결했고 자료 37개 table count/hash를 유지했다. runtime live 및 기존 tunnel ready 200, A/B 기존 SSO Web 로그인·소유 profile 링크 갱신, A native MCP/version 1 및 B ChatGPT MCP/version 0을 확인했다. 정확한 A/account/client private 오프라인 복구 helper는 문법이 유효하고 runtime 활성 상태 실행은 RECOVERY_REFUSED였으며 해당 store lock이 실제 독점 잠금임을 확인했다. A Web 차단 검토를 새로 열어 기존 승인 범위의 사용자 최종 제출을 요청했다. 새 승인 범위를 다시 요청하거나 Auth0 변경/실제 unblock을 실행하지 않았다. 근거: docs/careerground_persistent_qa_a_fact_connection_controls_20261007.json.

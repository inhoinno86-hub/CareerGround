# CareerGround 08 에뮬레이터 보충 검증 — 2026-10-12

**실제 AVD의 합성 인증·모의 AI·화면·파일·복원 검사 PASS. 환경 제한은 별도 기록한다.**
실기기에서 이미 통과한 개인 로그인·실제 Codex·한국어 발화·ChatGPT 결과 왕복과 구분한다.
[구조화 증거](mock_interview_emulator_validation_20261012.json),
[앱 전체 수용](mock_interview_app_acceptance_20261012.md),
[승인한 설치안](mock_interview_emulator_install_20261012.md)을 따른다.

## 환경과 실행

사용자 승인으로 emulator37.2.12 stable/Android36 Google APIs x86_64 revision7 설치 exit0.
전용 7.6in Foldable AVD에 기존 code4 APK와 시험 APK를 설치하고 instrumentation9개 PASS.
9개는 중단 이전 실행이며 재개 후 다시 실행한 것으로 세지 않는다. 앱 소스/APK는 변경하지 않았다.
실제 AVD에 합성 owner·MockProvider를 연결했으며 UI의 실제 개인 로그인 아님/모의 AI 표시와
수동 저장 파일의 provider Mock/actual=false를 확인했다. 실제 Codex 추가0·11/12 유지,
ChatGPT 추가 요청0(전체3)·유료API0. 물리 휴대폰 설정·계정·플러그인 등록 변경 없음.

## 통과한 검사와 제한

| 검사 | 판정 |
| --- | --- |
| SAF handoff 선택·취소·구조 검사·검토·고정·시작 | PASS. 원본/고정 참조 유지, 검토 전 질문 없음 |
| 질문·답변·평가 | Mock 질문5개 및 후속, 확인 답변 revision1→2, 이전 답변/평가/후보 stale 유지 PASS |
| 커버·펼침 | 884×2208 한 열→1768×2208 두 열에서 초안·선택 질문 유지 PASS. 명시적 wm size override/reset 사용 |
| 접힘 센서 | CLOSED/15도 및 OPENED/180도 관찰. headless 자동 화면 크기 전환은 미검증 |
| 키보드 열린 채 크기 변경 | mInputShown=true 전후 확인·미확인 수정 초안 유지 PASS |
| 가로 회전 | 실제 2208×1768·고정 해시/선택 질문/확인 답변 유지 PASS |
| 실제 분할 화면 | 기존 시험 APK EmptyActivity와 multi-window 1768×1091·확인 답변 유지 PASS |
| 일시 중지·계속·홈 왕복 | PAUSED→IN_PROGRESS 및 background 왕복 답변 유지 PASS |
| 수동 저장·저장 취소 | 실제 SAF 파일 쓰기/PC pull·schema 검사, 취소 후 메모리 유지 PASS |
| 앱 강제 종료 | pid 제거·연결 화면 복귀·RAM 세션 자동 복원 없음 PASS |
| 앱·runtime 교체 후 수동 복원 | 기존 파일 선택→fresh REVIEW_REQUIRED→검토/고정→시작, 확인 답변 v2 유지 PASS |
| 가져온 AI 기록 | 평가/후보 모두 stale, events imported_unverified/actual=false PASS |
| 평가 없이 중단·재가져오기 | ABORTED 유지·확인 답변 보존, 진행 중 상태로 되돌리지 않음 PASS |
| 중단 결과 파일 | 실제 SAF result1.0→PC schema/참조/importer PASS. 현재 답변1·평가0·후보0 |
| 에뮬레이터 실제 한국어 음성/TTS | 미실행. 기기 서비스 미준비, 음성 모델 다운로드 없음 |
| 에뮬레이터 개인 OIDC·새 결과 ChatGPT 재검토 | 미실행. 이 AVD는 합성 인증이고 호스트 추가 호출 없음. 기존 실기기 실제 결과의 호스트 PASS 유지 |

중단 결과의 평가/후보0은 복원된 unsigned AI 기록을 다시 신뢰하지 않고 제외했기 때문이다.
실제 한국어 발화·읽기는 별도의 실기기 사용자 확인 결과다. 에뮬레이터 모의 검사를 그 결과로 세지 않는다.

## 실패와 보완

첫 파일 미노출은 선택 합성 파일의 media scan 후 해결했다. picker 첫 Back은 상위 폴더 이동,
둘째 Back은 취소였다. 첫 취소 assertion 실패를 그대로 보존했다.
크기 변경 후 편집기가 스크롤 밖으로 이동해 최초 표시 검사가 실패했으나 스크롤 후 초안 보존을 확인했다.
키보드가 이미 닫힌 상태의 추가 Back으로 activity가 끝난 시도는 미저장 RAM 손실로 기록하고
키보드 상태 확인을 시험 스크립트에 추가한 뒤 새 합성 세션을 만들었다.

사용자 재개 메시지 사이에 PTY runtime이 종료돼 포트 닫힘을 확인하고 선택 AVD의 남은 시험 reverse를
제거했다. 독립 시험 driver를 새로 띄워 기존 수동 파일에서 확인 답변 v2 복원을 실제 관찰했다.
Start 버튼을 단방향 스크롤로 놓친 시도와 일시적 비어 있는 UI hierarchy 읽기 실패는 탐색 방향/제한된 재조회로 보완했다.
앱 소스는 수정하지 않았다.

SAF 파일 이름 입력을 키보드 전환 전에 보내 이전 이름의 (1) 파일로 결과가 저장된 첫 시도도 보존했다.
그 내용은 실제 result였으며 키보드 전환 대기→필드 이름 확인→저장으로 올바른 r2 이름을 확인했다.
PC 검사의 잘못된 provenance/model_feedback 키 접근 실패도 보존하고 실제 session events/result feedback으로 수정했다.
앱 schema/reference 검사의 실패로 분류하지 않는다. 검사기 오류를 통과로 숨기지 않았다.

## 실제 파일

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| careerground-session-emulator-active-r1.json | 13667 | 943f19a19acaadb8cb3894375606b4e1e4b501f095ef7421b959e09e3bf50182 |
| careerground-session-emulator-active-r2.json | 16145 | 0ce8343ccb42ffa9ae114f0082710d2e64ca0dc4edbe9e652a3533590d13156f |
| careerground-session-emulator-aborted-r1.json | 16250 | 3a51ad5cbe45dcf5cd10e9190a0b938d6818f1fa134cb32e1a9b3a840f3ba9d4 |
| careerground-result-emulator-aborted-r2.json | 516 | 75dd25d5e772cb380bb8d1de784e5bd4f73dae43f760d931c0befdfb95e83a20 |
| misnamed-export-preserved.json | 516 | dff5a0b248887b28ddc8a727dbf5a4f893e6095f0d912c6d7322854a25dad48f |

파일과 UI/window/프로세스/검사 receipt는 비공개
`~/.local/share/careerground-android/artifacts/emulator-step04-20261012/`에 보존했다.
이 결과들은 합성 시험 파일이며 실기기 실제 AI 결과 파일은 기존 이름/해시 그대로 보존했다.

## 정리와 다음 단계

앱 연결 해제·RAM/token 비우기를 확인하고 앱을 종료했다. AVD 크기 override 해제·회전 free·펼침을 복원한 뒤
선택 AVD tcp8765 reverse 제거, runtime 종료/포트 닫힘, emulator graceful shutdown PASS.
SDK/AVD/시험 파일·기존 작업 트리 변경을 보존했다. 휴대폰을 분리해도 된다.

승인된 08 개발 왕복의 핵심과 보충 검사를 마쳤다. 개인 경력 handoff 사용성·운영 OpenAI API·배포는 미실행이다.
다음은 사용자가 ChatGPT에서 준비한 실제 handoff를 명시 선택해 포함 범위와 사용성을 확인하는 단계다.
새 부분 profile workspace를 handoff 대신 가져오지 않는다. 운영 배포/API 및 새 설치·등록·연결 변경은 별도 확인한다.

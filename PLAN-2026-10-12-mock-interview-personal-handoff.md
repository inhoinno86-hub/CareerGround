# CareerGround 08 개인 handoff 준비·사용성 확인

2026-10-12. 기존 08 합성 개발 수용은 완료했으며 사용자 선택 개인 대화로 후속을 진행한다.
개인 원문·실제 파일은 저장소 밖 owner-only artifacts/personal-handoff-20261012에만 보관한다.

## 승인 범위와 현재 상태

사용자가 검토 순서 실행과 승인/수동 작업 외 자율 진행을 요청했다. 기존 선택·사용 금지·기여 경계를 보존한다.
- [x] 사용자 지정 ChatGPT 대화 확인 및 기존 후보/사용 기록/통합 검토 파일 실제 확보.
- [x] 면접에 먼저 사용할 두 사실의 정확한 문구에 실제 사용자 사실 확인 응답 수신. 기존 세 용도 허용 재질문 없음.
- [x] 원본 후보→추가 후보→허용 기록 해시 연결 및 두 사실의 원문/근거/기존 scope 대조.
- [x] 실제 workspace 원본과 새 확인 반영 검토 버전 확보·정식 schema/reference 검사·이전 버전 보존 확인. 전체 원본의 History 중복과 PDF 미검사를 별도 기록.
- [x] 기존 JD/resume 아티팩트 부재 확인. 사용자 선택 OpenAI FDE의 공식 서울 JD와 두 사실 기반 기본/맞춤 초안 준비. 부분 근거2·공백7.
- [x] 실제 사용자 문장·고정 버전·포함 범위 승인 후 검토 완료 기본/맞춤 v2와 handoff 생성·정식 검사 PASS. 원본·pending v1 보존.
- [x] 개인 OIDC 로그인·선택 파일 앱 가져오기·표시/검토·수동 저장/재개 사용성 확인. 사용자 중단 후 재연결·앱 종료/새 runtime에서 실제 SAF 세션 복원 PASS.
- [x] 승인 누적15회 안에서 첫 답변1개의 실제 AI/SAF result/ChatGPT 정식 재검토·파일 다운로드 왕복 PASS. 미응답5문항·신규 후보2개 별도 사실/사용 검토·운영API/배포는 미실행으로 구분.

## 실행 기록

기존 원본 4개를 선택 대화의 실제 UI 다운로드 요청/인증된 BrowserOS 응답으로 확보했다.
DOM 클릭/hover 전 포인터/로그인되지 않은 별도 HTTP403 실패를 기록했고 브라우저 세션의 파일 GET200으로 보완했다.
브라우저 다운로드 동작은 default로 복원했고 cookie/token/signed URL은 저장하지 않았다.
두 사실 사용자 확인은 수신했지만 실제 workspace 갱신은 파일 검증 전이다.
같은 ChatGPT 대화에 career-review 요청1회 전송, 기존 선택 기준을 자동 승격하지 않는 새 검토 버전과 원본 파일·비교 receipt를 요청했다.
host 응답 완료. 실제 workspace v5·v6·v7 및 보존 receipt·검토표·검사 결과 파일을 확보했다.
PC 원본 portable.py + 기존 jsonschema4.26.0으로 원본 해시, 이전 아티팩트, 다른43개 사실, 사용 허용·제약·기여 경계 불변을 확인했다.
전체 원본은 DUPLICATE_ID·ATTACHMENT_NOT_CHECKED로 integrity FAIL이며 실패를 보존한다.
최신 History가 이전 모든 operation을 그대로 포함하므로 별도 전체 후보의 중복만 해소했다. PDF 미검사는 유지한다.
면접 준비용 부분 view는 사용자 선택 두 사실·두 근거·관련 제약4개만 추출하며 첨부0개, 전체 profile 기준 선택 변경 없음.
검토 전 workspace/resume v1과 검토 후 v2를 별도 보존했고 실제 승인 내용으로 exporter/handoff 검사 PASS.
개인 자료는 저장소 밖 owner-only 파일에만 보관한다. 실제 휴대폰 가져오기·면접·결과 왕복은 아직 NOT_RUN.

사용자가 기존 누적 Codex 한도15회를 명시 승인했다. 같은 원장의 attempts11 유지·limit12→15만 잠금 하에 반영했다.
기본값12를 유지하는 명시적 runtime 옵션을 추가했으며 budget 경계8시험·면접 engine8시험 PASS.
추가 Codex0·유료API0·ChatGPT 개인 준비 요청1회. 새 외부 설치·등록/연결 설정 변경·배포 없음.
현재 ADB에 승인 대상 휴대폰이 없어 재연결·잠금 해제를 사용자에게 요청했다. 개인 runtime은 미시작 상태다.

## 휴대폰 연결 후 중단 지점 — 2026-10-12

사용자 재연결 후 폴드7/code4·잠금 해제 확인. 기존 개인 OIDC runtime을 loopback에 실행하고
승인한 USB reverse만 연결했다. 사용자가 같은 계정으로 로그인해 실제 앱/runtime 인증 통과를 확인했다.
선택 handoff만 휴대폰의 별도 개인 시험 폴더로 전달했으며 원본 bytes 일치 PASS.
실제 SAF 선택·앱 구조 검사·표시 digest/raw SHA·profile v7/맞춤 v2 일치 PASS.
사용자 승인 범위를 앱에서 검토하고 READY 세션으로 고정한 뒤 실제 SAF 세션 파일 저장 PASS.
저장 파일은 PC에도 비공개 보존했고 포함된 handoff 원본 일치·OIDC/READY·local reference restore 검사 PASS.
local restore는 재검토 필요 상태를 반환했다. 실제 휴대폰 재가져오기·강제 종료 후 복원 시험은 NOT_RUN이다.

사용자가 현재 작업만 마무리하고 휴대폰을 분리해 자리를 비우겠다고 요청했다.
진행 중인 저장만 완료하고 앱 연결 해제·RAM 비우기·앱 종료, 이번 reverse8765 제거·runtime 종료를 확인했다.
휴대폰과 PC의 handoff/세션 파일·원본·승인 기록은 보존했다. 기기 네트워크·화면 설정 변경 없음.
개인 AI 질문·답변·평가·result·ChatGPT 결과 재검토는 NOT_RUN, Codex11/15·이번 호출0·유료0 유지.
**사용자 요청에 따른 일시 중단.** 재개 시 휴대폰 재연결·기존 runtime/USB 연결 복원·필요한 같은 계정 로그인,
수동 세션 가져오기·범위 재검토/고정 후 실제 질문 생성·사용자 답변·결과 왕복 순서로 이어간다.
사실/용도/문장/고정 버전·15회 한도 승인은 재질문하지 않는다.
비공개 최신 상태: artifacts/personal-handoff-20261012/preparation-status-r3.json,
저장/검사와 정리 receipt는 같은 폴더의 phone-session-save-validation-r1.json, disconnect-checkpoint-r1.json.

## 확인이 필요한 경계

정확한 사실 문구, 이력서 문장, 기준 버전·handoff 포함 범위는 실제 사용자 검토로 기록한다.
새 외부 설치·등록/연결 변경·배포·유료 실행과 승인한 누적 Codex15회 초과는 실행 전 구체안을 확인한다.
개인 경력 사실을 추정하거나 합성 사실/자료를 개인 기준본으로 승격하지 않는다.
유료 API/운영 배포/무관한 경력 수집·다른 개인 대화는 자동 착수하지 않는다.

## 다시 재개한 진행 — 2026-10-12

사용자가 휴대폰 재연결·나머지 진행을 요청하여 이전 일시 중단을 해제했다.
같은 OIDC 설정/runtime/원장15·USB 연결을 복원하고 사용자 같은 계정 로그인 후 실제 저장 세션 SAF 복원 PASS.
REVIEW_REQUIRED와 고정 profile/resume·원본/계약 해시 일치, 두 사실의 실제 표시 문구를 확인했다.
첫 직접 문구 비교는 Android JSON의 escaped slash 때문에 실패했으며 표시 정규화 후 두 문장 일치 PASS.
실제 승인 범위를 다시 고정하고 면접을 시작했다.

실제 질문 생성 attempt12는 QUESTION_GAP_REFERENCE로 거부됐다. 모델 응답의 공백 질문이 참조를 포함한 경우다.
검사기는 유지하고 질문/후속의 gap=true 배열 비움·gap=false 사실/원문·부분 근거 연결 지시를 명확히 했다.
기존 합성 fixture로 혼합 공백 참조 거부·부분 근거·전체 batch 미반영·수정 재시도 경계 시험2개를 보충해 engine10시험 PASS.
시험 준비 시 빈 근거 mapping을 partial로 바꿔 INVALID_MAPPING이 난 검증 코드 오류를 수정했고,
저장 session의 최상위 records를 interview 키로 조회했던 검증 코드 오류도 보완했다. 앱 오류와 구분하여 보존한다.
실제 실패 세션 SAF 파일을 PC에도 비공개 보존한 뒤 runtime을 재시작하고 같은 파일을 재검토·고정했다.
actual attempt13에서 질문5개 생성·참조 검사 PASS. 한국어 기기 내 인식 준비를 확인하고 첫 질문의 실제 사용자 답변/확인/제출을 요청했다.
현재 Codex13/15·유료0. 답변 평가·result·ChatGPT 결과 재검토는 대기 중이며 성공으로 표시하지 않는다.

사용자가 실제 기기 내 음성 답변을 확인·제출했다. actual attempt14의 평가 PASS로 답변1·평가1·pending 후보2개를 생성했다.
이번 사용성 왕복은 첫 답변1개이며 총 질문6개(핵심5+후속1) 중 미응답5개를 전체 면접 수료로 표현하지 않는다.
실제 SAF result 저장·원래 handoff 대조·PC 정식 검사와 해시/ID/답변 참조/위조 후보 부정4사례 PASS.
추가 세션 export는 승인 한도 확장 후 events.attempt schema maximum12가 남아 SESSION_SCHEMA로 실패했다.
세션 내부0.1 규격의 상한15를 반영하고 13/14/15 기록 export/restore·16 거부 시험을 보충해 engine11시험 PASS.
자동화가 준비 실패 메시지 확인 없이 다음 저장을 진행하여 이전 result를 세션 r1 이름으로 저장한 것을 종류 대조로 발견했다.
잘못 이름 붙인 결과 사본을 실패 증거로 보존하고, 자동화는 준비 실패 시 후속 저장을 중단하도록 보완했다.
실제 정상 세션 r2 재준비/SAF 저장·41169bytes 검사·원본 bytes/실제13·14/역사12/기기 내 입력/quote 연결 PASS.
실제 휴대폰에서 r2를 재가져와 COMPLETED 상태 유지와 구조 검사 PASS를 확인했다.
result/session r1·r2를 같은 파일로 오인하지 않으며 이전 원본·실패 파일은 덮어쓰거나 삭제하지 않았다.

휴대폰 단계 종료 뒤 앱 연결/RAM·앱 실행·reverse8765·runtime을 정리했다. 저장 handoff/result/session은 PC/폰에 보존했다.
Codex14/15·이번 실제3회(실패1+질문 성공1+평가1)·유료0, 새 설치/등록/연결 설정 변경/배포 없음.
사용자 선택 ChatGPT 대화에 원래 handoff/result·원본 검사 코드와 manifest만 ZIP으로 첨부하여 interview-review 요청1회 실제 전송했다.
전체 session/owner/token/PDF/다른 사실은 ZIP에 포함하지 않았다. 기존 전체 profile 기준은 자동 변경하지 않는다.
개인 host 요청 누적2회(사실 검토1+결과 재검토1), 현재 host 검사 처리 중이다. host PASS는 아직 판정하지 않는다.

## 개인 첫 답변 왕복 수용 완료 — 2026-10-12

Host가 공급된 원본 검사 코드를 수정 없이 Python3.13.5/jsonschema4.26.0에서 직접 실행했다고 보고했다.
정상/부정4사례·import_result 복사본·입력 불변성 PASS이며, 실제 receipt/검토 Markdown 두 파일을
선택 대화 UI의 인증된 다운로드 GET200으로 확보했다. UI의 파일 링크가 streaming height에 가려져
DOM click/포인터가 작동하지 않아 완료된 응답 새로고침 후 정확한 파일 링크에 키보드 Enter를 사용해 보완했다.
두 파일 raw SHA가 Host 표기와 일치하고8개 manifest 파일·ZIP/manifest 해시·검사 stdout receipt가 PC 기준과 모두 일치했다.
Host가 PC 저장소/설치 플러그인 자체를 원격 감사한 것은 아니며, PC에서 확인한 코드의 동일 해시를 대조한 것이다.
검토 문서의 답변/후보 원문은 동일하며 피드백5행은 Markdown quote/빈 줄 표기만 달라 문장·순서 대조로 보존을 확인했다.

첫 ZIP은 PC 사전 검사에서 생성된 Python cache2개가 manifest 밖에 포함됐고 Host는 이를 추출/실행하지 않았다.
첫 ZIP과 host 수용을 그대로 보존하고 정확히 manifest8개+manifest.json만 담은 clean r2 ZIP을 추가했다.
원본 data/검사 code bytes는 동일하다. clean r2는 별도 Host 요청을 보내지 않았으며 추가 Host 실행 PASS로 표시하지 않는다.
최종 **선택 개인 자료의 첫 답변 실제 파일 왕복 PASS**. 답변1·평가1·pending 후보2개, 미응답5문항·새 후보의 사실/용도 검토는 별도 미실행.
원본45개 사실/기준 v5·이전 버전·금지/기여 경계 불변. 신규 후보/전사 표현을 자동 교정·기준본에 반영하지 않았다.
Codex14/15·이번3회(실패1 포함)·개인 host2회·유료API0. 앱/RAM/runtime/reverse 정리 완료, 파일과 승인 기록 보존.
이 후속의 남은 사용자 필수 수동 작업은 없다. 이후 새 후보를 경력에 반영하려면 전사/범위를 별도 확인한다.
상세 수용: [개인 실제 왕복 기록](docs/mock_interview_personal_roundtrip_20261012.md).

# CareerGround 08 개인 자료의 첫 답변 실제 왕복 — 2026-10-12

**선택 개인 handoff → 실제 휴대폰 저장/재가져오기 → 기기 내 음성 확인 답변 → 실제 Codex 평가 →
SAF result → 같은 선택 ChatGPT 대화의 정식 재검토 → 실제 검토 파일 다운로드 PASS.**
기존 합성 개발 수용의 후속 사용성 확인이며, 첫 답변1개의 왕복이다. 전체 면접/경력 인증/운영 배포 수용으로 확대하지 않는다.
원본·실패 증거·개인 원문/답변/근거/검토 파일은 저장소 밖 owner-only 폴더에 보존했다.

## 실행과 판정

| 항목 | 실제 관찰·검사 | 판정 |
| --- | --- | --- |
| 개인 자료 준비 | 실제 원본 선택, 기존 사실2개 확인·허용 보존, 문장·버전·포함 범위 사용자 승인, minimal handoff 정식 검사 | PASS |
| 원본 전체 workspace | 누적 History 중복·PDF 바이너리 미검사 유지; 부분 면접 준비본과 분리 | 기존 FAIL/제한 보존 |
| 기기 | Fold7 SM-F966N / Android16 / 기존 code4 APK, 같은 계정 OIDC, loopback·승인 USB 경로 | 실제 |
| 가져오기·표시·고정 | SAF handoff/수동 세션, 원본/digest·고정 버전·문구 대조, 재검토·READY 고정 | PASS |
| 중단 뒤 재개 | 사용자 외출 시 저장/정리 뒤 새 runtime/같은 계정으로 실제 READY 세션 복원 | PASS |
| 실제 질문 | 첫12회차 실패 보존; 보완 후13회차 핵심5문항 참조 검사 | PASS(실패 뒤 재시도) |
| 사용자 답변 | 기기 내 한국어 입력 후 사용자 확인·명시적 제출, 원문 변경 없음 | 답변1개 |
| 실제 평가 |14회차, 기준5개·답변 인용·pending 후보2개, 기존 경력 자동 반영 없음 | PASS |
| 결과 저장·대조 | 실제 native SAF result4207bytes, 원래 handoff와 정식 검사·부정4사례 | PASS |
| 세션 저장·재복원 | 내부 상한 보완 뒤 실제 r2 세션41169bytes·원본/레코드 검사·실제 COMPLETED 재가져오기 | PASS |
| 실제 host | 선택 대화에 원본 handoff/result·manifest·동일 검사 code만 공급. 직접 실행·정상/부정4사례, 두 검토 파일 실제 다운로드 | PASS |
| 새 후보 처리 | 두 후보는 pending, 별도 사실/사용 확인 없음. 원본·기존 기준·이력서/전달 자료 불변 | 자동 반영 없음 |

질문은 핵심5개와 후속1개 중 답변1개·미응답5개다. 모의 provider/답변으로 실제 실행을 대체하지 않았다.
11개 engine 회귀는 Mock-only이며 실제 AI 실행과 구분한다. 실제 provider 호출은 이번3회(실패1+질문1+평가1)다.
사용자가 승인한 같은 누적 원장14/15, 유료API0, 개인 준비/결과 host 요청 누적2회.

## 실제 파일 증거

| 파일 역할 | bytes | raw SHA-256 |
| --- | ---: | --- |
| 고정 handoff |23430|`4023298438e24e33b086b0c7747f1518ffc89d506b4143ba0c86a0c6ac7ba70b`|
| native result |4207|`a234692b2dd250ee095345feb2d34cfecd9df0c369aa6905fe2fd6230b583dd8`|
| 정상 completed session r2 |41169|`51f58d4e208358041e73ea9a57e536721881274b0783b85197799a4bcf29f269`|
| Host 정식 검사 receipt |10738|`0daf6126a3dc66f6b8d05d58e1e437c97ff8bcf657ba3a833814397289eb8faf`|
| Host 개인 검토 Markdown |15593|`b70c7bee86db14ab677fef183b25b1c02448bada59e02b850e45a72cc3577614`|

handoff canonical digest: `e3eb6d9fa321aecfaedd5cad23e1b5311eb8949ca42addda5ae0013252a722eb`.
개인 파일 위치: `~/.local/share/careerground-android/artifacts/personal-handoff-20261012/`.
다운로드한 Host 원본 두 개는 그 안의 `originals/`에 있다. 공개 기록에는 경력/전사/후보 원문·계정 정보를 복제하지 않았다.

Host는 공급된 reference code를 수정/재구현/축소하지 않고 Python3.13.5/jsonschema4.26.0에서 실행했다.
manifest8개 파일·ZIP/manifest·입력 hash 및 실제 stdout receipt가 PC 기준과 일치했다.
PC에서 저장소와 설치된 Portable0.2.0 reference byte 동일성을 독립 대조했다.
Host는 공급된 동일 hash를 확인한 것이며 원격 저장소/Host 설치 플러그인 자체를 감사하지 않았다.
Host가 앱/기기/사용량을 ZIP만으로 독립 인증했다고 표시하지 않는다. 기기는 PC/앱 관찰, Host는 파일 검사가 각각 근거다.

## 실패·보완과 제한

- 질문12회차: 공백 질문에 근거 참조가 포함돼 `QUESTION_GAP_REFERENCE` 거부. 검사기는 유지하고
  gap/partial/factual 및 후속 참조 지시를 보완했다. 혼합 batch 미반영·올바른 재시도 경계 시험 뒤 실제13회차 PASS.
- 세션 export: 한도 확장 시 내부0.1 events.attempt의 maximum12가 남아 `SESSION_SCHEMA` 실패.
  maximum15로 보완했다.13/14/15 export/restore·16 거부를 포함한 engine11시험 PASS, 실제 r2 저장/재가져오기 PASS.
- 저장 자동화: 준비 실패 확인 없이 진행해 이전 result가 세션 r1 이름으로 저장됐다. 해당 사본은 실패 증거로 보존하고 session으로 표시하지 않는다.
  준비 실패 시 후속 저장을 중단하도록 보완하고, 정상 파일은 별도 r2 이름·kind/schema/내용 대조로 확인했다.
- 검증 코드의 준비 오류: 빈 근거 mapping을 partial로 변경한 합성 fixture, session 최상위 records를 잘못 조회한 부분을 보완했다.
  미리보기는 escaped slash 표시, Markdown 피드백은 quote/빈 줄 포맷을 고려한 원문·행/순서 대조로 확인했다. 앱 오류와 구분한다.
- BrowserOS 다운로드: 포인터/DOM click이 가려진 링크에 작동하지 않았다. 완료된 대화 새로고침 후 정확한 파일 링크의 키보드 Enter와
  실제 인증 GET200으로 파일을 확보했다. Host 표기 raw SHA와 일치하며 새 Host 요청은 추가하지 않았다.
- 첫 ZIP에는 PC 사전 검사에서 생긴 manifest 밖 bytecode2개가 포함됐다. Host는 이를 추출/실행하지 않았고 제한으로 기록했다.
  원본 ZIP을 보존하고 manifest8개+manifest.json만 담은 clean r2를 추가했다. 동일 data/code bytes를 확인했고 새 Host 실행은 하지 않았다.
- 제출 전사는 일부 기술명·단계명·종료 조건이 불명확하다. 원문을 조용히 수정하거나 역량/성과 증거로 확정하지 않았다.
  개인 기획/검토/배포 새 범위는 두 pending 후보의 별도 사실/목적별 사용 검토에 남는다.

Portable handoff/result1.0·APK code4는 변경하지 않았다. 앱 내부 draft session0.1의 event 상한과 runtime prompt만 보완했다.
개인 기간·성과·현재 Worker 연결·저작 외부 검증·회사 정책 승인, PDF 전체 묶음, 모든5문항 답변,
새 후보 사실/사용 확인·전체 profile 기준 변경·운영API·공개 배포는 이번에 수행하지 않았다.

## 보관과 다음 상태

앱 연결/RAM·앱 실행·reverse8765·loopback runtime을 정리했다. PC/휴대폰의 선택 handoff·result·세션과
원본/실패 파일·승인 기록은 보존했다. 기기 네트워크/화면 설정 변경·새 설치·등록/연결 설정 변경·배포는 없다.
재개용 정상 파일은 `careerground-session-personal-completed-r2.json`이다. 잘못 이름 붙은 r1은 사용하지 않는다.
기존 승인과 원장15회 한도는 유지한다. 이후 전체 면접을 진행하려면 잔여1회와 필요한 평가 횟수의 한도를 먼저 검토한다.
새 후보를 경력에 반영하려면 검토 문서의 전사 표현·개인 개발/검토/배포 범위를 별도 사실·사용 검토로 확인한다.
이번 첫 개인 답변의 실제 왕복에는 남은 필수 작업이 없다.

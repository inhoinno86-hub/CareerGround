# CareerGround 08 앱 현재 수용·재개 지점 — 2026-10-11 r2

**STEP 01 승인 / STEP 02 수용 / STEP 03 실제 면접·결과 파일 PASS, 오프라인 음성 미검증 /
STEP 04 실제 ChatGPT 재검토 관찰, 호스트 정식 검사 미완료. 전체 완료는 아니다.**

[구조화 기록](mock_interview_app_acceptance_20261011_r2.json),
[승인 계획](../PLAN-2026-10-10-mock-interview-app.md),
[음성 보완·이전 실패](mock_interview_voice_continuation_20261011.md)를 함께 따른다.
이전 수용 기록은 그 당시의 실행 결과로 보존한다. 실제 개인 경력은 제공되지 않았으며 합성 자료만 사용했다.

## 실제 실행 결과

- Fold7 SM-F966N / Android 16, 앱 **0.2.1-step03-voice(code 4)**.
  사용자가 수정 후 긴 한국어 발화를 수행하고 이상 없음을 확인했다. 앱 초안에서도 마지막 문장을 확인했다.
  이전 조기 종료 FAIL은 해결 이력으로 남긴다. 실제 발화 길이와 recognizer 내부 종료 시간은 미계측이다.
- 원 초안에는 기존 영어 답변과 두 번의 한국어 시험이 누적됐고 일부 단어 오인식이 있었다.
  원 전사는 비공개 artifact에 별도 보존했다. 합성 기준 문장에 맞춰 중복·오인식을 정리한 영어 답변으로
  명시 수정·확인·제출했다. 결과의 영어 답변은 한국어 전사의 원문이라고 주장하지 않는다.
- 실제 Codex 11회째 평가 PASS. 현재 답변 revision 3, input_kind=on_device_confirmed.
  5항목 평가·후속 질문 1개·pending 후보 1개를 생성했다. 직접 기여와 동료 배포 실행, 미측정 성과,
  Kubernetes 근거 공백을 유지했다. 이전 답변·평가·후보는 stale이며 현재 result에서 제외한다.
- 실제 finish 200·COMPLETED, result/export 200, Android SAF로 두 파일 저장 PASS.
  휴대폰 파일을 PC로 읽어 정식 schema·참조·validate_result/import_result 검사 PASS.
  완료 세션 파일의 실제 SAF 재가져오기와 동일 계정 검증 200 PASS. 완료 상태를 유지하며 면접을 재개시키지 않는다.
- 해시/ID 충돌, 없는 답변 참조, approved 후보 위조 4개를 실제 로컬 검사기가 거부했다.
  이번 Portable 회귀 **35 PASS**. 변경 없는 앱의 기존 Python 44/JVM 10/실기기 instrumentation 9 PASS와
  lint 오류 0·경고 8은 이전 실행 결과이며 이번에 전부 재실행했다고 표현하지 않는다.

## 저장한 파일

휴대폰: `Download/CareerGround-step02-20261011-130033/`.
PC: `/home/inno/.local/share/careerground-android/artifacts/step03-20261011/`.
두 위치의 명시적 수동 파일을 보존했다. 앱 자동 저장 기능을 추가한 것이 아니다.

| 파일 | bytes | SHA256 |
| --- | ---: | --- |
| `careerground-result-step03-fold7-r1.json` | 2,373 | `2d9f38c8f4526e56ff5adbb3efc148897a12b877314df1eec533db62c941864e` |
| `careerground-session-step03-fold7-r1.json` | 22,568 | `bd306c323f5703f7ee3a18aca86b783649245cfecd4af59e214ebc298f906a92` |
| `careerground-session-step03-voice-ready-r1.json` | 18,884 | `b672ca71e9dfe347bbb68edac2d0b770600203d826f387cde39c6eccf590b670` |

result: 현재 확인 답변 1·AI 평가 1·pending 후보 1.
세션: 질문 8·답변 3·평가 3·후보 3·이벤트 4; 이전 답변/평가/후보 각 2개 stale.
원래 `handoff-v1.json` raw SHA256는 `11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8`,
canonical digest는 `a1ca01fb34e8c6c8a5cf5a3bb2e54b32227d05d9076aa77d1de642b70fd1edd1`로 유지했다.
profile-synthetic v3 / jd-synthetic v1 / resume-jd-synthetic v1을 자동 갱신하지 않았다.

unsigned 세션을 다시 가져오면 과거 AI 평가·후보는 stale, 이벤트는 imported_unverified가 된다.
완료 세션은 기록 확인에 사용한다. **기존 최종 result를 그대로 보존하며, 재가져온 기록으로 다시 만든 결과를
원래 실제 AI 결과와 동일하다고 취급하지 않는다.** 음성-only 후속 시험은 별도 voice-ready 파일을 가져와 재검토·시작한다.

## 실제 ChatGPT 왕복

사용자가 BrowserOS ChatGPT 로그인 완료를 알렸다. 기존
[CareerGround Portable 0.2.0 / 스킬 8개](https://chatgpt.com/plugins/Plugin_47a97bf406048191a8a671f47778376a)에
접근했으며 새 플러그인 설치나 연결 변경은 하지 않았다.
[이번 합성 재검토 대화](https://chatgpt.com/c/6acb999c-2fac-83ec-b5e5-2aecaf3156b4), 표시 모델 GPT-6.1 Sol / Light.
원래 handoff와 실제 휴대폰 result 두 파일을 첨부하고 **interview-review 1회 요청**을 실행했다.

호스트 응답에서 실제 파일 읽기·raw/canonical hash 계산·고정 참조 대응·답변 참조와 pending을 관찰했다.
user_answer/model_feedback/pending 후보를 분리하고,
“I incorporated teammate feedback into the item order and kept review notes.”를 별도 사실 확인·사용 허용 전
미확인 후보로 유지했다. 기존 profile/resume/handoff 생성·덮어쓰기·금지 해제·자동 승인은 하지 않았다고 응답했다.
별도 사실 검토에서는 두 행동의 기간·직접 기여를, 사용 검토에서는 기본/맞춤 이력서·면접 목적을 각각 확인하도록 안내했다.

**호스트의 정식 schema/reference 검사는 ATTEMPTED / VALIDATOR_UNAVAILABLE다.**
두 호스트 Python 환경에 jsonschema가 없어서 완료하지 못했다. 입력 파일 오류나 정식 검사 PASS로 바꾸지 않았다.
PC 정식 검사 PASS와 호스트 파일 읽기·참조 검토 PASS를 분리한다. 추가 설치·유료 호출·자동 모델 재시도는 하지 않았다.
호스트는 `interview-review-receipt-step04.json` 파일을 생성했다. BrowserOS download 도구 실패는 별도 기록하며
PC에 실제 내려받은 receipt로 계산하지 않는다. 응답 원문·대화 URL은 비공개 artifact에 보존했다.
후보의 사실/사용을 아직 승인하지 않았으므로 호스트의 새 profile 버전 생성 경로도 NOT_RUN이다.

## 남은 검증과 재개 방법

남은 항목은 네트워크를 끈 실제 한국어 음성-only 시험, 호스트 정식 검사 환경 보완·재검토,
별도 사실/목적별 사용 확인 후 새 버전·이전 버전 보존 여정이다. 개인 handoff 사용성·에뮬레이터·배포·
OpenAI API·유료 실행은 미실행이다. 사용자 실제 경력 확정을 기다리며 합성 개발을 멈춘 상태는 아니다.

현재 수동 파일 저장과 완료 세션 복원을 마친 뒤 앱 연결 해제·RAM/token 비우기를 실행했다.
승인 기기의 tcp:8765 reverse를 제거하고 PC loopback runtime을 종료했다. Wi-Fi/모바일 데이터는 각 1,
USB 화면 유지 설정은 원래 0으로 재조회했다. 휴대폰 파일은 삭제하지 않았다. **USB를 분리해도 된다.**

다음에 휴대폰을 연결하고 “CareerGround 08 재개, 이 r2 기록부터 이어서 진행”이라고 알리면 된다.
에이전트는 이 문서·계획 25절·비공개 증거를 읽고 기존 승인 범위로 runtime/reverse를 다시 준비한다.
사용자는 필요할 때 잠금 해제·같은 계정 로그인·직접 발화만 수행한다. 완료 파일은 기록 확인에,
voice-ready 파일은 남은 음성-only 시험에 선택한다. 원본/고정 버전/사용 금지/기여 경계를 그대로 유지한다.

실제 Codex는 **11/12회**, 실패·재시도를 포함한 기존 원장을 재사용한다:
`/home/inno/.local/share/careerground-android/artifacts/codex-step03-20261011/calls.json`.
새 원장으로 한도를 초기화하지 않는다. ChatGPT 호스트 요청 1회는 별도이며 추가 구독 사용량이 발생했다.
한도 오류가 나면 자동 재시도하지 않는다. 외부 설치·등록/연결 변경·배포·유료 실행과 기존 승인 초과 호출은
구체적으로 준비한 뒤 확인한다. 기존 작업 트리와 실패 증거를 보존했고 commit/push/merge는 하지 않았다.

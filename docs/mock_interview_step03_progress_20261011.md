# STEP 03 구현·부분 검증 — 2026-10-11

**STEP 02 수용 / STEP 03 부분 검증 / STEP 04 NOT_RUN.**
최신 음성 조기 종료 실패와 0.2.1 보완은 [후속 기록](mock_interview_voice_continuation_20261011.md)을 따른다.
실제 개인 로그인·세션 파일 왕복은 [STEP 02 수용 기록](mock_interview_oidc_device_20261011.md)을 따른다.
사용자는 같은 계정의 재로그인과 앱 복귀를 완료했고, 수정된 auth_mode=oidc 파일의 저장·복원을 확인했다.
이후 승인 계획에 따라 합성 자료로 STEP 03을 진행했다. 개인 경력 파일은 사용하지 않았다.

## 판정과 남은 작업

| 범위 | 판정 | 실제 관찰과 한계 |
| --- | --- | --- |
| 격리 filesystem | PASS | 프로젝트·canary·사용자 config·AGENTS·셸/Python 경로가 보이지 않음. 기존 auth 파일 읽기 가능/쓰기 불가. 네트워크 없는 별도 사전 시험 |
| 기존 Codex 로그인 | PASS | static CLI 0.162.1의 격리된 login status와 실제 구조화 응답. 기존 로그인·HOME/CODEX_HOME 변경 없음 |
| 명령 삽입 합성 시험 | PASS, 제한된 관찰 | 파일 읽기·셸·허구의 단독 배포/80% 절감 지시를 무시하고 기간·공동 기여·미측정 조건을 유지한 질문. 관찰된 도구 이벤트 0 |
| 실제 PC 면접 엔진 | PASS | 핵심 5질문, 근거 공백 질문, 한 확인 답변의 5항목 평가·후속 1개·새 사실 pending 1개 생성 |
| PC 생성 result 1.0 | PASS | validate_result 오류 0, import_result 반환 일치. 이 결과는 휴대폰 SAF나 ChatGPT 호스트 검증이 아님 |
| Python | PASS 44 | 기존 가져오기/인증 30 + Codex 경계 6 + Mock 면접 상태/수정/재개/오류 8. Mock 시험은 실제 AI 시험과 별개 |
| 기존 Portable 교환 | PASS 7 | handoff/result 1.0 변경 없이 기존 importer 검증 |
| Android 빌드/JVM/lint | PASS | offline r1/r2 빌드, JVM 2개, lint 오류 0/경고 8. 기존 전용 캐시만 사용 |
| 새 APK 설치 | PASS | 동일 개발 인증서의 0.2.0-step03, code 3. 기존 code 2 APK를 먼저 보존 |
| 한국어 기기 내 STT 준비 | PASS 조회만 | 실제 SM-F966N의 createOnDeviceSpeechRecognizer/checkRecognitionSupport에서 한국어 설치 준비 확인. 녹음·전사 성공은 NOT_RUN |
| 한국어 로컬 TTS 준비 | PASS 조회만 | 네트워크 불필요·설치된 한국어 voice 선택 가능. 실제 소리 재생은 NOT_RUN |
| Android instrumentation | PASS 6/6 재시험 | r2는 잠금 상태에서 1/6 실패. 사용자가 잠금을 해제한 뒤 동일 APK r3에서 6개 모두 통과. 첫 실패 로그 보존 |
| 휴대폰 실제 AI·텍스트 수정 | PASS | OIDC 앱 복귀, 고정 합성 handoff 가져오기/검토/시작, 실제 5질문, v1/v2 답변 평가. 수정 뒤 구평가/후보/후속 제외, 미평가 완료 요청은 FEEDBACK_REQUIRED 409 |
| 마이크 거절 후 텍스트 대안 | PASS | 실제 Android 권한 UI에서 거절 후 텍스트 v2 수정·명시적 제출·실제 평가 가능 |
| 휴대폰 전사 확인·result SAF 왕복 | NOT_RUN | 음성 직접 발화 대기, 최종 result/session SAF는 후속 |
| ChatGPT 플러그인 재검토 | NOT_RUN | STEP 03 기기 수용 후 STEP 04 진행. PC importer 통과로 대체하지 않음 |

사용자가 잠금 해제와 OIDC 앱 복귀를 완료했다. 실제 앱 질문 생성(8회째), v1 평가(9회째),
v2 수정 평가(10회째)가 통과했다. 이전 평가/후보는 수정 뒤 화면에서 제외됐으며 미평가 상태의
완료 요청은 409로 거부됐다. 마이크 권한 거절 뒤 텍스트 대안도 실제 기기에서 확인했다.

현재 필요한 수동 작업은 **질문 읽기 소리 확인과 합성 한국어 문장의 직접 발화·전사 초안 확인**이다.
승인한 음성-only 계획대로 휴대폰 Wi-Fi·모바일 데이터를 임시 해제했다(각 0 확인).
PC/USB 연결을 유지했고 active default network=none도 관찰했다. 직접 발화 완료 확인이 없어
Wi-Fi·모바일 데이터는 원래 값으로 복원·재조회했다. 실제 발화·재생·오프라인 전사는 아직 미실행이다.
USB 화면 유지 설정도 원래 값 0으로 복원·재조회했다. 앱/면접 RAM 세션과 loopback runtime은 유지한다.

## 구현한 동작

- 선택·허용된 고정 사실/출처·검토 문장·JD 요구사항·기여/제외 제약·목표만 AI context로 만든다.
  전체 workspace/history·연락처·첨부 원시 파일·JD 속 URL/명령은 실행하지 않는다.
- 질문을 JD/fact/source/sentence 또는 명시한 공백에 연결한다. 기본 핵심 5개, 후속은 핵심별
  현재 답변에서 최대 1개, 추적 기록 전체 10개 이내다. 건너뛰기·조기 종료를 제공한다.
- 확인된 사용자 답변과 AI 피드백/pending을 분리한다. 수정은 새 answer ID/revision을 만들고
  이전 평가·후보 및 이전 답변에 의존한 후속 질문/답변을 stale로 제외한다.
- 5개 평가 기준은 JD 대응, 행동·근거, 직접·공동 기여, 기간·수치 일관성, 설명 명료성이다.
  실제 답변의 정확한 인용을 검사하며 candidate는 원문에서 직접 발췌한 pending만 허용한다.
- 코칭은 현재 평가를 표시하고 모의 면접은 종료까지 평가·후보를 숨긴다. 완료는 최신 확인 답변의
  평가가 준비돼야 하며 미평가 상태에서도 중단 후 부분 result 내보내기가 가능하다.
- 모델 응답은 schema/참조 검사를 통과해야 반영한다. 오류·한도·중복 동시 호출은 정상 답변으로
  저장하지 않는다. 중지/재개·답변 수정·로그아웃 뒤 늦은 결과는 폐기한다.
- 수동 session 0.1 초안에 질문/답변 revision/평가/후보/요청 메타데이터를 담고 Portable result 1.0은
  그대로 유지했다. 재가져온 unsigned 파일은 다시 검토하며 과거 AI 평가를 stale로 제외하고
  호출 provenance를 imported_unverified로 표시한다. 원래 경력/이력서를 수정하지 않는다.
- Android 음성은 기기 내 recognizer만 사용한다. 초안 확인/수정 후 명시적 제출하며 부분 전사나
  confidence는 평가하지 않는다. 최대 120초, 중지 결과 대기 5초 후 취소한다. 화면 이탈/중단/로그아웃
  시 취소하고 원음/전사를 자동 저장하지 않는다. 로컬 TTS만 선택하고 음성 시작 전에 읽기를 멈춘다.

## 실패·보완 이력

1. 실제 사전 호출 1–3은 정상 구조화 응답과 함께 Code Mode 호스트 비활성 진단을 반환했다.
   code_mode 계열을 명시적으로 끈 뒤에도 CLI 0.162.1에서 동일 진단이 발생했다.
   시작 전의 정확한 진단 1개만 별도 집계하고, 다른 오류·알 수 없는 이벤트·도구 이벤트는 거부한다.
   이를 없애려고 도구 호스트 설치나 권한 확대를 수행하지 않았다.
2. 실제 PC 엔진 최초 요청(5회째)은 제공자 schema 오류로 거부됐다. 실패 기록을 보존했다.
   wire schema에서 uniqueItems를 제외하고 응답의 전체 로컬 schema 검사는 유지했다.
   그 변경 후 실제 6회째 기본 질문, 7회째 평가와 result 생성/검사를 통과했다.
3. 새 Android 시험에서 시작 화면의 Compose hierarchy를 찾지 못했다. 당시 화면은 Dozing/잠금
   상태였다. 화면 깨우기/일반 dismiss로 앱이 나타나지 않아 사용자 잠금 해제를 요청했다.
   실패 로그는 보존했다. 사용자 잠금 해제 후 동일 APK의 r3에서 6/6 통과해 화면 상태 원인을 분리했다.

## 비용·격리·자료 보존

총 실제 CLI 요청은 **10/12회**다. 사전 시험·실패·재시도를 모두 포함한다. 동시 호출은 1개로
제한하고 owner-only 호출 원장의 lock/횟수를 사용해 runtime 재시작으로 한도가 초기화되지 않게 했다.
추가 구매·OpenAI API key·유료 API 호출은 0이다. 구독 사용량을 무료/무제한이라고 표현하지 않는다.
면접 요청 model은 기존 개발 설정과 같은 `gpt-6.1-sol`을 명시했다. CLI 이벤트는 서버 resolved model ID를
반환하지 않아 요청 ID와 실제 실행 여부를 기록한다. 사전 호출 1–2의 기본 model resolved ID는 미확인이다.

기존 static CLI·bubblewrap만 사용한다. 빈 mount/PID namespace에 CLI·읽기 전용 auth 파일과
TLS/DNS/비개인 출력 schema만 제공한다. API key/proxy/사용자 설정과 프로젝트 파일은 전달하지 않는다.
요청/응답은 파이프/RAM, child cache는 tmpfs이고 운영 원장에는 횟수 메타데이터만 저장한다.
filesystem 사전 시험·도구 이벤트 0 관찰은 위 범위의 증거이며 모든 공격에 대한 완전한 증명은 아니다.

기존 handoff bytes SHA256 `11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8`,
canonical digest `a1ca01fb34e8c6c8a5cf5a3bb2e54b32227d05d9076aa77d1de642b70fd1edd1`,
profile v3/JD v1/resume v1과 기존 작업 트리·플러그인·과거 시험 파일을 보존했다.
새 외부 의존성 설치·제공자 등록 변경·배포·유료 실행은 수행하지 않았다.

합성 시험 artifact root는 `/home/inno/.local/share/careerground-android/artifacts/step03-20261011/`이다.
APK·PC 합성 result/session·실패 기록을 별도 이름으로 보존하며 인증 token·이메일·기기 serial은 보고서에 없다.
STEP 03 runtime은 loopback 127.0.0.1:8765로 실행 중이며 해당 승인 기기의 USB reverse만 연결했다.
사용자의 진행 중인 브라우저 callback을 위해 loopback runtime과 해당 reverse를 대기 상태로 유지한다.
추가 AI 자동 호출은 없고, 임시 화면 유지·통신 설정은 원래 값으로 복원했다. 공개 listen 포트는 없다.

## 확인한 공식 문서

[Codex CLI](https://learn.chatgpt.com/docs/cli/reference),
[ephemeral 실행](https://learn.chatgpt.com/docs/non-interactive-mode),
[Codex 설정](https://learn.chatgpt.com/docs/config-file/config-reference),
[구조화 출력 지원 범위](https://developers.openai.com/api/docs/guides/structured-outputs),
[Android SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer),
[RecognitionSupport](https://developer.android.com/reference/android/speech/RecognitionSupport).
문서 지원과 위 실제 기기/모델 실행 증거를 구분한다.

## 최신 실행·재개 지점

이 문서의 이전 NOT_RUN/실패는 해당 시점 기록으로 보존한다. 이후 사용자 긴 발화 재시험,
최종 휴대폰 result/session SAF와 PC 정식 검사, 실제 ChatGPT 재검토를 실행했다.
호스트 정식 checker의 jsonschema 부재, 오프라인 음성·새 버전 생성 경로 미실행과 안전한 USB 분리 후 재개는
[r2 수용 기록](mock_interview_app_acceptance_20261011_r2.md)을 따른다.

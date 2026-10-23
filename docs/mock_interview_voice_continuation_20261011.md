# 한국어 전사 조기 종료 보완 — 2026-10-11

**구현·빌드·기기 회귀 PASS / 수정 후 긴 발화 재시험 NOT_RUN. STEP 03 부분 검증 / STEP 04 NOT_RUN.**
[구조화 기록](mock_interview_voice_continuation_20261011.json),
[이전 STEP 03 진행 기록](mock_interview_step03_progress_20261011.md)을 함께 따른다.
합성 자료로만 시험했으며 실제 사용자 경력·비밀번호·token을 시험 자료에 넣지 않았다.

## 실제 실패와 원인

사용자는 Fold7에서 한국어 전사 반환과 질문 읽기 소리를 확인했다. 다만 문장을 계속 읽는 중에
전사가 끝나 뒷 문장이 누락됐다고 보고했다. 앱에서도 첫 문장만 있는 미확인 초안과 완료 상태를
관찰했다. 해당 초안을 답변으로 제출하거나 평가하지 않았다.

기존 `DeviceVoice.onResults`가 첫 최종 결과를 받자마자 `listening=false`로 처리했다.
따라서 인식 서비스의 한 발화 종료를 면접 답변 전체 종료로 취급한 것이 앱 측 원인이다.
기기가 해당 시점에 발화를 종료한 정확한 내부 이유·무음 시간은 계측하지 않아 단정하지 않는다.
기존 120초는 상한 타이머였으며 기기 서비스가 120초 동안 계속 듣도록 보장하는 설정이 아니었다.

Android는 지원하는 서비스에 segmented session을 요청하고 문장 구간을 별도로 받을 수 있지만
관련 extra가 서비스에 따라 무시될 수 있다.
[RecognizerIntent 공식 문서](https://developer.android.com/reference/android/speech/RecognizerIntent),
[구간 콜백](https://developer.android.com/reference/android/speech/RecognitionListener)을 확인했다.

## 수정한 동작

- 기기 내 recognizer에 segmented session과 4초 종료 무음 설정을 요청한다. 부분 가설은 교체하고
  확정된 구간을 누적한다. 서비스가 최종 집계도 반환할 때 같은 구간을 두 번 추가하지 않는다.
- 서비스가 단일 발화 결과로 종료하면 앱의 녹음 창은 유지하고 terminal callback 이후 200ms 뒤
  같은 기기 내 recognizer로 이어 듣는다. `onEndOfSpeech`만으로 재시작하지 않는다.
  [SpeechRecognizer 호출 순서](https://developer.android.com/reference/android/speech/SpeechRecognizer)를 따른다.
- 사용자의 **인식 마치기**, 취소, 화면 이탈이 계속 듣기보다 우선한다. 재연결 중 중지도 새 인식을 막는다.
  마지막 결과는 최대 5초 기다리고, 늦은 이전 콜백은 초안에 반영하지 않는다.
- 전체 120초 제한은 구간별로 초기화하지 않는다. 최대 32회 인식 시도, 연속 무음/불일치 오류 3회로
  반복을 제한하며 다른 오류는 초안을 남기고 종료한다. 클라우드 전사·음성 파일 저장·자동 제출은 없다.
- 재연결 사이에는 짧은 음성 공백이 가능하므로 초안 확인 안내를 표시한다. 단순 시간 설정만으로
  무손실 연속 인식이 보장됐다고 설명하지 않는다. 실제 긴 한국어 답변 수용은 재시험으로 판정한다.

## 수동 대기 중 세션 만료와 보존

수동 음성 입력을 기다리는 동안 기존 runtime 세션의 30분 TTL이 경과했다.
일반 export 요청은 실제 `SESSION_UNAVAILABLE` 404로 거부됐다. 정상 SAF 내보내기 PASS가 아니다.
앱 RAM에 남아 있던 합성 화면 report·원래 선택 handoff bytes·미확인 전사 초안만 별도 보존했다.
전용 debug 앱에서 해당 getter만 읽었고 client/token/인증 필드는 조회하지 않았다.
임시 loopback JDWP forward는 제거하고 debugger를 분리했다.

이전 동일 계정의 수동 OIDC 세션 파일에서 opaque owner binding을 재사용해 **명시적 복구 파일**을
별도 이름으로 만들었다. 이는 소유권·AI provenance 증명이 아니다. 원래 handoff bytes 일치,
내부 session schema와 참조 검사, fresh REVIEW_REQUIRED, 가져온 과거 평가 stale 및
이벤트 imported_unverified 처리까지 로컬에서 통과했다. 기존 확인 답변 2개와 질문 7개를 보존했고
미확인 전사 초안은 답변에 넣지 않았다. 복구 파일을 phone 시험 폴더에 복사했으나 실제 앱의
동일 계정 검사·가져오기/SAF 왕복은 로그인 복귀 후 확인한다.

향후에는 runtime 만료 뒤에도 앱 RAM의 **현재 화면 기록으로 복구 파일 준비**를 선택할 수 있게 했다.
일반 export의 SESSION_UNAVAILABLE에도 이 경로를 제공한다. 자동 파일 저장이나 TTL 연장이 아니다.
원래 handoff·현재 확인 답변과 화면 기록만 담으며 미제출 초안·모의 면접에서 숨긴 평가는 제외한다.
재가져오기는 정확한 원본/owner/기록 검사와 새 범위 검토가 필요하고 가져온 AI 평가는 stale다.
만료된 이전 세션 삭제 404 때문에 새 파일 선택까지 막히던 경로도 보완했다.

## 검증 결과와 미실행

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| 기존 실제 전사/TTS | 부분 PASS + 조기 종료 FAIL | 사용자 발화·청취와 native 초안 관찰. 오프라인 성공은 미확인 |
| Kotlin JVM | PASS 10 | 기존 2 + 연속 구간/명시 중지/늦은 콜백/고정 상한/부분 전사/길이 8 |
| Fold7 instrumentation | PASS 9 | 기존 6 + 수동 RAM snapshot 3. 실제 녹음 재시험을 대신하지 않음 |
| Python | PASS 44 | 기존 Mock/Codex 경계/인증/세션 계약 회귀. 실제 AI 신규 호출 아님 |
| offline 빌드/lint/Ruff | PASS | lint 오류 0·경고 8. 새 외부 의존성 없음 |
| 복구 파일 구조/참조/importer | PASS 로컬 | 정상 SAF export와 구분. 원래 고정 bytes 보존 |
| 수정 후 긴 한국어 발화/오프라인 음성 | NOT_RUN | 직접 발화 필요 |
| 최종 result SAF·ChatGPT 재검토 | NOT_RUN | STEP 03 기기 수용 뒤 순차 진행 |

설치 APK: **0.2.1-step03-voice / code 4**.
SHA256 `fb8018604ccbdccf00b36a0639aa85b69a7886d7feb5c1698aa720176c3753e4`.
이전 APK·실패 증거·원본·작업 트리는 보존했다. 실제 Codex는 여전히 **10/12회**, 유료 API 0회다.

합성 artifact root: `/home/inno/.local/share/careerground-android/artifacts/step03-20261011/`.
새 로그인 요청으로 실제 앱 복귀·runtime 사용자 검증을 통과했다. 수정 후 긴 발화 재시험을 기다린다.
개발 runtime/USB reverse는 이어서 쓰도록 유지하며 공개 배포·등록 변경은 하지 않았다.

USB 화면 유지 설정과 휴대폰 통신 설정은 원래 값으로 복원·재조회했다. 앱 로그인 callback을 위해
loopback runtime/승인 기기 reverse만 대기 상태로 유지한다. 추가 AI 자동 호출은 없다.

## 로그인 오류와 새 요청 복구

수정 APK의 로그인 화면에서 실제 `invalid_request`가 발생했다. Auth0 상세 화면은 로그인
transaction session을 찾지 못했다고 안내했다. 만료·브라우저 이동·cookie 문제 가운데 정확한
계기는 미확인이다. 기존 Custom Tab을 닫고 앱의 개인 계정 로그인으로 새 요청을 시작하자
앱 복귀와 실제 `/v1/status` 200, OIDC runtime 사용자 검증을 통과했다. 등록/연결 설정 변경,
cookie 삭제, 앱 데이터 삭제, PKCE/state/nonce 완화는 하지 않았다.
[Auth0 공식 오류 안내](https://support.auth0.com/center/s/article/Users-occasionally-see-an-error-You-may-have-pressed-the-back-button)는
이전 로그인 흐름을 재사용할 수 없을 때 앱에서 새 인증 흐름을 시작하도록 설명한다.

보존한 합성 복구 파일은 실제 동일 계정에서 restore 200·REVIEW_REQUIRED, 범위 재검토·고정·시작을
통과했다. 이후 새 APK의 **현재 화면 기록으로 복구 파일 준비 → SAF 저장**을 실제 실행했다.
`careerground-session-step03-voice-ready-r1.json`은 18,884 bytes,
SHA256 `b672ca71e9dfe347bbb68edac2d0b770600203d826f387cde39c6eccf590b670`다.
휴대폰에서 다시 읽어 session schema·고정 원본 bytes·참조 검사 PASS. 과거 평가/후보 stale,
가져온 AI 이벤트 imported_unverified를 유지했고 미제출 초안은 제외했다. 이는 정상 runtime
export 또는 최종 result 생성과 구분하는 명시적 RAM 복구 파일이다.
수정 후 긴 발화·오프라인 전사·최종 result/ChatGPT 왕복은 여전히 NOT_RUN이다. 추가 AI 호출은 없다.

저장한 새 복구 파일을 실제 SAF로 다시 선택해 동일 계정 restore 200·REVIEW_REQUIRED,
새 범위 확인·고정·IN_PROGRESS까지 왕복했다. 새 파일의 기기 내 저장·재가져오기 PASS이며
최종 면접 result와 실제 AI 재평가는 아직 실행하지 않았다.

## 최신 실행·재개 지점

이 문서의 이전 NOT_RUN/실패는 해당 시점 기록으로 보존한다. 이후 사용자 긴 발화 재시험,
최종 휴대폰 result/session SAF와 PC 정식 검사, 실제 ChatGPT 재검토를 실행했다.
호스트 정식 checker의 jsonschema 부재, 오프라인 음성·새 버전 생성 경로 미실행과 안전한 USB 분리 후 재개는
[r2 수용 기록](mock_interview_app_acceptance_20261011_r2.md)을 따른다.

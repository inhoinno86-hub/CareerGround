# CareerGround 08 앱 왕복 수용 — 2026-10-12

**핵심 실기기·실제 AI·파일·ChatGPT 왕복 PASS. 폴더블 에뮬레이터의 합성 화면·파일·복원 보충 검사를 완료했다. 자동 접힘 표시 전환·에뮬레이터 실제 음성 등 환경 제한은 별도 기록한다.**
실제 사용자 경력 품질·운영 배포·OpenAI API 수용은 포함하지 않는다.
[구조화 기록](mock_interview_app_acceptance_20261012.json),
[이전 수용과 실패](mock_interview_app_acceptance_20261011_r2.md),
[승인 계획](../PLAN-2026-10-10-mock-interview-app.md)을 함께 보존한다.

## 실제 실행과 모의 시험

| 대상 | 판정과 증거 |
| --- | --- |
| STEP 01 | 기존 승인 유지. 선택 재질문·한도 초기화 없음 |
| STEP 02 | 기존 개인 로그인·고정 자료·SAF·회전/접힘 수용 유지. 오늘 같은 계정 복귀 및 voice-ready 세션 가져오기200 → fresh REVIEW_REQUIRED → 검토 READY → 시작 IN_PROGRESS PASS |
| STEP 03 | 이전 code4 실제 Codex 질문·답변 수정/음성 확인·평가·result SAF 수용 유지. 오늘 실제 오프라인 한국어 발화 PASS. 오늘 새 Codex 호출0 |
| STEP 04 | 실제 앱 결과+원래 handoff를 기존 ChatGPT interview-review에서 정식 검사. 별도 사용자 사실/사용 선택 후 career-review로 새 profilev4·이전v3 보존, 실제 파일 다운로드·독립검사 PASS |
| 에뮬레이터 | 승인한 설치 및 합성 화면/수정/중단/파일/복원 PASS. 자동 접힘 표시 전환·실제 음성 등 환경 제한 별도 기록 |
| 개인 경력·운영 배포 | 실제 개인 handoff 미제공. 배포/API/유료 실행 NOT_RUN |

앱은 Android **0.2.1-step03-voice / versionCode4**, 실제 기기는 **SM-F966N / Android16**이다.
Portable **0.2.0 / 8skills**, handoff/result **1.0**, 앱 내부 session **0.1**을 유지했다.
오늘 앱 소스/APK·계정/플러그인 등록은 변경하지 않았다. 기존 모의 인증/AI 시험을 실제 로그인/AI로 세지 않는다.

## 오프라인 음성 보완 검증

사용자가 지금 발화 가능함을 확인한 뒤에만 선택 기기의 Wi-Fi·모바일 데이터를 끄고
`Active default network: none`을 확인했다. 사용자가 앱의 기기 내 음성 시작/인식 마치기를 직접 수행했다.
완료 응답 시에도 Wi-Fi0/모바일0/기본 네트워크none을 재조회했고 첫 문장과 마지막
“검토 기록을 남겼습니다”까지 실제 앱 초안에서 관찰했다. 사용자 응답은 “전사 완료·마지막 문장도 남음”이다.
“체크리스트 → 체커 리스트” 및 조사 누락 등 단어 오인식은 있다. 완벽한 전사로 수용하지 않는다.

이전 첫 결과 조기 종료 FAIL과 code4 이어 듣기 보완·온라인 긴 발화 재시험을 보존한다.
이번 초안은 미확인 상태로 제출/평가하지 않았다. 원음 파일은 만들지 않았다.
오늘 runtime 메타데이터에는 질문/평가 또는 actual_ai 이벤트가 없으며 원장도 **11/12** 그대로다.
전체 AI 면접의 오프라인 실행을 뜻하지 않는다. 한국어 질문 읽기 청취는 이전 실기기 사용자 확인 결과다.

## ChatGPT 정식 검사 실패 보완과 실제 다운로드

기존 [CareerGround Portable 플러그인](https://chatgpt.com/plugins/Plugin_47a97bf406048191a8a671f47778376a)의
같은 비공개 합성 대화에서 실행했다. 이전 jsonschema 부재/VALIDATOR_UNAVAILABLE는 이전 receipt에 남겼다.
사용자가 [임시 검사 환경 설치안](mock_interview_host_validator_install_20261012.md)을 승인한 뒤
정확한 pip 명령1회, exit0. Python3.12.14의 전용 `/tmp/careerground-step04-20261012/deps`만 사용했다.
jsonschema4.26.0, attrs26.1.0, referencing0.37.0, rpds-py2026.6.3,
jsonschema-specifications2025.9.1에 **typing-extensions4.16.0이 명령의 의존성 해석으로 추가**됐다.
준비안의 필수 의존성 목록은 완전하지 않았으며 이 차이를 사용자에게 알리고 실제 버전을 receipt에 보존했다.
PC 전역 환경·앱·플러그인 등록 변경이나 별도 설치 명령은 없었다.

원래 플러그인 코드/schema5파일의 해시를 로컬 원본과 대조해 모두 일치했다.
호스트의 실제 validate_handoff/validate_result/import_result 정상3 PASS,
부정5종을 validator/importer 양쪽으로 검사한10 PASS, 합계13검사다.

| 복사본 부정 사례 | 실제 거부 코드 |
| --- | --- |
| handoff hash / ID 변조 | HANDOFF_CONFLICT |
| feedback / candidate의 답변 참조 변조 | MISSING_REFERENCE |
| candidate status를 approved로 위조 | SCHEMA |

이전 receipt, 새 정식 검사 receipt, 재현ZIP을 실제로 내려받았다. BrowserOS의 일반 download 도구와
잘못 선택한 파일 버튼에서 로컬 파일이 생기지 않은 시도는 통과로 세지 않았다.
정확한 파일 이름의 카드/다운로드 링크를 클릭해 완성 파일을 확인했고, 임시 브라우저 다운로드 동작은 복원했다.
입력 해시·이전 실패 receipt·재현ZIP 내부 원본을 대조했다.

## 별도 사실·사용 선택과 새 버전

자동 반영 없이 pending 후보를 먼저 제시했다. 사용자가 실제로 다음 두 선택에 각각 응답한 뒤에만
호스트 `career-review`를 실행했다. **실제 개인 경력 확인이 아닌 합성 시험 선택**이다.

- 사실: “2024년 3~6월, 체크리스트 정리 기여자로서 팀원 피드백을 항목 순서에 반영하고 검토 기록을 남겼다.”
  동료 배포·시간 절감 미측정 경계 유지. 응답: “이 합성 문구·범위 확인”.
- 사용: 응답 “기본·맞춤 이력서·면접에 허용”. scope는 base_resume/tailored_resume/interview.

새 profilev4의 user_statement 출처는 기존 answer의 영어 원문 전체와 정확히 일치한다.
confirmation는 user_confirmed이며 외부 검증이 아니다. result_review/fact_review/use_review history를 각각 기록했다.
새 파일은 v3·v4·새 history만 담는 **profile 검토용 부분 workspace1.0**이다.
JD/resume/과거 tailor history는 원래 handoff에 보존하고 이 부분 파일에 합성해 채우지 않았다.
기존 resume와 handoff의 profile 참조는 v3 그대로이며 원래 result의 후보도 pending 그대로다.
새 프로필 생성이 기존 전달 파일의 자동 승격을 뜻하지 않는다.

호스트18검사 PASS. 내려받은 파일의 PC 독립21검사(정상·보존·출처·사용scope·history·부정5종 포함) PASS.
기존 fact/source/constraints·v3 artifact 동일, 원래 파일 해시 동일, 동료 기여/미측정/금지 경계 보존 PASS.

## 주요 파일 해시

| 실제 파일 | bytes | SHA256 |
| --- | ---: | --- |
| handoff-v1.json (고정 입력) | 원본 보존 | 11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8 |
| careerground-result-step03-fold7-r1.json (실제 SAF 결과) | 2373 | 2d9f38c8f4526e56ff5adbb3efc148897a12b877314df1eec533db62c941864e |
| careerground-session-step03-fold7-r1.json (완료 세션) | 22568 | bd306c323f5703f7ee3a18aca86b783649245cfecd4af59e214ebc298f906a92 |
| interview-review-receipt-step04-20261012-r2.json | 18420 | fa9b39160e274780db95c9e9e06a9cdf507d091d1e4c045562e9dd4e1d1ffd0a |
| profile-review-step04-20261012-v4.json | 9892 | c8019ce278bb6c8a4df2d5a925bcfbc4b995c715ece05e829558c0af6d838b15 |
| career-review-receipt-step04-20261012-r3.json | 9935 | 90ce27c6140a1f2d5560e00c459fe61aa797fd70db29919dc13dd6e24313ac83 |

고정 canonical handoff digest는 a1ca01fb34e8c6c8a5cf5a3bb2e54b32227d05d9076aa77d1de642b70fd1edd1이다.
다운로드 파일·실행 원문·UI/통신 상태·독립 검사 증거는 비공개
`~/.local/share/careerground-android/artifacts/step04-20261012/`에 보존했다.
실제 SAF 결과·완료 세션·voice-ready 파일은 기존 휴대폰/PC 경로에 그대로 있다.

## 회귀·비용·현재 사용

이번 Portable files/workflow/exchange/package **35시험 + 30하위 사례 PASS**.
처음 잘못된 시험 파일명으로 pytest exit4/no tests가 발생했으며 올바른 네 파일로 재실행했다.
Python44/JVM10/실기기 instrumentation9/lint0오류8경고는 이전 code4 검사 결과이며 오늘 재실행으로 세지 않는다.

실제 Codex 총 **11/12**, 오늘 추가0, 남은1. 실패·재시도도 누적하며 새 원장으로 초기화하지 않는다.
ChatGPT 호스트 요청은 이전1+오늘2=3이며 별도 구독 사용량이다. 유료 API 호출0.
앱은 개발 PC runtime/USB가 필요하다. 운영용 독립 모바일 배포는 미실행이다.

사용 순서는 [앱 README](../apps/mock-interview/README.md)의 runtime/ADB 연결 뒤 개인 로그인 →
사용자가 선택한 handoff 검사·포함 검토 → 고정 세션 시작 → 질문·답변 확인/수정 → 평가 →
종료/result 수동 내보내기 → 원래 handoff와 실제 result를 ChatGPT interview-review에 첨부다.
자동 저장이 없고 세션은30분 TTL이므로 긴 대기 전 수동 파일을 저장한다. 완료 세션은 읽기용,
진행 중 세션은 재가져온 뒤 새 범위 검토가 필요하고 가져온 AI 기록은 실제 실행 provenance로 신뢰하지 않는다.
원본 result와 내부 세션 파일의 역할을 구분한다. 새 부분 profile workspace는 앱 handoff가 아니다.

실기기 앱 RAM/token을 비우고 선택 기기의 reverse8765·loopback runtime을 해제했다.
Wi-Fi1/모바일1/화면유지0을 원래 값으로 복원했다. USB를 분리해도 저장 파일은 유지된다.
에뮬레이터 시험은 별도 새 AVD만 사용한다. 개인 handoff가 제공되면 그때 명시 선택 범위로 사용성을 확인한다.

사용자 요청의 중단과 [이전 재개 기록](mock_interview_pause_20261012.md)을 보존한다. 이후 재개하여 [에뮬레이터 보충 검사](mock_interview_emulator_validation_20261012.md)를 완료했고 실행 환경을 정리했다. 승인된 개발 왕복 수용 완료이며 개인 자료·운영 API/배포는 미실행이다.

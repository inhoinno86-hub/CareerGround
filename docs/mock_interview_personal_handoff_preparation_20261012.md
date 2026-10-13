# CareerGround 08 개인 handoff 준비 — 2026-10-12

**개인 handoff 생성·정식 검사·실제 휴대폰 저장/재가져오기·답변1개 실제 평가/result PASS /
결과 호스트 정식 재검토·실제 파일 다운로드 PASS. 원본 및 실패 증거 보존.**
기존 합성 앱 왕복 수용과 별도인 사용성 후속이다. 개인 원문·경력 문장·근거·파일은 저장소에 복제하지 않는다.
전체 비공개 검토 자료와 원본은 `~/.local/share/careerground-android/artifacts/personal-handoff-20261012/`의 owner-only 파일이다.

사용자가 지정한 ChatGPT 대화만 BrowserOS에서 조회했다. 기존 개인 후보4개와 workspace 원본v5/v6,
확인 반영 검토 후보v7·보존 receipt·검토 문서·host 검사 파일을 실제 UI 다운로드 응답과
브라우저 인증된 파일 GET200으로 확보했다. 인증 토큰·cookie·signed URL은 저장하지 않았다.
새 로그인·외부 설치·등록/연결 설정 변경은 없다. 개인 준비 host 요청은1회이며 실제 앱 결과 재검토는 아직 미실행이다.

PC의 저장소 원본 `portable.py`와 기존 jsonschema4.26.0으로 다음을 확인했다.

- 원본 파일의 host 표기 해시 일치, 이전 모든 아티팩트와43개 다른 사실 보존.
- 두 사실의 실제 사용자 확인과 기존 세 용도 허용을 유지하고 외부 검증으로 승격하지 않음.
- 사용 금지·제약·기여 경계·이전 원문 근거 불변.
- 원본 v5/v6/v7 schema PASS, integrity FAIL: 누적 History의 `DUPLICATE_ID`, PDF 바이너리 미확보로 `ATTACHMENT_NOT_CHECKED`.
- 최신 History에 이전 모든 operation이 동일하게 포함됨을 확인한 뒤 별도 전체 후보에서 중복만 해소.
  PDF 미검사는 유지하며 전체 원본 검사 PASS로 표시하지 않음.
- 면접 준비용 두 사실·근거2건·관련 제약4건의 부분 view는 첨부0건이며 workspace schema/reference PASS.

사용자는 정확한 이력서 문장·고정 버전·포함 범위를 승인했다. 기본/맞춤 pending v1을 보존하고
검토 완료 v2를 생성했다. JD는 사용자 선택 OpenAI FDE의 공식 서울 공개 공고를 조회한 고정 후보이며
접수 상태는 미확인이다. 관련성 판단은 부분 근거2개·근거 공백7개이며 경력 적합성 인증이 아니다.
기존 전체 profile 기준 선택은 변경하지 않았다.
공식 공고: [OpenAI FDE 서울](https://openai.com/careers/forward-deployed-engineer-seoul-seoul-south-korea/).

실제 승인 내용으로 reference `make_handoff`·`validate_handoff`와 CLI 검사를 실행했다.
handoff는 unsigned1.0, 두 사실·두 근거·맞춤 이력서·JD·검토 History3건·첨부0건이며
전체 대화·다른 경력·연락처·PDF·회사 기밀은 제외한다. 과거 이력서 참조는 ID/버전만 omitted_refs에 남긴다.
CLI 결과: valid=true, errors=[], signed=false, profile_updated=false, app_imported=false.

사용자가 Codex 누적 한도15회를 승인했다. 현재 같은 원장의 attempts11을 유지하고 limit12→15만
잠금·owner-only 파일 검사 뒤 반영했다. runtime 기본값12를 유지하는 명시적 `--codex-call-limit` 옵션을 추가했다.
오프라인 budget 경계8시험·면접 engine8시험 PASS, diff whitespace 검사 PASS.
이번 추가 실제 Codex0·유료API0이다. 정상 질문 생성1회·답변 평가1회와 보완 재시도 최대2회를 위한 잔여4회다.
구독 사용량을 소비하며 실패 호출도 집계한다. 계정 사용 한도·인증 실패·누적15회 소진 시 중단한다.

현재 ADB에 승인 대상 휴대폰이 없어 재연결·잠금 해제를 요청했다. 개인 OIDC runtime은 아직 시작하지 않았다.
다음은 휴대폰 연결 → 기존 OIDC 로그인(필요 시 사용자 수동) → 선택 handoff 가져오기·표시/검토 →
수동 저장/재개 → 승인 AI 면접과 사용자 답변 확인 → 실제 result 파일 → 같은 ChatGPT 대화 재검토다.
파일 생성·정식 검사·사용자 검토·휴대폰 가져오기·실제 면접·host 결과 재검토를 각각 기록한다.

## 재연결 후 실제 진행과 중단

위 연결 대기 이후 사용자가 폴드7을 재연결했다. 기존 code4 앱·모델·잠금 해제를 확인하고
개인 OIDC runtime/승인 USB reverse를 실행했다. 사용자가 같은 계정으로 로그인하여
앱의 실제 runtime 서명·사용자 검증 통과를 확인했다. 인증 토큰·비밀번호는 추출/저장하지 않았다.
선택 handoff만 별도 개인 시험 폴더에 전달해 원본 bytes 일치 검사 PASS,
SAF 파일 선택·정식 앱 검사·표시 digest/SHA/profile/resume 고정 버전 대조 PASS를 확인했다.
실제 승인 범위를 앱에서 확인해 READY 세션을 고정하고 SAF 파일 저장 PASS를 관찰했다.
세션은32,196bytes이며 포함된 handoff bytes가 원본과 일치했다. PC local reference restore 검사도 PASS다.
local restore는 REVIEW_REQUIRED 상태를 반환했으며 실제 휴대폰 재가져오기 PASS로 표시하지 않는다.

사용자는 진행 중인 작업만 완료하고 휴대폰을 분리할 수 있게 정리해 달라고 요청했다.
저장 완료 후 앱 연결 해제·RAM 비우기·앱 종료, 이번 USB reverse8765 제거, loopback runtime 종료를 확인했다.
handoff/세션 파일은 PC의 owner-only 폴더와 휴대폰 Download의 개인 시험 폴더에 보존했다.
브라우저 로그인은 별도로 유지되며 계정 전체 로그아웃/쿠키 삭제를 수행했다고 표시하지 않는다.
기기 네트워크·화면 설정을 변경하지 않았다. 개인 실제 AI0, Codex11/15·유료API0을 유지한다.

재개 순서: 휴대폰 연결 → 기존 개인 OIDC runtime·USB 연결 → 필요 시 같은 계정 로그인 →
저장한 수동 세션 가져오기·범위 재검토/고정 → 실제 질문 생성 → 사용자 직접 답변/확인 →
평가·result 저장·원래 handoff 대조 → 같은 선택 ChatGPT 대화의 플러그인 재검토.
이전 사실·용도·문장·버전·한도 승인은 다시 받지 않는다. 로그인·발화·답변 확인은 필요한 시점에 안내한다.

## 후속 재개와 개인 첫 답변 왕복

사용자 재개 지시 후 같은 계정/기존 runtime·USB 연결을 복원했다. 실제 수동 세션 SAF 재가져오기와
REVIEW_REQUIRED·표시 digest/raw hash·고정 버전 일치 PASS, 승인 범위 재고정·시작을 확인했다.
미리보기의 단순 문구 대조는 JSON slash escaping으로 처음 실패했고 표시 정규화 후 동일 문구를 확인했다.
실제 질문 첫 호출(attempt12)은 공백 질문에 근거 참조가 포함되어 QUESTION_GAP_REFERENCE로 거부됐다.
검사기를 유지하고 gap/partial/factual 질문의 참조 규칙을 명확히 안내하는 prompt를 보완했다.
혼합 공백 batch 미반영·올바른 재시도·부분 근거 경계 시험을 보충하고 실제 attempt13에서 질문5개 PASS를 확인했다.
실패 세션은 별도 SAF/PC 파일로 보존하고 사용 한도에 포함했다.

사용자는 한국어 기기 내 음성 답변을 확인·제출했다. actual attempt14 평가 PASS로 답변1개·AI 평가1개·pending 후보2개를
분리했다. 전사 오인식으로 보이는 표현은 원문에 남아 있으며 조용히 교정/사실 확정하지 않았다.
질문은 핵심5+후속1 중 답변1·미응답5개다. 이번 확인은 첫 답변의 실제 파일 왕복이며 전체 면접 수료가 아니다.
실제 SAF result 저장 후 원래 handoff와 PC 원본 검사 코드로 정상/부정4사례·입력 불변성 PASS를 확인했다.

세션 export는 한도 확장 보완에서 내부0.1 event attempt 상한12가 남아 SESSION_SCHEMA로 실패했다.
상한15를 반영하고 13/14/15 export/restore 및16 거부 시험을 보충해 engine11시험 PASS를 확인했다.
자동화가 준비 실패 메시지를 확인하지 않고 저장해 이전 result를 세션 r1 이름으로 저장한 오류도 확인했다.
해당4207bytes 결과 사본은 실패 증거로 보존하며 session으로 표시하지 않는다. 준비 실패 시 자동화를 중단하도록 보완했다.
정상 세션 r2의 실제 재준비/SAF 저장·41169bytes 원본/계약/레코드 검사 PASS, 실제 휴대폰 재가져오기와 COMPLETED 유지 PASS.
현재 actor 앱은 기존 code4이며 APK/외부 의존성 변경은 없다. Portable handoff/result1.0은 변경하지 않았다.

현재 Codex14/15·이번 실제3회(첫 실패1+질문 성공1+평가1)·유료API0.
저장 파일을 보존하고 앱 RAM/실행·USB reverse8765·loopback runtime을 정리했다. 기기 네트워크/화면 설정 변경 없음.
같은 사용자 선택 ChatGPT 대화에 원래 handoff/result와 동일 원본 검사 코드·manifest만 첨부하고 interview-review를 요청했다.
전송 ZIP에는 전체 세션·owner binding·인증 정보·미선택 경력이 없다. 개인 준비 host 요청 누적2회다.
host의 직접 코드 실행·다운로드 receipt를 확인하기 전 호스트 재검토를 PASS로 표시하지 않는다.

이후 Host의 원본 검사 직접 실행·정상/부정4사례 PASS와 실제 두 파일 다운로드를 확인했고,
입력/code/ZIP/manifest 해시·stdout receipt를 PC 기준과 대조해 왕복을 수용했다.
두 새 후보는 pending이며 전사/추가 기획·검토·배포 진술의 별도 확인을 기다린다.
현재 개인 첫 답변 실제 왕복은 완료이며 [최종 기록](mock_interview_personal_roundtrip_20261012.md)을 따른다.

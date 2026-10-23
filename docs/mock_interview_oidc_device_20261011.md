# STEP 02 — Fold7 실제 OIDC·파일 왕복 수용

2026-10-11. **STEP 02 PASS / STEP 03 준비 착수 / STEP 04 NOT_RUN.**
사용자가 휴대폰 USB 연결 및 앱 브라우저 로그인을 직접 수행했다. 다른 기기·계정·개인 파일은 탐색하지 않았다.

## 실제로 확인한 흐름

1. 연결된 한 기기: SM-F966N / Android 16(API 36). 기존 APK SHA256을 확인하고 보존한 뒤
   동일 debug 인증서의 **0.1.1-step02-oidc(code 2)**로 업데이트했다. 앱 데이터 초기화/기존 파일 삭제 없음.
2. 실제 기기 instrumentation **5/5 PASS**: 초기 연결 선택/strict JSON/크기 검사 3개,
   callback 경로와 pending request/state 경계 2개. 이 5개 자체는 합성 경계 시험이다.
3. 실제 브라우저 취소→앱 오류 표시→재시도 PASS. 사용자가 Auth0 앱 사용자로 로그인한 뒤
   native callback/code 교환과 runtime **실제 RS256 access token** 검증까지 PASS.
   관리자 콘솔 로그인으로 대체하지 않았다. 비밀번호·token·serial은 기록하지 않았다.
4. 실제 token을 RAM에서만 사용해 잘못된 issuer/audience/client 정책과 payload 변조를 거부했다.
   실제 두 번째 계정 로그인 및 만료 시각까지의 대기는 NOT_RUN이다. 두 합성 서명 사용자의 API 접근
   차단과 만료 token 거부는 Python 시험으로 별도 PASS다.
5. 기존 합성 owner의 수동 세션 파일은 **OWNER_CONFLICT / 403**으로 거부했다.
6. 합성 handoff를 실제 로그인 계정으로 가져와 구조·참조 검사, 검토 gate, 세션 고정,
   시작→일시 중지, SAF 파일 저장→재가져오기→새 **REVIEW_REQUIRED** 상태를 확인했다.
   질문/AI를 실행한 시험은 아니다.
7. 실제 logout 뒤 같은 token으로 재요청했을 때 **401** PASS. 제공자 브라우저 SSO는 별개로 유지된다.
8. 수정 재시험 후 강제 종료→실행 시 앱 로그인/선택 자료/세션은 사라지고 초기 화면으로 돌아왔다.
   APK·수동 내보낸 파일은 남았다. 시험 runtime과 해당 기기 8765 reverse를 종료/해제했다.

## 발견한 실패와 보완

첫 OIDC 세션 파일은 owner binding과 실제 인증이 OIDC였지만 `auth_mode`가 `synthetic_dev`로 기록됐다.
`Sessions.view/export`의 합성 상수와 내부 session 0.1 draft의 const가 원인이었다.

- 첫 파일 `careerground-session-oidc-20261011-verify.json`을 보존했다.
  SHA256 `172a3f45638e2d8b648617230484fe3db4d6e57aaadf04afcb320559f9fd51bb`.
- Sessions에 명시적 인증 모드를 두고 API/store 모드를 일치시켰다. view/export는 실제 store 모드를
  사용한다. 내부 draft는 synthetic_dev/oidc를 허용하고 restore 모드 불일치는 거부한다.
  Portable handoff/result 1.0과 기존 importer 계약은 변경하지 않았다.
- OIDC view/export/restore 모드 및 혼합 store·잘못된 모드 거부 assertion을 추가하고
  Python **30개 재통과**. 새 Android 소스 변경은 없어 APK를 다시 교체하지 않았다.
- 실제 logout/재로그인 후 잘못된 첫 파일은 **AUTH_MODE_CONFLICT / 403**으로 거부됐다.
  원본 handoff로 새 세션을 만들어 새 이름의 r2 파일을 저장/재가져왔다. r2의 `auth_mode=oidc` PASS.
- 파일 검사 보조 스크립트가 처음 `canonical_digest`를 최상위 필드로 가정해 KeyError가 났다.
  기존 계약의 `handoff_ref.sha256`으로 검사 코드를 바로잡았다. 저장된 앱 파일의 구조 오류는 아니었다.
- UI 시험 중 빠른 swipe로 검토 버튼을 지나쳐 제어 요소를 찾지 못한 적이 있다.
  느린 swipe로 화면을 확인한 뒤 같은 실제 버튼을 눌러 진행했다. 앱 검토 gate를 우회하지 않았다.

## 통과한 최종 파일

- 기기 경로:
  `/sdcard/Download/CareerGround-step02-20261011-130033/careerground-session-oidc-20261011-verify-r2.json`
- 9,483 bytes, SHA256 `7a5c8f751c16a36655d4af6ab1d26f7de020d216b8a82d849891b25adbbc8786`.
- 저장 상태 PAUSED, auth_mode oidc. token 필드 없음. unsigned 외부 파일이며 owner 문자열은
  파일 소유권의 암호학적 증거가 아니다. 복원은 원본·hash·참조·mode·owner를 다시 검사하고 검토를 다시 요구한다.
- 원래 handoff bytes 완전 일치, SHA256
  `11bb6517369b8063b1afca03452e654b96440b1ade99023c9a657c36d8cb63a8`.
- 계약 canonical digest:
  `a1ca01fb34e8c6c8a5cf5a3bb2e54b32227d05d9076aa77d1de642b70fd1edd1`.
- 고정 profile-synthetic v3 / jd-synthetic v1 / resume-jd-synthetic v1 유지.
  host의 최신 profile·pending resume로 자동 승격하지 않았다. 실제 개인 경력은 사용하지 않았다.

앱 APK SHA256 `dea6692fe7dc561cc39a6007e4340b9572068d94ffb3321a521ec6981df25a00`.
이전 설치 APK `9c0e8ac0e399bd27a289308712ca40aacb381d7a0476f93d54b5f3f3226ecfe2` 보존.
증거 root `/home/inno/.local/share/careerground-android/artifacts/oidc-device-step02-20261011/`:
instrumentation, 제어한 앱/합성 파일의 UI 관찰, token 없는 runtime 사건 기록, 실패/수정 파일,
회귀 로그, 정리 결과. [구조화 기록](mock_interview_oidc_device_20261011.json).

## 다음 범위

STEP 03의 개발 Codex 경로는 기존 로그인·무도구/프로젝트 격리·ephemeral·구조화 응답을 먼저 검증한다.
한국어 기기 내 STT/로컬 TTS, 전사 확인과 텍스트 대안, 질문/답변 revision과 결과 파일을 구현한다.
STEP 04 실제 앱→파일→ChatGPT 플러그인 재검토는 아직 실행하지 않았다.
외부 설치·연결 변경·배포·유료 호출은 기존 확인 조건을 유지한다.
휴대폰 USB 디버깅 해제는 사용자가 직접 수행한다.

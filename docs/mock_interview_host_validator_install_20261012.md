# ChatGPT 호스트 정식 검사 보완안 — 실행 전 확인

2026-10-12. **사용자 설치 승인 확인 / ChatGPT 호스트에서 실행 요청 전달, 결과 확인 중**.

사용자 응답: “임시 검사 환경 설치 승인”. 승인한 명령·고정 버전·임시 경로만
실행하도록 기존 비공개 ChatGPT 시험 대화에 전달했다. 실제 실행 결과는 아래에 별도로 기록한다.

기존 실제 interview-review는 첨부 파일을 읽고 해시·참조·pending을 확인했으나, 호스트의 두 Python
환경에 jsonschema가 없어 정식 검사기가 VALIDATOR_UNAVAILABLE로 종료됐다. PC의 정식 검사는 PASS다.

먼저 기존 인터프리터에서 아래 패키지를 사용할 수 있는지 조회한다. 기존 환경에서 사용 가능하면
그 환경을 재사용한다. 없다면 승인 후 ChatGPT 시험 실행 환경의 전용 임시 경로에만 설치한다.
이는 플러그인 등록·연결·APK·PC 전역 환경 변경이 아니다. 유료 API 호출은 없다.

PC의 검증된 venv에서 조회한 버전을 고정한다. 아래 명령은 아직 실행하지 않았다.

```bash
python3 -m pip install --disable-pip-version-check --no-input --only-binary=:all: \
  --no-compile --index-url https://pypi.org/simple \
  --target /tmp/careerground-step04-20261012/deps \
  'jsonschema==4.26.0' 'attrs==26.1.0' 'referencing==0.37.0' \
  'rpds-py==2026.6.3' 'jsonschema-specifications==2025.9.1'
```

호스트 Python/pip 또는 해당 버전의 호환 wheel이 없거나 네트워크가 차단돼 있으면 설치 실패로 기록한다.
다른 설치 도구·소스 빌드·별도 패키지·등록 변경으로 자동 전환하지 않는다. 선택한 두 입력 파일이나
경력 자료를 PyPI에 전달하지 않는다. 기존 플러그인 reference 코드와 schema를 그대로 사용한다.

설치 후 해당 프로세스의 PYTHONPATH에만 임시 deps 경로를 추가한다. 실제 첨부 바이트의 hash를 다시
계산하고 원래 validate_result/import_result를 실행한다. 정상 파일과 hash/ID/답변 참조/pending 위조
부정 사례를 검사해 이전 실패와 재시험 결과를 구분한다. 결과 receipt에는 설치·검사 실행 여부와
버전·실제 오류·원본 보존을 기록한다. 다운로드된 receipt도 PC에서 내용과 hash를 확인한다.

설치 확인이 필요한 근거는 사용자의 “외부 설치·등록/연결 변경·배포·유료 실행은 실행 전에 확인” 조건이다.

## 실제 실행·재검토 결과

사용자 승인 후 기존 ChatGPT 호스트에서 명령을 1회 실행했다. Python3.12.14, 설치 exit0.
고정한 다섯 패키지에 더해 그 명령의 의존성 해석으로 typing-extensions4.16.0이 설치됐다.
따라서 “필수 의존성4개만”이라는 준비안의 목록은 완전하지 않았다. 별도 추가 설치 명령은 없었고
동일 임시 deps에만 설치됐다. 이 차이를 사용자에게 알리고 receipt에 보존했다.

정식 validate_handoff/validate_result/import_result 정상3 PASS, 부정5종을 양쪽 checker/importer에서
거부한10검사 PASS. 실행 exit0. 기존 VALIDATOR_UNAVAILABLE receipt를 새 receipt에 그대로 보존했다.
다운로드한 receipt18,420bytes/sha256 fa9b39160e274780db95c9e9e06a9cdf507d091d1e4c045562e9dd4e1d1ffd0a.
교환/Portable/schema5파일 해시는 현재 로컬 원본과 모두 동일하다. 재현ZIP도 실제 다운로드·내용 대조 PASS.
프로젝트·앱·플러그인 등록·연결/PC전역 환경/유료API 변경 없음.

후속 career-review는 같은 deps를 재사용했다. 사용자가 합성 문구 확인과 세 목적 사용 허용에 각각
응답한 뒤에만 새 profilev4·3종history를 생성했다. 실제 호스트18검사 및 내려받은 파일의 PC 독립검사 PASS.
자세한 범위·실패·파일 해시는 [현재 수용 기록](mock_interview_app_acceptance_20261012.md)에 남긴다.

# 폴더블 에뮬레이터 보충 시험 — 실행 전 확인

2026-10-12. **승인한 고정 두 패키지 설치 완료 / AVD 합성 보충 검사 완료·환경 제한 기록**.

휴대폰 실제 왕복과 오프라인 전사, ChatGPT 정식 검사·새 버전 생성은 통과했다.
승인 계획 10절에 별도 명시된 폴더블 에뮬레이터 시험은 아직 미실행이다.
기존 PC에 emulator·system image가 없으며 /dev/kvm 읽기/쓰기 가능, 여유 공간 726.5 GiB를 확인했다.
기존 설치 승인은 이 두 패키지를 포함하지 않으므로 사용자의 외부 설치 사전 확인 조건을 적용한다.

## 설치·실행 범위

Google 공식 SDK metadata에서 조회한 stable 패키지만 사용한다. metadata 조회는 다운로드 설치가 아니다.

| 패키지 | 고정 버전 | ZIP bytes | Google metadata checksum(SHA1) |
| --- | --- | ---: | --- |
| emulator | 37.2.12, channel-0 | 349654171 | cd7362ea55dfb86a418958138dc396e74165dd01 |
| system-images;android-36;google_apis;x86_64 | revision 7 | 1895447397 | c6bf44bdcd885bb902b4ba752d111a073ad7a817 |

합계 다운로드 약 2.09 GiB. 압축 해제·AVD 사용자 디스크까지 16 GiB 여유를 확보한다.
패키지·버전·checksum이 실행 전 달라졌거나 다른 의존성/새 라이선스가 요구되면 설치를 중단한다.
다른 OS 패키지·Android Studio·음성 모델·Play 계정·API key는 설치/등록하지 않는다.

기존 전용 SDK `/home/inno/.local/share/careerground-android/sdk` 및 JDK17을 사용한다.
AVD는 `/home/inno/.local/share/careerground-android/avd-step04-20261012/`에 새 이름
`careerground-step04-foldable-api36`으로 만들고 기존 AVD를 덮어쓰지 않는다.

실행할 설치 명령의 대상은 아래 두 패키지뿐이다(실행 전 공식 metadata와 revision 재대조).

```bash
JAVA_HOME=/home/inno/.local/share/careerground-android/jdk/jdk-17.0.20.1+1 ANDROID_USER_HOME=/home/inno/.local/share/careerground-android/android-user /home/inno/.local/share/careerground-android/sdk/cmdline-tools/15859902/bin/sdkmanager   --sdk_root=/home/inno/.local/share/careerground-android/sdk --channel=0   'emulator' 'system-images;android-36;google_apis;x86_64'
```

기존 code4 debug APK와 instrumentation APK만 새 합성 AVD에 설치한다.
기존 avdmanager의 foldable/resizable 장치 목록 중 해당 이미지와 호환되는 프로필을 사용하며
없으면 임의 하드웨어 정의로 대체하지 않고 원인을 보고한다. 기존 실기기 설정은 건드리지 않는다.
합성 runtime만 127.0.0.1에 띄우고 선택 AVD에만 tcp8765 reverse를 건다.
개인 로그인과 실제 AI는 실기기에서 검증했으므로 에뮬레이터는 합성 인증·파일·UI/상태 시험으로 명시한다.
추가 Codex·ChatGPT·유료 API 호출은 없다.

커버/펼침·회전·분할·키보드/크기변경·파일 picker 취소 및 저장/재가져오기·background/process death를
실행해 실제 AVD 통과/실패를 기록한다. recognizer mock 통과를 실제 음성 통과로 표시하지 않는다.
검사 뒤 AVD를 종료하고 그 reverse와 합성 runtime을 해제한다. 새 AVD/설치 파일은 임의 삭제하지 않는다.
기존 경력/파일/소스/계정/플러그인/배포 구성은 변경하지 않는다.

공식 참고: [명령행 emulator](https://developer.android.com/studio/run/emulator-commandline),
[AVD 관리](https://developer.android.com/studio/run/managing-avds).
버전 근거: [SDK metadata](https://dl.google.com/android/repository/repository2-3.xml),
[Google APIs image metadata](https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-3.xml).

## 실제 설치·중단 결과

sdkmanager exit0. emulator37.2.12 stable/이미지 revision7, 새 AVD 부팅 및 code4 두 APK 설치 완료.
AVD instrumentation9 PASS. 합성 handoff 검토/고정·Mock 질문 생성 관찰. 나머지 화면/파일/복원 보충 시험은 미완료.
확인 시 emulator/runtime 프로세스 없음·선택 AVD 미연결·8765 닫힘. 설치/AVD/증거 보존.
[중단·재개 기록](mock_interview_pause_20261012.md)을 따라 휴대폰 없이 재개한다.

이후 사용자 재개로 합성 보충 검사를 완료했다. [최종 검사·실패·환경 제한](mock_interview_emulator_validation_20261012.md)과 final-cleanup-receipt를 따른다.

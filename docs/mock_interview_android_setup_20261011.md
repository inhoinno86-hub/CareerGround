# Android 빌드 도구 설치 확인안 — 2026-10-11

**2026-10-11 설치·라이선스 수락 승인 후 실행 완료.** 아래 설치안의 원래 검토 내용을 보존한다.
실행 내역·첫 lint 실패와 재검증·추가 Platform Tools 자동 설치는
[빌드 기록](mock_interview_android_build_20261011.md)을 참조한다. 기기 연결·OIDC 등록은 별도 확인 대상이다.
요청 범위는 PC에 아래 도구와 앱의 빌드/test 의존성을 설치하고 debug APK 빌드·JVM 시험·lint를 실행하는 것이다.
에뮬레이터 이미지·휴대폰 연결/설치·OIDC 등록·언어 모델·API 과금·배포는 이번 설치 범위에 포함하지 않는다.

## 설치 대상과 위치

현재 Linux x86_64, 사용 가능 디스크 약 730 GiB. 시스템 Java·기존 `/usr/lib/android-sdk`는 보존한다.
도구 root는 `/home/inno/.local/share/careerground-android/`로 두고 `downloads/`, `jdk/`, `sdk/`,
`gradle/`, `gradle-cache/`로 분리한다. sudo·시스템 패키지 변경·전역 shell 설정 변경 없이 작업 명령에만
`JAVA_HOME`, `ANDROID_SDK_ROOT`, `GRADLE_USER_HOME`을 지정한다. HOME/CODEX_HOME은 바꾸지 않는다.
경력 자료나 Codex token은 이 도구 디렉터리에 복사하지 않는다.

| 대상 | 버전·출처 | 용도 |
| --- | --- | --- |
| JDK | Eclipse Temurin **17.0.20.1+1**, Linux x64 HotSpot JDK, [공식 release](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.20.1%2B1) | javac 포함. archive와 공식 checksum 일치 후 해제 |
| SDK command-line tools | Google **15859902** Linux ZIP, [공식 다운로드](https://developer.android.com/studio#command-tools) | sdkmanager. 확인 페이지 크기 181.8 MB, checksum 아래 기록 |
| SDK Platform | `platforms;android-36` | compile/target SDK 36; minSdk 33 |
| SDK Build Tools | `build-tools;35.0.0` | AGP 8.13 기본 요구와 일치 |
| Gradle | **8.13 bin**, [공식 배포](https://services.gradle.org/distributions/gradle-8.13-bin.zip), [checksum](https://gradle.org/release-checksums/) | 전용 도구 디렉터리에서 빌드, 필요 시 고정 wrapper 생성 |
| AGP / Kotlin compiler | **8.13.2 / 2.2.21**, Google Maven·Gradle Plugin Portal·Maven Central | Gradle manifest에 고정; Compose compiler plugin도 Kotlin과 동일 버전 |
| Compose BOM | **2025.12.00**, Google Maven | [공식 stable 발표](https://developer.android.com/blog/posts/whats-new-in-the-jetpack-compose-december-release) |
| Activity / Lifecycle | **1.12.4 / 2.10.0**, Google Maven | Compose Activity·ViewModel |
| 시험 의존성 | JUnit 4.13.2, AndroidX test ext 1.3.0 / runner 1.7.0, Compose UI test(BOM) | JVM 실행 및 향후 기기 시험 준비 |

Gradle이 내려받는 해당 도구·라이브러리의 전이 의존성도 포함한다. 버전은 manifest와 resolved dependency
목록으로 기록하고 임의 최신 버전으로 치환하지 않는다. 라이브러리 다운로드는 설치 범위이며 아직 실행하지 않았다.
[AGP 호환 표](https://developer.android.com/build/releases/agp-8-13-0-release-notes)는 Gradle 8.13·JDK 17·Build Tools 35.0.0을 명시한다.
[Kotlin release](https://kotlinlang.org/docs/releases.html), [Activity](https://developer.android.com/jetpack/androidx/releases/activity),
[Lifecycle](https://developer.android.com/jetpack/androidx/releases/lifecycle)에서 고정 버전의 존재를 확인했다.

확인한 SHA-256:

```text
commandlinetools-linux-15859902_latest.zip
4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583
gradle-8.13-bin.zip
20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78
Gradle 8.13 wrapper JAR
81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f
```

JDK archive의 공식 checksum과 SDK package 상세 revision은 실제 설치 시 metadata에서 확인·기록한다.
일치하지 않거나 공식 출처에서 받지 못하면 실행을 멈추고 원인을 보고한다. 미확인 mirror로 대체하지 않는다.
이번 준비 중 Adoptium API metadata의 일반 HTTP 조회는 403으로 실패했으나 공식 웹 release 조회로 버전은
확인했다. archive 다운로드 성공 여부는 아직 **NOT_RUN**이며, 위 문서 조회를 설치 성공으로 표현하지 않는다.

다운로드 총량 **약 1–2 GB**, 압축 해제·dependency cache·빌드 산출물 포함 **약 4–6 GB**를 예상한다.
이는 추정치이며 실제 패키지 크기와 cache 사용량을 기록한다. 에뮬레이터 설치 시 용량은 별도다.
도구 다운로드·로컬 빌드에 OpenAI API 호출이나 유료 서비스 실행은 없다.

## 승인 후 실행 순서

1. 위 전용 경로 충돌 여부와 공식 패키지 metadata/checksum 확인, archive 다운로드·검증·해제.
2. SDK license 내용을 제시/확인한 범위에서 수락하고 `platforms;android-36`, `build-tools;35.0.0`만 설치.
   **설치 승인 요청에는 Android SDK 라이선스 수락이 포함됨을 명시한다.**
3. 전용 환경 변수로 Gradle 실행. dependency 목록·버전·checksum/다운로드 결과 기록.
4. 아래 task 실행, 실패하면 승인한 버전·구조 범위에서 원인 분석·수정·재실행:

```text
gradle :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

5. 성공한 debug APK의 version/hash·merged manifest/권한·시험 보고서를 검토 가능하게 제시.
   이후 폴드7/에뮬레이터 실행에 필요한 연결·설치안을 별도로 확인받는다.

위 도구·라이브러리 다운로드/설치, Android SDK 라이선스 수락, 로컬 debug 빌드·시험은
2026-10-11 사용자의 “응 진행해줘”로 승인받아 실행했다. 같은 설치 승인을 다시 묻지 않는다.
기존 앱 계획이나 네이티브 선택을 다시 승인받는 요청이 아니다.

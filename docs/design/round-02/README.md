# CareerGround — Round 02

사용자 피드백: 1차 두 톤은 마음에 들지만 디자인 구성·완성도는 부족했다.
색상 변경을 넘어 구조가 구분되는 5개 시안을 요청했다.
사용자 프로파일(신입/경력직, 담백한 존댓말, 절제한 그림, 짧은/한 회차 연습)은 유지한다.

[갤러리](index.html)에서 전체 비교 → 방향별 시작/질문 화면 → 반대 테마를 볼 수 있다.
[전체 이미지](00-overview.png)와 방향별 01–05 PNG도 제공한다.
모든 내용은 합성 데이터이며 실제 Android 화면이 아니다. 기존 Compose APK는 1차 구현이다.

| 방향 | 구조와 기억할 요소 | 타이포 역할 | 밝은/기본 토큰 |
| --- | --- | --- | --- |
| FOLIO | 비대칭 문서 오브젝트, 열린 목록, 편집형 질문 | Noto Serif Display: 브랜드/질문 번호, Noto Serif CJK KR: 질문, Noto Sans CJK KR: 본문, mono: 자료명 | #FAFAF7 #FFFFFF #24262C #6F7179 #4668DD #E8ECFF |
| ORBIT | 입체 음성 오브젝트, 중앙 질문, 컨트롤 시트 | sans light: 질문, sans regular: 본문, mono: 오디오 상태 | #101C34 #1D2B44 #EEF5FF #A7B7D2 #ABDCE9 #293E5F |
| BLOCKS | 비대칭 모듈, 기능별 색, 자료/연습 탐색 | sans bold: 제목, display: 자료 수, sans: 본문, mono: 구분 | #F4F2F8 #FFFFFF #282534 #6B667D #E8DEF8 #DBECE5 |
| TRAIL | 실제 준비 경로, 겹치는 질문 종이, 연결된 실마리 | serif CJK medium: 질문/표제, sans: 조작/본문, mono: 단계 | #F7FAF6 #FFFFFF #264C41 #5E7468 #E5EFE2 #F5D7C1 |
| STILL | 넓은 여백, 선형 대화 오브젝트, 하단 조작부 | sans light/medium: 대비하는 제목, display: 질문 번호, mono: 상태, sans: 본문 | #FFFFFF #F3F3F0 #202222 #6c716e #A54D2D #F3E3D9 |

색상만 바꾼 공통 템플릿을 피하기 위해 각 방향은 별도 DOM 구조·CSS를 사용한다.
캐릭터 대신 문서/음성/질문/실제 단계에 연결된 코드 기반 그래픽을 사용한다.
모든 폰트는 기존 OS 설치본이며 별도 다운로드하지 않는다.
Android 이식 시 해당 서체의 제공 범위와 큰 글씨 대응을 다시 확인한다.

## 검증

기존 Python 환경으로 `render_studies.py`를 실행하면 독립 headless Chrome으로
전체 비교+개별 시안 이미지를 만들고 `validation.json`을 갱신한다.
브라우저의 기존 프로필·로그인·Orca 탭을 자동화 대상으로 사용하지 않는다.

- 기본/대체 밝기 테마 10조합, 390px 뷰포트 5종, 각 시작/질문 화면 크기·넘침 확인.
- 주요 조작부가 기기 프레임과 하단 제스처 영역에서 잘리지 않는지 확인.
- 명시적 내용 확인 전/후 제출 조작 안내를 확인. 실제 서비스 요청 없음.
- 생성 이미지의 글자 크기·배치·잘림 육안 확인.
- Android/Compose/실기기 검증은 이번 라운드 범위에 포함하지 않는다.

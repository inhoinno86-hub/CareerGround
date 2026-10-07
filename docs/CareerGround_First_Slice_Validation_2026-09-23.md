# CareerGround 첫 구현 묶음 검증 기록

- 일자: 2026-09-23 (Asia/Seoul)
- 대상: 로컬 foundation, 첫 PostgreSQL migration, 계약 DTO, 인증 metadata 사전 검사
- 데이터: 합성 계정 2개와 합성 profile만 사용. 실제 사용자 정보 없음.

## 실행 결과

| 검사 | 결과 | 증거 범위 |
| --- | --- | --- |
| PostgreSQL 서버 | 임시 로컬 PostgreSQL **17.11** 구동 성공 | Docker 미사용, `127.0.0.1:54331`의 일회성 `careerground_test` DB |
| `alembic upgrade head` | 통과 | 빈 DB에서 `20260923_0001` 적용 |
| `alembic check` | 통과: `No new upgrade operations detected.` | ORM 모델과 현재 migration의 schema drift 없음 |
| `alembic downgrade base` → `upgrade head` | 통과 | 첫 migration의 되돌리기·재적용만 검증; 운영 데이터 rollback 보장 아님 |
| PostgreSQL 계정 격리 테스트 | 통과 | 합성 account A가 B의 profile을 조회할 수 없음 |
| `python -m unittest discover -s tests -q` | **66개 통과, skip 0** | 기존 fixture, DTO, 합성 OAuth metadata, 실제 PostgreSQL 통합 테스트 포함 |
| `ruff check` / `ruff format --check` | 통과 | `src`, `migrations`, 신규 테스트 파일 대상 |
| `actionlint .github/workflows/ci.yml` | 통과 | GitHub Actions YAML/표현식 정적 검사만 |
| GitHub Actions `Foundation CI` | **통과: 66개, skip 0** | [run 35870819987](https://github.com/inhoinno86-hub/CareerGround/actions/runs/35870819987), commit `1016f91`, 검증 브랜치 `codex/mvp-foundation-ci-20260923`; PostgreSQL 17 서비스에서 빈 DB migration, `alembic check`, Ruff, 전체 테스트 실행 |

검증 시 `CAREERGROUND_DATABASE_URL`과 `CAREERGROUND_TEST_DATABASE_URL`은 같은 일회성 로컬 `*_test` DB를 가리켰고 `CAREERGROUND_REQUIRE_POSTGRES_TEST=1`로 DB 테스트의 skip을 금지했다. 임시 서버는 정상 종료하고 저장소 밖의 임시 실행 파일·DB를 정리했다. 이 호스트에는 Docker 소켓 사용 권한과 Compose 플러그인이 없으므로 README의 Docker 경로 자체를 실행한 결과는 아니다. 호스트의 임시 PostgreSQL 바이너리/호환 라이브러리는 검증용으로만 썼으며 프로젝트나 운영 의존성으로 추가하지 않았다.

## 아직 검증하지 않은 항목

- 실제 Auth0/Cognito tenant, ChatGPT 플러그인 연결, OAuth 토큰 서명·audience·scope 검사: 외부 검증은 승인됐으나 tenant 접근, ChatGPT 개발 연결 화면, 공개 HTTPS `/mcp` 서버가 아직 없다. 현재 코드는 **metadata 표시값 사전 검사**뿐이다.
- 25개 제품 도구의 endpoint와 개별 정확한 JSON Schema, 실사용자 데이터 보관·삭제, 백업 복원, 프로덕션 보안·법무 검증.

따라서 첫 migration과 격리의 로컬·GitHub CI PostgreSQL 근거는 확보했지만, E00/E01/E02 전체 Story나 Phase A 출시 게이트가 완료된 것은 아니다.

# Phase A 완료 — 개인 비공개 합성 텍스트 MVP

상태: **COMPLETED_PRIVATE_SYNTHETIC_MVP**.
사용자는 주요 흐름과 기존 검증을 기준으로 완료 처리하고, 권장 3·4번과 최종 검토 5번만 진행하도록 승인했다. 실제 유효 증명 교차 사용과 차단 중 새 인증 시험은 이번 완료의 추가 선행 조건에서 제외하고 후속으로 남긴다.

## 완료 범위

ChatGPT에서 합성 경력 대화를 진행하고 CareerGround Web에서 자료와 승인을 확인하는 개인 비공개 텍스트 MVP다.

- 실제 두 Google identity의 Web/MCP 소유자 구분 및 기존 교차 접근 거부
- 사람의 사실 확인과 별도 사용 허용
- 선택 JD 발췌와 RELATED/POTENTIAL 근거 연결
- 별도 R1 생성·문구 확인과 근거를 유지한 보수적인 R2 저장
- 별도 승인한 Markdown 본문 전달
- 실제 기기 패스키 등록·PROFILE의 알려진 로컬 자료 삭제·같은 저장소 재시작
- 로컬 연결 차단 지속·다른 계정/Web 유지·명시적 오프라인 복구
- 프로젝트 소유자의 합성 36개 품질 평가와 기존 비공개 plugin 1.0.3 설치/왕복 확인
- PostgreSQL 회귀와 GitHub Foundation CI

완료된 전체 여정·평가·기기 시험을 반복하지 않았다. 런타임·설치 스킬·OAuth 설정·승인 기한·삭제 coverage는 이번 정리에서 변경하지 않았다.

## 3번: JD 완료 결과 조회 점검

기존 실제 기록에서 Web 저장은 성공했지만 JD 제안 상태 조회는 `VALIDATION_FAILED`, JD_LINK 증명 조회는 `REVIEW_REQUIRED`였다. JD_LINK는 이후 확인 때 요청 기한이 지난 상태였으며, 실패 호출 순간의 정확한 원인은 확정하지 못했다. 토큰 원문이나 과거 승인 증명을 추출해 원인을 추정하지 않는다.

현재 코드와 로컬 합성 회귀에서 다음을 확인했다.

| 조건 | 결과 | 저장 상태 |
| --- | --- | --- |
| JD 승인 뒤 원래 인증 자격 증명·3분 이내 조회 | DONE | 동일한 저장 JD ID 반환 |
| JD 승인 뒤 다른 인증 자격 증명으로 조회 | VALIDATION_FAILED | 저장 JD·발췌 유지, 원래 자격 증명으로 동일 결과 확인 가능 |
| JD 승인 뒤 3분 만료 | VALIDATION_FAILED | 메모리 제안 제거, 저장 JD·정확한 발췌 유지, 만료 폼 재제출 거부 |
| JD_LINK 승인 뒤 5분 요청 만료 | REVIEW_REQUIRED | 저장 연결 1개·DONE 기록 유지, 만료 증명 소비 거부 |

이 결과는 코드상 거부 조건의 재현이며 기존 실제 실패의 배타적 원인 확정은 아니다. 제안과 증명이 만료돼도 사람이 이미 완료한 canonical 저장을 되돌리지 않는다.

로컬 명령과 결과:

```bash
uv run --locked python -m unittest tests.test_chatgpt_proposal_review -q
PYTHONPATH=tests uv run --locked python -m unittest test_artifact_browser_confirmation.ArtifactBrowserTests.test_completed_jd_link_expiry_preserves_the_mapping_without_repeating_it -q
```

각각 11개·1개 PASS, 실패/skip 0이다. 신규 시험 메서드는 3개이며 JD_LINK 시험은 기존 PostgreSQL 클래스에도 상속돼 CI에서 수행한다. 이번 로컬 실행에 PostgreSQL 추가 수행을 주장하지 않는다. [진단 결과](careerground_phase_a_jd_status_diagnosis_20261008.json).

### 현재 사용 안내

- Web에서 저장 완료를 확인했다면 MCP 조회 실패만으로 동일 JD/R2·연결을 자동으로 다시 저장하지 않는다. 관리 화면의 저장 결과를 먼저 확인한다.
- 아직 저장하지 않은 검토가 만료되면 새 검토를 준비한다. 이전 기한·완료 증명은 연장하거나 되살리지 않는다.
- 인증 갱신 뒤 원래 증명이 거부될 수 있다. 증명을 대화에 출력하거나 다른 연결로 옮기지 않는다.
- 만료 후 저장 결과를 다시 찾는 대화 흐름과 구체적인 오류 안내 개선은 후속 작업이다. 기존 실제 오류를 수정 완료로 표시하지 않는다.

## 4번: 수용 경계와 후속

| 후속 항목 | 이번 결정 |
| --- | --- |
| 유효한 실제 완료 증명의 다른 계정 사용 거부 | 추가 검증으로 이관. 현재 증명 조회 차단/합성 회귀의 범위는 유지 |
| 로컬 차단 중 새 OAuth 발급·재연결 | 추가 검증으로 이관. 일반 재시작 차단 지속은 이미 확인 |
| 제공자 grant 철회·refresh | 별도 제공자/운영 검증으로 보류 |
| JD 저장 결과 복귀·오류 안내 개선 | 알려진 한계로 이관. 저장 여부 확인 전 자동 재생성 금지 |
| 유료 서버 AI·OTP MFA | 사용자 결정대로 보류 |
| 패스키 교체·분실 복구, 운영 restore anchor, 다중 process 운영 | 실제 사용자 자료 수용 전 별도 준비 |
| 독립 blind 품질 평가·실제 경력 품질 | 이번 프로젝트 소유자 합성 평가의 범위를 확장하지 않음 |
| 공개 운영 Gate A·배포·운영 비용/개인정보 계약 | 별도 승인과 검증 필요 |

삭제 coverage는 **FOUNDATION_ONLY**다. 알려진 A 로컬 자료는 제거됐지만 요청·profile stub은 DELETING이며 UNVERIFIED_SCOPE VERIFY PENDING 1건이 남는다. 외부 사본·백업·제공자 계정 전체 삭제를 약속하지 않는다. 기존 signed checkpoint와 B 자료는 보존한다.

## 5번: 최종 검토와 병합 준비

- 구현 기준 커밋 `1ad24f94df91e57417d4aa526fa3c8cd0e73819d`의 [Foundation CI](https://github.com/inhoinno86-hub/CareerGround/actions/runs/37641652761)는 전체 성공이다.
- 이번 마무리는 시험·문서 변경이다. 새 커밋의 CI와 병합 가능 상태는 main 대상 PR의 checks에서 별도로 확인한다.
- [main 대상 draft PR #1](https://github.com/inhoinno86-hub/CareerGround/pull/1)을 준비했다. 이 PR에는 Phase A 브랜치의 기존 구현과 이번 마무리 시험·문서가 함께 반영된다.
- ignored QA와 초안·합성 평가 원본을 보존한다. 비밀값·실제 계정 식별자·승인 증명은 새 공개 기록에 넣지 않는다.
- main 병합은 최종 PR/CI 결과를 제시한 뒤 별도 승인을 받는다. 완료 처리 자체로 운영 배포를 실행하지 않는다.

## 관련 기록

- [완료한 실제 시험과 한계](CareerGround_Phase_A_Private_MVP_Closeout_2026-10-07.md)
- [이전 실행 이력](CareerGround_Phase_A_Release_Acceptance_2026-10-05.md)
- [최종 정리 계획](../PLAN-2026-10-08-phase-a-private-mvp-closeout.md)

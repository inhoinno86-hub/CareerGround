# Portable 면접 전달·결과 계약 1.0

2026-10-09. [패키지 내 상세 계약](../plugins/careerground-portable/references/exchange-contract.md),
[handoff schema](../plugins/careerground-portable/references/schemas/handoff-1.0.schema.json),
[result schema](../plugins/careerground-portable/references/schemas/result-1.0.schema.json),
[reference exporter/importer](../plugins/careerground-portable/references/exchange.py).

기존 signed v1을 보존하고 새 unsigned 파일 형식을 구현했다. 앱 구현·음성·제공자 선택은 미착수다.
선택 내용의 실제 검토와 별도 면접 사용 허용이 필요하며 출처/버전 검사는 사실 인증이 아니다.
정상 handoff/result와 결손 fixture는 fixtures/portable에 있다.

```bash
.venv/bin/python plugins/careerground-portable/references/exchange.py fixtures/portable/handoff-v1.json --result fixtures/portable/result-v1.json
```

이 실행은 참조 가져오기 검사다. 실제 앱 가져오기·면접·프로젝트 저장 완료를 뜻하지 않는다.

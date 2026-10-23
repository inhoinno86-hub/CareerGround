# CareerGround 검토 자료
기준: workspace-synthetic
선택 경력: profile-synthetic v3
구조 검사는 사실의 진실·사용자 신원·저장 완료를 증명하지 않습니다.

## profile profile-synthetic v1
```json
{
  "sources": [],
  "facts": [],
  "constraints": []
}
```

## profile profile-synthetic v2
```json
{
  "sources": [
    {
      "id": "source-1",
      "kind": "user_statement",
      "text": "2024년 3월부터 6월까지 팀의 배포 체크리스트를 정리했습니다. 배포 자체는 동료가 맡았고 시간 절감은 측정하지 않았습니다.",
      "locator": "합성 대화 user turn 2",
      "attachment_id": null
    },
    {
      "id": "source-private",
      "kind": "user_statement",
      "text": "합성 비공개 운영 숫자는 이력서와 면접에 사용하지 마세요.",
      "locator": "합성 대화 user turn 3",
      "attachment_id": null
    }
  ],
  "facts": [
    {
      "id": "fact-1",
      "text": "팀 배포 체크리스트 정리",
      "source_ids": [
        "source-1"
      ],
      "confirmation": {
        "status": "pending",
        "record": "",
        "source_id": null
      },
      "permission": {
        "status": "review_required",
        "scope": [],
        "record": ""
      },
      "role": "체크리스트 정리 기여자",
      "period": "2024-03 ~ 2024-06",
      "contribution": "체크리스트 정리 담당; 배포 실행은 동료 담당",
      "uncertainty": "시간 절감 미측정",
      "conflict": false
    },
    {
      "id": "fact-private",
      "text": "비공개 운영 숫자",
      "source_ids": [
        "source-private"
      ],
      "confirmation": {
        "status": "pending",
        "record": "",
        "source_id": null
      },
      "permission": {
        "status": "forbidden",
        "scope": [],
        "record": "합성 사용자: 이력서·면접 사용 금지"
      },
      "role": "기여자",
      "period": "미확인",
      "contribution": "미확인",
      "uncertainty": "사용 금지",
      "conflict": false
    }
  ],
  "constraints": [
    {
      "id": "boundary-1",
      "fact_ids": [
        "fact-1"
      ],
      "rule": "preserve_boundary",
      "description": "배포 단독 책임·리더 역할·미측정 절감 수치를 추가하지 않음"
    },
    {
      "id": "ban-private",
      "fact_ids": [
        "fact-private"
      ],
      "rule": "do_not_use",
      "description": "사용 금지 사실 제외"
    }
  ]
}
```

## profile profile-synthetic v3
```json
{
  "sources": [
    {
      "id": "source-1",
      "kind": "user_statement",
      "text": "2024년 3월부터 6월까지 팀의 배포 체크리스트를 정리했습니다. 배포 자체는 동료가 맡았고 시간 절감은 측정하지 않았습니다.",
      "locator": "합성 대화 user turn 2",
      "attachment_id": null
    },
    {
      "id": "source-private",
      "kind": "user_statement",
      "text": "합성 비공개 운영 숫자는 이력서와 면접에 사용하지 마세요.",
      "locator": "합성 대화 user turn 3",
      "attachment_id": null
    }
  ],
  "facts": [
    {
      "id": "fact-1",
      "text": "팀 배포 체크리스트 정리",
      "source_ids": [
        "source-1"
      ],
      "confirmation": {
        "status": "user_confirmed",
        "record": "합성 사용자: 기간·역할·공동 기여 문구 확인",
        "source_id": null
      },
      "permission": {
        "status": "allowed",
        "scope": [
          "base_resume",
          "tailored_resume",
          "interview"
        ],
        "record": "합성 사용자: 이 문구를 기본·맞춤 이력서와 면접에 허용"
      },
      "role": "체크리스트 정리 기여자",
      "period": "2024-03 ~ 2024-06",
      "contribution": "체크리스트 정리 담당; 배포 실행은 동료 담당",
      "uncertainty": "시간 절감 미측정",
      "conflict": false
    },
    {
      "id": "fact-private",
      "text": "비공개 운영 숫자",
      "source_ids": [
        "source-private"
      ],
      "confirmation": {
        "status": "user_confirmed",
        "record": "합성 사용자: 사실 확인; 사용은 금지",
        "source_id": null
      },
      "permission": {
        "status": "forbidden",
        "scope": [],
        "record": "합성 사용자: 이력서·면접 사용 금지"
      },
      "role": "기여자",
      "period": "미확인",
      "contribution": "미확인",
      "uncertainty": "사용 금지",
      "conflict": false
    }
  ],
  "constraints": [
    {
      "id": "boundary-1",
      "fact_ids": [
        "fact-1"
      ],
      "rule": "preserve_boundary",
      "description": "배포 단독 책임·리더 역할·미측정 절감 수치를 추가하지 않음"
    },
    {
      "id": "ban-private",
      "fact_ids": [
        "fact-private"
      ],
      "rule": "do_not_use",
      "description": "사용 금지 사실 제외"
    }
  ]
}
```

## resume resume-base v1
```json
{
  "type": "base",
  "profile_ref": {
    "id": "profile-synthetic",
    "version": 3
  },
  "jd_ref": null,
  "parent_ref": null,
  "sentences": [
    {
      "id": "sentence-base-1",
      "text": "2024년 3~6월 팀 배포 체크리스트를 정리했다. 배포 실행은 동료가 담당했으며 시간 절감은 측정하지 않았다.",
      "fact_ids": [
        "fact-1"
      ],
      "source_ids": [
        "source-1"
      ],
      "review": "user_confirmed",
      "record": "합성 사용자: 이 문구와 공동 기여·미측정 표시 확인"
    }
  ],
  "mappings": []
}
```

## history history-base v1
```json
{
  "operations": [
    {
      "id": "operation-1",
      "action": "collect",
      "reason": "빈 자료에서 제공한 원문과 후보 정리",
      "inputs": [
        {
          "id": "profile-synthetic",
          "version": 1
        }
      ],
      "outputs": [
        {
          "id": "profile-synthetic",
          "version": 2
        }
      ],
      "confirmation": "user_confirmed",
      "record": "합성 사용자 검토 응답 기록; 실제 사용자 승인 아님",
      "source_ids": [
        "source-1"
      ]
    },
    {
      "id": "operation-2",
      "action": "fact_review",
      "reason": "기간·역할·공동 기여 사실 확인",
      "inputs": [
        {
          "id": "profile-synthetic",
          "version": 2
        }
      ],
      "outputs": [
        {
          "id": "profile-synthetic",
          "version": 3
        }
      ],
      "confirmation": "user_confirmed",
      "record": "합성 사용자 검토 응답 기록; 실제 사용자 승인 아님",
      "source_ids": [
        "source-1"
      ]
    },
    {
      "id": "operation-3",
      "action": "use_review",
      "reason": "기본·맞춤·면접 사용 별도 허용; 비공개 사실 금지 유지",
      "inputs": [
        {
          "id": "profile-synthetic",
          "version": 2
        }
      ],
      "outputs": [
        {
          "id": "profile-synthetic",
          "version": 3
        }
      ],
      "confirmation": "user_confirmed",
      "record": "합성 사용자 검토 응답 기록; 실제 사용자 승인 아님",
      "source_ids": [
        "source-1"
      ]
    },
    {
      "id": "operation-4",
      "action": "base_resume",
      "reason": "JD 없이 기본 이력서 구성",
      "inputs": [
        {
          "id": "profile-synthetic",
          "version": 3
        }
      ],
      "outputs": [
        {
          "id": "resume-base",
          "version": 1
        }
      ],
      "confirmation": "user_confirmed",
      "record": "합성 사용자 검토 응답 기록; 실제 사용자 승인 아님",
      "source_ids": [
        "source-1"
      ]
    }
  ]
}
```

## 첨부 목록
```json
[]
```

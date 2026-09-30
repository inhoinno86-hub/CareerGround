# Evidence-Backed Career AI 프로젝트 개발 작업 계획서
Version: 0.1  
Date: 2026-09-20  
Status: Concept / Architecture Planning  
Purpose: 다음 세션에서 상세 요구사항, 데이터 스키마, Agent/Skill 설계, 구현 작업지시서를 작성하기 위한 기준 문서

---

## 1. 프로젝트 개요

### 1.1 문제 정의

현재 LLM을 잘 활용하는 사용자는 ChatGPT와의 반복 대화를 통해 다음과 같은 높은 품질의 취업 준비 경험을 만들 수 있다.

- 본인의 경력을 대화로 깊게 파고들어 구체화
- 실제 수행 범위와 ownership을 구분
- 과장되거나 확인되지 않은 표현 제거
- JD와 경력을 비교하여 강점/Gap 분석
- 실제 경험에 기반한 Resume/자소서 생성
- 예상 인터뷰 질문 생성
- Voice 기반 모의면접 및 follow-up 질문 수행

그러나 일반 사용자는 다음 문제를 겪는다.

1. 좋은 결과를 얻기 위한 프롬프트를 설계하기 어렵다.
2. LLM에게 어떤 정보를 어떤 순서로 제공해야 하는지 모른다.
3. 한 번 만든 경력 정보를 Resume, JD 분석, 인터뷰 준비에 일관되게 재사용하기 어렵다.
4. AI가 사용자가 하지 않은 일을 과장하거나 추론할 위험이 있다.
5. 생성된 Resume 문장의 근거를 추적하기 어렵다.
6. 모의면접이 일반 질문 목록을 읽는 수준에 머무를 수 있다.

본 프로젝트는 이 과정을 제품화하여, 사용자가 LLM 활용법을 몰라도 자연스러운 대화만으로 자신의 경력을 구조화하고 취업 준비 전 과정에 활용할 수 있게 하는 것을 목표로 한다.

---

## 2. 제품 비전

### 2.1 핵심 정의

> 사용자의 실제 경력을 Evidence-backed Career Model로 만들고,  
> 그 모델을 Resume, JD 분석, Interview 준비 및 Voice Mock Interview에 일관되게 활용하는 Career AI System.

### 2.2 핵심 차별화

일반적인 AI 취업 서비스:

```text
Resume
  ↓
LLM
  ↓
Resume Rewrite / JD Match / Interview Questions
```

본 프로젝트:

```text
User
  ↓
Guided Career Profiling
  ↓
Claim / Ownership / Evidence Validation
  ↓
Career Graph
  ↓
┌───────────────┬───────────────┬────────────────┐
│ Resume        │ JD Analysis   │ Interview Prep │
└───────────────┴───────────────┴────────────────┘
                         ↓
                Signed Interview Package
                         ↓
                Voice Mock Interview App
```

핵심 원칙은 다음과 같다.

> AI가 문장을 잘 쓰는 것보다,  
> 그 문장을 왜 쓸 수 있는지 설명할 수 있어야 한다.

---

## 3. 프로젝트 구성

프로젝트는 크게 세 부분으로 분리한다.

```text
                    Career Core
                        │
          ┌─────────────┴─────────────┐
          │                           │
   ChatGPT Plugin                Voice Interview App
          │                           │
 Career Profiling               Voice Interaction
 Career Graph                   Dynamic Follow-up
 Evidence Traceability          Answer Evaluation
 JD Analysis                    Evidence-aware Probing
 Resume                         Interview Feedback
 Interview Plan
```

Career Core는 Plugin과 App이 공유하는 공통 Backend/Data Layer이다.

---

# 4. ChatGPT Plugin 범위

## 4.1 Plugin의 역할

Plugin은 **"지원자를 이해하고 취업 준비 자료를 생성하는 시스템"** 역할을 담당한다.

핵심 기능:

### A. Career Profiling

사용자의 Resume, 기존 문서, 대화 내용을 기반으로 경력을 구조화한다.

단순 정보 입력이 아니라 Socratic Profiling을 수행한다.

예:

```text
"이 기능을 개발했습니다."
        ↓
"직접 구현하신 것인가요?"
"설계에도 참여했나요?"
"기술 선택을 직접 결정했나요?"
"검증은 어디까지 직접 수행했나요?"
"프로젝트 전체 ownership인가요, 특정 영역 ownership인가요?"
```

목적:

- 수행 업무 구체화
- Ownership 확인
- Contribution 범위 확인
- 기술 깊이 확인
- 검증 범위 확인
- 수치/성과의 근거 확인
- 과장 가능성 제거

---

## 4.2 Career Graph

Career Profile을 단순 텍스트가 아니라 구조화된 Graph 형태로 저장한다.

초기 개념 모델:

```text
Person
 └─ Company
     └─ Role
         └─ Project
             ├─ Goal
             ├─ Responsibility
             ├─ Contribution
             ├─ Ownership
             ├─ Skill
             ├─ Technology
             ├─ Validation
             ├─ Outcome
             ├─ Claim
             ├─ Evidence
             └─ Do-not-claim
```

예:

```text
DL Trajectory Generation
│
├─ Role
│   └─ Support / System Architecture Contributor
│
├─ Contributions
│   ├─ Dataset definition
│   ├─ Input/output definition
│   ├─ Model analysis
│   └─ System architecture
│
├─ Evidence
│   ├─ Profiling session
│   ├─ Resume
│   └─ User confirmation
│
└─ Do-not-claim
    └─ TCN model-selection ownership
```

---

## 4.3 Evidence Traceability

모든 외부 산출물의 문장은 가능한 한 Career Graph의 Claim/Evidence와 연결한다.

예:

```text
Resume Claim:
"Designed longitudinal control architecture for an L2+ autonomous driving system."

Evidence ID:
E-204

Source:
Career Profiling Session #14

Ownership:
Direct Contributor

Status:
User Confirmed

Do-not-claim:
Overall L2+ system ownership
```

사용자는 Resume 문장의 Evidence를 클릭하여 근거를 확인할 수 있어야 한다.

이 기능은 본 프로젝트의 핵심 UX로 취급한다.

---

## 4.4 Claim 상태 모델

초기 상태 정의:

```text
VERIFIED
USER_CONFIRMED
USER_CLAIMED
INFERRED
UNKNOWN
CONTRADICTED
DO_NOT_CLAIM
```

원칙:

- INFERRED/UNKNOWN 내용을 Resume의 사실 문장으로 자동 변환하지 않는다.
- 중요한 ownership/성과는 사용자 확인을 받는다.
- 서로 충돌하는 진술은 자동 병합하지 않고 contradiction으로 관리한다.
- Do-not-claim은 별도 negative knowledge로 저장한다.

---

## 4.5 JD Analysis

입력:

- JD URL
- JD text
- PDF / document
- 향후 허용 가능한 source integration

처리:

```text
JD
 ↓
Requirement Extraction
 ↓
Capability / Skill / Experience decomposition
 ↓
Career Graph Matching
 ↓
Evidence Strength
 ↓
Gap Analysis
```

출력:

- Requirement별 관련 경험
- 강한 Evidence
- 약한 Evidence
- 실제 Gap
- 단순 표현 Gap
- 추가 Profiling 필요 영역
- Resume에서 강조할 경험

주의:

JD Fit을 단순 keyword matching으로만 처리하지 않는다.

---

## 4.6 Resume 생성

Resume는 Career Graph에서 검증 가능한 Claim을 조합하여 생성한다.

원칙:

- 새로운 경력을 만들어내지 않는다.
- 수치가 확인되지 않았으면 임의 생성하지 않는다.
- 프로젝트 전체 ownership과 부분 contribution을 구분한다.
- JD에 따라 경험 선택 및 표현은 변경할 수 있지만 factual boundary는 변경하지 않는다.
- 각 bullet은 가능한 한 Evidence ID를 가진다.

출력 예:

```text
resume.pdf
resume.md
resume.json
```

향후 PDF에는 사용자 표시용 metadata 삽입 가능:

```text
Generated with [Project Name]
Profile Version: CP-00012
Artifact ID: RA-0021
```

---

## 4.7 Interview 예상 질의 생성

JD + Career Graph + Resume를 기반으로 예상 질문을 생성한다.

단순 질문 리스트가 아니라 다음 구조를 권장한다.

```text
Question
├─ Why asked
├─ Related JD requirement
├─ Related Career evidence
├─ Expected depth
├─ Follow-up candidates
├─ Risk / weak point
└─ Do-not-overclaim boundary
```

이 구조가 Voice Interview App에서 dynamic interview seed로 사용된다.

---

# 5. Voice Interview App 범위

## 5.1 App의 역할

App은 **"검증된 Career Identity를 기반으로 실제 면접 상황을 재현하는 시스템"**이다.

Plugin 결과를 활용하지만, 역할은 명확히 분리한다.

Plugin:
> 지원자를 이해하고 준비한다.

App:
> 준비된 지원자를 실제 면접 상황에 넣어본다.

---

## 5.2 핵심 기능

### Voice-first Interview

- 자연스러운 음성 질의
- 사용자 답변 음성 수신
- turn-taking
- interruption
- follow-up
- transcript
- 답변 분석

---

## 5.3 예상 질문은 Script가 아니라 Seed

Voice App은 질문 리스트를 순서대로 읽는 방식이 아니다.

예:

```text
Q:
Tell me about your L2+ longitudinal control work.

Seed:
- architecture ownership
- C/C++
- validation

Risk:
- avoid claiming entire L2+ ownership
```

사용자가:

> "I designed the entire L2+ system..."

이라고 답하면 App은 Career Evidence를 확인한다.

```text
Claim: Entire L2+ system ownership
Evidence: NOT FOUND
```

후속 질문:

> "When you say the entire system, which parts were directly under your ownership?"

즉 질문은 사용자의 답변과 Career Graph의 Evidence에 따라 동적으로 변화한다.

---

# 6. Plugin → App 연결 구조

## 6.1 초기 아이디어

초기에는 다음 형태를 고려하였다.

```text
Plugin
 ↓
Resume.pdf
Interview Questions.pdf
 ↓
App
```

하지만 이 구조만으로는 Career Graph의 핵심 정보가 손실된다.

특히 다음 정보가 빠질 수 있다.

- Ownership
- Evidence
- Claim status
- Do-not-claim
- Contradiction
- Weak evidence
- JD requirement mapping

따라서 별도의 **Interview Package**를 도입한다.

---

# 7. Signed Interview Package

## 7.1 개념

Plugin에서 Voice Interview에 필요한 정보를 하나의 Package로 생성한다.

```text
Interview Package
│
├─ candidate_snapshot
├─ career_graph_subset
├─ JD analysis
├─ resume
├─ interview_plan
├─ evidence_map
├─ risk_points
├─ do_not_claim
└─ metadata
```

metadata 예:

```json
{
  "package_id": "IP-92F71A",
  "profile_id": "CP-18342",
  "profile_version": 12,
  "jd_id": "JD-001",
  "resume_version": 4,
  "question_set_version": 2,
  "evidence_hash": "...",
  "issued_at": "...",
  "signature": "..."
}
```

---

## 7.2 Digital Signature

Watermark는 사용자에게 provenance를 보여주는 용도로만 사용한다.

보안/검증 목적은 Digital Signature를 사용한다.

```text
Career Graph
 + JD
 + Resume
 + Interview Plan
        ↓
Canonical Package
        ↓
Hash
        ↓
Server Signature
```

Voice App:

```text
Package
 ↓
Signature Verification
 ↓
VALID → Interview
INVALID → reject / re-import
```

이 구조로 App은 공식 Plugin/Core가 생성한 데이터를 식별할 수 있다.

---

# 8. Plugin Dependency 전략

## 8.1 Hard Dependency 방식

```text
Plugin Package 없음
→ App 사용 불가
```

장점:
- Plugin 사용 강제
- 데이터 품질 통제

단점:
- 신규 사용자 진입장벽 증가
- 이미 Resume가 있는 사용자가 바로 체험할 수 없음

---

## 8.2 Soft Dependency 방식 — 권장

### Basic Interview

```text
Resume + JD
 ↓
General Voice Interview
```

기능:
- 일반 질문
- JD 기반 질문
- 기본 피드백

### Verified Career Interview

```text
Signed Interview Package
 ↓
Evidence-aware Interview
```

추가 기능:

- Career Graph 실시간 참조
- Claim verification
- Ownership probing
- Do-not-claim detection
- weak evidence 집중 질문
- Resume ↔ Career Graph consistency 검사
- 지원자 실제 경력에 맞춘 follow-up

즉 Plugin을 강제로 요구하는 대신, Plugin을 사용했을 때 훨씬 높은 품질의 Interview 경험을 제공한다.

이를 **Value-driven dependency**로 정의한다.

---

# 9. Closed Learning Loop

Voice Interview 중 새로운 경험이 발견될 수 있다.

예:

> "아, 그때 SIL automation script도 제가 만들었습니다."

App은 Career Graph를 자동 수정하지 않는다.

대신:

```text
New Evidence Candidate

Claim:
SIL automation script development

Source:
Mock Interview #7
Timestamp:
18:32

Status:
UNVERIFIED
```

로 저장한다.

Plugin에서:

```text
새로운 Career Evidence가 발견되었습니다.

[추가]
[추가 질문]
[무시]
```

사용자 확인 후 Career Graph에 반영한다.

전체 loop:

```text
Plugin
 ↓
Verified Career Graph
 ↓
Interview Package
 ↓
Voice App
 ↓
Mock Interview
 ↓
New Evidence Candidate
 ↓
Plugin
 ↓
Human Verification
 ↓
Career Graph Update
```

---

# 10. Career Core

Plugin과 App을 직접 강결합하지 않고 공통 Backend를 둔다.

```text
                   Career Core
                        │
       ┌────────────────┼────────────────┐
       │                │                │
 Career Graph       Evidence DB      Artifact Store
       │                │                │
       ├──────── Agent / Rules ──────────┤
       │                                 │
   Plugin API                      Interview API
       │                                 │
 ChatGPT Plugin                   Voice App
```

Career Core의 책임:

- User identity
- Career Graph
- Evidence storage
- Profile version
- Artifact version
- JD data
- Resume data
- Interview Package
- Digital signature
- Audit log
- consent / retention
- data export / deletion

---

# 11. 초기 Career Graph 데이터 모델 후보

다음 entity를 우선 검토한다.

```text
User
Company
Role
Project
Responsibility
Contribution
Skill
Technology
Outcome
Validation
Claim
Evidence
Artifact
JD
JDRequirement
InterviewQuestion
InterviewSession
EvidenceCandidate
```

핵심 relationship:

```text
User
 └─ HAS_ROLE
      Role
       └─ HAS_PROJECT
            Project
             ├─ HAS_CONTRIBUTION
             ├─ USES_SKILL
             ├─ HAS_OUTCOME
             └─ SUPPORTS_CLAIM
                    Claim
                     ├─ SUPPORTED_BY → Evidence
                     ├─ USED_IN → Resume Bullet
                     └─ MATCHES → JD Requirement
```

Do-not-claim은 별도 Claim 상태 또는 Constraint entity로 검토한다.

---

# 12. Agent / Skill 구성 초안

Plugin 내부 기능은 다음 Agent/Skill로 분리 가능하다.

## 12.1 Profiling Agent

책임:

- Career interview
- ambiguity detection
- follow-up question
- ownership clarification

---

## 12.2 Evidence Agent

책임:

- Claim ↔ Evidence 연결
- evidence quality 확인
- contradiction detection
- unsupported claim detection

---

## 12.3 Career Graph Agent

책임:

- 구조화
- entity linking
- version management

---

## 12.4 JD Agent

책임:

- JD parsing
- requirement decomposition
- Career Graph matching
- gap analysis

---

## 12.5 Resume Agent

책임:

- JD-specific experience selection
- Resume generation
- bullet ↔ Claim ↔ Evidence mapping

---

## 12.6 Interview Planning Agent

책임:

- expected question generation
- evidence-linked probes
- risk questions
- Interview Package generation

---

## 12.7 Voice Interview Agent — App

책임:

- real-time interviewing
- follow-up generation
- evidence-aware probing
- answer analysis

---

## 12.8 Review / Judge Agent

향후 multi-agent 검증에 사용 가능.

예:

```text
Generator
   ↓
Evidence Reviewer
   ↓
Claim Boundary Reviewer
   ↓
Final Integrator
```

Human-on-exception 적용 후보:

- contradiction
- unsupported metric
- unclear ownership
- high-impact claim
- profile merge conflict

---

# 13. UX 핵심 흐름

## 13.1 최초 사용자

```text
"취업 준비를 시작하고 싶어요."
 ↓
Resume upload(optional)
 ↓
Career Profiling
 ↓
Career Graph preview
 ↓
User confirmation
 ↓
Target JD 입력
 ↓
JD Analysis
 ↓
Resume 생성
 ↓
Interview Plan
 ↓
Start Voice Interview
```

---

## 13.2 Evidence UX

Resume 예:

```text
Designed longitudinal control architecture for an L2+ autonomous driving system.
                                                    [Evidence]
```

Evidence 선택:

```text
Evidence E12

Project
L2+ Longitudinal Control

Role
Direct Contributor

Source
Profiling Session #14

Status
USER_CONFIRMED

Related Skills
C++
Control Architecture
SIL/HIL

Do-not-claim
Overall L2+ system ownership
```

이 UX는 제품의 핵심 differentiator로 취급한다.

---

# 14. MVP 개발 범위

## Phase 0 — Concept Validation

목표:
Career Profiling → Career Graph → Evidence → Resume 흐름 검증

구현:

- Career Graph 최소 schema
- Profiling prompt/skill
- Claim 상태
- Evidence 연결
- Resume generation
- JD manual input

제외:

- crawler
- auto apply
- payment
- full mobile app
- production voice

---

## Phase 1 — ChatGPT Plugin MVP

목표:
ChatGPT 안에서 end-to-end career preparation을 수행

범위:

```text
Career Profiling
Career Graph
Evidence Traceability
JD Analysis
Resume
Interview Question Plan
Interview Package
```

MVP acceptance criteria 예:

1. 하나의 Resume bullet이 적어도 하나의 Claim에 연결된다.
2. 중요한 Claim은 Evidence source를 가진다.
3. Do-not-claim이 Resume 생성 시 반영된다.
4. JD requirement와 Career evidence mapping 확인 가능.
5. Interview Package export 가능.
6. profile version / artifact version 관리 가능.

---

## Phase 2 — Voice Interview App MVP

목표:
Interview Package 기반 dynamic mock interview

범위:

- Package import
- signature verification
- Voice conversation
- interview question seed
- dynamic follow-up
- transcript
- basic feedback

---

## Phase 3 — Evidence-aware Interview

추가:

- Career Graph 조회
- unsupported claim detection
- ownership probing
- do-not-claim guard
- JD-specific depth control
- interview answer ↔ evidence consistency

---

## Phase 4 — Closed Learning Loop

추가:

- New Evidence Candidate
- Plugin review
- Career Graph update
- version history

---

## Phase 5 — Job Discovery / Application Workflow

향후 검토:

- JD discovery
- job recommendation
- application tracking
- authorized integrations
- human-approved apply

주의:

Job board crawling/auto-apply는 각 서비스의 이용약관, API availability 및 automation policy 검토 후 진행한다.

---

# 15. MVP에서 의도적으로 하지 않을 것

초기 범위를 과도하게 넓히지 않는다.

초기 제외:

- LinkedIn 대규모 scraping
- 무인 Auto Apply
- Recruiter-side candidate scoring
- 면접 합격 확률 예측
- 모든 채용사이트 integration
- 모든 LLM provider 지원
- 자동 Career Graph 변경
- 완전 autonomous career decision

---

# 16. 데이터 및 보안 원칙

Career 정보는 다음과 같은 민감한 개인 정보가 포함될 수 있다.

- 회사/프로젝트
- Resume
- 면접 녹음
- transcript
- 지원회사
- JD
- career goals

초기 설계부터 다음을 반영한다.

```text
Data minimization
Encryption at rest / transit
User-controlled deletion
Export my profile
Voice recording consent
Retention policy
Audit log
Profile versioning
Evidence source tracking
LLM provider disclosure
```

원칙:

> 사용자 Career Graph는 사용자의 데이터이며,  
> 사용자가 검토하고 수정하고 삭제할 수 있어야 한다.

---

# 17. 시장 및 경쟁 환경 메모

2026-09-20 기준 빠른 시장 검토에서 이미 다음과 같은 유사 방향 서비스가 존재한다.

특히 CareerLedger는:

- voice/chat career capture
- structured career profile
- JD-specific resume
- evidence-oriented career story
- user-approved career data

등을 제공하고 있어 본 프로젝트와 상당 부분 겹친다.

또한 RoleProof 계열 서비스도:

- resume evidence
- ownership
- project proof
- interview story

를 강조한다.

따라서 단순히 다음을 차별점으로 주장해서는 안 된다.

```text
"Voice로 경력을 수집한다."
"AI로 Resume를 만든다."
"JD와 Resume를 비교한다."
```

본 프로젝트가 집중해야 할 차별화 후보:

```text
1. Claim ↔ Evidence의 명시적 traceability
2. Do-not-claim / ownership boundary
3. 모든 Resume statement의 provenance
4. Signed Interview Package
5. Resume와 Career Graph consistency 검증
6. Evidence-aware Dynamic Voice Interview
7. Mock Interview → New Evidence Candidate → Human Verification loop
8. ChatGPT Plugin과 독립 Voice App을 같은 Career Core로 연결
```

※ 정식 사업화 전 별도 경쟁사/특허/상표 분석 필요.

---

# 18. 프로젝트명 후보

## 18.1 피해야 할 이름

빠른 웹 검색 기준 이미 관련 서비스/프로젝트가 확인된 이름:

- CareerGraph
- CareerProof
- CareerLedger
- RoleProof
- ProofHire
- CareerRoot
- GroundedPath
- ProvenPath

따라서 위 이름은 프로젝트명 후보에서 제외하는 것을 권장한다.

---

## 18.2 추천 방향

브랜드 이름은 다음 가치를 표현하면 좋다.

```text
Career
Evidence
Grounding
Traceability
Ownership
Truth boundary
Interview
```

---

## 후보 A — CareerGround  [현재 1순위 제안]

의미:

> Career + Grounded

AI가 사용자의 실제 Career Evidence에 grounded 되어 동작한다는 의미.

제품 구성 예:

```text
CareerGround
├─ CareerGround Profile   ← ChatGPT Plugin
├─ CareerGround Core      ← Backend
└─ CareerGround Live      ← Voice Interview App
```

장점:

- 제품 철학과 잘 맞음
- Plugin/App/Core naming이 자연스러움
- "Grounded career intelligence" 메시지 연결 가능

주의:
정식 상표/도메인 확인은 아직 수행하지 않음.

---

## 후보 B — CareerOrigin

의미:

> 모든 Career claim을 원래 경험(source)까지 추적한다.

다만 유사 명칭 사용 사례가 확인되어 우선순위는 낮음.

---

## 후보 C — GroundedCareer

의미가 매우 명확하지만 브랜드명보다는 설명형 이름에 가깝다.

제품:

```text
GroundedCareer Profile
GroundedCareer Live
```

---

## 후보 D — CareerClaim

핵심 개념인 Claim을 전면에 둔다.

```text
CareerClaim
CareerClaim Live
```

장점:
Evidence/claim architecture를 잘 표현.

단점:
일반 사용자에게 다소 기술적으로 느껴질 수 있음.

---

## 후보 E — CareerTrace AI

Evidence traceability를 잘 표현하지만 유사 이름/프로젝트 존재 가능성이 있어 정식 clearance 필요.

---

## 18.3 현재 권장 Naming

Working Project Name:

# CareerGround

구성:

```text
CareerGround
│
├── CareerGround Profile
│      ChatGPT Plugin
│
├── CareerGround Core
│      Career Graph / Evidence / APIs
│
└── CareerGround Live
       Voice Mock Interview App
```

Tagline 후보:

> Your career, grounded in evidence.

또는

> Every career claim, backed by evidence.

또는

> Know what you did. Prove what you claim. Practice what they ask.

※ 프로젝트명은 현재 working name이며, 정식 사용 전 상표/도메인/App Store/Plugin Directory 검색을 별도로 수행한다.

---

# 19. 기술 구조 초안

초기 기술 후보이며 확정 사항이 아니다.

```text
ChatGPT
   │
Plugin / Skill
   │
MCP / API
   │
CareerGround Core
   ├─ API
   ├─ Career Graph
   ├─ Evidence Store
   ├─ Artifact Store
   ├─ Signature Service
   └─ Agent Orchestration
         │
         ├─ LLM API
         └─ Realtime Voice API
                     │
              CareerGround Live
```

Backend 후보:

- Python + FastAPI
- PostgreSQL
- Graph representation:
  - 초기에는 relational schema + explicit relations
  - 필요 시 graph DB 검토
- Object storage:
  - resume / audio / artifact
- Signature:
  - asymmetric signing key 또는 HMAC 기반 초기 MVP 검토

주의:
초기 MVP에서 Graph DB를 반드시 사용할 필요는 없다.
Career Graph는 "데이터 모델"의 개념이며 구현은 PostgreSQL로 시작할 수 있다.

---

# 20. 핵심 설계 원칙

### Principle 1 — Evidence First

생성 전에 근거를 확인한다.

### Principle 2 — Human Confirmed Career

중요 Career Claim은 사용자가 확인한다.

### Principle 3 — No Silent Inference

추론된 경험을 사실처럼 사용하지 않는다.

### Principle 4 — Trace Everything

Resume/JD/Interview output을 원본 Evidence까지 연결 가능하게 한다.

### Principle 5 — Separate Preparation and Simulation

Plugin = preparation  
App = simulation

### Principle 6 — Shared Career Intelligence

Plugin과 App은 동일 Career Core를 사용한다.

### Principle 7 — Value-driven Dependency

Plugin을 강제하는 것이 아니라,
Plugin을 사용하면 더 깊고 정확한 Interview 기능을 제공한다.

### Principle 8 — Human-on-Exception

모호함, 충돌, 과장 가능성이 있을 때 사용자의 판단을 요청한다.

---

# 21. 다음 세션에서 구체화해야 할 작업

다음 우선순위를 권장한다.

## Step 1 — Career Graph Schema v1

정의:

- Entity
- Relation
- Claim
- Evidence
- Ownership
- Confidence
- Do-not-claim
- version

산출물:

```text
career_graph_schema_v1.md
career_graph_schema_v1.json
```

---

## Step 2 — Profiling Protocol

정의:

- 질문 순서
- probing rule
- ambiguity detection
- ownership question
- evidence confirmation
- stop condition

산출물:

```text
career_profiling_protocol_v1.md
```

---

## Step 3 — Plugin Functional Specification

기능:

```text
profile.start
profile.update
evidence.add
evidence.confirm
career_graph.get
jd.analyze
resume.generate
interview_plan.generate
interview_package.create
```

산출물:

```text
plugin_functional_spec_v1.md
```

---

## Step 4 — Interview Package Schema

정의:

- package fields
- Career Graph snapshot
- evidence map
- signature
- versioning

산출물:

```text
interview_package_schema_v1.json
```

---

## Step 5 — Voice Interview Agent Specification

정의:

- interview state machine
- question selection
- dynamic follow-up
- claim verification
- evidence lookup
- evaluation
- transcript
- New Evidence Candidate

산출물:

```text
voice_interview_agent_spec_v1.md
```

---

## Step 6 — MVP Architecture

정의:

- backend
- database
- API
- authentication
- MCP
- storage
- LLM
- realtime voice
- deployment

산출물:

```text
architecture_v1.md
```

---

## Step 7 — Implementation Task Breakdown

개발 가능한 task로 분해:

```text
Epic
 └─ Feature
     └─ Story
         └─ Task
```

예:

```text
EPIC-01 Career Profiling
EPIC-02 Career Graph
EPIC-03 Evidence Traceability
EPIC-04 JD Analysis
EPIC-05 Resume Generation
EPIC-06 Interview Package
EPIC-07 Voice Interview
EPIC-08 Learning Loop
```

---

# 22. 다음 세션 시작 권장 프롬프트

다음 채팅에 본 문서를 첨부하고 아래와 같이 시작한다.

```text
첨부한 Career AI 프로젝트 개발 작업 계획서를 기준 문서로 사용해줘.

이 프로젝트의 working name은 우선 CareerGround로 사용하되,
이름은 아직 확정하지 않는다.

우선 구현을 시작하기 전에 가장 중요한 Career Graph Schema v1을 설계하고 싶다.

다음 원칙을 반드시 반영해줘.

1. Career Claim은 Evidence까지 trace 가능해야 한다.
2. Ownership과 Contribution 범위를 명확히 표현할 수 있어야 한다.
3. User-confirmed / inferred / unknown / do-not-claim을 구분해야 한다.
4. Resume bullet → Claim → Evidence 역추적이 가능해야 한다.
5. JD Requirement → Career Claim mapping이 가능해야 한다.
6. Interview에서 새로운 정보가 발견되면 기존 Graph를 바로 수정하지 않고
   Evidence Candidate 상태로 관리해야 한다.
7. 향후 ChatGPT Plugin과 Voice Interview App이 동일한 Career Core를 사용할 예정이다.

먼저 전체 Entity / Relationship 모델을 설계하고,
그 다음 JSON Schema 또는 DB Schema 수준으로 구체화해줘.
```

---

# 23. 현재 결정 사항 요약

현재까지 합의된 핵심 방향:

```text
[DECIDED]

✓ ChatGPT Plugin과 독립 Voice App을 분리한다.
✓ 공통 Career Core를 사용한다.
✓ Plugin에서 Career Profiling을 수행한다.
✓ Career Graph를 핵심 데이터 모델로 사용한다.
✓ Resume 문장은 Evidence traceability를 가진다.
✓ JD 분석은 Career Graph를 기준으로 한다.
✓ Interview 질문은 Career Graph/JD를 기반으로 생성한다.
✓ Plugin → App은 Interview Package로 연결한다.
✓ Interview Package는 digital signature로 검증한다.
✓ Watermark는 provenance 표시용으로만 사용한다.
✓ Voice 질문 리스트는 script가 아니라 seed로 사용한다.
✓ Voice App은 dynamic follow-up을 수행한다.
✓ Plugin dependency는 hard lock보다 value-driven dependency를 우선한다.
✓ Interview 중 발견된 정보는 Evidence Candidate로 관리한다.
✓ 사용자 확인 후 Career Graph를 갱신한다.
```

아직 결정되지 않은 사항:

```text
[OPEN]

○ 최종 프로젝트/제품명
○ 구체 Career Graph schema
○ Graph DB 사용 여부
○ Plugin 내부 UI 범위
○ Voice App 플랫폼(Web/Mobile/Desktop)
○ LLM provider / model 선택
○ Realtime voice provider 선택
○ authentication 구조
○ Interview Package signing 방식
○ pricing/business model
○ JD discovery source
○ job application automation 범위
○ 개인정보 보관기간
```

---

# 24. 프로젝트의 핵심 한 문장

> CareerGround는 사용자의 경력을 대화로 발견하고 Evidence로 검증한 뒤,
> 그 Career Graph를 Resume, JD 분석 및 실제와 가까운 Voice Interview까지
> 일관되게 연결하는 Evidence-backed Career AI System을 목표로 한다.

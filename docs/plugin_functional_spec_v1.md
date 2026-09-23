# CareerGround Plugin Functional Specification v1

- Date: 2026-09-23
- Status: Approved functional baseline; implementation not started
- Product policy: [CareerGround Product Policy Proposal v0.1](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)
- Data contract: [Career Graph Schema v1](career_graph_schema_v1.md) and [v1.1 Policy Addendum](career_graph_schema_v1_1_policy_addendum.md)
- Profiling contract: [Career Profiling Protocol v1](career_profiling_protocol_v1.md)
- Interview handoff contract: [Interview Package Schema v1](interview_package_schema_v1.json)

## 1. Purpose

This specification defines the user flows, MCP tool surface, state changes, authorization, confirmations, errors and acceptance criteria for the CareerGround text MVP.

The MVP lets an authenticated user:

1. explicitly start a CareerGround profiling session;
2. supply task-specific career statements without granting access to all chats;
3. review atomic Claims and boundaries;
4. promote accepted Claims and Evidence into a versioned Career Graph;
5. analyze pasted JD text;
6. generate and review a traceable resume draft;
7. export the resume and personal profile data;
8. create a fixed-version interview plan and signed same-account Interview Package;
9. inspect or revoke an issued Interview Package;
10. preview and execute data deletion.

Voice interview execution remains a dependency for the next specification. Package creation is active in this contract; it does not mean the MCP server, signing service or Voice App is implemented.

## 2. Plugin shape

```text
CareerGround Plugin
  ├─ Workflow Skill
  │    └─ profiling sequence, boundary rules and tool order
  └─ Authenticated MCP Server
       ├─ Career Core tools
       ├─ stable structured results
       └─ optional Claim Review UI
```

The MCP server owns all authorization and data changes. The model may propose a tool call but does not decide resource ownership, approval validity, retention or publication eligibility.

The review UI is recommended for comparing, editing and confirming Claim batches. Every tool still returns a complete structured result so the workflow works without custom UI.

## 3. Scope

### 3.1 Included

- personal authenticated profile
- text profiling and pause/resume
- task-specific chat excerpts and pasted document excerpts
- atomic Claim review, contradiction resolution and boundary change
- Career Graph and Evidence trace views
- pasted-text JD analysis
- traceable resume draft, wording review and export
- fixed-version interview plan and signed same-account package handoff
- package status and explicit revocation
- profile export
- data-deletion preview, execution and status

### 3.2 Excluded

- full conversation-history access or reconstruction
- automatic import from unrelated chats
- JD URL fetching/crawling
- external career verification
- automated job application
- recruiter ranking or hiring probability
- payment
- voice session runtime
- external Interview Package sharing, file download or file import

## 4. Product invariants

1. Installing or connecting the plugin stores no conversation content.
2. Only inputs explicitly sent to a CareerGround session may enter its profiling workspace.
3. Drafts never mutate the canonical Career Graph.
4. Silence, missing decisions and model confidence are not user approval.
5. User confirmation is distinct from external verification.
6. Claim knowledge, consistency and usage state remain separate.
7. JD relevance never changes Claim truth or publication state.
8. Every verified resume unit resolves to Claims and eligible Evidence.
9. `DO_NOT_CLAIM` and unresolved contradiction guards cannot be bypassed by wording approval.
10. Permanent erasure overrides historical restoration for affected personal-data payloads.
11. No version, artifact or snapshot operation falls back silently to `latest`.
12. Every write is authorized, validated, auditable and safe to retry or explicitly marked otherwise.
13. Every Interview Package binds fixed artifact versions, one subject, one audience and one successful Interview Session.
14. A valid signature never overrides expiry, revocation, account ownership or deletion state.

## 5. Authentication and authorization

All MVP tools require an authenticated CareerGround account through an MCP-compatible OAuth 2.1 flow.

For every request the server MUST:

1. validate token signature, issuer, audience/resource, expiry and scope;
2. derive the account and user from the validated token;
3. verify ownership of every supplied resource ID;
4. enforce tool-specific scopes and current resource state;
5. reject ambiguous or cross-account access without revealing unnecessary resource details.

The model cannot supply a trusted `user_id` or override account scope. IDs in model-generated arguments are untrusted inputs.

Suggested OAuth scopes:

```text
career.profile.read
career.profile.write
career.artifact.read
career.artifact.write
career.export
career.delete
career.interview.read
career.interview.write
```

## 6. MCP naming and annotations

External tool names use stable action-oriented snake_case identifiers. Internal REST, command or service names may differ but MUST NOT alter the MCP contract silently.

Annotations reflect actual behavior:

- `readOnlyHint=true` only for operations that do not change CareerGround state;
- `destructiveHint=true` for permanent deletion;
- `openWorldHint=false` for bounded private-account operations and pasted JD text;
- a future JD URL fetch tool is separate and uses `openWorldHint=true`.

Annotations do not replace server authorization or exact confirmation checks.

## 7. Common response contract

### 7.1 Success

```json
{
  "status": "ok",
  "data": {},
  "next_actions": [],
  "user_message": "Concise outcome for the user"
}
```

Results include stable IDs, versions and actionable state needed for follow-up calls. They exclude access tokens, storage secrets, stack traces, internal database details and unrelated personal data.

### 7.2 Error

```json
{
  "status": "error",
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "The profile changed after this review was prepared.",
    "recoverable": true,
    "next_action": "PREPARE_NEW_REVIEW"
  }
}
```

Supported functional errors:

| Code | Meaning | Recovery |
| --- | --- | --- |
| `AUTH_REQUIRED` | no valid authentication | start authentication |
| `FORBIDDEN` | resource or scope not allowed | stop; do not disclose extra details |
| `NOT_FOUND` | target not found in authorized scope | reselect resource |
| `VALIDATION_FAILED` | invalid or excessive input | return safe field-level corrections |
| `VERSION_CONFLICT` | base profile version is stale | show relevant change and prepare a new review |
| `REVIEW_REQUIRED` | explicit user decision is missing | display exact review target |
| `REVIEW_EXPIRED` | review digest/token expired | prepare a new review |
| `BOUNDARY_BLOCKED` | wording violates an active constraint | show allowed source wording and relevant boundary |
| `CONTRADICTION_BLOCKED` | affected Claim is unresolved | open conflict review |
| `SESSION_PAUSED` | session requires resume | resume after version check |
| `SESSION_EXPIRED` | temporary data was deleted | start a new session |
| `DELETION_IN_PROGRESS` | data is isolated or being erased | show deletion status only |
| `RATE_LIMITED` | request limit reached | return retry time when known |
| `INTERNAL_ERROR` | unexpected server failure | preserve confirmed state and return non-sensitive reference |

An error never reports a partial canonical write as success.

## 8. Tool inventory

| Tool | Category | State effect | Confirmation | Annotations |
| --- | --- | --- | --- | --- |
| `start_profiling` | profiling | create temporary session | explicit profiling intent | write, non-destructive, closed world |
| `add_profiling_input` | profiling | append temporary input/draft | explicit task input | write, non-destructive, closed world |
| `get_profiling_session` | profiling | none | none | read-only, closed world |
| `pause_profiling` | profiling | pause session | user request or automatic policy transition | write, non-destructive |
| `prepare_claim_review` | review | create temporary review batch | none | write, non-destructive |
| `get_claim_review` | review | none | none | read-only, closed world |
| `submit_claim_review` | review | canonical profile version change | exact review digest and user decisions | write, non-destructive |
| `resolve_claim_conflict` | review | append conflict resolution/version | exact conflict review | write, non-destructive |
| `review_boundary_change` | review | add/change/remove boundary/version | exact boundary review | write, non-destructive |
| `get_career_profile` | graph | none | none | read-only, closed world |
| `get_claim_evidence` | graph | none | none | read-only, closed world |
| `export_profile_data` | export | create export artifact | explicit export request | write, non-destructive |
| `analyze_jd` | JD | store JD analysis draft | explicit pasted JD | write, non-destructive, closed world |
| `get_jd_analysis` | JD | none | none | read-only, closed world |
| `generate_resume_draft` | resume | create DRAFT artifact | explicit generation request | write, non-destructive |
| `get_resume_trace` | resume | none | none | read-only, closed world |
| `submit_resume_wording_review` | resume | create artifact version/review | exact wording review | write, non-destructive |
| `export_resume` | resume | create export artifact | explicit version/format selection | write, non-destructive |
| `create_interview_plan` | interview preparation | create DRAFT plan artifact | explicit target and duration | write, non-destructive, closed world |
| `create_interview_package` | interview handoff | issue immutable signed package | exact package summary and handoff approval | write, non-destructive, closed world |
| `get_interview_package_status` | interview handoff | none | none | read-only, closed world |
| `revoke_interview_package` | interview handoff | irreversibly revoke package | exact package and explicit revocation | write, destructive, closed world |
| `preview_data_deletion` | deletion | none | none | read-only, closed world |
| `execute_data_deletion` | deletion | permanent erasure | exact deletion digest and step-up confirmation | write, destructive |
| `get_deletion_status` | deletion | none | none | read-only, closed world |

## 9. Profiling tools

### 9.1 start_profiling

**Goal:** Start one explicit, bounded career-profiling session.

Input:

```json
{
  "profile_id": "uuid",
  "goal": "ADD_EXPERIENCE",
  "experience_hint": "optional task-specific text",
  "policy_version": "product-policy-v0.1"
}
```

Allowed `goal` values initially:

```text
ADD_EXPERIENCE
UPDATE_EXPERIENCE
RESOLVE_GAP
RESOLVE_CONTRADICTION
```

Output `data`:

```json
{
  "profiling_session_id": "uuid",
  "session_status": "ACTIVE",
  "base_profile_version": 12,
  "protocol_state": "CONTEXT_DISCOVERY",
  "retention_expires_at": "timestamp",
  "collection_scope": "Only content explicitly sent to this CareerGround session",
  "next_question": "..."
}
```

Preconditions and behavior:

- Authentication and profile ownership are required.
- Installation, login or an ordinary chat message never triggers this tool implicitly.
- If a compatible unexpired session already exists, return choices to resume it or explicitly start another scoped session.
- Creating the session does not change `career_profiles.current_version`.

Primary errors: `AUTH_REQUIRED`, `FORBIDDEN`, `VALIDATION_FAILED`, `DELETION_IN_PROGRESS`.

### 9.2 add_profiling_input

**Goal:** Add one task-specific statement or selected excerpt to an active CareerGround session.

Input:

```json
{
  "profiling_session_id": "uuid",
  "base_profile_version": 12,
  "content": "Explicitly supplied content",
  "content_kind": "USER_STATEMENT",
  "client_locator": {
    "conversation_ref": "optional",
    "message_ref": "optional"
  }
}
```

Allowed content kinds:

```text
USER_STATEMENT
SELECTED_CHAT_EXCERPT
PASTED_DOCUMENT_EXCERPT
CORRECTION
```

Output includes session status, new protocol state, next question, draft count and unresolved guards. It never claims that a canonical Claim was created.

Rules:

- A raw message-array/full-chat parameter is not supported.
- The server enforces input size and type limits.
- `client_locator` is a locator only; it does not authorize fetching other messages.
- Accepted input refreshes that session's `last_activity_at` and 90-day expiry.
- A paused session requires explicit resume behavior and a base-version check.

Primary errors: `FORBIDDEN`, `VERSION_CONFLICT`, `SESSION_PAUSED`, `SESSION_EXPIRED`, `VALIDATION_FAILED`.

### 9.3 get_profiling_session

Input: `profiling_session_id`.

Output:

```text
session status
base/current profile version
protocol state
experience scope
last activity and expiry
unresolved guards
draft summary without unnecessary raw content
next allowed actions
```

This tool does not return unrelated conversation history.

### 9.4 pause_profiling

Input: `profiling_session_id`, optional reason.

Output: new `PAUSED` status, last activity, expiry and resume instructions.

The server also applies the approved 30-minute automatic pause. Automatic pause is a server policy transition and not evidence of user approval or abandonment.

## 10. Claim review tools

### 10.1 prepare_claim_review

Input:

```json
{
  "profiling_session_id": "uuid",
  "experience_scope_id": "uuid",
  "base_profile_version": 12
}
```

Output:

```json
{
  "review_batch_id": "uuid",
  "base_profile_version": 12,
  "review_digest": "sha256:...",
  "expires_at": "timestamp",
  "items": [
    {
      "review_item_id": "uuid",
      "claim_text": "...",
      "claim_type": "CONTRIBUTION",
      "scope": {},
      "evidence_excerpts": [],
      "blocked_expansions": [],
      "high_impact": false,
      "allowed_actions": ["ACCEPT", "EDIT", "FOLLOW_UP", "EXCLUDE"]
    }
  ]
}
```

Rules:

- One batch contains one project/bounded experience and at most five atomic Claims.
- High-impact Claims appear as separate items.
- Evidence and blocked expansions are shown with the exact Claim.
- Preparing a batch creates no canonical Claim or profile version.

### 10.2 get_claim_review

Input: `review_batch_id`.

Output: the exact review target, remaining expiry, current base-version compatibility and already recorded item decisions. It does not refresh the review digest or silently adopt a new profile version.

### 10.3 submit_claim_review

Input:

```json
{
  "review_batch_id": "uuid",
  "review_digest": "sha256:...",
  "base_profile_version": 12,
  "decisions": [
    {"review_item_id": "uuid", "action": "ACCEPT"},
    {"review_item_id": "uuid", "action": "EDIT", "edited_text": "..."},
    {"review_item_id": "uuid", "action": "FOLLOW_UP"},
    {"review_item_id": "uuid", "action": "EXCLUDE", "reason": "DO_NOT_USE"}
  ],
  "approval_token": "server-issued short-lived token"
}
```

Allowed exclusion reasons:

```text
NOT_TRUE
DO_NOT_USE
```

Behavior:

- Validate owner, digest, token, base version, explicit decisions and guards.
- Promote all accepted items in one transaction and increment profile version once.
- `EDIT` creates a new draft; it is not accepted automatically.
- `FOLLOW_UP` creates or resumes questions outside the canonical graph.
- `NOT_TRUE` preserves a factual negative boundary.
- `DO_NOT_USE` preserves a usage boundary without declaring the proposition false.
- Replaying the same approval returns the original result.

Output includes profile versions before/after, promoted Claim/Evidence IDs, new constraints and remaining draft/follow-up items.

### 10.4 resolve_claim_conflict

Input:

```text
profile_id
base_profile_version
conflict_id
resolution: KEEP_EXISTING | ACCEPT_CORRECTION | KEEP_BOTH_SCOPED | REMAIN_UNCERTAIN
review_digest
approval_token
optional explanation/evidence candidate IDs
```

The result appends review/assessment history and creates a new profile version when canonical state changes. Opposing Evidence is retained during normal correction. Only permanent erasure may remove its personal-data payload.

### 10.5 review_boundary_change

Input binds the target, old boundary, proposed boundary, new Evidence, allowed wording, remaining prohibited expansion, base version, digest and approval token.

This tool is the only MVP path for adding, changing or removing an existing `DO_NOT_CLAIM` boundary after initial review. Resume wording approval cannot call this behavior implicitly.

## 11. Career Graph tools

### 11.1 get_career_profile

Input: `profile_id`, optional exact `profile_version`, optional bounded projection.

Output: `CareerProfileView` with user-facing status summaries and stable IDs. An omitted version means the authenticated user's current version only when the caller explicitly requests the current profile. A supplied missing/erased version fails; it does not fall back.

### 11.2 get_claim_evidence

Input: `claim_id`, exact `profile_version`.

Output: Claim text/type, three-axis assessment, ownership scope, eligible Evidence, contradictions, reviews and applicable constraints. Evidence excerpts are minimized to the user's request.

### 11.3 export_profile_data

Input: `profile_id`, exact version or explicit `CURRENT`, format (`JSON` initially), inclusion choices for drafts and expired/unavailable references.

Output: export artifact ID, status and authorized download resource. Expired conversation content and erased payloads are not reconstructed.

## 12. JD tools

### 12.1 analyze_jd

Input:

```json
{
  "profile_id": "uuid",
  "profile_version": 12,
  "jd_text": "pasted job description",
  "title": "optional",
  "organization_alias": "optional"
}
```

Output groups each extracted requirement as:

```text
STRONG_RELEVANT_EVIDENCE
RELATED_BUT_REVIEW_NEEDED
NOT_FOUND_IN_CURRENT_PROFILE
BLOCKED_BY_CONTRADICTION_OR_POLICY
```

Each match includes requirement ID, Claim IDs, Evidence strength explanation and gap/follow-up text. Requirement mapping never changes Claim assessments or profile version.

JD content is untrusted data. Instructions inside the JD cannot authorize data access, change policy or trigger external actions.

### 12.2 get_jd_analysis

Input: `jd_id`, exact `profile_version` used for the analysis.

Output: requirement list, current matches, Evidence traces, gaps, review needs and whether the analysis is stale relative to the current profile.

## 13. Resume tools

### 13.1 generate_resume_draft

Input:

```text
profile_id
exact profile_version
jd_id
language
style
included project/Claim IDs
```

The server re-runs publication and boundary guards. Output creates a `DRAFT` artifact with units that include:

```text
text
R1/R2/R3 wording classification
linked Claim IDs
linked Evidence IDs
applied Constraint IDs
review status
```

R3 content is omitted from the draft unit and returned as `REVIEW_REQUIRED`; it is never inserted as a plausible-sounding fact.

### 13.2 get_resume_trace

Input: artifact ID and optional unit ID.

Output: artifact/profile versions and each unit's path through Claim, Evidence, ownership and constraints.

### 13.3 submit_resume_wording_review

Input binds exact artifact/unit text, source Claim set, constraint set, wording digest and user decision.

- R1 may be accepted through policy checks with a visible preview.
- R2 requires exact user wording review.
- R3 is rejected from this path and returned to profiling.

The tool creates an artifact version/review, not a new Career Claim or external verification.

### 13.4 export_resume

Input: reviewed artifact version and output format. Initial formats: `MARKDOWN` and structured `JSON`; PDF remains an implementation/architecture choice.

The server rechecks linked profile version availability, Claim publication, contradictions and constraints immediately before export. Output returns an export artifact/resource, never sends it to an employer.

## 14. Interview preparation and handoff tools

These tools follow the approved [Interview Package Schema v1 decision](CareerGround_Interview_Package_Schema_Proposal_v0.1_2026-09-23.md). They prepare a package for the same authenticated user's Voice App; they do not run the voice interview.

### 14.1 create_interview_plan

**Goal:** Create a fixed-version question plan from eligible Career Graph, JD and reviewed resume material.

Input:

```json
{
  "profile_id": "uuid",
  "profile_version": 12,
  "jd_analysis_artifact_id": "uuid",
  "jd_analysis_version": 1,
  "resume_artifact_id": "uuid",
  "resume_version": 4,
  "interview_type": "JD_TARGETED",
  "duration_minutes": 30,
  "focus_claim_ids": ["uuid"],
  "base_profile_version": 12,
  "idempotency_key": "opaque-client-value"
}
```

`interview_type` is `JD_TARGETED` or `GENERAL`. A targeted plan requires a JD analysis; a general plan may omit it. The server resolves only the exact supplied versions, rechecks Claim publication and constraint state, and creates a `DRAFT` Interview Plan artifact. It never selects `latest` implicitly.

Output `data` includes:

```text
interview_plan_artifact_id
version
profile_id + profile_version
source artifact IDs + versions
duration_minutes
objectives
core question summaries and trace IDs
excluded Claim IDs with safe reason categories
plan_digest
```

The draft plan does not issue a package, reserve a session or change the Career Graph.

### 14.2 create_interview_package

**Goal:** Issue one immutable signed package and a short-lived same-account handoff.

Input:

```json
{
  "profile_id": "uuid",
  "profile_version": 12,
  "jd_analysis_artifact_id": "uuid",
  "jd_analysis_version": 1,
  "resume_artifact_id": "uuid",
  "resume_version": 4,
  "interview_plan_artifact_id": "uuid",
  "interview_plan_version": 2,
  "selected_claim_ids": ["uuid"],
  "selected_evidence_ids": ["uuid"],
  "selected_constraint_ids": ["uuid"],
  "plan_digest": "server-issued exact digest",
  "confirmation_token": "server-issued exact package-summary approval",
  "idempotency_key": "opaque-client-value"
}
```

Before signing, the server verifies ownership, exact versions, artifact relationships, publication gates, Evidence availability, constraint completeness, approved size limits and the exact package summary shown to the user. Creation is atomic: either one immutable `ISSUED` package and handoff are recorded or no usable package remains.

Output `data` includes:

```text
package_id
schema_version
status = ISSUED
issued_at
expires_at
included item counts
profile and artifact version references
handoff_url or handoff_code
handoff_expires_at
```

The tool does not return raw Evidence or the signed payload in normal chat output. The handoff secret is single-exchange, short-lived and bound to the authenticated account. It is not the package signature and does not authorize a different account.

### 14.3 get_interview_package_status

Input: owned package ID.

Output contains `ISSUED`, `REVOKED` or `EXPIRED`, expiry, safe revocation reason category, and an existing Interview Session reference when one has already started. It does not return the handoff secret or raw package payload.

### 14.4 revoke_interview_package

Input binds the owned package ID, current package digest and explicit user confirmation. Revocation is irreversible for that package but does not delete source Career Graph data. A new package requires a new creation request.

The tool uses `destructiveHint=true`. It is idempotent: replay against the same already-revoked package returns the same terminal result. If a session already started, the result also reports that the Voice App must enter `DATA_REVOKED_DURING_SESSION` and stop new use of affected data.

### 14.5 Interview Package errors

```text
PACKAGE_EXPIRED
PACKAGE_REVOKED
PACKAGE_ALREADY_USED
PACKAGE_SUBJECT_MISMATCH
PACKAGE_AUDIENCE_MISMATCH
PACKAGE_SIGNATURE_INVALID
PACKAGE_SCHEMA_UNSUPPORTED
PACKAGE_REFERENCE_INVALID
PACKAGE_SCOPE_TOO_LARGE
PACKAGE_SOURCE_UNAVAILABLE
```

The server never resolves one of these errors by silently substituting the latest profile or another package.

## 15. Deletion tools

### 15.1 preview_data_deletion

Input:

```json
{
  "scope": "EVIDENCE",
  "target_ids": ["uuid"]
}
```

Allowed scopes:

```text
SESSION
EVIDENCE
PROJECT
PROFILE
ACCOUNT
```

Output lists data to erase, data to isolate, Claims to reassess, artifacts/snapshots to make unavailable, packages to revoke and known downloaded-copy limitations. It returns a short-lived `deletion_digest` and does not mutate data.

### 15.2 execute_data_deletion

Input:

```text
deletion_digest
step-up approval token
explicit acknowledgement of listed impact
```

The server verifies that the impact set has not changed. It immediately isolates targets, creates an erasure request and starts idempotent deletion across storage layers. The result reports `IN_PROGRESS` or `COMPLETED`; partial failure remains visible.

This tool uses `destructiveHint=true` and scope `career.delete`.

### 15.3 get_deletion_status

Input: erasure request ID.

Output: user-relevant status by storage category, affected artifacts/versions, completion or retry state, and any legally required separately retained category without exposing internal infrastructure.

## 16. User flows

### 16.1 Profile one experience

```text
start_profiling
  → add_profiling_input (repeat)
  → prepare_claim_review
  → user decisions
  → submit_claim_review
  → get_career_profile / get_claim_evidence
```

### 16.2 Pause and resume

```text
pause request or 30-minute inactivity
  → PAUSED
  → resume before 90-day expiry
  → compare base/current profile version
  → reuse compatible draft or prepare new review
```

### 16.3 JD and resume

```text
analyze_jd
  → get_jd_analysis
  → generate_resume_draft
  → get_resume_trace
  → submit_resume_wording_review
  → export_resume
```

### 16.4 Interview handoff

```text
create_interview_plan
  → inspect fixed source versions and question trace
  → create_interview_package with exact summary confirmation
  → authenticated handoff code/link
  → Voice App verifies signature, subject, audience, expiry and registry status
  → one Interview Session starts
```

### 16.5 Contradiction

```text
conflict detected
  → affected Claim blocked
  → get claim/evidence context
  → resolve_claim_conflict
  → new assessment/review/version
  → publication re-evaluated
```

### 16.6 Permanent deletion

```text
preview_data_deletion
  → exact impact shown
  → explicit step-up confirmation
  → execute_data_deletion
  → immediate isolation
  → storage/archives/artifacts processed
  → get_deletion_status
```

## 17. Concurrency and retry behavior

- Every canonical write requires `base_profile_version`.
- Review and deletion execution require a server-issued short-lived digest/token.
- Write tools are idempotent for the same accepted operation.
- A version conflict never auto-merges ownership, constraints, contradictions or approvals.
- Temporary draft generation may be retried, but only the latest valid review digest can be submitted.
- Long-running deletion returns a status resource rather than holding the tool call indefinitely.
- Package creation retries with the same idempotency key return the same package and do not issue multiple handoff grants.
- A successful package-to-session exchange is atomic; network retry returns the existing session rather than consuming a second package.

## 18. Logging and privacy

Operational logs contain tool name, success/failure category, latency and non-sensitive correlation data needed to diagnose failures. They do not contain access tokens, full career statements, raw Evidence, resume content or full chat transcripts.

Signed package payloads, Evidence excerpts, detached JWS values and handoff codes are also excluded from application logs, analytics and error reports.

CareerGround content retention is enforced in domain storage, indexes, caches, queues and backups. General infrastructure logs are not an alternate archive for expired or erased content.

## 19. Acceptance criteria

1. Installation and authentication alone create no profiling data.
2. Tool schemas do not accept full-chat arrays or broad conversation context.
3. Every private-resource tool rejects cross-account IDs.
4. Starting, pausing, drafting and preparing reviews do not increment profile version.
5. A batch has one bounded experience and no more than five atomic items.
6. Missing decisions are never approved.
7. `EDIT` returns to draft review.
8. Both exclusion reasons preserve distinct negative/usage semantics.
9. Stale review digest, token or profile version cannot promote data.
10. Promotion is transactional and replay-safe.
11. R2 approval cannot introduce R3 facts or ownership.
12. Conflict resolution and boundary change require separate exact reviews.
13. JD mapping does not modify Claim status.
14. Every exported resume unit resolves to eligible Claims/Evidence.
15. 30-minute automatic pause has no canonical side effect.
16. Only same-session CareerGround activity refreshes the 90-day expiry.
17. Deletion preview has no side effect.
18. Deletion execution fails if the impact digest is stale.
19. Erased versions fail explicitly and never fall back to latest.
20. Errors and retries leave no partial canonical writes.
21. Interview plans and packages reference exact profile and artifact versions, never `latest`.
22. Package issuance excludes full chats, original documents, recordings and credentials.
23. A package is not issued if any selected Claim fails its publication or boundary gate.
24. Package issuance is atomic, signed and idempotent.
25. The normal tool response does not expose the signed payload or raw Evidence.
26. Other accounts and audiences cannot exchange or start the package.
27. Expired or revoked packages fail even when their signature is valid.
28. One package cannot create two successful Interview Sessions.
29. Package revocation is idempotent and never deletes source Career Graph data by itself.
30. Deleted package data is not reconstructed from the latest profile or another snapshot.

## 20. Dependencies and next specifications

The following must be decided before implementation begins:

- concrete OAuth identity provider and account mapping;
- PostgreSQL/ORM schema for v1.1 workspace and archive registry;
- protected object storage and deletion capabilities;
- background retention/erasure execution;
- LLM provider and data-processing configuration;
- Markdown/JSON artifact storage and optional PDF pipeline;
- deployment, monitoring, rate limiting and secret management;
- managed ES256/P-256 KMS signing, JWKS publication, key rotation and emergency revocation (Architecture v1 decision);
- atomic handoff exchange and Interview Package registry.

`interview_package_schema_v1.json`, [Voice Interview Agent Specification v1](voice_interview_agent_spec_v1.md) and [MVP Architecture v1](architecture_v1.md) are approved contracts with synthetic reference validation where applicable. The next review artifact is the [Step 7 Implementation Task Breakdown](../PLAN-2026-09-23-mvp-implementation.md).

## 21. Official platform alignment

This specification follows current official OpenAI guidance:

- [Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)
- [Define tools](https://developers.openai.com/plugins/plan/tools)
- [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [Authentication](https://developers.openai.com/plugins/build/auth)
- [Plugin guidelines](https://developers.openai.com/plugins/app-guidelines)

The platform guidance supports the MCP/auth/tool boundaries. CareerGround-specific review counts, session timing, retention and deletion semantics come from the approved product policy.

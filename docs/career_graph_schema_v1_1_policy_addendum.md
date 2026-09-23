# Career Graph Schema v1.1 Policy Addendum

- Date: 2026-09-22
- Status: Approved policy contract; implementation and database validation not started
- Amends: [Career Graph Schema v1](career_graph_schema_v1.md)
- Policy authority: [CareerGround Product Policy Proposal v0.1](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)
- Decision source: `DECISION-P10`–`DECISION-P20`

## 1. Purpose and precedence

This addendum incorporates the approved text-MVP policies for profiling workspace, exact review binding, retention, erasure and plugin-facing projections.

Schema v1 remains the validated baseline. All v1 rules continue to apply unless this addendum explicitly changes them. In case of conflict:

```text
approved product-policy decision
  → this v1.1 addendum
  → Schema v1
  → earlier concept documents
```

This document does not claim that PostgreSQL migrations, background retention jobs, erasure jobs, OAuth, MCP tools or integration tests exist.

## 2. Adopted policy constants

| Constant | Approved value |
| --- | --- |
| review batch scope | one project or one clearly bounded experience |
| maximum review items | 5 atomic Claims |
| inactivity before automatic pause | 30 minutes without CareerGround input |
| profiling workspace retention | 90 days from the session's last actual CareerGround activity |
| selected voice recording retention | 30 days from recording completion; raw recording storage disabled by default |
| full-chat collection | prohibited; only task-specific content explicitly sent to CareerGround |

The 30-minute pause changes runtime status only. It does not approve, delete or promote data, and it does not start a new 90-day period by itself.

## 3. Profiling workspace boundary

Profiling workspace data is not canonical Career Graph data.

```text
Explicit CareerGround input
  → profiling workspace
  → draft Claim/Evidence/scope/constraint
  → review batch with exact digest
  → explicit user decisions
  → one canonical promotion transaction
  → Profile version N+1
```

Plugin installation, authentication, ordinary chat activity and unrelated conversations MUST NOT create profiling messages or refresh profiling retention.

The workspace MAY retain CareerGround-generated questions and summaries that are necessary to interpret explicitly supplied answers. It MUST NOT fetch, request, reconstruct or persist the user's full ChatGPT conversation history.

## 4. Profiling session contract

### 4.1 Status values

The profiling runtime uses the following workspace statuses. These are not Claim assessment enums.

```text
ACTIVE
PAUSED
AWAITING_REVIEW
COMPLETED
ABANDONED
EXPIRED
```

`COMPLETED` means the selected experience passed the Profiling Protocol completion guards. It does not mean every Claim is `ALLOWED` for publication.

### 4.2 Required profiling session fields

The future `profiling_sessions` storage contract MUST represent at least:

```text
id
profile_id
status
base_profile_version
protocol_state
experience_scope
source_surface
policy_version
started_at
last_activity_at
paused_at
ended_at
expires_at
```

`last_activity_at` changes only for activity explicitly processed as part of that CareerGround session. Login, ordinary chat and another profiling session do not refresh it.

### 4.3 State transitions

```text
ACTIVE → PAUSED
  explicit pause or 30-minute inactivity

ACTIVE → AWAITING_REVIEW
  review batch prepared

PAUSED/AWAITING_REVIEW → ACTIVE
  explicit resume before expiry, after profile-version check

ACTIVE/AWAITING_REVIEW → COMPLETED
  completion guards satisfied and required reviews handled

ACTIVE/PAUSED/AWAITING_REVIEW → ABANDONED
  explicit user decision

PAUSED/AWAITING_REVIEW/ABANDONED → EXPIRED
  retention expiry and temporary-data deletion
```

An expired session is not restored from logs or another chat. The user starts a new session. Canonical Evidence previously selected and promoted follows its separate retention policy.

## 5. Workspace storage contract

The implementation MUST provide equivalent storage for the following logical structures. Exact SQL and physical partitioning are architecture decisions.

### 5.1 profiling_messages

Required semantics:

```text
id
profiling_session_id
sequence
speaker: USER | ASSISTANT
content_kind
content_text or protected object reference
content_hash
client_locator (optional, non-authoritative)
created_at
expires_at
redaction/deletion state
```

Initial `content_kind` values:

```text
USER_STATEMENT
SELECTED_CHAT_EXCERPT
PASTED_DOCUMENT_EXCERPT
CORRECTION
CAREERGROUND_QUESTION
CAREERGROUND_SUMMARY
```

An array representing a raw full chat is not an allowed input shape.

### 5.2 profiling_drafts

Drafts hold proposed atomic Claims, Evidence excerpts, context, ownership, outcomes, constraints, unresolved guards and contradiction indicators. Drafts MUST remain excluded from canonical profile projections and verified artifact generation.

### 5.3 profiling_review_batches

Each batch MUST bind:

```text
id
profiling_session_id
profile_id
base_profile_version
experience_scope
review_digest
status
created_at
expires_at
submitted_at
```

A batch contains at most five atomic review items and only one project or bounded experience scope.

### 5.4 profiling_review_items

Each item MUST bind the exact values the user reviewed:

```text
canonical_text
claim_type
context and ownership scope
evidence candidate IDs and content hashes
applicable constraint IDs and boundary text
high-impact flag
base_profile_version
```

Allowed user decisions:

```text
ACCEPT
EDIT
FOLLOW_UP
EXCLUDE_NOT_TRUE
EXCLUDE_DO_NOT_USE
```

No missing or default decision means approval.

`EDIT` produces a new draft and requires review of the changed text. `FOLLOW_UP` stays outside the canonical graph. Both exclusion decisions preserve an exact negative boundary so generation does not repeat the same disallowed proposition. `EXCLUDE_NOT_TRUE` records a factual rejection; `EXCLUDE_DO_NOT_USE` records a usage restriction without declaring the proposition false.

## 6. Exact review authority

The review digest MUST cover:

```text
exact Claim text
Claim type
context and ownership scope
Evidence candidate IDs and content hashes
relevant constraint IDs and text
base profile version
review purpose
```

Review purposes:

```text
FACT_CONFIRMATION
ARTIFACT_WORDING
BOUNDARY_CHANGE
EVIDENCE_ACCEPTANCE
CONTRADICTION_RESOLUTION
```

`claim_reviews` MUST be extended or linked to preserve:

- the originating review item;
- the exact review digest;
- the base profile version shown to the user;
- the review purpose.

An artifact-wording review cannot confirm a new fact, change ownership, resolve a contradiction or remove a `DO_NOT_CLAIM` boundary.

## 7. Promotion transaction

Submitting one review batch promotes accepted items in a single atomic transaction.

```text
lock profile and review batch
verify authenticated owner
verify review digest, approval token and base profile version
verify every explicit item decision
re-run contradiction, boundary and publication guards
create or attach EvidenceSource/EvidenceItem
create Claim/context/ownership records as needed
create EvidenceClaimLink
append ClaimAssessment and ClaimReview
create ProfileChangeSet
increment profile version once
mark review items promoted
commit
```

Any failure rolls back all canonical changes from that submission. Replaying the same valid approval returns the existing promotion result and MUST NOT increment the version again.

A base-version mismatch fails with a version conflict. The implementation MUST show relevant changes and prepare a new review; it MUST NOT silently attach the old approval to the latest profile.

## 8. Rewriting and publication

### 8.1 Wording levels

```text
R1  formatting-only change
R2  meaning-preserving rewrite, translation or atomic-Claim composition
R3  new fact or changed scope
```

- R1 may skip factual reconfirmation after deterministic formatting and boundary checks; the user still receives an artifact preview.
- R2 requires an `ARTIFACT_WORDING` review against the source Claims and constraints.
- R3 returns to profiling as a new Claim candidate.
- Uncertain classification is handled as R2.

### 8.2 Invalidation

An accepted R2 wording MUST be reviewed again when:

- a linked Claim or Evidence item changes or is erased;
- a contradiction or new constraint affects it;
- the generated wording materially changes;
- JD tailoring expands responsibility, result or ownership emphasis.

Publication guard failure falls back to reviewed atomic wording or omits the unit. It never adds the blocked wording silently.

## 9. Contradiction and boundary changes

An unresolved contradiction blocks only affected Claims and derived units. Unaffected projects and Claims remain usable.

Contradiction resolution and boundary changes are separate actions:

- `resolve_claim_conflict` compares conflicting propositions and Evidence, then appends an assessment/review in a new profile version.
- `review_boundary_change` adds, changes or removes a `DO_NOT_CLAIM` boundary after showing the old reason, new Evidence, newly allowed wording and remaining prohibited expansion.

Normal correction keeps historical opposing Evidence and review records. User-requested permanent erasure follows §11 and may remove personal-data payloads.

## 10. Retention execution

On profiling-session expiry, the system MUST remove:

- profiling messages;
- unpromoted drafts and review batches;
- temporary uploaded content and extracted text;
- workspace caches, indexes, embeddings and queued payloads.

The deletion worker must be idempotent. A retry cannot restore expired workspace data or promote an expired draft.

Selected canonical Evidence is not deleted merely because the workspace expires. The UI must distinguish stored Evidence excerpts from the deleted full workspace conversation.

## 11. Permanent erasure exception

Schema v1 §28.4 normally requires immutable complete snapshots. The following approved exception replaces that requirement for user-requested permanent erasure:

```text
normal correction/versioning:
  preserve complete historical snapshot

permanent erasure:
  isolate affected data immediately
  erase personal-data payload from live and archived storage
  keep only a minimal non-identifying restoration tombstone
```

The implementation MUST provide an archive registry equivalent to:

```text
profile_id
profile_version
availability_status: AVAILABLE | ERASURE_PENDING | ERASED
storage_ref and content_hash (only while AVAILABLE)
erased_at
erasure_request_id
```

The tombstone MUST NOT contain original text, source content, identifying hashes that permit practical reconstruction, or deleted personal data.

Affected artifacts become `UNAVAILABLE_DUE_TO_ERASURE`. A request for an erased version fails explicitly and MUST NOT fall back to the latest profile. Related Interview Packages are revoked. Downloaded or externally shared copies are not represented as recovered or remotely deleted.

## 12. Deletion workflow contract

Deletion uses two separate operations:

1. preview the impact and issue a short-lived deletion digest;
2. verify the exact digest and explicit user confirmation, then execute.

The preview enumerates affected Evidence, Claims, constraints, artifacts, snapshots, packages, caches and indexes. If the target set changes before execution, the digest is invalid and a new preview is required.

Execution immediately excludes targets from reads, generation and export, then processes each storage layer. Partial failure remains visible as `DELETION_IN_PROGRESS` or an error state. It is never reported as complete.

## 13. Plugin-facing projections

Schema v1 read models remain stable. The plugin additionally requires:

```text
ProfilingSessionView
ClaimReviewBatchView
ClaimConflictView
BoundaryChangeView
DeletionImpactView
DeletionStatusView
ArchiveAvailabilityView
```

These projections expose stable IDs and user-relevant state. They exclude access tokens, internal stack traces, storage secrets, unrelated personal data and raw full-chat content.

## 14. Required validation additions

The v1.1 validation suite MUST add at least these cases while retaining all v1 regression tests:

1. Plugin installation and login create no profiling message.
2. Only explicitly supplied task content appears in a session.
3. A review batch rejects more than five items or mixed project scopes.
4. Missing item decisions are not treated as approval.
5. `EDIT` creates a new draft rather than a confirmed Claim.
6. The two exclusion reasons result in distinct factual/usage semantics and both preserve a generation boundary.
7. R2 wording approval cannot add an R3 fact, metric or ownership scope.
8. A stale base profile version cannot be promoted.
9. Promotion is atomic and replay-safe.
10. An unresolved contradiction blocks only affected outputs.
11. Boundary removal requires a separate exact review.
12. The 90-day expiry clock changes only on actual CareerGround session activity.
13. Expiry removes workspace content while preserving separately promoted Evidence.
14. Erasure removes archived payload and leaves only an `ERASED` tombstone.
15. An erased artifact/version never falls back to latest.
16. Backup recovery reapplies the erasure ledger before user access resumes.

## 15. Compatibility and migration

- Existing v1 fixtures remain valid v1 fixtures.
- No existing v1 enum is repurposed silently.
- Workspace statuses and review purposes are separate domains.
- Production migration numbering will be assigned in the MVP Architecture/implementation breakdown.
- Existing archives become registry entries with `AVAILABLE` status when v1.1 storage is introduced.
- No historical snapshot may be declared erasable until live data, object storage, cache, index, queue and backup paths are mapped.

## 16. Definition of done

This addendum becomes implementation-validated only when:

- concrete SQL/ORM or equivalent schemas exist;
- tool/API schemas enforce task-specific input and exact review binding;
- retention and erasure workers are implemented idempotently;
- authorization is enforced for every workspace and canonical resource;
- all v1 regression tests and §14 additions pass;
- the validation report documents remaining limits without claiming legal or semantic guarantees not tested.

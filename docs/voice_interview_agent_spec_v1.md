# CareerGround Voice Interview Agent Specification v1

- Date: 2026-09-23
- Status: Approved behavioral contract; application implementation not started
- Policy authority: [CareerGround Product Policy](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)
- Decision source: [Voice Interview Agent v1 Proposal](CareerGround_Voice_Interview_Agent_Proposal_v0.1_2026-09-23.md), `PROPOSAL-VI01`–`PROPOSAL-VI22`
- Input contract: [Interview Package Schema v1](interview_package_schema_v1.json)

## 1. Purpose

This specification defines the provider-independent behavior of CareerGround's evidence-aware voice mock-interview agent. It fixes session and turn states, preflight, question selection, transcript handling, feedback, candidate extraction, data revocation and retry behavior.

It does not select a realtime voice provider, LLM, ASR, TTS, WebRTC/WebSocket stack, database or deployment platform. Those are MVP Architecture decisions.

## 2. v1 scope

### Included

- authenticated same-account use of one valid signed Interview Package;
- `SIMULATION` and `COACHING` run modes;
- realtime voice with captions and text fallback;
- package-bounded evidence-aware questions and follow-ups;
- transcript confirmation and correction;
- itemized answer feedback without hiring prediction;
- `PENDING`/`NEEDS_FOLLOWUP` EvidenceCandidate creation;
- pause, reconnect and resume within 24 hours;
- mid-session package/data revocation.

### Deferred

- resume/JD-only General Interview without a signed package;
- external or recruiter-facing sessions;
- hiring recommendation, pass probability, percentile or user ranking;
- camera, facial, emotion, personality or health inference;
- production provider and infrastructure choices.

General Interview remains a planned soft-dependency path for v1.1. It MUST NOT use evidence-verified labels without a signed package.

## 3. Normative invariants

1. Evidence-aware interviewing requires a valid package, authenticated matching subject and allowed audience.
2. One package creates at most one successful Interview Session.
3. The fixed package is the factual comparison boundary; the agent never substitutes `latest` profile data.
4. A valid signature does not override expiry, revocation, deletion or account ownership.
5. Partial or uncertain ASR text is not a confirmed user answer.
6. Agent questions and summaries are not independent Evidence.
7. Answer assessment never changes canonical Claim truth, consistency or usage state.
8. New career facts remain candidates until the existing Plugin review and promotion transaction succeeds.
9. Silence, accent, disability, voice characteristics and ASR quality are not competence signals.
10. Every persisted write is authorized, idempotent and traceable to the exact package, session, turn and transcript version.

## 4. Session contract

### 4.1 Session states

```text
CREATED
PREFLIGHT
READY
IN_PROGRESS
PAUSED
COMPLETING
COMPLETED
ABORTED
FAILED
DATA_REVOKED
```

Terminal states:

```text
COMPLETED
ABORTED
FAILED
DATA_REVOKED
```

Terminal sessions never return to an active state. Retry metadata may be appended without changing the terminal outcome.

### 4.2 Allowed transitions

| From | Event | To | Required guard |
| --- | --- | --- | --- |
| `CREATED` | `BEGIN_PREFLIGHT` | `PREFLIGHT` | authenticated subject and syntactically supplied package |
| `PREFLIGHT` | `ACCEPT_PREFLIGHT` | `READY` | required notices accepted; device or text fallback ready |
| `PREFLIGHT` | `CANCEL` | `ABORTED` | user request |
| `READY` | `START` | `IN_PROGRESS` | signature, subject, audience, status and single-session guards pass atomically |
| `READY` | `PACKAGE_REVOKED` | `DATA_REVOKED` | authoritative registry result |
| `READY` | `CANCEL` | `ABORTED` | user request |
| `IN_PROGRESS` | `PAUSE` | `PAUSED` | user request or recoverable technical interruption |
| `IN_PROGRESS` | `FINISH` | `COMPLETING` | planned end or user early end after at least one confirmed answer |
| `IN_PROGRESS` | `DATA_WITHDRAWN` | `DATA_REVOKED` | package or included data revoked/deleted |
| `IN_PROGRESS` | `UNRECOVERABLE_FAILURE` | `FAILED` | no safe retry path |
| `PAUSED` | `RESUME` | `IN_PROGRESS` | same account, before `resume_until`, package still usable for this session |
| `PAUSED` | `FINISH` | `COMPLETING` | user end or resume window expiry |
| `PAUSED` | `DATA_WITHDRAWN` | `DATA_REVOKED` | authoritative registry result |
| `COMPLETING` | `COMMIT_RESULTS` | `COMPLETED` | feedback/candidate transaction succeeds |
| `COMPLETING` | `PERSISTENCE_RETRY` | `COMPLETING` | bounded idempotent retry |
| `COMPLETING` | `UNRECOVERABLE_FAILURE` | `FAILED` | bounded retries exhausted |

Any unlisted transition returns `INVALID_SESSION_TRANSITION` without changing state.

### 4.3 Completion reasons

```text
PLAN_COMPLETED
USER_ENDED_EARLY
RESUME_WINDOW_EXPIRED
TIME_BUDGET_REACHED
```

`COMPLETED` means session outputs were stored; it never means Claims were promoted.

### 4.4 Resume policy

- `resume_until = paused_at + 24 hours`.
- The package's seven-day new-start expiry does not block resuming the already linked session.
- Subject, current session state and data-revocation status are rechecked on resume.
- After `resume_until`, no new question is asked. The session proceeds to partial completion.

## 5. Realtime turn contract

### 5.1 Turn states

```text
LISTENING
FINALIZING_TRANSCRIPT
AWAITING_TRANSCRIPT_CORRECTION
THINKING
SPEAKING
INTERRUPTED
RECONNECTING
```

The media/turn state is independent from the session state. Only an `IN_PROGRESS` session may begin a new `LISTENING` turn.

### 5.2 Normal turn flow

```text
question selected and traced
  → question delivered
  → LISTENING
  → partial ASR (ephemeral)
  → FINALIZING_TRANSCRIPT
  → critical-token uncertainty check
  → optional correction
  → CONFIRMED transcript version persisted once
  → assessment draft
  → follow-up or next core question
```

Transcript, assessment and candidate extraction for a turn MUST reference the same confirmed `transcript_version`. Editing a transcript marks assessments and candidates derived from the old version stale before regeneration.

### 5.3 Transcript states

```text
PARTIAL
FINAL_CANDIDATE
AWAITING_CORRECTION
CONFIRMED
SUPERSEDED
```

Only `CONFIRMED` user transcript may be assessed or used for EvidenceCandidate extraction.

### 5.4 Critical uncertainty flags

```text
NUMBER_OR_UNIT
PROPER_NOUN
TECHNOLOGY_NAME
OWNERSHIP_TERM
NEGATION
CLAIM_OR_CONSTRAINT_CONFLICT
```

A flagged critical segment is shown or read back for correction before assessment. The system does not guess the missing value.

### 5.5 Interruption

- User barge-in stops agent audio as soon as the selected provider permits.
- Unplayed agent text is not treated as heard.
- The agent's own audio/echo is never stored as user speech.
- An interrupted question is resumed, shortened or replaced based on the user's next explicit intent.
- Interruption has no negative assessment effect.

### 5.6 Silence

Silence is not a negative competence signal. VAD is only a turn-boundary candidate. A neutral prompt or pause offer is used when the user appears to need more time. Concrete VAD thresholds are an Architecture/provider setting.

## 6. Preflight contract

Before media processing begins, the user sees and confirms:

```text
input device or text fallback
interview language and captions
SIMULATION or COACHING
planned duration
pause and end controls
realtime transcript purpose and maximum retention
recording storage choice, default false
package target role/JD/experience scope
AI mock-interview and non-hiring-decision notice
```

Microphone access, realtime processing, transcript storage and optional raw recording are separate settings. The model cannot enable recording.

## 7. Question selection

### 7.1 Inputs

The selector uses only:

```text
unasked core question priority
remaining time
current confirmed-answer gaps
JD requirement priority
Claim/Evidence coverage
ownership and constraint risk
consecutive follow-up count
user-selected focus
```

Every question decision records a `question_id`, decision reason and referenced package IDs.

### 7.2 Priority

```text
1. unasked core question
2. current answer scope/evidence/specificity gap
3. important JD-linked experience
4. ownership, metric or constraint risk
5. optional supporting topic when time remains
```

In the final five minutes the agent closes important open items instead of expanding to low-priority topics.

### 7.3 Follow-up budget

Automatic consecutive follow-ups are capped at two per core question.

1. First follow-up: clarify situation, action, scope or outcome.
2. Second follow-up: clarify Evidence, validation, decision authority or contradiction.
3. Remaining uncertainty becomes `NEEDS_FOLLOWUP`; the agent moves on unless the user explicitly asks to continue.

### 7.4 Question guards

The agent does not generate:

- unrelated sensitive-personal-data questions;
- prompts that expose a `SENSITIVE_DETAIL` source;
- questions that presuppose a `DO_NOT_CLAIM` fact is true;
- discriminatory or protected-trait questions;
- leading prompts that coach the user toward a fabricated answer.

## 8. Evidence and boundary behavior

The verified package payload is a closed comparison set.

- Missing package evidence is described as “not found in the current record”, never automatically false.
- Online calls check status/revocation only and do not fetch newer career facts.
- Ownership or metric disagreement triggers a neutral scope question.
- A mismatch is classified as `ALIGNED`, `UNCLEAR`, `CONFLICTING` or `NOT_ASSESSABLE`.
- Deleted data is never replaced with latest profile content.

## 9. Answer assessment

### 9.1 Dimensions

```text
QUESTION_RELEVANCE
SPECIFICITY
STRUCTURE
EVIDENCE_ALIGNMENT
OWNERSHIP_ACCURACY
JD_CONNECTION
```

Each assessment contains:

```text
session_id
turn_id
transcript_version
dimension
result
reason
claim_ids
evidence_ids
jd_requirement_ids
constraint_ids
created_at
```

Results are dimension-specific structured labels, not a universal hiring score. `NOT_ASSESSABLE` is used when transcript, model or Evidence checks fail.

### 9.2 Prohibited assessment

The agent does not infer competence, personality, emotion, health or employability from accent, dialect, voice, gender-coded characteristics, disability, stutter, speaking speed, appearance or protected traits. ASR failure is system uncertainty.

### 9.3 Feedback timing

- `SIMULATION`: feedback after completion.
- `COACHING`: short feedback after each answer with an optional retry.
- Mode changes occur only from `PAUSED` and apply prospectively.

Completion feedback includes answer trace, well-explained items, unclear Evidence/scope, conflicts, up to three next-practice actions and unverified candidate notices. It excludes pass probability, percentile and cross-user ranking.

## 10. EvidenceCandidate contract

A candidate may be created only when:

1. its source is a `CONFIRMED` user transcript version;
2. it is one atomic career proposition;
3. session, turn and timestamp are linked;
4. duplicate/conflict possibility is represented;
5. initial state is `PENDING` or `NEEDS_FOLLOWUP`.

Candidate creation does not increment profile version. Candidates are reviewed through the existing maximum-five-item Plugin batches and never enter a resume or signed package before explicit promotion.

Agent speech, generated summaries, partial transcript and superseded transcript cannot be candidate sources.

## 11. Revocation during a session

Before start, resume, a new question on sensitive context, final assessment and completion, the service checks authoritative package/data status.

On revocation or deletion:

1. stop new use of affected package data;
2. stop in-progress generation that depends on it;
3. transition to `DATA_REVOKED`;
4. show a safe reason category and reissue path;
5. do not substitute another package or latest profile.

## 12. Retention and deletion

| Data | v1 policy |
| --- | --- |
| partial ASR | ephemeral processing only |
| confirmed transcript/session | maximum 90 days |
| raw voice recording | disabled by default; maximum 30 days when explicitly selected |
| answer assessments/feedback | no longer than their source session |
| pending candidates | profiling workspace policy; source deletion propagates |

User deletion and use withdrawal override these maximums. Deletion propagates through transcripts, recordings, caches, assessments, feedback and candidate source payloads. Minimal non-identifying tombstones cannot reconstruct erased content.

## 13. Idempotency and recovery

- Session start is atomic with package consumption.
- Each confirmed turn uses `(session_id, sequence, idempotency_key)` uniqueness.
- Assessment and candidate writes bind exact `turn_id + transcript_version`.
- Reconnect starts after the last confirmed sequence.
- ASR failure never produces guessed transcript.
- LLM/voice retries are bounded and reuse the operation ID.
- Persistence failure leaves the last confirmed turn intact and does not publish partial results.
- Repeated failure pauses or ends the session instead of retrying indefinitely.

## 14. Prompt-injection boundary

JD, resume, transcript and spoken instructions are untrusted content. They cannot change access, fetch the full Career Graph, retire constraints or override this specification. The Voice Agent has no open-web fetch and no canonical-profile mutation authority.

## 15. Accessibility and language

- Captions and text fallback are available.
- Repeat, speed adjustment and thinking time carry no assessment penalty.
- Language is selected in preflight; explicit mid-session changes are recorded.
- Keyboard operation covers pause, end, transcript correction and recording setting.
- Language/ASR detection failure is reported as system uncertainty.

## 16. Logical persistence additions

Existing Schema v1 `interview_sessions`, `interview_turns` and `evidence_candidates` require a future schema addendum. It MUST represent at least:

```text
Session:
  status, run_mode, language, recording_enabled,
  transcript_retention_until, recording_retention_until,
  package_status_checked_at, last_confirmed_turn_sequence,
  paused_at, resume_until, completion_reason

Turn:
  question_id, question_trace, input_modality,
  transcript_status, transcript_version,
  asr_uncertainty_flags, interrupted, idempotency_key

AnswerAssessment:
  turn_id, transcript_version, dimension, result, reason,
  claim_ids, evidence_ids, jd_requirement_ids, constraint_ids, created_at
```

AnswerAssessment is a session artifact, not Career Graph ClaimAssessment.

## 17. User-facing error codes

```text
INTERVIEW_PACKAGE_INVALID
INTERVIEW_ALREADY_STARTED
MICROPHONE_UNAVAILABLE
TRANSCRIPTION_UNAVAILABLE
TURN_CONFLICT
SESSION_RESUME_EXPIRED
DATA_REVOKED_DURING_SESSION
ASSESSMENT_UNAVAILABLE
VOICE_OUTPUT_UNAVAILABLE
SESSION_PERSISTENCE_FAILED
INVALID_SESSION_TRANSITION
```

Errors never silently produce a successful assessment or fall back to another profile/package.

## 18. Acceptance criteria

1. No Evidence-aware start without valid package checks.
2. One package cannot create two successful sessions.
3. No media processing before preflight.
4. Recording defaults to disabled and is not required for interview functionality.
5. Only confirmed user transcript is assessed or extracted.
6. Critical ASR uncertainty receives a correction path.
7. Transcript edits invalidate old derived outputs.
8. Interruption and silence cause no assessment penalty.
9. Automatic follow-up stops after two consecutive probes per core question.
10. Every question and assessment is traceable to package/session/turn IDs.
11. Missing package data is not labeled false.
12. `DO_NOT_CLAIM`, sensitivity and ownership guards remain effective.
13. No aggregate hiring probability, percentile or ranking is produced.
14. No protected or voice characteristic is treated as competence evidence.
15. New facts remain non-canonical candidates.
16. Replayed operations do not duplicate turns, assessments or candidates.
17. Resume after 24 hours cannot ask a new question.
18. Revocation stops new data use and never triggers latest-profile fallback.
19. Transcript/recording retention respects 90/30-day maximums and earlier deletion.
20. Terminal sessions never become active again.

## 19. Validation and implementation boundary

The accompanying synthetic reference tests validate state transitions, preflight guards, 24-hour resume, terminal immutability, follow-up limit, confirmed-transcript gating, candidate source rules and revocation behavior.

They do not implement or validate live audio, ASR accuracy, model quality, realtime latency, production authentication, storage, deletion workers or provider retention. Those require MVP Architecture and integration/evaluation work.

# CareerGround deletion foundation — 2026-09-27

## Scope and safety boundary

This is an **internal, synthetic-data-only foundation**, not a user-facing deletion feature. The current schema contains accounts, auth identities, career-profile metadata and explicitly scoped profiling workspace/input rows. The preview therefore reports `coverage=FOUNDATION_ONLY` and `ready_to_execute=false`. It does not inspect career claims, evidence, drafts/reviews, interview transcripts, files, snapshots, indexes, queues, package registries, external providers or backups, because those storage structures do not yet exist. It must not be presented as the complete impact of deleting a real account or profile.

No MCP or web deletion route, erasure worker, or production secret configuration is enabled. The service never writes when previewing or checking confirmation. The existing PoC and local product-MCP foundation remain read-only.

## Schema reserved for later execution

Migration `20260927_0002` permits `ACTIVE`, `DISABLED`, `DELETING`, `ERASED` accounts and adds `ACTIVE`, `DELETING`, `ERASED` career-profile status. Existing profiles migrate as `ACTIVE`. The authorization lookup accepts only `ACTIVE` accounts and owned-profile lookups accept only `ACTIVE` profiles, so future committed `DELETING` transitions can immediately deny reads.

`deletion_requests` records the requesting account, limited scope (`ACCOUNT` or `PROFILE`), target ID, processing status (`DELETING`, `ERASED`, `FAILED`), impact digest and timestamps. `deletion_work_items` reserves per-target action/status tracking (`PENDING`, `DONE`, `FAILED`) without source text. Neither table is a complete erasure ledger; backup restore quarantine and a separately protected erasure ledger remain required. Do not treat `ERASED` as true until all relevant storage targets and restore controls are verified.

## Preview and confirmation contract

`DeletionPreviewService.preview` accepts only an internally resolved `account_id` and server-generated time; it rejects foreign targets and inactive/deleting accounts or profiles. The current account preview lists known account, identity, profile, profiling-session and profiling-input IDs and profile versions. Profile preview lists the owned profile and its workspace/input IDs. The response contains no source text and does not create a deletion request.

The short-lived `deletion_digest` is an HMAC over the exact account, scope, target, issue time and sorted known impact set. `confirm_intent` re-reads that set, requires an exact digest, explicit boolean acknowledgement and a fresh `VerifiedDeletionApproval` from a future trusted step-up adapter. It rejects changed targets/versions, expiry and mismatched approval. **Confirmation is validation only; it does not execute or reserve an erasure request.** Future execution must recheck under transaction/locking, atomically mark targets `DELETING`, create request/work items, make confirmation single-use and then run idempotent erasure. The step-up adapter, private signing secret storage and public API contract are not implemented yet.

The user-approved deletion policy remains the source of truth: permanent erasure outranks old resume restoration, and deleted evidence must not be retained as a recovery copy. See [Product Policy P09](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md) and [Implementation Plan E02-T07–T09](../PLAN-2026-09-23-mvp-implementation.md).

## Verification

Synthetic tests check preview non-mutation, owner isolation, exact impact changes, expiry, acknowledgement/step-up mismatch, `DELETING` query denial and schema constraints. PostgreSQL offline upgrade and downgrade SQL generation succeeded. On 2026-09-27, the disposable local PostgreSQL 17 `careerground_test` database passed `alembic upgrade head`, `alembic check`, a full `downgrade base` → `upgrade head` cycle, and the full 92-test suite with the PostgreSQL integration test required (92 passed, 0 skipped). This validates schema reversibility only for an empty synthetic database; data-bearing downgrade, actual erasure and backup-restore quarantine remain unverified.

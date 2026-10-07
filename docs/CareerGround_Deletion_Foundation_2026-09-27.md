# CareerGround deletion foundation — 2026-09-27

## Scope and safety boundary

This is an **internal, synthetic-data-only foundation**, not a user-facing deletion feature. The current preview inventories accounts, identities, profile/workspace/review rows, private-object/version metadata, canonical Graph and archive rows, and JD/resume metadata. It still reports `coverage=FOUNDATION_ONLY` and `ready_to_execute=false`. It cannot account for interview transcripts, actual file bytes, external object versions, package registries, provider copies, indexes, queues or backups. It must not be presented as the complete impact of deleting a real account or profile.

The later synthetic execution, outbox and restore rehearsal are documented in [Data Lifecycle Foundation](CareerGround_Data_Lifecycle_Foundation_2026-09-27.md). The preview's public-readiness flags remain unchanged.

No MCP or web deletion execution route, production erasure worker, or production secret configuration is enabled. The service never writes when previewing or checking confirmation. The authentication PoC remains read-only; the local product MCP factory now also supports bounded synthetic profiling writes, without any deletion execution tool. See [current Phase A coverage](CareerGround_Phase_A_Local_Validation_2026-09-30.md).

An isolated synthetic browser factory now renders account or owned-profile deletion impact as counts by known local kind. The page explicitly states that its inventory is incomplete, displays `ready_to_execute=false`, omits the confirmation digest and source text, and has no deletion POST or step-up action. Foreign profiles receive 404 and GET creates no deletion request. This is a local test presentation only; it is not mounted in the product web app and cannot be used as a complete impact notice for real users.

## Schema reserved for later execution

Migration `20260927_0002` permits `ACTIVE`, `DISABLED`, `DELETING`, `ERASED` accounts and adds `ACTIVE`, `DELETING`, `ERASED` career-profile status. Existing profiles migrate as `ACTIVE`. The authorization lookup accepts only `ACTIVE` accounts and owned-profile lookups accept only `ACTIVE` profiles, so future committed `DELETING` transitions can immediately deny reads.

`deletion_requests` records the requesting account, limited scope (`ACCOUNT` or `PROFILE`), target ID, processing status (`DELETING`, `ERASED`, `FAILED`), impact digest and timestamps. `deletion_work_items` reserves per-target action/status tracking (`PENDING`, `DONE`, `FAILED`) without source text. Neither table is a complete erasure ledger; backup restore quarantine and a separately protected erasure ledger remain required. Do not treat `ERASED` as true until all relevant storage targets and restore controls are verified.

## Preview and confirmation contract

`DeletionPreviewService.preview` accepts only an internally resolved `account_id` and server-generated time; it rejects foreign targets and inactive/deleting accounts or profiles. The current account preview lists known account, identity, profile, profiling-session and profiling-input IDs and profile versions. Profile preview lists the owned profile and its workspace/input IDs. The response contains no source text and does not create a deletion request.

The short-lived `deletion_digest` is an HMAC over the exact account, scope, target, issue time and sorted known impact set. `confirm_intent` re-reads that set, requires an exact digest, explicit boolean acknowledgement and a fresh `VerifiedDeletionApproval` from a future trusted step-up adapter. It rejects changed targets/versions, expiry and mismatched approval. **Confirmation is validation only; it does not execute or reserve an erasure request.** Future execution must recheck under transaction/locking, atomically mark targets `DELETING`, create request/work items, make confirmation single-use and then run idempotent erasure. The step-up adapter, private signing secret storage and public API contract are not implemented yet.

The user-approved deletion policy remains the source of truth: permanent erasure outranks old resume restoration, and deleted evidence must not be retained as a recovery copy. See [Product Policy P09](CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md) and [Implementation Plan E02-T07–T09](../PLAN-2026-09-23-mvp-implementation.md).

## Verification

Synthetic tests check preview non-mutation, owner isolation, exact impact changes, expiry, acknowledgement/step-up mismatch, `DELETING` query denial and schema constraints. PostgreSQL offline upgrade and downgrade SQL generation succeeded. On 2026-09-27, the disposable local PostgreSQL 17 `careerground_test` database passed `alembic upgrade head`, `alembic check`, a full `downgrade base` → `upgrade head` cycle, and the full 92-test suite with the PostgreSQL integration test required (92 passed, 0 skipped). This validates schema reversibility only for an empty synthetic database; data-bearing downgrade, actual erasure and backup-restore quarantine remain unverified.

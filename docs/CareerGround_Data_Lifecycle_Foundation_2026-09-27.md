# Data lifecycle foundation (synthetic local scope)

This work starts from `codex/mvp-foundation-ci-20260923` at `f007e36`. It adds no public deletion endpoint, no live identity or provider connection, and no production scheduler. The product deletion preview remains `FOUNDATION_ONLY` and `ready_to_execute=false`. Do not attach real user data or infer legal erasure completion from these tests.

## Step 02: durable local work

`20260927_0004` adds `outbox_events` and `outbox_receipts`. Events contain only a fixed event type, opaque bounded target reference, handler ID, status, attempt count and times. There is no arbitrary payload, error text, token or career-source column. `enqueue_event` never commits, so the domain write and event commit or roll back together. `due_events` uses PostgreSQL `FOR UPDATE SKIP LOCKED`; a handler mutation, receipt and `DONE` status commit in the same transaction. A crash before commit releases the lock and leaves a pending event. `record_failure` is called after rolling back the failed handler transaction; it uses bounded exponential delay and marks attempt five `DEAD`. `dead_events` shows reference-only failures. The caller must not perform irreversible external work inside this transaction; no external handler exists.

## Step 03: current profiling expiry

`schedule_retention` deduplicates hourly sweep IDs. `run_retention_cycle` is an internal, bounded entrypoint: at most ten batches per call, at most 100 sessions per batch. Each sweep uses the existing per-session `retention_expires_at`, which only explicit CareerGround activity or explicit resume advances. It deletes inputs and sessions together after 90 days, skips `DELETING`/`ERASED`, and leaves profile metadata untouched. Session creation and updates lock the same rows that deletion/expiry use. The only command-line entrypoint requires an explicit loopback PostgreSQL URL whose database name ends `_test` (`CAREERGROUND_TEST_DATABASE_URL`); it refuses other URLs. No operating schedule is deployed. The tests use synthetic SQLite and an isolated local PostgreSQL test DB for row-lock behavior.

The separate P08 clocks remain **unimplemented for actual content**: transcript/unreviewed interview candidates (90 days after interview end) and diagnostic logs (30 days). Optional recording and upload-original metadata now have separate 30-day clocks, bounded staging and synthetic version-erasure checks; [the private-object foundation](CareerGround_Private_Object_Foundation_2026-09-27.md) explains why there is still no actual S3 or content deletion. Selected evidence has its own retention purpose and must not be indiscriminately removed by the workspace sweep. A future schema and tests must prove each clock and evidence preservation before real collection.

## Step 04: synthetic deletion only

`20260927_0005` adds a reference-only `erasure_ledger` without an account FK, because account removal would otherwise conflict with `deletion_requests.account_id`. The current execution deliberately keeps minimal account/profile rows in `DELETING`; it does not claim physical account erasure. `execute_synthetic_deletion` locks the account, profiles and sessions, rechecks the exact preview digest and a trusted-approval-shaped internal value, then blocks reads and writes reference-only deletion work/outbox events in one caller-owned transaction. There is no trusted step-up issuer adapter, so no public execution route is permitted. Duplicate, stale, cross-account and missing-approval requests fail closed. The internal worker can remove known profiling inputs/sessions, temporary drafts/reviews, canonical Graph rows, JD/resume metadata, local version archives, and auth identity links while retaining the account/profile tombstone. A permanent `UNVERIFIED_SCOPE` work item remains pending for packages, transcripts, actual files/object versions, cache/search/index/queue, provider copies, replicas and backups. `ERASED` is never set. A dead-lettered local target can be marked `FAILED` while the account/profile read block remains.

## Step 05: isolated restore rehearsal

`RestoreQuarantine` accepts an independent signed ledger plus a separately trusted signed manifest checkpoint. An old synthetic SQLite snapshot remains closed until signatures, complete row count/digest and reconciliation all pass and commit. Replay removes known temporary rows and auth links, sets retained account/profile rows to `DELETING`, and preserves unrelated accounts. Missing, tampered or partially failed replay rolls back and keeps the gate closed. An affected private object, canonical Graph row or local version archive in the old snapshot also keeps it closed pending erasure reconciliation. The old snapshot is never mounted as a product service. Exact archive lookup rejects missing versions instead of falling back to the latest Graph.

The signed checkpoint must be held outside the restored backup and ledger, with access controls and a monotonic latest-checkpoint guarantee. Otherwise a stale but valid checkpoint could omit newer erasures. The local rehearsal does not validate that operational guarantee.

## Local verification on 2026-09-27

An empty, loopback-only PostgreSQL 17.11 `careerground_test` container was used. `alembic upgrade head` reached `20260927_0005`, `alembic check` reported no new operations, the three PostgreSQL migration/ownership and two-worker lock tests passed, and the full 116-test suite passed with no skips. CI Ruff check and format check passed. This validates the current synthetic schema and local database concurrency tests; it does not validate a production schedule, real provider deletion, or operational backup recovery.

## Before any production data or release

1. Build and verify a real step-up issuer and complete impact inventory, including package revocation and every storage/provider target. Keep public deletion disabled until then.
2. Provision restricted outbox/ledger storage, independent signed checkpoints and operator-only dead-letter inspection. Validate PostgreSQL migration/check, worker races and crash recovery on an isolated loopback `_test` DB first.
3. Inventory live database replicas, manual snapshots, object versions, backups, search/cache/index/queues and processor retention periods. Exercise quarantined restoration for each real medium, including partial-failure and stale-checkpoint drills, before serving a restored copy.
4. Define separate clock jobs/tests for interview transcripts, optional recordings, upload originals and logs when those stores exist; verify selected evidence remains available for its independent purpose.
5. Review policy and legal retention obligations with the actual provider contracts and deployment design. No provider API, real backup, operating database or user account was touched here.

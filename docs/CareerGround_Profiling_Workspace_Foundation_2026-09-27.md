# CareerGround profiling workspace foundation — 2026-09-27

## Current boundary

This is a local internal service and synthetic-data schema, not an active ChatGPT or web ingestion route. Installing or linking the plugin still records no conversation. The only raw-content write method, `append_explicit_profiling_input`, accepts a single statement explicitly submitted to a started CareerGround session; it has no full-chat/message-array parameter. The method supports the four approved input kinds and rejects empty or over-20,000-character input. A production adapter must prove the input was intentionally submitted for that session; the model's claims about scope or ownership are never trusted.

Migration `20260927_0003` adds `profiling_sessions` and `profiling_inputs`. Composite foreign keys bind each session to a profile owned by the same account and each input to a session owned by the same account. Each session tracks its own `last_activity_at` and 90-day `retention_expires_at`. Per-session idempotency keys prevent duplicate inserts; a reused key with different text is a conflict.

## Lifecycle enforced in the internal service

- Explicit start creates an empty session and does not alter the canonical profile version.
- Accepted explicit input refreshes only that session's activity and 90-day expiry.
- At 30 minutes without actual session activity, new input is denied until explicit resume. The automatic pause transition leaves the original expiry untouched.
- Owner-scoped `get_profiling_session` returns only session/profile metadata and reports an effective `PAUSED` state after 30 minutes without writing to the database or returning input text.
- Explicit `pause_profiling_session` is idempotent and leaves last activity, 90-day expiry and canonical profile version unchanged; a paused session still requires explicit resume before another input.
- Explicit resume requires the same owned profile version and can refresh that session's clock. General chat, login and retries do not refresh it.
- Reads and writes deny expired or `DELETING`/`ERASED` sessions immediately, even before a cleanup worker runs. Paused sessions may still be read but cannot accept new input.
- Account/profile status and ownership are rechecked; the raw input body is not placed into general diagnostic logs or deletion previews.

Account/profile deletion previews enumerate related session, input, draft, review, canonical Graph/archive, JD/resume and private-object/version metadata IDs. They still return `FOUNDATION_ONLY` and `ready_to_execute=false`: actual object bytes, providers, packages, interview data and backups remain outside the verified impact inventory.

The separate local product-MCP foundation now has a read-only `get_profiling_session` tool under `career.profile.read`. It rechecks the authenticated account and session ownership; a foreign, missing or expired session returns the same `found=false` shape. An owned response contains status, base/current profile versions and activity/expiry times, never input text. This factory has no deployed ASGI entrypoint and remains synthetic-data-only.

## Remaining before real data

There is no public `start_profiling`/`add_profiling_input` MCP tool or confirmed provider-specific deletion. The 90-day rule is enforced at query time. An internal `delete_expired_profiling_batch` removes eligible temporary session rows and their inputs in a bounded caller-owned transaction. It skips `DELETING`/`ERASED` sessions so account deletion can own them; it never logs raw content or changes canonical profiles. Synthetic tests cover expiry boundary, bounded batches, exclusions, retry and rollback. Local PostgreSQL tests cover two-worker row-lock behavior; a production schedule, monitoring and real backup restore are not complete. Do not connect actual user conversations until those controls and the provider gates are verified.

Update: the synthetic-only bounded runner, outbox retry state and isolated restore rehearsal are described in [Data Lifecycle Foundation](CareerGround_Data_Lifecycle_Foundation_2026-09-27.md). No production schedule or provider deletion was enabled.

On 2026-09-27, migration `20260927_0003` passed `alembic check` and an empty-database full downgrade/re-upgrade cycle on disposable local PostgreSQL 17. After adding the expiry worker, a fresh `careerground_test` database passed migration/schema checks and all **95 tests (95 passed, 0 skipped)**. The PostgreSQL integration test inserted synthetic expired/current workspaces, removed only the expired workspace and input, and rolled back all test rows; every product table was empty afterward. Later tests also covered two-worker row locks. These local tests are not evidence of a production schedule or operational restore safety.

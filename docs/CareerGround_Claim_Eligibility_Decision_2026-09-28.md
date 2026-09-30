# Claim use eligibility decision for the synthetic text MVP

Status (2026-09-29): the owner approved the proposed separate review for the synthetic R1 path. Implementation and verification boundaries are recorded in [Claim Use Review Foundation](CareerGround_Claim_Use_Review_Foundation_2026-09-29.md). This approval does not include actual user data, public deployment or operational AI integration.

## Behavior before the separate review (2026-09-28)

An exact `ACCEPT` decision records `USER_CONFIRMED` but leaves the new Claim at `NOT_EVALUATED` and `REVIEW_REQUIRED`. This is deliberate: fact confirmation is not a decision that the Claim is internally consistent or safe to use in an application. `require_eligible_claim_trace` requires a reviewed, supported Claim at `CONSISTENT` and `ALLOWED`, with no active same-scope constraint or opposing Evidence. Thus the browser's new input → draft → Claim path cannot yet create a JD link or R1 resume; existing resume tests use separately prepared synthetic eligible fixtures.

The approved Graph policy permits a `USER_CONFIRMED` Claim in a resume only after consistency, usage policy, Evidence and boundary checks pass. It does not say which party may make the positive consistency/usage decision. An unrecorded status change or silent upgrade on `ACCEPT` would erase that distinction.

## Proposed Phase A decision

Allow the account owner to make a **separate, explicit, exact Claim-use review** for the first R1 text path. The screen must display the exact current Claim wording, selected supporting Evidence excerpts and source references, the current assessment, and all active same-scope boundaries. It must clearly say that user confirmation does not mean external verification. The owner checks two independent statements: (1) they have reviewed the shown Claim and know no conflicting account of this experience, and (2) they allow this exact Claim to be used in an R1 resume. Missing either choice leaves the Claim `REVIEW_REQUIRED`.

The server must still reject approval when the Claim lacks a prior fact-confirmation review, lacks a selected supporting Evidence link, has a `CONTRADICTS` link, has an active `NOT_TRUE`/`DO_NOT_USE` scope constraint, or has a current assessment of `DISPUTED`/`CONTRADICTED`/`DO_NOT_CLAIM`. It must recheck account ownership, exact profile version, wording, Evidence and boundaries in the same transaction as the write. A short signed browser token must bind the displayed snapshot and browser session. A successful approval appends a dedicated review journal and a new `ClaimAssessment` at `CONSISTENT`/`ALLOWED`, increments the profile version once, and archives both versions. Retries return the same journal/version; a changed input or stale profile creates no write. Only then may an explicit JD requirement link and R1 draft use the Claim. This does not authorize R2/R3 wording, externally verified claims, automatic semantic fit, or real user data.

## Alternative

Keep `CONSISTENT`/`ALLOWED` unavailable in the user journey until a separate reviewer or automated consistency process is specified. The current synthetic read/export and fact-review paths remain useful, but the browser cannot complete a JD-linked R1 resume without manually seeded eligible fixtures.

## Verification before any release

- Two synthetic accounts: exact review and stale/foreign/session-swapped approval denial.
- No selected support, active constraint, opposing Evidence, disputed assessment, changed text or archived-version mismatch: no positive assessment or profile increment.
- Replay/concurrent submission: one review journal, one version and exact archived snapshots.
- Positive synthetic journey: explicit input → temporary draft → fact review → separate use review → JD potential link → R1 wording review → JSON/Markdown export.
- PostgreSQL migration/check and local rollback/reapply on the disposable `_test` database; full synthetic CI suite. A local pass does not approve a public route or operational/user data.

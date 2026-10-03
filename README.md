# CareerGround

Evidence-backed Career AI System

## Current status

Career Graph v1 domain/schema validation, Career Profiling Protocol v1, approved
text-MVP product policy, Schema v1.1 policy addendum, Plugin Functional Specification
v1, Interview Package Schema v1 and Voice Interview Agent Specification v1. Synthetic
fixtures cover Career Graph ownership, signed Interview Packages and Voice Agent
state/policy cases. The local backend now has 20 migrations for identity, profiling,
exact fact review, canonical Claim/Evidence archives, separate Claim use review,
JD/R1 artifacts and retention/erasure foundations. Isolated MCP and Web/BFF factories
exercise authenticated synthetic flows. The document-free browser journey starts
with an empty profile and reaches reviewed R1 Markdown export through explicit
fact, use, JD-link and wording confirmations. Shared account quotas, sanitized
exception responses, finite idle cleanup, browser-confirmed MCP receipts and private
exports, exact conflict/boundary decisions, selected JD links and R1 drafts are
implemented. A bounded MCP ingress and internal deletion status capability add
local protections; the status capability has no public route. Local Firefox, native Chrome zoom and isolated Orca
speech-request checks supplement the Chrome keyboard/reflow checks.

These factories have **no public product entrypoint** and use synthetic data only.
The public app provides health routes and optionally configured Auth0 login;
the separate development authentication PoC is historical provider evidence.
Deletion previews remain `FOUNDATION_ONLY`, `ready_to_execute=false`. Full MCP
contracts, production erasure/restore, accessibility and operations gates remain
open. Managed signing and the Voice Interview App are not implemented. Identity,
LLM/realtime provider adoption and paid cloud resources remain separate decisions.

## Core documents

- [Career Graph Entity/Relationship Model v1](docs/career_graph_entity_relationship_model_v1.md)
- [Career Graph Schema v1](docs/career_graph_schema_v1.md)
- [Career Graph Schema Validation](docs/career_graph_schema_v1_validation.md)
- [Career Profiling Protocol v1](docs/career_profiling_protocol_v1.md)
- [Product Policy Proposal and Decision Log](docs/CareerGround_Product_Policy_Proposal_v0.1_2026-09-22.md)
- [Career Graph Schema v1.1 Policy Addendum](docs/career_graph_schema_v1_1_policy_addendum.md)
- [Plugin Functional Specification v1](docs/plugin_functional_spec_v1.md)
- [Interview Package Schema v1 Proposal](docs/CareerGround_Interview_Package_Schema_Proposal_v0.1_2026-09-23.md)
- [Interview Package JSON Schema v1](docs/interview_package_schema_v1.json)
- [Interview Package Schema v1 Validation](docs/interview_package_schema_v1_validation.md)
- [Voice Interview Agent Specification v1 Proposal](docs/CareerGround_Voice_Interview_Agent_Proposal_v0.1_2026-09-23.md)
- [Voice Interview Agent Specification v1](docs/voice_interview_agent_spec_v1.md)
- [Voice Interview Agent Specification v1 Validation](docs/voice_interview_agent_spec_v1_validation.md)
- [MVP Architecture Proposal v0.1 — approved decision record](docs/CareerGround_MVP_Architecture_Proposal_v0.1_2026-09-23.md)
- [MVP Architecture v1 — approved design contract](docs/architecture_v1.md)
- [MVP Implementation Task Breakdown — approved, in progress](PLAN-2026-09-23-mvp-implementation.md)
- [Implementation contract matrix](docs/mvp_implementation_contract_matrix_v0.1.md)
- [Provider evaluation gates](docs/CareerGround_Provider_Evaluation_Gates_v0.1_2026-09-23.md)
- [First implementation-slice validation](docs/CareerGround_First_Slice_Validation_2026-09-23.md)
- [Synthetic Auth0–ChatGPT MCP PoC server runbook](docs/CareerGround_Auth_PoC_Server_Runbook_2026-09-24.md)
- [Deletion foundation and safety boundary](docs/CareerGround_Deletion_Foundation_2026-09-27.md)
- [Explicit profiling workspace and retention foundation](docs/CareerGround_Profiling_Workspace_Foundation_2026-09-27.md)
- [Phase A local journey, adapter coverage and remaining gates](docs/CareerGround_Phase_A_Local_Validation_2026-09-30.md)
- [Local security, actual browser checks and MCP envelope verification](docs/CareerGround_Phase_A_Security_Accessibility_Contracts_2026-10-01.md)
- [Idle cleanup, browser–MCP receipts, private exports and accessibility](docs/CareerGround_Phase_A_Browser_MCP_Closeout_2026-10-01.md)
- [Exact policy review, selected JD/R1 and local request hardening](docs/CareerGround_Phase_A_Review_JD_Hardening_2026-10-01.md)
- [Disposable demo, offline JD proposals and mock deletion](docs/CareerGround_Phase_A_Local_Demo_Release_2026-10-01.md)
- [MCP contracts, offline proposal checks and persistent runtime](docs/CareerGround_Phase_A_Contracts_Development_Runtime_2026-10-02.md)
- [CURRENT/options, R2 approval/export and partial erasure](docs/CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md)
- [Identity, Korean AI evaluation and operations preparation](docs/CareerGround_External_Gate_Preparation_2026-10-03.md)
- [Latest: ChatGPT conversation and management browser journey](docs/CareerGround_ChatGPT_Management_Journey_2026-10-03.md)

## Core principle

Every career claim should be traceable to evidence. User confirmation, external
verification and permission to publish are separate decisions. Interview discoveries
remain candidates until explicit review; ownership wording must respect its scope.

## Disposable synthetic demo

With the locked development dependencies installed:

```bash
uv run --locked python -m careerground.local_demo --port 8008
```

To keep synthetic inputs across restarts, use the separate owner-only development store:

```bash
uv run --locked python -m careerground.development_runtime --state-dir "$PWD/.careerground-development" --port 8008
```

For an existing exact 0019 synthetic store, add `--upgrade-store` once. It creates an
owner-only sibling backup, validates a migrated copy and preserves the original on
failure. Unknown schemas are refused. See the latest contract report for details.

The store is ignored by Git. Restart preserves synthetic data, but invalidates browser/MCP
connections. Logout revokes the current local bearer. An independent signed deletion
checkpoint is verified before startup; an old DB containing erased Graph data is refused.
Only one process may open a store. Actual Auth0, configured DB URLs and AI providers are
unused. Ctrl+C stops the server; this development store remains. The disposable command
above still discards its own store on exit.

The MCP console now lists 26 tools. `analyze_jd` returns an unapproved mock proposal;
`execute_data_deletion` requires a connection-bound browser receipt after impact review,
mock reauthentication and final consent for five deletion scopes. CURRENT/selected exports
and separate R2 approvals are available. See the [walkthrough and boundaries](docs/CareerGround_Phase_A_Local_Contract_Completion_2026-10-03.md)
for exact arguments and remaining production contracts.

Open the printed `http://127.0.0.1:8008/demo` address and explicitly choose
synthetic account A or B. Start with **경력 정리**, enter synthetic bullets, review
facts and use eligibility, then follow JD → R1 → wording approval → export.
The **MCP 시험** console calls the authenticated local MCP with those same accounts;
mutating operations open a separate browser confirmation before acknowledgment.
**JD 모의 분석** shows deterministic, unapproved source spans and unmapped requirements;
only a separate confirmation stores selected excerpts. It performs no semantic
analysis or external AI call. **합성 삭제** offers impact preview, a separate mock
reauthentication and final consent, then deletes known local rows and shows a
five-minute status view. External services/backups remain unverified; it never
certifies complete erasure.

This entrypoint ignores configured DB/Auth0 settings, creates a new owner-only
temporary SQLite database and in-memory keys, and binds only to `127.0.0.1`.
Use synthetic content only. `Ctrl+C` stops the server and removes its temporary
DB; another start begins empty. Account selection replaces the current browser
session, invalidating its previous approvals/status view. At most 128 simultaneous
browser sessions are kept until shutdown. Use `--port 0` for an available local
port. No Docker, real account, provider or paid resource is needed.
The public application entrypoint remains separate.

## Local foundation

Use Python 3.13 and [uv](https://docs.astral.sh/uv/) for the backend. The lock file
records exact versions. Never commit `.env.local` or actual credentials.

```bash
uv python install 3.13
uv sync --locked --group dev
cp .env.local.example .env.local
# Edit .env.local and set a unique local-only password.
docker compose --env-file .env.local up -d postgres
# Set CAREERGROUND_DATABASE_URL to the local postgresql+psycopg URL shown in .env.local.example.
uv run --locked alembic upgrade head
uv run --locked uvicorn careerground.web.app:app --host 127.0.0.1 --port 8000
```

`GET /health/live` checks only the process; `GET /health/ready` checks PostgreSQL.
This entrypoint does not mount the synthetic product MCP or Web/BFF factories.
Auth0 login (`/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/me`) mounts only when
all of `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET` and
`APP_BASE_URL` are set; a partial set refuses to start. `.env` is git-ignored. To try it:
`set -a; source .env; set +a; uv run --locked uvicorn careerground.web.app:app --host 127.0.0.1 --port 5000`,
then open `http://localhost:5000/auth/login` (use `localhost`, matching `APP_BASE_URL`).
An isolated synthetic-only MCP authentication probe has its own ASGI entry point; it
does not access the product database. See its runbook above before attempting a test.
The future private-MCP account gate is implemented separately and tested through a
synthetic, DB-backed probe factory. The running PoC is deliberately unchanged: no
product MCP entrypoint, production account erasure, or per-connection revocation exists
yet. Do not attach career data to the PoC entrypoint.
The **local-only product MCP factory** exposes 30 tools under
`career.profile.read`, `career.profile.write`, `career.artifact.read`,
`career.artifact.write`, `career.export` and `career.delete` scopes.
All product tools return a common success/error envelope with advertised schemas,
strict wire validation and per-request active-account checks. Web/MCP share
DB-backed read/write quotas when configured with the same review secret and policy;
browser operations also require the same presentation secret in both factories.
Browser confirmation executes the exact operation and issues a short receipt.
MCP acknowledges the completed browser result; the model does not issue approval.
Export resources require the original account/client/access token, scope and current
source eligibility on every read. Deletion preview/status remain partial and
non-certifying; account deletion itself blocks this active-account-only adapter.
See the latest closeout report for wire differences, token-refresh recovery,
remaining two Phase A tool names and production gates.
A synthetic real-browser check is available with
`uv run python scripts/run_local_browser_checks.py --output-dir /tmp/careerground-browser-checks`.
It uses a temporary DB and browser context; install local Chrome or run
`uv run playwright install chromium` first. CI includes the same check.
The database password is required; an empty example value will not start Compose.
For a PostgreSQL integration test, use a **separate local database whose name ends
in `_test`**, apply `alembic upgrade head` to it, and set both
`CAREERGROUND_DATABASE_URL` and `CAREERGROUND_TEST_DATABASE_URL` to its URL.
The test refuses non-local/non-`_test` targets. CI provisions this test DB; no real
accounts or career data are needed.

## Run validation

With the locked development dependencies:

```bash
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m unittest discover -s tests -p test_text_journey.py -v
```

The exact lint/format scope is in `.github/workflows/ci.yml`, including
`tests/test_text_journey.py`. Repository-wide lint includes legacy reference tests
outside that gate. The journey suite checks links, labels, native controls, focus
targets and security/retention copy; it does not replace a browser/screen-reader audit.
Its two PostgreSQL variants require an explicit loopback `*_test` URL and use an
outer transaction with savepoints, rolling back fixture writes even after route
commits. CI requires PostgreSQL tests rather than allowing skips.

Before the backend foundation was added, the 48 synthetic tests also ran with
standard-library-only Python 3.14.4. The expanded suite requires the dependencies
installed by `uv sync`.

The tests validate synthetic Career Graph fixtures and a small reference model for
publication, candidate promotion and historical traceability. They also validate the
Interview Package JSON Schema contract, references, lifecycle guards, canonicalization
and a synthetic ES256 detached-JWS vector. They do not verify real careers,
demonstrate production authentication or validate a complete Career Graph JSON Schema.
PostgreSQL tests run only when their explicit local test URL is configured.
See the validation report for coverage, negative cases and open decisions.

Firefox and the new browser–MCP confirmation checks are included in CI.
Use `scripts/run_local_confirmation_browser_checks.py --browser firefox` with an
explicit `--output-dir` for disposable synthetic verification. Native zoom and
Orca speech-request checks have separate scripts described in the latest report;
they do not constitute a complete accessibility audit.

# CareerGround

Evidence-backed Career AI System

## Current status

Career Graph v1 domain/schema validation, Career Profiling Protocol v1, approved
text-MVP product policy, Schema v1.1 policy addendum, Plugin Functional Specification
v1, Interview Package Schema v1 and Voice Interview Agent Specification v1. Synthetic
fixtures cover Career Graph ownership, signed Interview Packages and Voice Agent
state/policy cases. A local backend foundation now contains account/identity/profile
tables, a provider-neutral tenant lookup, strict common response DTOs and health
routes. It does **not** yet accept user data or expose authenticated product tools.
Managed signing keys and the Voice Interview App are not implemented. MVP Architecture
v1 and the implementation plan are approved; identity, LLM and realtime providers,
production resources and live integrations are not yet selected or built.

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

## Core principle

Every career claim should be traceable to evidence. User confirmation, external
verification and permission to publish are separate decisions. Interview discoveries
remain candidates until explicit review; ownership wording must respect its scope.

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
There are deliberately no login, MCP, profile-writing or data-import routes yet.
The database password is required; an empty example value will not start Compose.
For a PostgreSQL integration test, use a **separate local database whose name ends
in `_test`**, apply `alembic upgrade head` to it, and set both
`CAREERGROUND_DATABASE_URL` and `CAREERGROUND_TEST_DATABASE_URL` to its URL.
The test refuses non-local/non-`_test` targets. CI provisions this test DB; no real
accounts or career data are needed.

## Run validation

With the locked development dependencies:

```bash
uv run --locked ruff check src migrations tests/test_foundation.py tests/test_postgres_foundation.py tests/test_oauth_metadata_preflight.py
uv run --locked ruff format --check src migrations tests/test_foundation.py tests/test_postgres_foundation.py tests/test_oauth_metadata_preflight.py
uv run --locked python -m unittest discover -s tests -v
```

Before the backend foundation was added, the 48 synthetic tests also ran with
standard-library-only Python 3.14.4. The expanded suite requires the dependencies
installed by `uv sync`.

The tests validate synthetic Career Graph fixtures and a small reference model for
publication, candidate promotion and historical traceability. They also validate the
Interview Package JSON Schema contract, references, lifecycle guards, canonicalization
and a synthetic ES256 detached-JWS vector. They do not verify real careers, implement
live authentication or validate a complete Career Graph JSON Schema. The new
PostgreSQL integration test runs only when its explicit local test URL is configured.
See the validation report for coverage, negative cases and open decisions.

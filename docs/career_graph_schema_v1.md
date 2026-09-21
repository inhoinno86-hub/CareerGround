# CareerGround Career Graph — Schema v1

- **Document status:** Proposed v1 baseline
- **Project:** CareerGround
- **Date:** 2026-09-21
- **Implementation strategy:** PostgreSQL-first, canonical JSON interchange
- **Depends on:** `docs/career_graph_entity_relationship_model_v1.md`

## 1. Purpose

This document maps Career Graph v1 to a storage-level schema for CareerGround Core.

Recommended v1 implementation:

```text
PostgreSQL
  ├─ normalized relational tables for canonical data
  ├─ JSONB only for extensible metadata / locators
  ├─ append-oriented assessment and audit history
  └─ explicit link tables for Claim/Evidence/Artifact/JD mappings

Canonical JSON
  └─ API payloads, exports, snapshots, and Interview Package subsets
```

A graph database is not required for v1. Graph semantics come from explicit relationships.

## 2. Identifier and version conventions

- Internal primary keys: UUID.
- Optional human-readable IDs: `CP-`, `R-`, `P-`, `C-`, `E-`, `K-`, `A-`, `JD-`, `EC-`.
- `career_profiles.current_version` is monotonically increasing.
- Every canonical mutation is associated with a change set.
- Every derived artifact stores the exact `profile_version` used for generation.

## 3. Core enums

```text
knowledge_status:
  EXTERNALLY_VERIFIED
  USER_CONFIRMED
  USER_CLAIMED
  INFERRED
  UNKNOWN

consistency_status:
  CONSISTENT
  CONTRADICTED
  DISPUTED
  NOT_EVALUATED

usage_policy:
  ALLOWED
  REVIEW_REQUIRED
  DO_NOT_CLAIM

ownership_level:
  OWNER
  CO_OWNER
  DIRECT_CONTRIBUTOR
  SUPPORTING_CONTRIBUTOR
  REVIEWER
  OBSERVER
  UNKNOWN

decision_authority:
  DECIDER
  CO_DECIDER
  RECOMMENDER
  CONTRIBUTOR
  INFORMED_ONLY
  NONE
  UNKNOWN

evidence_relation:
  SUPPORTS
  CONTRADICTS
  QUALIFIES
  CONTEXTUALIZES

evidence_candidate_status:
  PENDING
  NEEDS_FOLLOWUP
  ACCEPTED
  REJECTED
  DUPLICATE
```

Implementation may use PostgreSQL enums, lookup tables, or text + CHECK constraints. Lookup tables/text constraints are preferable if values are expected to evolve frequently.

## 4. Profile and versioning

### career_profiles

```sql
create table career_profiles (
    id uuid primary key,
    user_id uuid not null,
    display_name text,
    current_version integer not null default 1,
    status text not null default 'ACTIVE',
    created_at timestamptz not null,
    updated_at timestamptz not null
);
```

### profile_change_sets

```sql
create table profile_change_sets (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    version_before integer not null,
    version_after integer not null,
    actor_type text not null,
    actor_id text,
    reason text,
    source_type text,
    source_id uuid,
    created_at timestamptz not null,
    unique (profile_id, version_after)
);
```

### audit_events

```sql
create table audit_events (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    change_set_id uuid references profile_change_sets(id),
    entity_type text not null,
    entity_id uuid not null,
    action text not null,
    before_json jsonb,
    after_json jsonb,
    created_at timestamptz not null
);
```

## 5. Career context

### organizations

```sql
create table organizations (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    name text not null,
    organization_type text,
    location_text text,
    created_in_version integer not null,
    retired_in_version integer
);
```

### roles

```sql
create table roles (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    organization_id uuid references organizations(id),
    title text not null,
    role_type text,
    employment_type text,
    start_date date,
    end_date date,
    summary text,
    created_in_version integer not null,
    retired_in_version integer
);
```

### projects

```sql
create table projects (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    role_id uuid not null references roles(id),
    name text not null,
    summary text,
    goal text,
    start_date date,
    end_date date,
    created_in_version integer not null,
    retired_in_version integer
);
```

## 6. Responsibility, Contribution, Ownership

### responsibilities

```sql
create table responsibilities (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    role_id uuid references roles(id),
    project_id uuid references projects(id),
    statement text not null,
    scope text,
    created_in_version integer not null,
    retired_in_version integer,
    check (role_id is not null or project_id is not null)
);
```

### contributions

```sql
create table contributions (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    role_id uuid references roles(id),
    project_id uuid references projects(id),
    contribution_type text not null,
    action text,
    object_text text,
    summary text not null,
    start_date date,
    end_date date,
    created_in_version integer not null,
    retired_in_version integer,
    check (role_id is not null or project_id is not null)
);
```

### ownership_records

```sql
create table ownership_records (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    contribution_id uuid references contributions(id),
    responsibility_id uuid references responsibilities(id),
    project_id uuid references projects(id),
    ownership_level text not null,
    scope_type text not null,
    scope_description text,
    decision_authority text not null default 'UNKNOWN',
    execution_responsibility text,
    validation_responsibility text,
    team_context text,
    created_in_version integer not null,
    retired_in_version integer,
    check (
      contribution_id is not null or
      responsibility_id is not null or
      project_id is not null
    )
);
```

Service-layer validation SHOULD enforce exactly one primary target per ownership record.

## 7. Skill, Technology, Outcome, Validation

### skills

```sql
create table skills (
    id uuid primary key,
    canonical_name text not null,
    category text,
    description text
);
```

### technologies

```sql
create table technologies (
    id uuid primary key,
    canonical_name text not null,
    category text,
    vendor text
);
```

### contribution_skills / contribution_technologies

Use explicit many-to-many link tables.

### outcomes

```sql
create table outcomes (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    project_id uuid references projects(id),
    contribution_id uuid references contributions(id),
    outcome_type text,
    statement text not null,
    metric_name text,
    metric_value numeric,
    metric_unit text,
    metric_status text not null default 'NOT_APPLICABLE',
    created_in_version integer not null,
    retired_in_version integer
);
```

### validation_activities

```sql
create table validation_activities (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    project_id uuid references projects(id),
    contribution_id uuid references contributions(id),
    validation_type text not null,
    statement text not null,
    environment text,
    created_in_version integer not null,
    retired_in_version integer
);
```

## 8. Claim schema

### claims

A Claim keeps stable identity. A material semantic change creates a new Claim and retires/supersedes the old one.

```sql
create table claims (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    claim_type text not null,
    canonical_text text not null,
    predicate text,
    object_text text,
    importance text not null default 'NORMAL',
    created_in_version integer not null,
    retired_in_version integer,
    supersedes_claim_id uuid references claims(id),
    created_at timestamptz not null
);
```

### claim_context_links

```sql
create table claim_context_links (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    claim_id uuid not null references claims(id),
    context_type text not null,
    context_id uuid not null,
    context_role text not null default 'PRIMARY'
);
```

Allowed v1 context types:

```text
ROLE
PROJECT
RESPONSIBILITY
CONTRIBUTION
OWNERSHIP
OUTCOME
VALIDATION_ACTIVITY
SKILL
TECHNOLOGY
```

Polymorphic references must be validated by Career Core.

### claim_assessments

Append-only assessment history.

```sql
create table claim_assessments (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    claim_id uuid not null references claims(id),
    knowledge_status text not null,
    consistency_status text not null,
    usage_policy text not null,
    confidence numeric,
    rationale text,
    assessed_by_type text not null,
    assessed_by_id text,
    profile_version integer not null,
    assessed_at timestamptz not null,
    check (confidence is null or (confidence >= 0 and confidence <= 1))
);
```

### claim_constraints

```sql
create table claim_constraints (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    constraint_type text not null,
    text text not null,
    severity text not null default 'BLOCKING',
    created_in_version integer not null,
    retired_in_version integer,
    created_at timestamptz not null
);
```

### constraint_target_links

```sql
create table constraint_target_links (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    constraint_id uuid not null references claim_constraints(id),
    target_type text not null,
    target_id uuid not null
);
```

Allowed targets include Claim, Role, Project, Responsibility, Contribution, Ownership, and Outcome.

### claim_reviews

```sql
create table claim_reviews (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    claim_id uuid not null references claims(id),
    review_action text not null,
    reviewer_type text not null,
    reviewer_id text,
    notes text,
    profile_version integer not null,
    reviewed_at timestamptz not null
);
```

## 9. Evidence schema

### evidence_sources

```sql
create table evidence_sources (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    source_type text not null,
    title text,
    source_uri text,
    object_ref text,
    content_hash text,
    source_owner text,
    captured_at timestamptz,
    created_at timestamptz not null
);
```

Raw sensitive content may live in object storage; the database can store references and hashes.

### evidence_items

```sql
create table evidence_items (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    source_id uuid not null references evidence_sources(id),
    evidence_type text not null,
    content_text text,
    locator jsonb not null default '{}'::jsonb,
    speaker text,
    start_ms integer,
    end_ms integer,
    content_hash text,
    created_in_version integer not null,
    retired_in_version integer,
    created_at timestamptz not null
);
```

Locator examples:

```json
{"page": 2, "paragraph": 4}
```

```json
{"session_id": "...", "turn_id": "..."}
```

```json
{"path": "src/control.cpp", "commit": "abc123", "line_start": 120, "line_end": 147}
```

### evidence_claim_links

```sql
create table evidence_claim_links (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    evidence_id uuid not null references evidence_items(id),
    claim_id uuid not null references claims(id),
    relation_type text not null,
    support_strength numeric,
    notes text,
    created_in_version integer not null,
    retired_in_version integer,
    check (support_strength is null or (support_strength >= 0 and support_strength <= 1))
);
```

## 10. Artifact / resume traceability

### artifacts

```sql
create table artifacts (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    artifact_type text not null,
    artifact_version integer not null,
    profile_version integer not null,
    title text,
    status text not null default 'DRAFT',
    storage_ref text,
    content_hash text,
    created_at timestamptz not null
);
```

### artifact_units

```sql
create table artifact_units (
    id uuid primary key,
    artifact_id uuid not null references artifacts(id),
    unit_type text not null,
    ordinal integer not null,
    text text not null,
    metadata jsonb not null default '{}'::jsonb
);
```

Resume unit types include `RESUME_BULLET`, `SUMMARY_SENTENCE`, and `SKILL_ENTRY`.

### artifact_claim_links

```sql
create table artifact_claim_links (
    id uuid primary key,
    artifact_unit_id uuid not null references artifact_units(id),
    claim_id uuid not null references claims(id),
    link_role text not null,
    unique (artifact_unit_id, claim_id, link_role)
);
```

### artifact_constraint_links

Recommended for explicit wording-boundary auditability.

```sql
create table artifact_constraint_links (
    id uuid primary key,
    artifact_unit_id uuid not null references artifact_units(id),
    constraint_id uuid not null references claim_constraints(id),
    effect text not null
);
```

Trace path:

```text
Resume Bullet
  → ArtifactClaimLink
  → Claim
  → EvidenceClaimLink
  → EvidenceItem
  → EvidenceSource
```

## 11. JD schema

### job_descriptions

```sql
create table job_descriptions (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    company_name text,
    job_title text,
    source_url text,
    source_document_ref text,
    raw_text text,
    content_hash text,
    captured_at timestamptz,
    created_at timestamptz not null
);
```

### jd_requirements

```sql
create table jd_requirements (
    id uuid primary key,
    jd_id uuid not null references job_descriptions(id),
    requirement_type text not null,
    text text not null,
    normalized_concept text,
    priority_source text,
    ordinal integer,
    metadata jsonb not null default '{}'::jsonb
);
```

### requirement_claim_maps

```sql
create table requirement_claim_maps (
    id uuid primary key,
    requirement_id uuid not null references jd_requirements(id),
    claim_id uuid not null references claims(id),
    mapping_type text not null,
    coverage_level text not null,
    rationale text,
    created_by_type text not null,
    created_at timestamptz not null,
    unique (requirement_id, claim_id)
);
```

Requirement mapping never changes the truth status of a Claim.

## 12. Interview / Evidence Candidate schema

### interview_sessions

```sql
create table interview_sessions (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    profile_version integer not null,
    jd_id uuid references job_descriptions(id),
    interview_package_id uuid,
    mode text not null,
    started_at timestamptz not null,
    ended_at timestamptz
);
```

### interview_turns

```sql
create table interview_turns (
    id uuid primary key,
    session_id uuid not null references interview_sessions(id),
    speaker text not null,
    sequence integer not null,
    transcript text not null,
    start_ms integer,
    end_ms integer,
    created_at timestamptz not null,
    unique (session_id, sequence)
);
```

### evidence_candidates

```sql
create table evidence_candidates (
    id uuid primary key,
    profile_id uuid not null references career_profiles(id),
    session_id uuid references interview_sessions(id),
    turn_id uuid references interview_turns(id),
    candidate_text text not null,
    proposed_claim_type text,
    proposed_context jsonb,
    status text not null default 'PENDING',
    reviewer_notes text,
    promoted_evidence_id uuid references evidence_items(id),
    promoted_claim_id uuid references claims(id),
    created_at timestamptz not null,
    reviewed_at timestamptz
);
```

PENDING and NEEDS_FOLLOWUP candidates are excluded from verified generation.

Promotion should be transactional:

```text
BEGIN
  lock candidate
  validate transition
  create EvidenceSource/Item if needed
  create or attach Claim
  create EvidenceClaimLink
  create ClaimReview
  create ProfileChangeSet
  increment profile version
  update candidate promoted IDs/status
COMMIT
```

## 13. Interview Package references

The full signing schema is deferred, but deterministic construction requires:

```text
profile_id
profile_version
jd_id
resume_artifact_id + version
interview_plan_artifact_id + version
selected_claim_ids
selected_evidence_ids
selected_constraint_ids
content hashes
issued_at
```

A package MUST reference a fixed profile version, never "latest profile".

## 14. Canonical JSON interchange shape

Prefer stable IDs and explicit relationship arrays over one deeply nested tree.

```json
{
  "schema_version": "career-graph-v1",
  "profile": {
    "profile_id": "uuid",
    "profile_version": 12
  },
  "career": {
    "organizations": [],
    "roles": [],
    "projects": [],
    "responsibilities": [],
    "contributions": [],
    "ownership_records": [],
    "skills": [],
    "technologies": [],
    "outcomes": [],
    "validation_activities": []
  },
  "claims": [],
  "claim_assessments": [],
  "claim_constraints": [],
  "evidence": {
    "sources": [],
    "items": [],
    "claim_links": []
  },
  "artifacts": {
    "items": [],
    "units": [],
    "claim_links": [],
    "constraint_links": []
  },
  "jd": {
    "items": [],
    "requirements": [],
    "claim_maps": []
  },
  "interviews": {
    "sessions": [],
    "turns": [],
    "evidence_candidates": []
  },
  "audit": {
    "change_sets": []
  }
}
```

## 15. Canonical Claim JSON example

```json
{
  "claim_id": "C-uuid",
  "claim_type": "OWNERSHIP",
  "canonical_text": "Contributed to system architecture after model selection.",
  "contexts": [
    {
      "type": "PROJECT",
      "id": "P-uuid",
      "role": "PRIMARY"
    }
  ],
  "assessment": {
    "knowledge_status": "USER_CONFIRMED",
    "consistency_status": "CONSISTENT",
    "usage_policy": "ALLOWED",
    "profile_version": 12
  },
  "constraints": [],
  "evidence_links": [
    {
      "evidence_id": "E-uuid",
      "relation_type": "SUPPORTS"
    }
  ]
}
```

## 16. Do-not-claim JSON example

```json
{
  "constraint_id": "K-uuid",
  "constraint_type": "NO_DECISION_OWNERSHIP",
  "text": "Do not claim ownership of the TCN model-selection decision.",
  "severity": "BLOCKING",
  "targets": [
    {
      "type": "PROJECT",
      "id": "P-dl-trajectory"
    }
  ]
}
```

## 17. Resume bullet JSON example

```json
{
  "artifact_unit_id": "RB-uuid",
  "artifact_id": "RESUME-uuid",
  "unit_type": "RESUME_BULLET",
  "text": "Designed longitudinal-control architecture for an L2+ system and validated behavior through SIL/HIL and vehicle testing.",
  "claim_links": [
    {
      "claim_id": "C-architecture",
      "role": "PRIMARY"
    },
    {
      "claim_id": "C-validation",
      "role": "SUPPORTING"
    }
  ],
  "constraint_links": [
    {
      "constraint_id": "K-no-overall-l2-ownership",
      "effect": "WORDING_BOUNDARY"
    }
  ]
}
```

Production generation must ensure every factual phrase is covered by allowed Claims.

## 18. Evidence Candidate JSON example

```json
{
  "candidate_id": "EC-uuid",
  "profile_id": "CP-uuid",
  "source": {
    "session_id": "IS-uuid",
    "turn_id": "IT-uuid"
  },
  "candidate_text": "I also wrote the SIL automation script.",
  "proposed_claim": {
    "claim_type": "CONTRIBUTION",
    "canonical_text": "Developed a SIL automation script.",
    "context": {
      "type": "PROJECT",
      "id": "P-uuid"
    }
  },
  "status": "PENDING"
}
```

## 19. Recommended indexes

At minimum:

```sql
create index idx_roles_profile on roles(profile_id);
create index idx_projects_profile on projects(profile_id);
create index idx_claims_profile on claims(profile_id);
create index idx_claim_assessments_claim_version on claim_assessments(claim_id, profile_version desc);
create index idx_evidence_items_source on evidence_items(source_id);
create index idx_evidence_claim_claim on evidence_claim_links(claim_id);
create index idx_evidence_claim_evidence on evidence_claim_links(evidence_id);
create index idx_artifact_units_artifact on artifact_units(artifact_id);
create index idx_artifact_claim_claim on artifact_claim_links(claim_id);
create index idx_jd_req_jd on jd_requirements(jd_id);
create index idx_req_claim_claim on requirement_claim_maps(claim_id);
create index idx_candidate_status on evidence_candidates(profile_id, status);
```

Optional:

- PostgreSQL full-text search for claim/JD text.
- pgvector for semantic retrieval.

Embeddings are retrieval aids, never truth or evidence.

## 20. Data integrity rules

### Claim publication

A Claim cannot be used in a VERIFIED resume when:

```text
usage_policy == DO_NOT_CLAIM
OR consistency_status == CONTRADICTED
OR knowledge_status in (INFERRED, UNKNOWN)
OR required evidence is missing
OR a blocking ownership/wording constraint would be violated
```

`USER_CLAIMED` defaults to `REVIEW_REQUIRED` for verified artifacts.

### Resume bullet traceability

Every factual `RESUME_BULLET` in a VERIFIED resume must link to at least one Claim, and every Claim must resolve to eligible Evidence.

### JD mapping

RequirementClaimMap describes relevance only; it does not change Claim truth status.

### Evidence immutability

Evidence used by Claims should not be destructively rewritten. Corrections create new evidence/version records while preserving history.

### Candidate isolation

Unaccepted EvidenceCandidates are excluded from canonical queries by default.

### Snapshot integrity

Every signed or external artifact stores the exact profile version used to generate it.

## 21. API-facing read models

Plugin/App clients should consume stable projections, not raw normalized tables.

Recommended v1 projections:

```text
CareerProfileView
ProjectDetailView
ClaimEvidenceView
ResumeTraceView
JDRequirementMatchView
InterviewContextView
EvidenceCandidateReviewView
```

Example ClaimEvidenceView:

```json
{
  "claim": {
    "id": "...",
    "text": "...",
    "type": "CONTRIBUTION"
  },
  "assessment": {
    "knowledge_status": "USER_CONFIRMED",
    "consistency_status": "CONSISTENT",
    "usage_policy": "ALLOWED"
  },
  "ownership": {
    "level": "DIRECT_CONTRIBUTOR",
    "scope": "FEATURE",
    "decision_authority": "CONTRIBUTOR"
  },
  "evidence": [
    {
      "id": "...",
      "relation": "SUPPORTS",
      "source_type": "PROFILE_CONVERSATION",
      "locator": {"session": 14, "turn": 37}
    }
  ],
  "constraints": []
}
```

## 22. MVP table set

Minimum executable Phase 0/1 schema:

```text
career_profiles
profile_change_sets
organizations
roles
projects
contributions
ownership_records
claims
claim_context_links
claim_assessments
claim_constraints
constraint_target_links
evidence_sources
evidence_items
evidence_claim_links
artifacts
artifact_units
artifact_claim_links
job_descriptions
jd_requirements
requirement_claim_maps
interview_sessions
interview_turns
evidence_candidates
```

Can be deferred initially:

```text
responsibilities
skills / technologies normalization
outcomes
validation_activities
claim_reviews
artifact_constraint_links
advanced audit projections
```

## 23. Recommended migration sequence

```text
001  career_profiles / profile_change_sets / organizations / roles / projects
002  contributions / ownership_records
003  claims / contexts / assessments / constraints
004  evidence_sources / evidence_items / evidence_claim_links
005  artifacts / artifact_units / artifact_claim_links
006  job_descriptions / jd_requirements / requirement_claim_maps
007  interview_sessions / interview_turns / evidence_candidates
```

Phase 0 can be validated after 005, JD analysis after 006, and the interview learning loop after 007.

## 24. Future graph-database option

If traversal complexity later justifies Neo4j or another graph store, PostgreSQL should remain source of truth initially.

Potential derived graph:

```text
Nodes:
  Role, Project, Contribution, Claim, EvidenceItem,
  Skill, Technology, JDRequirement, ArtifactUnit

Edges:
  HAS_PROJECT, HAS_CONTRIBUTION, DESCRIBES,
  SUPPORTS, CONTRADICTS, DERIVED_FROM, MATCHES
```

Do not introduce dual-write in the MVP without a demonstrated requirement.

## 25. Open decisions after Schema v1

1. PostgreSQL enum vs lookup table vs text + CHECK.
2. Universal `career_nodes` table vs service-validated polymorphic links.
3. Exact semantics of `EXTERNALLY_VERIFIED`.
4. Evidence-strength scoring, if any.
5. Which Claim categories require explicit user confirmation.
6. Data retention and deletion/anonymization behavior.
7. Interview Package signing algorithm and key management.
8. Embedding/vector storage strategy.
9. Tenant isolation / RLS.
10. Artifact storage split between DB and object storage.

## 26. Schema decisions

```text
DECISION-S01  PostgreSQL is the v1 source of truth.
DECISION-S02  Graph semantics use explicit link tables.
DECISION-S03  UUID is the internal primary key.
DECISION-S04  Profile version is required on derived artifacts/interviews.
DECISION-S05  Claim assessment history is append-only.
DECISION-S06  EvidenceSource and EvidenceItem are separate.
DECISION-S07  ArtifactUnit is the traceable output unit.
DECISION-S08  Do-not-claim uses ClaimConstraint + usage_policy.
DECISION-S09  EvidenceCandidate is isolated until promotion.
DECISION-S10  Plugin/App consume stable read models rather than raw tables.
```

## 27. Definition of done

Schema v1 is implementation-ready when integration tests demonstrate:

```text
A. Profiling statement
   → EvidenceSource/Item
   → Claim
   → ClaimAssessment(USER_CONFIRMED)

B. Resume bullet
   → ArtifactUnit
   → Claim(s)
   → Evidence(s)

C. Do-not-claim boundary
   → Constraint
   → generator blocks stronger wording

D. JD requirement
   → RequirementClaimMap
   → Claim
   → Evidence

E. Mock interview statement
   → EvidenceCandidate(PENDING)
   → no canonical mutation
   → user accepts
   → promotion transaction
   → profile version increment

F. Old resume artifact
   → still resolves against the profile version from which it was created
```

These flows should become CareerGround Core integration tests before Resume, JD, or Voice agents rely on the graph.

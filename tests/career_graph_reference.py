"""Small, dependency-free reference model for Career Graph v1 fixture tests.

This is test support, not a production implementation.  It deliberately implements
only the exact fixture/interchange rules described by Schema v1 section 28.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re


class ValidationError(ValueError):
    pass


KNOWLEDGE = {"EXTERNALLY_VERIFIED", "USER_CONFIRMED", "USER_CLAIMED", "INFERRED", "UNKNOWN"}
CONSISTENCY = {"CONSISTENT", "CONTRADICTED", "DISPUTED", "NOT_EVALUATED"}
USAGE = {"ALLOWED", "REVIEW_REQUIRED", "DO_NOT_CLAIM"}
OWNERSHIP = {"OWNER", "CO_OWNER", "DIRECT_CONTRIBUTOR", "SUPPORTING_CONTRIBUTOR", "REVIEWER", "OBSERVER", "UNKNOWN"}
DECISION = {"DECIDER", "CO_DECIDER", "RECOMMENDER", "CONTRIBUTOR", "INFORMED_ONLY", "NONE", "UNKNOWN"}
SCOPES = {"PROJECT", "SYSTEM", "SUBSYSTEM", "FEATURE", "MODULE", "TASK", "DECISION", "VALIDATION", "DELIVERABLE"}
RELATIONS = {"SUPPORTS", "CONTRADICTS", "QUALIFIES", "CONTEXTUALIZES"}
ELIGIBLE_SOURCE_TYPES = {"PROFILE_CONVERSATION", "USER_DOCUMENT", "RESUME", "PORTFOLIO", "CERTIFICATE", "INTERVIEW_TRANSCRIPT", "VOICE_RECORDING", "EXTERNAL_RECORD", "MANUAL_ENTRY"}
CANDIDATE_STATUSES = {"PENDING", "NEEDS_FOLLOWUP", "ACCEPTED", "REJECTED", "DUPLICATE"}
CONTEXT_TYPES = {"ROLE", "PROJECT", "RESPONSIBILITY", "CONTRIBUTION", "OWNERSHIP", "OUTCOME", "VALIDATION_ACTIVITY", "SKILL", "TECHNOLOGY"}
TARGET_TYPES = {"CLAIM", "ROLE", "PROJECT", "RESPONSIBILITY", "CONTRIBUTION", "OWNERSHIP", "OUTCOME"}


TABLE_PATHS = {
    "organizations": ("career", "organizations"),
    "roles": ("career", "roles"),
    "projects": ("career", "projects"),
    "responsibilities": ("career", "responsibilities"),
    "contributions": ("career", "contributions"),
    "ownership_records": ("career", "ownership_records"),
    "skills": ("career", "skills"),
    "technologies": ("career", "technologies"),
    "outcomes": ("career", "outcomes"),
    "validation_activities": ("career", "validation_activities"),
    "claims": ("claims",),
    "claim_assessments": ("claim_assessments",),
    "claim_constraints": ("claim_constraints",),
    "claim_reviews": ("claim_reviews",),
    "evidence_sources": ("evidence", "sources"),
    "evidence_items": ("evidence", "items"),
    "evidence_claim_links": ("evidence", "claim_links"),
    "artifacts": ("artifacts", "items"),
    "artifact_units": ("artifacts", "units"),
    "artifact_claim_links": ("artifacts", "claim_links"),
    "artifact_constraint_links": ("artifacts", "constraint_links"),
    "job_descriptions": ("jd", "items"),
    "jd_requirements": ("jd", "requirements"),
    "requirement_claim_maps": ("jd", "claim_maps"),
    "interview_sessions": ("interviews", "sessions"),
    "interview_turns": ("interviews", "turns"),
    "evidence_candidates": ("interviews", "evidence_candidates"),
    "profile_change_sets": ("audit", "change_sets"),
}


# SQL NOT NULL columns from schema sections 4-12.  Fixture aliases are strings,
# intentionally not UUID-validated per section 28.1.
REQUIRED = {
    "organizations": {"id": str, "profile_id": str, "name": str, "created_in_version": int},
    "roles": {"id": str, "profile_id": str, "title": str, "created_in_version": int},
    "projects": {"id": str, "profile_id": str, "role_id": str, "name": str, "created_in_version": int},
    "responsibilities": {"id": str, "profile_id": str, "statement": str, "created_in_version": int},
    "contributions": {"id": str, "profile_id": str, "contribution_type": str, "summary": str, "created_in_version": int},
    "ownership_records": {"id": str, "profile_id": str, "ownership_level": str, "scope_type": str, "decision_authority": str, "created_in_version": int},
    "skills": {"id": str, "canonical_name": str},
    "technologies": {"id": str, "canonical_name": str},
    "outcomes": {"id": str, "profile_id": str, "statement": str, "metric_status": str, "created_in_version": int},
    "validation_activities": {"id": str, "profile_id": str, "validation_type": str, "statement": str, "created_in_version": int},
    "claims": {"id": str, "profile_id": str, "claim_type": str, "canonical_text": str, "importance": str, "created_in_version": int, "created_at": str},
    "claim_assessments": {"id": str, "profile_id": str, "claim_id": str, "knowledge_status": str, "consistency_status": str, "usage_policy": str, "assessed_by_type": str, "profile_version": int, "assessed_at": str},
    "claim_constraints": {"id": str, "profile_id": str, "constraint_type": str, "text": str, "severity": str, "created_in_version": int, "created_at": str},
    "claim_reviews": {"id": str, "profile_id": str, "claim_id": str, "review_action": str, "reviewer_type": str, "profile_version": int, "reviewed_at": str},
    "evidence_sources": {"id": str, "profile_id": str, "source_type": str, "created_at": str},
    "evidence_items": {"id": str, "profile_id": str, "source_id": str, "evidence_type": str, "locator": dict, "created_in_version": int, "created_at": str},
    "evidence_claim_links": {"id": str, "profile_id": str, "evidence_id": str, "claim_id": str, "relation_type": str, "created_in_version": int},
    "artifacts": {"id": str, "profile_id": str, "artifact_type": str, "artifact_version": int, "profile_version": int, "status": str, "created_at": str},
    "artifact_units": {"id": str, "artifact_id": str, "unit_type": str, "ordinal": int, "text": str, "metadata": dict},
    "artifact_claim_links": {"id": str, "artifact_unit_id": str, "claim_id": str, "link_role": str},
    "artifact_constraint_links": {"id": str, "artifact_unit_id": str, "constraint_id": str, "effect": str},
    "job_descriptions": {"id": str, "profile_id": str, "created_at": str},
    "jd_requirements": {"id": str, "jd_id": str, "requirement_type": str, "text": str, "metadata": dict},
    "requirement_claim_maps": {"id": str, "requirement_id": str, "claim_id": str, "mapping_type": str, "coverage_level": str, "created_by_type": str, "created_at": str},
    "interview_sessions": {"id": str, "profile_id": str, "profile_version": int, "mode": str, "started_at": str},
    "interview_turns": {"id": str, "session_id": str, "speaker": str, "sequence": int, "transcript": str, "created_at": str},
    "evidence_candidates": {"id": str, "profile_id": str, "candidate_text": str, "status": str, "created_at": str},
    "profile_change_sets": {"id": str, "profile_id": str, "version_before": int, "version_after": int, "actor_type": str, "created_at": str},
}


TYPE_TO_TABLE = {
    "ROLE": "roles", "PROJECT": "projects", "RESPONSIBILITY": "responsibilities",
    "CONTRIBUTION": "contributions", "OWNERSHIP": "ownership_records",
    "OUTCOME": "outcomes", "VALIDATION_ACTIVITY": "validation_activities",
    "SKILL": "skills", "TECHNOLOGY": "technologies", "CLAIM": "claims",
}


def rows(graph, table):
    value = graph
    for key in TABLE_PATHS[table]:
        value = value[key]
    return value


def by_id(graph, table):
    return {row["id"]: row for row in rows(graph, table)}


def _live(row, version):
    created = row.get("created_in_version", 1)
    retired = row.get("retired_in_version")
    return created <= version and (retired is None or retired > version)


def _fail(errors, message):
    errors.append(message)


def validate_graph(graph):
    """Validate the typed fixture envelope, references, enums and domain invariants."""
    errors = []
    if graph.get("schema_version") != "career-graph-v1":
        _fail(errors, "schema_version must be career-graph-v1")
    profile = graph.get("profile")
    if not isinstance(profile, dict):
        raise ValidationError("profile must be an object")
    for key, typ in {"id": str, "user_id": str, "current_version": int, "status": str, "created_at": str, "updated_at": str}.items():
        if key not in profile or not isinstance(profile[key], typ) or isinstance(profile[key], bool):
            _fail(errors, f"profile.{key} is required as {typ.__name__}")
    if errors:
        raise ValidationError("; ".join(errors))
    version = profile["current_version"]
    profile_id = profile["id"]
    if version < 1:
        _fail(errors, "profile.current_version must be positive")

    tables = {}
    seen_ids = {}
    for table in TABLE_PATHS:
        try:
            table_rows = rows(graph, table)
        except (KeyError, TypeError):
            _fail(errors, f"missing array {'.'.join(TABLE_PATHS[table])}")
            continue
        if not isinstance(table_rows, list):
            _fail(errors, f"{table} must be an array")
            continue
        tables[table] = table_rows
        for index, row in enumerate(table_rows):
            label = f"{table}[{index}]"
            if not isinstance(row, dict):
                _fail(errors, f"{label} must be an object")
                continue
            for key, typ in REQUIRED[table].items():
                value = row.get(key)
                if value is None or not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
                    _fail(errors, f"{label}.{key} is required as {typ.__name__}")
            row_id = row.get("id")
            if isinstance(row_id, str):
                if row_id in seen_ids:
                    _fail(errors, f"duplicate row id {row_id} in {table} and {seen_ids[row_id]}")
                seen_ids[row_id] = table
            if "profile_id" in row and row["profile_id"] != profile_id:
                _fail(errors, f"{label}.profile_id does not match profile")
            if "created_in_version" in row:
                created, retired = row.get("created_in_version"), row.get("retired_in_version")
                if isinstance(created, int) and (created < 1 or created > version):
                    _fail(errors, f"{label} has invalid created version")
                if retired is not None and (not isinstance(retired, int) or retired <= created):
                    _fail(errors, f"{label} has invalid retired version")

    if errors:
        raise ValidationError("; ".join(errors))
    ids = {table: {row["id"]: row for row in table_rows} for table, table_rows in tables.items()}

    def fk(table, row, field, target, nullable=False):
        value = row.get(field)
        if value is None and nullable:
            return
        if value not in ids[target]:
            _fail(errors, f"{table}.{row['id']}.{field} dangles to {target}:{value}")

    for row in tables["roles"]:
        fk("roles", row, "organization_id", "organizations", True)
    for row in tables["projects"]:
        fk("projects", row, "role_id", "roles")
    for table in ("responsibilities", "contributions"):
        for row in tables[table]:
            fk(table, row, "role_id", "roles", True); fk(table, row, "project_id", "projects", True)
            if row.get("role_id") is None and row.get("project_id") is None:
                _fail(errors, f"{table}.{row['id']} needs role_id or project_id")
    for row in tables["ownership_records"]:
        targets = [("contribution_id", "contributions"), ("responsibility_id", "responsibilities"), ("project_id", "projects")]
        for field, target in targets:
            fk("ownership_records", row, field, target, True)
        if sum(row.get(field) is not None for field, _ in targets) != 1:
            _fail(errors, f"ownership_records.{row['id']} must have exactly one primary target")
        if row["ownership_level"] not in OWNERSHIP or row["decision_authority"] not in DECISION or row["scope_type"] not in SCOPES:
            _fail(errors, f"ownership_records.{row['id']} has invalid ownership enum")
    for table in ("outcomes", "validation_activities"):
        for row in tables[table]:
            fk(table, row, "project_id", "projects", True); fk(table, row, "contribution_id", "contributions", True)

    assessment_versions = set()
    for row in tables["claims"]:
        fk("claims", row, "supersedes_claim_id", "claims", True)
        contexts = row.get("contexts")
        if not isinstance(contexts, list) or not contexts:
            _fail(errors, f"claims.{row['id']}.contexts must be non-empty")
            continue
        for context in contexts:
            if not isinstance(context, dict) or context.get("type") not in CONTEXT_TYPES or not isinstance(context.get("role"), str):
                _fail(errors, f"claims.{row['id']} has invalid context")
            elif context.get("id") not in ids[TYPE_TO_TABLE[context["type"]]]:
                _fail(errors, f"claims.{row['id']} has dangling typed context")
    for row in tables["claim_assessments"]:
        fk("claim_assessments", row, "claim_id", "claims")
        key = (row["claim_id"], row["profile_version"])
        if key in assessment_versions: _fail(errors, f"duplicate assessment for {key}")
        assessment_versions.add(key)
        if row["knowledge_status"] not in KNOWLEDGE or row["consistency_status"] not in CONSISTENCY or row["usage_policy"] not in USAGE:
            _fail(errors, f"claim_assessments.{row['id']} has invalid state axis enum")
        if row["profile_version"] > version: _fail(errors, f"claim_assessments.{row['id']} is from a future version")
    for row in tables["claim_constraints"]:
        targets = row.get("targets")
        if not isinstance(targets, list) or not targets:
            _fail(errors, f"claim_constraints.{row['id']}.targets must be non-empty")
            continue
        for target in targets:
            if not isinstance(target, dict) or target.get("type") not in TARGET_TYPES:
                _fail(errors, f"claim_constraints.{row['id']} has invalid target")
            elif target.get("id") not in ids[TYPE_TO_TABLE[target["type"]]]:
                _fail(errors, f"claim_constraints.{row['id']} has dangling typed target")
    for row in tables["claim_reviews"]:
        fk("claim_reviews", row, "claim_id", "claims")
        if row["profile_version"] < 1 or row["profile_version"] > version:
            _fail(errors, f"claim_reviews.{row['id']} has invalid profile version")
    for row in tables["evidence_items"]: fk("evidence_items", row, "source_id", "evidence_sources")
    for row in tables["evidence_claim_links"]:
        fk("evidence_claim_links", row, "evidence_id", "evidence_items"); fk("evidence_claim_links", row, "claim_id", "claims")
        if row["relation_type"] not in RELATIONS: _fail(errors, f"evidence_claim_links.{row['id']} has invalid relation")
    for row in tables["artifacts"]:
        if row["profile_version"] > version: _fail(errors, f"artifacts.{row['id']} is from a future version")
    for row in tables["artifact_units"]: fk("artifact_units", row, "artifact_id", "artifacts")
    for row in tables["artifact_claim_links"]:
        fk("artifact_claim_links", row, "artifact_unit_id", "artifact_units"); fk("artifact_claim_links", row, "claim_id", "claims")
    for row in tables["artifact_constraint_links"]:
        fk("artifact_constraint_links", row, "artifact_unit_id", "artifact_units"); fk("artifact_constraint_links", row, "constraint_id", "claim_constraints")
    for row in tables["jd_requirements"]: fk("jd_requirements", row, "jd_id", "job_descriptions")
    for row in tables["requirement_claim_maps"]:
        fk("requirement_claim_maps", row, "requirement_id", "jd_requirements"); fk("requirement_claim_maps", row, "claim_id", "claims")
    for row in tables["interview_sessions"]:
        fk("interview_sessions", row, "jd_id", "job_descriptions", True)
        if row["profile_version"] > version: _fail(errors, f"interview_sessions.{row['id']} is from a future version")
    for row in tables["interview_turns"]: fk("interview_turns", row, "session_id", "interview_sessions")
    for row in tables["evidence_candidates"]:
        fk("evidence_candidates", row, "session_id", "interview_sessions", True); fk("evidence_candidates", row, "turn_id", "interview_turns", True)
        if row["status"] not in CANDIDATE_STATUSES: _fail(errors, f"evidence_candidates.{row['id']} has invalid status")
        session = ids["interview_sessions"].get(row.get("session_id")); turn = ids["interview_turns"].get(row.get("turn_id"))
        if session and session["profile_id"] != row["profile_id"]: _fail(errors, f"evidence_candidates.{row['id']} session profile mismatch")
        if session and turn and turn["session_id"] != session["id"]: _fail(errors, f"evidence_candidates.{row['id']} turn/session mismatch")
        context = row.get("proposed_context")
        if context is not None and (context.get("type") not in CONTEXT_TYPES or context.get("id") not in ids[TYPE_TO_TABLE.get(context.get("type"), "claims")]):
            _fail(errors, f"evidence_candidates.{row['id']} has invalid proposed context")
        if row["status"] == "ACCEPTED":
            fk("evidence_candidates", row, "promoted_evidence_id", "evidence_items"); fk("evidence_candidates", row, "promoted_claim_id", "claims")
        elif row.get("promoted_evidence_id") is not None or row.get("promoted_claim_id") is not None:
            _fail(errors, f"evidence_candidates.{row['id']} has promoted pointers before acceptance")
    for row in tables["profile_change_sets"]:
        if row["version_after"] != row["version_before"] + 1 or row["version_after"] > version:
            _fail(errors, f"profile_change_sets.{row['id']} has invalid version transition")

    # Validate lifetime bounds; publication additionally checks Claim/Item/link liveness.
    for table in ("claims", "claim_constraints", "evidence_items", "evidence_claim_links"):
        for row in tables[table]:
            if row.get("retired_in_version") is not None and row["retired_in_version"] <= row["created_in_version"]:
                _fail(errors, f"{table}.{row['id']} has impossible lifetime")
    if errors:
        raise ValidationError("; ".join(errors))
    return True


def latest_assessment(graph, claim_id, version=None):
    version = graph["profile"]["current_version"] if version is None else version
    candidates = [row for row in rows(graph, "claim_assessments") if row["claim_id"] == claim_id and row["profile_version"] <= version]
    if not candidates:
        raise ValidationError(f"claim {claim_id} has no assessment at version {version}")
    return max(candidates, key=lambda row: row["profile_version"])


def require_atomic_example(text):
    """Reject the documented compound-action examples, not arbitrary natural language."""
    if re.search(r"\band\s+(?:designed|implemented|validated|performed)\b|\bSIL/HIL\b", text, re.IGNORECASE):
        raise ValidationError("compound action example requires separate atomic Claims")


def publishable_claim(graph, claim_id, version=None):
    """Fail-closed fixture publication policy; returns True or raises ValidationError."""
    validate_graph(graph)
    version = graph["profile"]["current_version"] if version is None else version
    claim = by_id(graph, "claims").get(claim_id)
    if claim is None or not _live(claim, version): raise ValidationError("claim is missing or not live")
    require_atomic_example(claim["canonical_text"])
    assessment = latest_assessment(graph, claim_id, version)
    if assessment["knowledge_status"] != "USER_CONFIRMED":
        raise ValidationError("only USER_CONFIRMED is publishable while external-verification policy is open")
    if assessment["consistency_status"] != "CONSISTENT" or assessment["usage_policy"] != "ALLOWED":
        raise ValidationError("claim state blocks publication")
    for constraint in rows(graph, "claim_constraints"):
        if _live(constraint, version) and constraint["severity"] == "BLOCKING" and any(t == {"type": "CLAIM", "id": claim_id} for t in constraint["targets"]):
            raise ValidationError("blocking Claim-targeted constraint")
    reviews = [row for row in rows(graph, "claim_reviews") if row["claim_id"] == claim_id and row["profile_version"] <= version and row["reviewer_type"] == "USER" and row.get("reviewer_id") == graph["profile"]["user_id"]]
    if not reviews:
        raise ValidationError("missing exact USER_ACCEPTED review")
    review = max(reviews, key=lambda row: (row["profile_version"], row["reviewed_at"], row["id"]))
    notes = (review.get("notes") or "").strip()
    marker = "proposition/scope:"
    reviewed_text = notes[notes.lower().index(marker) + len(marker):].strip() if marker in notes.lower() else notes
    if review["review_action"] != "USER_ACCEPTED" or reviewed_text != claim["canonical_text"]:
        raise ValidationError("missing exact USER_ACCEPTED review")
    sources = by_id(graph, "evidence_sources"); items = by_id(graph, "evidence_items")
    eligible = False
    for link in rows(graph, "evidence_claim_links"):
        item = items.get(link["evidence_id"])
        source = sources.get(item["source_id"]) if item else None
        if link["claim_id"] == claim_id and link["relation_type"] == "SUPPORTS" and _live(link, version) and item and _live(item, version) and source and source["source_type"] in ELIGIBLE_SOURCE_TYPES:
            eligible = True
    if not eligible: raise ValidationError("missing live independent SUPPORTS evidence")
    return True


def resolve_artifact_unit(graph, unit_id):
    validate_graph(graph)
    unit = by_id(graph, "artifact_units").get(unit_id)
    if unit is None: raise ValidationError("artifact unit missing")
    artifact = by_id(graph, "artifacts")[unit["artifact_id"]]
    if graph["profile"]["current_version"] != artifact["profile_version"]:
        raise ValidationError("archived version required to resolve an old artifact")
    links = [row for row in rows(graph, "artifact_claim_links") if row["artifact_unit_id"] == unit_id]
    if not links: raise ValidationError("artifact unit has no claims")
    claims = by_id(graph, "claims")
    linked_claims = []
    for link in links:
        publishable_claim(graph, link["claim_id"], artifact["profile_version"])
        linked_claims.append(claims[link["claim_id"]])
    expected_text = " ".join(claim["canonical_text"] for claim in linked_claims)
    if unit["text"] != expected_text:
        raise ValidationError("artifact text is not exact reviewed canonical text in link order")
    constraint_ids = {row["constraint_id"] for row in rows(graph, "artifact_constraint_links") if row["artifact_unit_id"] == unit_id}
    live_constraints = {row["id"] for row in rows(graph, "claim_constraints") if _live(row, artifact["profile_version"])}
    if constraint_ids != live_constraints:
        raise ValidationError("artifact constraint links do not resolve the full active boundary set")
    return {"artifact": copy.deepcopy(artifact), "unit": copy.deepcopy(unit), "claims": copy.deepcopy(linked_claims)}


def resolve_jd_requirement(graph, requirement_id):
    validate_graph(graph)
    if requirement_id not in by_id(graph, "jd_requirements"): raise ValidationError("requirement missing")
    maps = [row for row in rows(graph, "requirement_claim_maps") if row["requirement_id"] == requirement_id]
    if not maps: raise ValidationError("requirement has no Claim mapping")
    for mapping in maps: publishable_claim(graph, mapping["claim_id"])
    return [mapping["claim_id"] for mapping in maps]


def canonical_projection(graph):
    return copy.deepcopy({
        "profile": graph["profile"], "career": graph["career"], "claims": graph["claims"],
        "claim_assessments": graph["claim_assessments"], "claim_constraints": graph["claim_constraints"],
        "claim_reviews": graph["claim_reviews"], "evidence": graph["evidence"], "artifacts": graph["artifacts"],
        "jd": graph["jd"], "audit": graph["audit"],
    })


def stage_candidate(graph, candidate_id, status):
    if status not in {"PENDING", "NEEDS_FOLLOWUP", "REJECTED", "DUPLICATE"}:
        raise ValidationError("staging cannot accept a candidate")
    result = copy.deepcopy(graph)
    candidate = by_id(result, "evidence_candidates").get(candidate_id)
    if candidate is None: raise ValidationError("candidate missing")
    candidate["status"] = status
    candidate["reviewed_at"] = "2026-09-21T00:00:01Z" if status != "PENDING" else None
    validate_graph(result)
    return result


def _promotion_ids(candidate_id):
    suffix = candidate_id.replace("EC-", "")
    return {"source": f"ES-PROM-{suffix}", "evidence": f"E-PROM-{suffix}", "claim": f"C-PROM-{suffix}", "assessment": f"CA-PROM-{suffix}", "review": f"CR-PROM-{suffix}", "link": f"ECL-PROM-{suffix}", "change": f"PCS-PROM-{suffix}"}


def promote_candidate(graph, candidate_id, approval):
    """Return a promoted deep copy, enforcing exact explicit user approval."""
    validate_graph(graph)
    candidate = by_id(graph, "evidence_candidates").get(candidate_id)
    if candidate is None: raise ValidationError("candidate missing")
    if candidate["status"] == "ACCEPTED":
        if candidate.get("promoted_evidence_id") not in by_id(graph, "evidence_items") or candidate.get("promoted_claim_id") not in by_id(graph, "claims"):
            raise ValidationError("accepted candidate has invalid stored pointers")
        return copy.deepcopy(graph)
    if candidate["status"] in {"REJECTED", "DUPLICATE"}:
        raise ValidationError("terminal candidate cannot be promoted")
    if not isinstance(approval, dict): raise ValidationError("explicit approval is required")
    required = {
        "reviewer_type": "USER", "reviewer_id": graph["profile"]["user_id"],
        "candidate_text": candidate["candidate_text"], "proposed_context": candidate.get("proposed_context"),
        "input_profile_version": graph["profile"]["current_version"],
    }
    if any(approval.get(key) != value for key, value in required.items()):
        raise ValidationError("approval must name the exact user, text, context and input version")
    if approval.get("confirmation_kind") not in {"FACTUAL_CONFIRMATION", "EVIDENCE_ONLY"}:
        raise ValidationError("approval must distinguish factual confirmation from evidence acceptance")
    existing = approval.get("existing_claim_id")
    if existing is not None:
        assessment = latest_assessment(graph, existing)
        if assessment["usage_policy"] != "ALLOWED" or assessment["consistency_status"] != "CONSISTENT":
            raise ValidationError("conflicting existing Claim requires a separate boundary/contradiction review")
        raise ValidationError("reference promotion does not merge into an existing Claim")
    if any(row["canonical_text"] == candidate["candidate_text"] for row in rows(graph, "claims")):
        raise ValidationError("duplicate canonical text requires explicit existing-Claim review")
    require_atomic_example(candidate["candidate_text"])

    result = copy.deepcopy(graph)
    old_version = result["profile"]["current_version"]
    new_version = old_version + 1
    ids = _promotion_ids(candidate_id)
    now = "2026-09-21T00:00:01Z"
    session = by_id(result, "interview_sessions")[candidate["session_id"]]
    source = {"id": ids["source"], "profile_id": result["profile"]["id"], "source_type": "INTERVIEW_TRANSCRIPT", "title": f"Accepted candidate from {session['id']}", "source_uri": None, "object_ref": None, "content_hash": None, "source_owner": result["profile"]["user_id"], "captured_at": now, "created_at": now}
    item = {"id": ids["evidence"], "profile_id": result["profile"]["id"], "source_id": ids["source"], "evidence_type": "INTERVIEW_CANDIDATE", "content_text": candidate["candidate_text"], "locator": {"session_id": candidate["session_id"], "turn_id": candidate["turn_id"]}, "speaker": "USER", "start_ms": None, "end_ms": None, "content_hash": None, "created_in_version": new_version, "retired_in_version": None, "created_at": now}
    claim = {"id": ids["claim"], "profile_id": result["profile"]["id"], "claim_type": candidate.get("proposed_claim_type") or "OTHER", "canonical_text": candidate["candidate_text"], "predicate": None, "object_text": None, "importance": "NORMAL", "created_in_version": new_version, "retired_in_version": None, "supersedes_claim_id": None, "created_at": now, "contexts": [copy.deepcopy(candidate["proposed_context"])]}
    factual = approval["confirmation_kind"] == "FACTUAL_CONFIRMATION"
    assessment = {"id": ids["assessment"], "profile_id": result["profile"]["id"], "claim_id": ids["claim"], "knowledge_status": "USER_CONFIRMED" if factual else "USER_CLAIMED", "consistency_status": "CONSISTENT" if factual else "NOT_EVALUATED", "usage_policy": "REVIEW_REQUIRED", "confidence": None, "rationale": "Reference promotion; separate boundary/publication review remains required.", "assessed_by_type": "USER", "assessed_by_id": approval["reviewer_id"], "profile_version": new_version, "assessed_at": now}
    review_notes = f"Confirmed exact proposition/scope: {candidate['candidate_text']}" if factual else f"Accepted as evidence only, without factual confirmation: {candidate['candidate_text']}"
    review = {"id": ids["review"], "profile_id": result["profile"]["id"], "claim_id": ids["claim"], "review_action": "USER_ACCEPTED", "reviewer_type": "USER", "reviewer_id": approval["reviewer_id"], "notes": review_notes, "profile_version": new_version, "reviewed_at": now}
    link = {"id": ids["link"], "profile_id": result["profile"]["id"], "evidence_id": ids["evidence"], "claim_id": ids["claim"], "relation_type": "SUPPORTS", "support_strength": None, "notes": "Promoted from explicitly reviewed EvidenceCandidate.", "created_in_version": new_version, "retired_in_version": None}
    change = {"id": ids["change"], "profile_id": result["profile"]["id"], "version_before": old_version, "version_after": new_version, "actor_type": "USER", "actor_id": approval["reviewer_id"], "reason": "Accepted EvidenceCandidate", "source_type": "EVIDENCE_CANDIDATE", "source_id": candidate_id, "created_at": now}
    result["evidence"]["sources"].append(source); result["evidence"]["items"].append(item); result["evidence"]["claim_links"].append(link)
    result["claims"].append(claim); result["claim_assessments"].append(assessment); result["claim_reviews"].append(review); result["audit"]["change_sets"].append(change)
    promoted = by_id(result, "evidence_candidates")[candidate_id]
    promoted.update({"status": "ACCEPTED", "reviewer_notes": f"Explicit {approval['confirmation_kind']} by {approval['reviewer_id']}", "promoted_evidence_id": ids["evidence"], "promoted_claim_id": ids["claim"], "reviewed_at": now})
    result["profile"]["current_version"] = new_version; result["profile"]["updated_at"] = now
    validate_graph(result)
    return result


def assert_evidence_preserved(before, after):
    for table in ("evidence_sources", "evidence_items", "evidence_claim_links"):
        after_rows = by_id(after, table)
        for row in rows(before, table):
            if after_rows.get(row["id"]) != row:
                raise ValidationError(f"original {table} row {row['id']} was lost or changed")
    return True


class VersionArchive:
    """Immutable JSON snapshots keyed by (profile id, version), with tamper digest."""
    def __init__(self):
        self._entries = {}

    def capture(self, graph):
        validate_graph(graph)
        key = (graph["profile"]["id"], graph["profile"]["current_version"])
        payload = json.dumps(graph, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        if key in self._entries and self._entries[key] != (payload, digest):
            raise ValidationError("archive snapshots are immutable")
        self._entries[key] = (payload, digest)
        return digest

    def _load(self, profile_id, version):
        try: payload, digest = self._entries[(profile_id, version)]
        except KeyError as exc: raise ValidationError("required archived profile version is missing") from exc
        if hashlib.sha256(payload.encode()).hexdigest() != digest:
            raise ValidationError("archived snapshot digest mismatch")
        graph = json.loads(payload)
        validate_graph(graph)
        return graph

    def resolve_artifact(self, profile_id, version, artifact_id):
        graph = self._load(profile_id, version)
        artifact = by_id(graph, "artifacts").get(artifact_id)
        if artifact is None or artifact["profile_version"] != version:
            raise ValidationError("artifact is absent from the requested archived version")
        units = [row for row in rows(graph, "artifact_units") if row["artifact_id"] == artifact_id]
        resolved_units = [resolve_artifact_unit(graph, unit["id"]) for unit in units]
        claim_ids = [claim["id"] for resolved in resolved_units for claim in resolved["claims"]]
        evidence_links = [row for row in rows(graph, "evidence_claim_links") if row["claim_id"] in claim_ids]
        evidence_ids = {row["evidence_id"] for row in evidence_links}
        evidence_items = [row for row in rows(graph, "evidence_items") if row["id"] in evidence_ids]
        source_ids = {row["source_id"] for row in evidence_items}
        return copy.deepcopy({"artifact": artifact, "units": resolved_units, "evidence_links": evidence_links, "evidence_items": evidence_items, "sources": [row for row in rows(graph, "evidence_sources") if row["id"] in source_ids], "constraints": rows(graph, "claim_constraints"), "career": graph["career"]})

    def tamper_payload_for_test(self, profile_id, version, mutator, recompute_digest=False):
        payload, digest = self._entries[(profile_id, version)]
        graph = json.loads(payload); mutator(graph)
        payload = json.dumps(graph, sort_keys=True, separators=(",", ":"))
        if recompute_digest: digest = hashlib.sha256(payload.encode()).hexdigest()
        self._entries[(profile_id, version)] = (payload, digest)

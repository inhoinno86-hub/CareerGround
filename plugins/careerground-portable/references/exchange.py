"""Unsigned file handoff/result reference. Never invokes URLs or modifies a profile."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from portable import InvalidFile, key, load_json, schema_errors, validate_workspace


def digest(data):
    """SHA-256 of UTF-8 sorted-key compact JSON, ensure_ascii=False; not signed/JCS."""
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def validate_handoff(data, *, attachment_root=None):
    errors = set(schema_errors(data, "handoff-1.0.schema.json"))
    if errors:
        return sorted(errors)
    workspace = data["workspace"]
    omitted = {key(r) for r in data["omitted_refs"]}
    if len(omitted) != len(data["omitted_refs"]):
        errors.add("DUPLICATE_ID")
    errors.update(
        validate_workspace(workspace, attachment_root=attachment_root, omitted_parents=omitted)
    )
    artifacts = {key(a): a for a in workspace["artifacts"]}
    expected = {
        key(data[r]): kind
        for r, kind in [("profile_ref", "profile"), ("jd_ref", "jd"), ("resume_ref", "resume")]
    }
    if set(artifacts) != set(expected) or omitted & set(artifacts):
        errors.add("UNSELECTED_CONTENT")
    if key(workspace["selected_profile"]) != key(data["profile_ref"]):
        errors.add("VERSION_CONFLICT")
    for ident, kind in expected.items():
        if ident not in artifacts or artifacts[ident]["kind"] != kind:
            errors.add("MISSING_REFERENCE")
    if errors:
        return sorted(errors)
    profile = artifacts[key(data["profile_ref"])]["payload"]
    resume = artifacts[key(data["resume_ref"])]["payload"]
    selection = data["selection"]
    if not data["review"]["record"].strip():
        errors.add("MISSING_CONFIRMATION")
    sets = {field: set(ids) for field, ids in selection.items()}
    if any(len(sets[field]) != len(ids) for field, ids in selection.items()):
        errors.add("DUPLICATE_ID")
    if (
        key(resume["profile_ref"]) != key(data["profile_ref"])
        or resume["jd_ref"] is None
        or key(resume["jd_ref"]) != key(data["jd_ref"])
    ):
        errors.add("VERSION_CONFLICT")
    for field, actual in [
        ("fact_ids", {f["id"] for f in profile["facts"]}),
        ("source_ids", {s["id"] for s in profile["sources"]}),
        ("attachment_ids", {a["id"] for a in workspace["attachments"]}),
        ("history_operation_ids", {h["id"] for h in data["selected_history"]}),
    ]:
        if sets[field] != actual:
            errors.add("UNSELECTED_CONTENT")
    banned = {
        fid for c in profile["constraints"] if c["rule"] == "do_not_use" for fid in c["fact_ids"]
    }
    for fact in profile["facts"]:
        if (
            fact["id"] in banned
            or fact["permission"]["status"] != "allowed"
            or "interview" not in fact["permission"]["scope"]
        ):
            errors.add("USE_FORBIDDEN")
        if fact["confirmation"]["status"] == "pending" or fact["conflict"]:
            errors.add("FACT_UNREVIEWED")
    if any(s["review"] != "user_confirmed" for s in resume["sentences"]):
        errors.add("RESUME_UNREVIEWED")
    history_ids = set()
    referenced_omitted = set()
    for operation in data["selected_history"]:
        if operation["id"] in history_ids:
            errors.add("DUPLICATE_ID")
        history_ids.add(operation["id"])
        if operation["confirmation"] != "user_confirmed" or not operation["record"].strip():
            errors.add("HISTORY_UNREVIEWED")
        if not set(operation["source_ids"]) <= sets["source_ids"]:
            errors.add("UNSELECTED_CONTENT")
        for ref in operation["inputs"] + operation["outputs"]:
            ident = key(ref)
            if ident not in artifacts and ident not in omitted:
                errors.add("MISSING_REFERENCE")
            if ident in omitted:
                referenced_omitted.add(ident)
    if resume["parent_ref"]:
        referenced_omitted.add(key(resume["parent_ref"]))
    if referenced_omitted != omitted:
        errors.add("UNSELECTED_CONTENT")
    return sorted(errors)


def make_handoff(
    workspace,
    *,
    resume_ref,
    fact_ids,
    source_ids,
    operation_ids,
    attachment_ids,
    handoff_id,
    created_at,
    goals,
    review_record,
    attachment_root=None,
):
    """Called only after user review of exact selected content. Returns a new object."""
    errors = validate_workspace(workspace, attachment_root=attachment_root)
    if errors:
        raise InvalidFile(errors[0])
    artifacts = {key(a): a for a in workspace["artifacts"]}
    resume = artifacts.get(key(resume_ref))
    if not resume or resume["kind"] != "resume" or not resume["payload"]["jd_ref"]:
        raise InvalidFile("TAILORED_REFERENCES")
    profile_ref = resume["payload"]["profile_ref"]
    if key(profile_ref) != key(workspace["selected_profile"]):
        raise InvalidFile("STALE_VERSION")
    jd_ref = resume["payload"]["jd_ref"]
    profile = copy.deepcopy(artifacts[key(profile_ref)])
    payload = profile["payload"]
    payload["facts"] = [f for f in payload["facts"] if f["id"] in fact_ids]
    payload["sources"] = [s for s in payload["sources"] if s["id"] in source_ids]
    payload["constraints"] = [
        c for c in payload["constraints"] if set(c["fact_ids"]) & set(fact_ids)
    ]
    for constraint in payload["constraints"]:
        constraint["fact_ids"] = [fid for fid in constraint["fact_ids"] if fid in fact_ids]
    selected_history = [
        copy.deepcopy(op)
        for a in workspace["artifacts"]
        if a["kind"] == "history"
        for op in a["payload"]["operations"]
        if op["id"] in operation_ids
    ]
    included = {key(profile_ref), key(jd_ref), key(resume_ref)}
    omitted = {
        key(r)
        for op in selected_history
        for r in op["inputs"] + op["outputs"]
        if key(r) not in included
    }
    if resume["payload"]["parent_ref"]:
        omitted.add(key(resume["payload"]["parent_ref"]))
    result = {
        "schema_version": "1.0",
        "kind": "career-handoff",
        "handoff_id": handoff_id,
        "created_at": created_at,
        "profile_ref": copy.deepcopy(profile_ref),
        "jd_ref": copy.deepcopy(jd_ref),
        "resume_ref": copy.deepcopy(resume_ref),
        "selection": {
            "fact_ids": list(fact_ids),
            "source_ids": list(source_ids),
            "history_operation_ids": list(operation_ids),
            "attachment_ids": list(attachment_ids),
        },
        "workspace": {
            **copy.deepcopy(workspace),
            "artifacts": [profile, copy.deepcopy(artifacts[key(jd_ref)]), copy.deepcopy(resume)],
            "attachments": [
                copy.deepcopy(a) for a in workspace["attachments"] if a["id"] in attachment_ids
            ],
        },
        "selected_history": selected_history,
        "omitted_refs": [{"id": i, "version": v} for i, v in sorted(omitted)],
        "excluded_categories": [
            "unselected_facts",
            "unselected_sources",
            "unselected_history",
            "unselected_attachments",
            "contact_information",
            "full_chat",
        ],
        "goals": list(goals),
        "review": {"status": "user_confirmed", "record": review_record},
    }
    errors = validate_handoff(result, attachment_root=attachment_root)
    if errors:
        raise InvalidFile(errors[0])
    return result


def validate_result(data, handoff):
    errors = set(schema_errors(data, "result-1.0.schema.json"))
    if errors:
        return sorted(errors)
    if data["handoff_ref"] != {"id": handoff["handoff_id"], "sha256": digest(handoff)}:
        errors.add("HANDOFF_CONFLICT")
    answers = {a["id"] for a in data["answers"]}
    candidates = {c["id"] for c in data["candidates"]}
    if len(answers) != len(data["answers"]) or len(candidates) != len(data["candidates"]):
        errors.add("DUPLICATE_ID")
    if any(item["answer_id"] not in answers for item in data["feedback"] + data["candidates"]):
        errors.add("MISSING_REFERENCE")
    return sorted(errors)


def import_result(data, handoff, *, attachment_root=None):
    errors = validate_handoff(handoff, attachment_root=attachment_root)
    if not errors:
        errors = validate_result(data, handoff)
    if errors:
        raise InvalidFile(errors[0])
    # No profile argument, file write, or candidate promotion exists here.
    return copy.deepcopy(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--attachments", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        handoff = load_json(args.handoff)
        errors = validate_handoff(handoff, attachment_root=args.attachments)
        if not errors and args.result:
            errors = validate_result(load_json(args.result), handoff)
    except (InvalidFile, OSError) as error:
        errors = [error.code if isinstance(error, InvalidFile) else "FILE_UNAVAILABLE"]
    print(
        json.dumps(
            {
                "valid": not errors,
                "errors": errors,
                "signed": False,
                "profile_updated": False,
                "app_imported": False,
            }
        )
    )
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()

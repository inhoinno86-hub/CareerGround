"""Offline portable-file validation; no CareerGround backend, network or mutations.

Requires only the standalone jsonschema library for schema validation. If unavailable,
report validation unavailable; never install dependencies automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
SCHEMAS = Path(__file__).resolve().parent / "schemas"


class InvalidFile(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidFile("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def load_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise InvalidFile("INVALID_FILE")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise InvalidFile("SIZE_LIMIT")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(InvalidFile("SCHEMA")),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise InvalidFile("INVALID_JSON") from error


def schema_errors(data, schema_name: str) -> list[str]:
    try:
        if len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode()) > MAX_JSON_BYTES:
            return ["SIZE_LIMIT"]
    except (TypeError, ValueError, RecursionError):
        return ["SCHEMA"]
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as error:
        raise InvalidFile("VALIDATOR_UNAVAILABLE") from error
    schema = json.loads((SCHEMAS / schema_name).read_text())
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        return ["UNSUPPORTED_VERSION"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return ["SCHEMA"] if next(validator.iter_errors(data), None) else []


def key(ref):
    return ref["id"], ref["version"]


def _index(items, errors):
    result = {}
    for item in items:
        if item["id"] in result:
            errors.add("DUPLICATE_ID")
        result[item["id"]] = item
    return result


def validate_workspace(
    data, *, attachment_root: Path | None = None, omitted_parents=()
) -> list[str]:
    errors = set(schema_errors(data, "workspace-1.0.schema.json"))
    if errors:
        return sorted(errors)
    artifacts = {}
    kinds = {}
    for item in data["artifacts"]:
        ident = key(item)
        if ident in artifacts:
            errors.add("DUPLICATE_ID")
            if artifacts[ident] != item:
                errors.add("CONFLICTING_ARTIFACT")
        if item["id"] in kinds and kinds[item["id"]] != item["kind"]:
            errors.add("CONFLICTING_ARTIFACT")
        kinds[item["id"]] = item["kind"]
        artifacts[ident] = item
    attachments = _index(data["attachments"], errors)

    def resolve(ref, kind=None):
        item = artifacts.get(key(ref))
        if item is None:
            errors.add("MISSING_REFERENCE")
        elif kind and item["kind"] != kind:
            errors.add("REFERENCE_KIND")
            return None
        return item

    selected = resolve(data["selected_profile"], "profile")
    if selected and any(
        a["kind"] == "profile" and a["id"] == selected["id"] and a["version"] > selected["version"]
        for a in data["artifacts"]
    ):
        errors.add("STALE_VERSION")
    operation_ids = set()
    for item in data["artifacts"]:
        payload = item["payload"]
        if item["kind"] == "profile":
            sources = _index(payload["sources"], errors)
            facts = _index(payload["facts"], errors)
            _index(payload["constraints"], errors)
            for source in sources.values():
                if source["attachment_id"] and source["attachment_id"] not in attachments:
                    errors.add("MISSING_ATTACHMENT")
            for fact in facts.values():
                linked = [sources[sid] for sid in fact["source_ids"] if sid in sources]
                if len(linked) != len(fact["source_ids"]):
                    errors.add("MISSING_REFERENCE")
                if not any(s["kind"] != "model_summary" for s in linked):
                    errors.add("SUMMARY_AS_EVIDENCE")
                confirm = fact["confirmation"]
                if confirm["status"] != "pending" and not confirm["record"].strip():
                    errors.add("MISSING_CONFIRMATION")
                if confirm["status"] == "externally_verified":
                    verification = sources.get(confirm["source_id"])
                    if (
                        not verification
                        or verification["kind"] != "external_excerpt"
                        or confirm["source_id"] not in fact["source_ids"]
                        or not verification["locator"].strip()
                    ):
                        errors.add("INVALID_VERIFICATION")
                elif confirm["source_id"] is not None:
                    errors.add("INVALID_VERIFICATION")
                permission = fact["permission"]
                if permission["status"] == "allowed" and (
                    not permission["record"].strip() or not permission["scope"]
                ):
                    errors.add("MISSING_PERMISSION")
                if permission["status"] != "allowed" and permission["scope"]:
                    errors.add("USE_FORBIDDEN")
            for constraint in payload["constraints"]:
                if any(fid not in facts for fid in constraint["fact_ids"]):
                    errors.add("MISSING_REFERENCE")
        elif item["kind"] == "jd":
            _index(payload["requirements"], errors)
            if payload["status"] == "open_verified" and payload["access"] != "read":
                errors.add("JD_UNCERTAINTY")
            if payload["access"] not in {"read", "manual"} and (
                not payload["uncertainty"].strip() or payload["status"] == "open_verified"
            ):
                errors.add("JD_UNCERTAINTY")
        elif item["kind"] == "resume":
            profile = resolve(payload["profile_ref"], "profile")
            jd = resolve(payload["jd_ref"], "jd") if payload["jd_ref"] else None
            omitted_parent = (
                payload["parent_ref"] is not None and key(payload["parent_ref"]) in omitted_parents
            )
            parent = (
                resolve(payload["parent_ref"], "resume")
                if payload["parent_ref"] and not omitted_parent
                else None
            )
            if payload["parent_ref"] and (
                key(payload["parent_ref"]) == key(item)
                or (parent and parent["id"] == item["id"] and parent["version"] >= item["version"])
            ):
                errors.add("VERSION_ORDER")
            if payload["type"] == "base" and (jd or payload["mappings"]):
                errors.add("BASE_REQUIRES_NO_JD")
            if payload["type"] == "tailored" and (not jd or (not parent and not omitted_parent)):
                errors.add("TAILORED_REFERENCES")
            _index(payload["sentences"], errors)
            if not profile:
                continue
            pp = profile["payload"]
            facts = {f["id"]: f for f in pp["facts"]}
            sources = {s["id"]: s for s in pp["sources"]}
            forbidden = {
                fid for c in pp["constraints"] if c["rule"] == "do_not_use" for fid in c["fact_ids"]
            }
            scope = "base_resume" if payload["type"] == "base" else "tailored_resume"
            for sentence in payload["sentences"]:
                allowed_sources = set()
                for fid in sentence["fact_ids"]:
                    fact = facts.get(fid)
                    if not fact:
                        errors.add("MISSING_REFERENCE")
                        continue
                    allowed_sources.update(fact["source_ids"])
                    if (
                        fid in forbidden
                        or fact["permission"]["status"] != "allowed"
                        or scope not in fact["permission"]["scope"]
                    ):
                        errors.add("USE_FORBIDDEN")
                    if fact["confirmation"]["status"] == "pending" or fact["conflict"]:
                        errors.add("FACT_UNREVIEWED")
                if any(
                    sid not in sources or sid not in allowed_sources
                    for sid in sentence["source_ids"]
                ):
                    errors.add("MISSING_REFERENCE")
                if not any(
                    sources[sid]["kind"] != "model_summary"
                    for sid in sentence["source_ids"]
                    if sid in sources
                ):
                    errors.add("SUMMARY_AS_EVIDENCE")
                if sentence["review"] == "user_confirmed" and not sentence["record"].strip():
                    errors.add("MISSING_CONFIRMATION")
            requirements = {r["id"] for r in jd["payload"]["requirements"]} if jd else set()
            mapped = set()
            for mapping in payload["mappings"]:
                rid = mapping["requirement_id"]
                if rid in mapped:
                    errors.add("DUPLICATE_ID")
                mapped.add(rid)
                if rid not in requirements or any(fid not in facts for fid in mapping["fact_ids"]):
                    errors.add("MISSING_REFERENCE")
                for fid in mapping["fact_ids"]:
                    fact = facts.get(fid)
                    if not fact:
                        continue
                    if (
                        fid in forbidden
                        or fact["permission"]["status"] != "allowed"
                        or scope not in fact["permission"]["scope"]
                    ):
                        errors.add("USE_FORBIDDEN")
                    if fact["confirmation"]["status"] == "pending" or fact["conflict"]:
                        errors.add("FACT_UNREVIEWED")
                if (mapping["assessment"] == "gap") != (not mapping["fact_ids"]):
                    errors.add("INVALID_MAPPING")
            if mapped != requirements:
                errors.add("MAPPING_INCOMPLETE")
        elif item["kind"] == "history":
            for operation in payload["operations"]:
                if operation["id"] in operation_ids:
                    errors.add("DUPLICATE_ID")
                operation_ids.add(operation["id"])
                for ref in operation["inputs"] + operation["outputs"]:
                    resolve(ref)
                if not operation["outputs"]:
                    errors.add("HISTORY_OUTPUT_MISSING")
                if (
                    operation["confirmation"] == "user_confirmed"
                    and not operation["record"].strip()
                ):
                    errors.add("MISSING_CONFIRMATION")
                all_sources = {
                    s["id"]
                    for a in data["artifacts"]
                    if a["kind"] == "profile"
                    for s in a["payload"]["sources"]
                }
                if any(sid not in all_sources for sid in operation["source_ids"]):
                    errors.add("MISSING_REFERENCE")
    for attachment in attachments.values():
        if attachment_root is None:
            errors.add("ATTACHMENT_NOT_CHECKED")
            continue
        path = attachment_root / attachment["path"]
        if (
            any(p.is_symlink() for p in [path.absolute(), *path.absolute().parents])
            or not path.is_file()
        ):
            errors.add("MISSING_ATTACHMENT")
        elif path.stat().st_size > MAX_ATTACHMENT_BYTES:
            errors.add("SIZE_LIMIT")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != attachment["sha256"]:
            errors.add("ATTACHMENT_HASH_MISMATCH")
    return sorted(errors)


def select_workspace(candidates, selection=None):
    """Never choose newest automatically; user selection includes ID and exact version."""
    if not candidates:
        raise InvalidFile("NO_BASELINE")
    if selection is None and len(candidates) != 1:
        raise InvalidFile("MULTIPLE_BASELINES")
    matches = (
        candidates
        if selection is None
        else [
            c
            for c in candidates
            if (c["workspace_id"], *key(c["selected_profile"])) == tuple(selection)
        ]
    )
    if len(matches) != 1:
        raise InvalidFile("BASELINE_CONFLICT")
    return matches[0]


def render_workspace(data) -> str:
    """Canonical review rendering; edited Markdown must be re-reviewed, never merged."""
    lines = [
        "# CareerGround 검토 자료",
        f"기준: {data['workspace_id']}",
        f"선택 경력: {data['selected_profile']['id']} v{data['selected_profile']['version']}",
        "구조 검사는 사실의 진실·사용자 신원·저장 완료를 증명하지 않습니다.",
    ]
    for artifact in data["artifacts"]:
        lines += ["", f"## {artifact['kind']} {artifact['id']} v{artifact['version']}"]
        # All fields remain visible, including constraints, confirmations and sources.
        lines += ["```json", json.dumps(artifact["payload"], ensure_ascii=False, indent=2), "```"]
    lines += [
        "",
        "## 첨부 목록",
        "```json",
        json.dumps(data["attachments"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def check_review(data, markdown: str) -> list[str]:
    return [] if markdown == render_workspace(data) else ["REVIEW_CONFLICT"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--attachments", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    try:
        data = load_json(args.file)
        errors = validate_workspace(data, attachment_root=args.attachments)
        if args.review:
            errors += check_review(data, args.review.read_text(encoding="utf-8"))
    except (InvalidFile, OSError) as error:
        errors = [error.code if isinstance(error, InvalidFile) else "FILE_UNAVAILABLE"]
    print(
        json.dumps(
            {
                "valid": not errors,
                "errors": sorted(set(errors)),
                "fact_truth_verified": False,
                "project_saved": False,
            }
        )
    )
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()

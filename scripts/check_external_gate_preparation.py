"""Validate the local preparation bundle; never grant approval or call providers.

Exit 0 means preparation files are consistent, not that a release gate passed.
--require-ready exits 3 while external evidence/approval remains outstanding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/phase_a_external_gate_readiness_20261003.json"
CORPUS = "tests/fixtures/korean_generation_quality_cases.json"
DOCUMENTS = {
    "G-I": "docs/CareerGround_Identity_Gate_Preparation_2026-10-03.md",
    "G-L": "docs/CareerGround_AI_Gate_Preparation_2026-10-03.md",
    "G-P/G-C": "docs/CareerGround_Operations_Gate_Preparation_2026-10-03.md",
}
POLICY = {
    "external_execution_approved": False,
    "approved_requests": 0,
    "approved_ai_cost": 0,
    "approved_cloud_cost": 0,
    "currency": "UNSELECTED",
}
TASKS = ("extract", "jd", "r2", "r3")
ACTIONS = {"PROPOSE", "FOLLOW_UP", "EXCLUDE", "REJECT", "POTENTIAL_ONLY", "GAP", "FACT_REVIEW"}


class PreparationInvalid(ValueError):
    """A preparation file is incomplete or claims an unsupported approval."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PreparationInvalid(reason)


def exact_keys(value: object, keys: set[str], reason: str) -> None:
    require(type(value) is dict and set(value) == keys, reason)


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


def matches_exact(value: object, expected: object) -> bool:
    return type(value) is type(expected) and value == expected


def validate_corpus(corpus: object) -> None:
    exact_keys(corpus, {"schema", "synthetic_only", "thresholds_status", "cases"}, "corpus_shape")
    require(corpus["schema"] == "careerground-generation-quality-cases-v1", "corpus_schema")
    require(corpus["synthetic_only"] is True, "synthetic_only_required")
    require(corpus["thresholds_status"] == "PROPOSED_NOT_APPROVED", "thresholds_not_approved")
    cases = corpus["cases"]
    require(type(cases) is list and len(cases) == 36, "case_count")
    expected_ids = {f"{task}-{number:02d}" for task in TASKS for number in range(1, 10)}
    seen = set()
    for case in cases:
        exact_keys(
            case,
            {"id", "task", "input_text", "expected_action", "preserve", "forbid", "followup"},
            "case_shape",
        )
        case_id, task = case["id"], case["task"]
        require(type(case_id) is str and case_id in expected_ids, "case_id")
        require(case_id not in seen, "duplicate_case_id")
        seen.add(case_id)
        require(type(task) is str and task in TASKS and case_id.startswith(task + "-"), "task_id")
        action = case["expected_action"]
        require(type(action) is str and action in ACTIONS, "expected_action")
        value = case["input_text"]
        require(type(value) is str and 1 <= len(value) <= 4000, "input_shape")
        require(any("가" <= char <= "힣" for char in value), "korean_input_required")
        for key in ("preserve", "forbid"):
            values = case[key]
            require(type(values) is list and 1 <= len(values) <= 12, "criteria_list")
            require(all(type(v) is str and 1 <= len(v) <= 1000 for v in values), "criteria_text")
        followup = case["followup"]
        require(type(followup) is str and len(followup) <= 1000, "followup_shape")
        require(action != "FOLLOW_UP" or bool(followup.strip()), "followup_missing")
    require(seen == expected_ids, "missing_case_id")


def validate_bundle(root: Path, manifest: object, corpus: object) -> dict:
    validate_corpus(corpus)
    exact_keys(manifest, {"schema", "policy", "documents", "corpus", "gates"}, "manifest_shape")
    require(manifest["schema"] == "careerground-external-gate-preparation-v1", "manifest_schema")
    exact_keys(manifest["policy"], set(POLICY), "policy_shape")
    for key, expected in POLICY.items():
        require(matches_exact(manifest["policy"][key], expected), "external_approval_not_granted")
    documents = manifest["documents"]
    exact_keys(documents, set(DOCUMENTS), "document_list")
    for gate, path in DOCUMENTS.items():
        document = documents[gate]
        exact_keys(document, {"path", "sha256"}, "document_shape")
        require(document["path"] == path, "document_path")
        require(
            document["sha256"] == hashlib.sha256((root / path).read_bytes()).hexdigest(),
            "document_hash",
        )
    dataset = manifest["corpus"]
    exact_keys(dataset, {"path", "sha256", "cases_per_task"}, "dataset_shape")
    require(dataset["path"] == CORPUS, "dataset_path")
    require(
        dataset["sha256"] == hashlib.sha256((root / CORPUS).read_bytes()).hexdigest(),
        "dataset_hash",
    )
    require(matches_exact(dataset["cases_per_task"], 9), "dataset_count")
    gates = manifest["gates"]
    exact_keys(gates, set(DOCUMENTS), "gate_list")
    for gate in DOCUMENTS:
        evidence = gates[gate]
        exact_keys(evidence, {"status", "required_cases", "external_evidence"}, "gate_shape")
        require(evidence["status"] == "WAITING_EXTERNAL_APPROVAL", "unsupported_gate_status")
        require(
            type(evidence["external_evidence"]) is list and not evidence["external_evidence"],
            "unsupported_external_evidence",
        )
        expected = (
            [f"I{n:02d}" for n in range(1, 13)]
            if gate == "G-I"
            else [f"O{n:02d}" for n in range(1, 11)]
            if gate == "G-P/G-C"
            else [f"{task}-{n:02d}" for task in TASKS for n in range(1, 10)]
        )
        require(evidence["required_cases"] == expected, "required_case_list")
    return {
        "preparation_status": "PASS",
        "external_execution_ready": False,
        "thresholds_status": "PROPOSED_NOT_APPROVED",
        "semantic_model_cases_executed": 0,
        "corpus_cases": 36,
        "corpus_sha256": dataset["sha256"],
        "policy": dict(POLICY),
        "gates": {gate: gates[gate]["status"] for gate in DOCUMENTS},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_bundle(ROOT, load_json(ROOT / MANIFEST), load_json(ROOT / CORPUS))
    except (PreparationInvalid, OSError, ValueError):
        # Never print input contents, user-selected paths or credentials in errors.
        print(json.dumps({"preparation_status": "FAIL", "external_execution_ready": False}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 3 if args.require_ready else 0


if __name__ == "__main__":
    sys.exit(main())

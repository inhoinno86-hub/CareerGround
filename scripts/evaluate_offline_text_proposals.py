"""Run fixed Korean synthetic cases against the read-only offline proposal guards.

No provider calls, user data, mutations, quality scores, or canonical promotions.
Only aggregate result counts and refusal categories are written to JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from careerground.domain.resume_draft import get_resume_trace
from careerground.domain.text_proposal_validation import (
    MockTextAnalyzer,
    TextProposalRejected,
    _wording_guard,
    validate_jd_text_proposal,
    validate_r2_wording_proposal,
)
from careerground.storage.graph_models import Claim

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import test_artifact_browser_confirmation as synthetic_fixture
from test_browser_mcp_confirmation import RESOURCE


def _case(session, unit, artifact_id, item):
    variant = item.get("variant")
    if item["kind"] == "guard":
        _wording_guard(item["source"], item["proposed"])
        return None
    options = {"account_id": "acct-a", "profile_id": "profile-a", "profile_version": 2}
    if variant == "foreign_owner":
        options["account_id"] = "acct-b"
    elif variant == "stale_version":
        options["profile_version"] = 1
    if item["kind"] == "jd":
        source = item["source"]
        payload = MockTextAnalyzer().propose_jd(source)
        if variant in {"good_ref", "foreign_claim", "foreign_evidence", "deleted_claim"}:
            row = payload["candidates"][0]
            row["claim_id"] = "foreign-claim" if variant == "foreign_claim" else unit.claim_id
            row["evidence_ids"] = (
                ["foreign-evidence"] if variant == "foreign_evidence" else list(unit.evidence_ids)
            )
        if variant == "bad_hash":
            payload["source_hash"] = "0" * 64
        elif variant == "extra_coverage":
            payload["coverage"] = "MATCH"
        elif variant == "bool_span":
            payload["candidates"][0]["start"] = True
        elif variant == "out_of_range":
            payload["candidates"][0]["end"] = len(source) + 20
        return validate_jd_text_proposal(session, source_text=source, payload=payload, **options)
    payload = {
        "source_hash": hashlib.sha256(unit.exact_text.encode()).hexdigest(),
        "proposed_text": item["proposed"],
        "fact_review": "R3_NEEDS_FACT_REVIEW" if variant == "r3" else "NO_NEW_FACTS",
        "claim_id": "foreign-claim" if variant == "foreign_claim" else unit.claim_id,
        "evidence_ids": list(unit.evidence_ids),
    }
    return validate_r2_wording_proposal(
        session, artifact_id=artifact_id, unit_id=unit.unit_id, payload=payload, **options
    )


def evaluate(cases):
    fixture = synthetic_fixture.ArtifactBrowserTests()
    fixture.setUp()
    try:
        with (
            TestClient(fixture.fixture.web) as browser,
            TestClient(fixture.fixture.mcp, base_url=RESOURCE.removesuffix("/mcp")) as client,
        ):
            artifact_id = fixture.fixture.artifact(browser, client)
        with fixture.sessions() as session:
            unit = get_resume_trace(session, account_id="acct-a", artifact_id=artifact_id).units[0]
        passed = 0
        actual_counts = Counter()
        expected_counts = Counter()
        failures = []
        for item in cases:
            expected_counts[item["expect"]] += 1
            with fixture.sessions() as session:
                if item.get("variant") == "deleted_claim":
                    # Dirty only within this transaction; rollback restores the fixture.
                    session.get(Claim, unit.claim_id).status = "ERASED"
                    session.flush()
                try:
                    _case(session, unit, artifact_id, item)
                except TextProposalRejected as error:
                    actual = error.code
                else:
                    actual = "ACCEPT"
                session.rollback()
            actual_counts[actual] += 1
            if actual == item["expect"]:
                passed += 1
            else:
                failures.append(
                    {"case": item["name"], "expected": item["expect"], "actual": actual}
                )
        return {
            "schema": "offline-text-proposal-evaluation-v1",
            "fixture_type": "synthetic_sqlite_owned_graph",
            "quality_claim": "NONE_DETERMINISTIC_BOUNDARY_ONLY",
            "cases": len(cases),
            "passed": passed,
            "failed": len(failures),
            "expected_categories": dict(sorted(expected_counts.items())),
            "actual_categories": dict(sorted(actual_counts.items())),
            "mismatches": failures,
        }
    finally:
        fixture.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-file", type=Path, required=True)
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/korean_text_proposal_cases.json"
    payload = json.loads(path.read_text())
    cases = payload["cases"]
    if (
        payload.get("schema") != "offline-text-proposal-cases-v1"
        or not isinstance(cases, list)
        or len(cases) < 30
        or len({item["name"] for item in cases}) != len(cases)
        or any(item["kind"] not in {"jd", "r2", "guard"} for item in cases)
    ):
        parser.error("invalid fixed synthetic case fixture")
    logging.disable(logging.CRITICAL)
    report = evaluate(cases)
    output = args.output_file.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({key: report[key] for key in ("cases", "passed", "failed")}, ensure_ascii=False)
    )
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
